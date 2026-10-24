"""运行时编排：采集 -> 推理 -> 稳定器 -> SOP 状态机 -> 持久化 -> 实时推送。

该层是唯一允许把检测结果送入规则引擎的入口，保证前端无法自行裁定合规结果。
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from collections import deque
from datetime import datetime
from typing import Any

from app.core.config import Settings
from app.core.errors import ConflictError, ValidationError
from app.core.logging import log_buffer
from app.core.timeutil import iso, now
from app.db.database import Database
from app.db.repositories import EventRepository, SessionRepository, SopRepository
from app.domain.enums import (
    EventStatus,
    EventType,
    SessionStatus,
    SessionTrigger,
    Severity,
    StepRecordStatus,
)
from app.domain.models import Detection, SopStep
from app.inference.base import BaseDetector, DetectorStatus
from app.inference.mock import MockDetector
from app.services.camera import CameraManager
from app.services.sop_engine import EngineOutcome, SopEngine
from app.services.stabilizer import GestureStabilizer
from app.services.stream_hub import StreamHub

logger = logging.getLogger(__name__)

_GESTURES = ("ONE", "TWO", "THREE", "FOUR", "FIVE")


class RuntimeService:
    def __init__(
        self,
        settings: Settings,
        *,
        db: Database,
        sop_repo: SopRepository,
        session_repo: SessionRepository,
        event_repo: EventRepository,
        detector: BaseDetector,
        detector_reason: str,
        camera: CameraManager,
        hub: StreamHub,
    ) -> None:
        self.settings = settings
        self._db = db
        self._sop_repo = sop_repo
        self._session_repo = session_repo
        self._event_repo = event_repo
        self._detector = detector
        self._detector_reason = detector_reason
        self._camera = camera
        self._hub = hub

        self._engine = SopEngine(
            sop_repo.list_steps(),
            station_id=settings.station_id,
            fail_on_sequence_error=settings.fail_on_sequence_error,
            fail_on_timeout=settings.fail_on_timeout,
            session_max_seconds=settings.session_max_seconds,
        )
        self._stabilizer = GestureStabilizer(
            min_confidence=settings.detection_min_confidence,
            stable_frames=settings.detection_stable_frames,
            reset_ms=settings.detection_reset_ms,
        )
        self._lock = asyncio.Lock()
        self._tasks: list[asyncio.Task] = []
        self._started_at = now()
        self._shutting_down = False

        self._last_detection: dict[str, Any] | None = None
        self._last_detection_at: datetime | None = None
        self._measured_fps = 0.0
        self._inference_count = 0
        self._fps_window_start = time.monotonic()
        self._inference_times: deque[float] = deque(maxlen=50)

        self._pending_steps: list[SopStep] | None = None
        self._session_trigger: str | None = None
        self._session_finished_at: datetime | None = None
        self._config_note = ""
        # 会话结束后必须等手势释放（无检测）才允许下一次自动开始，
        # 避免同一手势连续触发多个错误会话。
        self._await_clear = False

    # ================= 生命周期 =================
    async def start(self) -> None:
        await asyncio.to_thread(self._camera.start)
        if not self.settings.runtime_enabled:
            logger.warning("SOP_RUNTIME_ENABLED=false，采集与推理后台任务未启动")
            return
        self._tasks = [
            asyncio.create_task(self._load_model(), name="model-loader"),
            asyncio.create_task(self._inference_loop(), name="inference-loop"),
            asyncio.create_task(self._tick_loop(), name="sop-tick-loop"),
            asyncio.create_task(self._telemetry_loop(), name="telemetry-loop"),
        ]
        logger.info("运行时已启动（推理模式=%s）", self.settings.inference_mode)

    async def stop(self) -> None:
        self._shutting_down = True
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []
        try:
            async with self._lock:
                if self._engine.is_running:
                    outcome = self._engine.abort("后端服务关闭", now())
                    await self._finish_session(outcome, now())
        except Exception:  # pragma: no cover
            logger.exception("关闭运行时会话时出错")
        await asyncio.to_thread(self._camera.stop)
        self._detector.unload()
        logger.info("运行时已停止")

    async def _load_model(self) -> None:
        try:
            await asyncio.to_thread(self._detector.load)
        except Exception as exc:  # pragma: no cover
            logger.exception("模型加载任务异常：%s", exc)
        await self._hub.broadcast({"type": "system", "data": await self.system_status()})

    # ================= 主循环 =================
    async def _inference_loop(self) -> None:
        interval = 1.0 / max(self.settings.inference_fps, 0.5)
        while True:
            started = time.monotonic()
            try:
                if self._detector.status in (DetectorStatus.READY, DetectorStatus.MOCK):
                    frame = self._camera.latest_frame()
                    if self._detector.status == DetectorStatus.READY and frame is None:
                        await asyncio.sleep(0.1)
                        continue
                    detection = await asyncio.to_thread(self._detector.predict, frame)
                    at = now()
                    latency = (time.perf_counter() - started) * 1000
                    self._inference_times.append(latency)
                    async with self._lock:
                        await self._process_detection(detection, at)
                    self._count_inference()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("推理循环异常")
            elapsed = time.monotonic() - started
            await asyncio.sleep(max(interval - elapsed, 0.02))

    async def _tick_loop(self) -> None:
        while True:
            try:
                async with self._lock:
                    if self._engine.is_running:
                        outcome = self._engine.tick(now())
                        if outcome.events:
                            if outcome.session_finished:
                                await self._finish_session(outcome, now())
                            else:
                                await self._apply_outcome(outcome)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("SOP 超时检查异常")
            await asyncio.sleep(0.5)

    async def _telemetry_loop(self) -> None:
        while True:
            try:
                payload = await self.get_monitor_snapshot()
                await self._hub.broadcast({"type": "telemetry", "data": payload})
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("实时推送异常")
            await asyncio.sleep(max(self.settings.ws_telemetry_interval_ms, 100) / 1000)

    def _count_inference(self) -> None:
        self._inference_count += 1
        elapsed = time.monotonic() - self._fps_window_start
        if elapsed >= 1.0:
            self._measured_fps = round(self._inference_count / elapsed, 1)
            self._inference_count = 0
            self._fps_window_start = time.monotonic()

    # ================= 检测处理 =================
    async def _process_detection(self, detection: Detection, at: datetime) -> None:
        camera_simulated = self._camera.describe().get("simulated", False)
        simulated = bool(detection.simulated or self._detector.simulated or camera_simulated)
        self._last_detection = {
            "gesture": detection.gesture,
            "label": detection.label,
            "confidence": round(float(detection.confidence), 4),
            "simulated": simulated,
            "inference_ms": detection.inference_ms,
            "boxes": detection.boxes,
            "at": iso(at),
        }
        self._last_detection_at = at
        if detection.gesture:
            self._camera.set_hint(f"{detection.gesture} {detection.confidence:.2f}")
        else:
            self._camera.set_hint(None)

        # 上一会话结束后，先等待画面中不再出现手势，再接受新的流程动作
        if self._await_clear:
            if detection.gesture is None:
                self._await_clear = False
                self._stabilizer.reset()
            else:
                return

        confirmed = self._stabilizer.update(detection, at)
        if not confirmed:
            return
        await self._handle_gesture(confirmed, detection.confidence, at, simulated=simulated)

    async def _handle_gesture(
        self,
        gesture: str,
        confidence: float,
        at: datetime,
        *,
        simulated: bool,
    ) -> None:
        if self._engine.has_session and not self._engine.is_running:
            self._engine.clear()

        if not self._engine.is_running:
            if not self.settings.auto_start_session:
                return
            # 自动开始只接受「第一步」对应的手势；其他动作在无会话时忽略，
            # 避免流程结束后残握手势反复创建失败会话。
            first_step = self._engine.steps[0] if self._engine.steps else None
            if first_step is None or gesture.upper() != first_step.gesture:
                return
            await self._begin_session(SessionTrigger.AUTO, at)

        outcome = self._engine.handle_detection(gesture, confidence, at)
        if outcome.session_finished:
            await self._finish_session(outcome, at)
        elif outcome.events or outcome.step_records:
            await self._apply_outcome(outcome)
        logger.debug(
            "手势确认 gesture=%s confidence=%.3f simulated=%s", gesture, confidence, simulated
        )

    async def _begin_session(self, trigger: str, at: datetime) -> None:
        outcome = self._engine.start(trigger=trigger, at=at)
        snapshot = self._engine.snapshot()
        if snapshot is None:  # pragma: no cover
            return
        self._session_trigger = trigger
        self._session_finished_at = None
        if trigger == SessionTrigger.MANUAL:
            self._await_clear = False
        self._session_repo.create(
            session_id=snapshot.session_id,
            station_id=self.settings.station_id,
            station_name=self.settings.station_name,
            trigger=trigger,
            started_at=iso(at),
            total_steps=len(snapshot.steps),
        )
        await self._apply_outcome(outcome)
        await self._hub.broadcast({"type": "session", "data": self._session_payload()})
        logger.info("SOP 会话开始：%s（%s）", snapshot.session_id, trigger)

    async def _apply_outcome(self, outcome: EngineOutcome) -> None:
        snapshot = self._engine.snapshot()
        if snapshot is None:
            return
        for record in outcome.step_records:
            try:
                self._session_repo.add_step_record(snapshot.session_id, record)
            except Exception:
                logger.exception("写入步骤记录失败")
        for event in outcome.events:
            status = EventStatus.CLOSED if event.severity == Severity.INFO else EventStatus.OPEN
            event_id = 0
            try:
                event_id = self._event_repo.add(
                    session_id=snapshot.session_id,
                    station_id=self.settings.station_id,
                    event_type=event.type,
                    severity=event.severity,
                    message=event.message,
                    step_order=event.step_order,
                    step_name=event.step_name,
                    created_at=iso(event.at),
                    status=status,
                )
            except Exception:
                logger.exception("写入异常事件失败")
            await self._hub.broadcast(
                {
                    "type": "event",
                    "data": {
                        "id": event_id,
                        "session_id": snapshot.session_id,
                        "station_id": self.settings.station_id,
                        "event_type": str(event.type),
                        "severity": str(event.severity),
                        "step_order": event.step_order,
                        "step_name": event.step_name,
                        "message": event.message,
                        "status": str(status),
                        "created_at": iso(event.at),
                    },
                }
            )

    async def _finish_session(self, outcome: EngineOutcome, at: datetime) -> None:
        snapshot = self._engine.snapshot()
        if snapshot is None:
            return
        await self._apply_outcome(outcome)
        completed_steps = sum(
            1 for record in snapshot.completed if record.status == StepRecordStatus.COMPLETED
        )
        anomaly_count = self._engine.anomaly_count
        compliance = bool(self._engine.compliance)
        self._session_repo.finish(
            session_id=snapshot.session_id,
            status=snapshot.status,
            finished_at=iso(at),
            completed_steps=completed_steps,
            anomaly_count=anomaly_count,
            compliance=compliance,
            end_reason=snapshot.end_reason,
        )
        self._session_finished_at = at
        self._stabilizer.reset()
        self._await_clear = True
        await self._hub.broadcast({"type": "session", "data": self._session_payload()})
        logger.info(
            "SOP 会话结束：%s status=%s 完成=%d/%d 异常=%d 合规=%s",
            snapshot.session_id,
            snapshot.status,
            completed_steps,
            len(snapshot.steps),
            anomaly_count,
            compliance,
        )

        if self._pending_steps is not None:
            steps = self._pending_steps
            self._pending_steps = None
            try:
                self._engine.clear()
                self._engine.set_steps(steps)
                self._config_note = "新 SOP 配置已在上一会话结束后生效"
                logger.info("待生效的 SOP 配置已应用")
                await self._hub.broadcast(
                    {"type": "system", "data": self._system_status_locked()}
                )
            except Exception:
                logger.exception("应用待生效 SOP 配置失败")

    # ================= 对外操作 =================
    async def start_session_manual(self) -> dict[str, Any]:
        async with self._lock:
            if self._engine.is_running:
                raise ConflictError("已有运行中的会话")
            if not self._engine.steps:
                raise ConflictError("没有启用的 SOP 步骤，请先完成配置")
            if self._engine.has_session:
                self._engine.clear()
            await self._begin_session(SessionTrigger.MANUAL, now())
        return await self.get_monitor_snapshot()

    async def stop_session_manual(self, reason: str = "操作员手动终止") -> dict[str, Any]:
        async with self._lock:
            if not self._engine.is_running:
                raise ConflictError("当前没有运行中的会话")
            outcome = self._engine.abort(reason, now())
            await self._finish_session(outcome, now())
        return await self.get_monitor_snapshot()

    async def apply_steps(self, steps: list[SopStep]) -> dict[str, Any]:
        async with self._lock:
            if self._engine.is_running:
                self._pending_steps = steps
                self._config_note = "当前会话运行中，新配置将在下一会话开始前生效"
                applied = False
            else:
                if self._engine.has_session:
                    self._engine.clear()
                self._engine.set_steps(steps)
                self._pending_steps = None
                self._config_note = "SOP 配置已立即生效"
                applied = True
            status = self._system_status_locked()
        await self._hub.broadcast({"type": "system", "data": status})
        return {"applied": applied, "note": self._config_note}

    async def reload_model(self) -> dict[str, Any]:
        await asyncio.to_thread(self._detector.load)
        status = await self.system_status()
        await self._hub.broadcast({"type": "system", "data": status})
        return status["model"]

    async def reconnect_camera(self) -> dict[str, Any]:
        info = await asyncio.to_thread(self._camera.restart)
        await self._hub.broadcast({"type": "system", "data": await self.system_status()})
        return info

    async def simulate(self, action: str, gesture: str | None = None) -> dict[str, Any]:
        if not self._detector.simulated:
            raise ConflictError("当前为真实模型模式，禁止注入模拟动作")
        action = (action or "").strip().lower()

        if action == "gesture":
            if not gesture:
                raise ValidationError("缺少 gesture 参数")
            gesture = gesture.upper()
            if gesture not in _GESTURES:
                raise ValidationError(f"不支持的手势：{gesture}")
            async with self._lock:
                await self._feed_gesture_locked(gesture)
            return {"action": action, "gesture": gesture, "message": f"已注入模拟动作 {gesture}"}

        if action == "reset":
            if isinstance(self._detector, MockDetector):
                self._detector.reset_sequence()
            return {"action": action, "message": "模拟检测序列已重置"}

        async with self._lock:
            if action == "timeout":
                if not self._engine.is_running:
                    if self._engine.has_session:
                        self._engine.clear()
                    await self._begin_session(SessionTrigger.MANUAL, now())
                current = self._engine.current_step
                if current is None:
                    raise ConflictError("当前没有待执行的步骤")
                pause = min(current.timeout_seconds + 2, 180)
                if isinstance(self._detector, MockDetector):
                    self._detector.pause(pause)
                return {
                    "action": action,
                    "message": f"已模拟 {pause}s 无检测输入，等待步骤 {current.order} 超时",
                }

            if action not in ("skip", "wrong_order", "repeat"):
                raise ValidationError(f"未知的模拟动作：{action}")

            if not self._engine.is_running:
                if self._engine.has_session:
                    self._engine.clear()
                await self._begin_session(SessionTrigger.MANUAL, now())

            snapshot = self._engine.snapshot()
            if snapshot is None:  # pragma: no cover
                raise ConflictError("会话未就绪")

            if action in ("skip", "wrong_order"):
                index = snapshot.current_index + 1
                if index >= len(snapshot.steps):
                    raise ConflictError("已到最后一步，无法演示跳过步骤")
                future = snapshot.steps[index]
                await self._feed_gesture_locked(future.gesture)
                return {
                    "action": action,
                    "gesture": future.gesture,
                    "message": (
                        f"已注入步骤 {future.order}「{future.name}」，"
                        f"当前步骤 {snapshot.current_index + 1} 将被判定为跳过/错序"
                    ),
                }

            completed = [
                record for record in snapshot.completed if record.status == StepRecordStatus.COMPLETED
            ]
            gesture_to_repeat = (
                completed[-1].gesture
                if completed
                else snapshot.steps[snapshot.current_index].gesture
            )
            await self._feed_gesture_locked(gesture_to_repeat)
            if not completed and self._engine.is_running:
                await self._feed_gesture_locked(gesture_to_repeat)
            return {
                "action": action,
                "gesture": gesture_to_repeat,
                "message": f"已重复注入动作 {gesture_to_repeat}，应触发重复步骤告警",
            }

    async def _feed_gesture_locked(self, gesture: str) -> None:
        at = now()
        self._last_detection = {
            "gesture": gesture,
            "label": f"INJECTED:{gesture}",
            "confidence": 0.99,
            "simulated": True,
            "inference_ms": 0.0,
            "boxes": [],
            "at": iso(at),
        }
        self._last_detection_at = at
        await self._handle_gesture(gesture, 0.99, at, simulated=True)

    # ================= 快照 =================
    async def get_monitor_snapshot(self) -> dict[str, Any]:
        async with self._lock:
            return self._build_monitor_snapshot()

    def _build_monitor_snapshot(self) -> dict[str, Any]:
        snapshot = self._engine.snapshot()
        configured_steps = snapshot.steps if snapshot else self._engine.steps
        completed_map = {record.order: record for record in snapshot.completed} if snapshot else {}
        steps_payload = []
        for index, step in enumerate(configured_steps):
            if snapshot is None:
                status = "PENDING"
            elif snapshot.status == SessionStatus.RUNNING:
                if index < snapshot.current_index:
                    record = completed_map.get(step.order)
                    status = str(record.status) if record else "PENDING"
                elif index == snapshot.current_index:
                    status = "CURRENT"
                else:
                    status = "PENDING"
            elif index < snapshot.current_index and step.order in completed_map:
                status = str(completed_map[step.order].status)
            else:
                status = "PENDING"
            record = completed_map.get(step.order)
            steps_payload.append(
                {
                    "order": step.order,
                    "name": step.name,
                    "gesture": step.gesture,
                    "description": step.description,
                    "timeout_seconds": step.timeout_seconds,
                    "status": status,
                    "duration_ms": record.duration_ms if record else None,
                    "confidence": record.confidence if record else None,
                }
            )

        current_step = None
        if snapshot and snapshot.status == SessionStatus.RUNNING:
            step = self._engine.current_step
            if step is not None:
                elapsed = float(self._engine.step_elapsed_seconds or 0.0)
                current_step = {
                    "order": step.order,
                    "name": step.name,
                    "gesture": step.gesture,
                    "description": step.description,
                    "timeout_seconds": step.timeout_seconds,
                    "elapsed_seconds": round(elapsed, 1),
                    "remaining_seconds": round(max(step.timeout_seconds - elapsed, 0.0), 1),
                }

        return {
            "station": {
                "id": self.settings.station_id,
                "name": self.settings.station_name,
            },
            "session": self._session_payload(),
            "steps": steps_payload,
            "current_step": current_step,
            "detection": self._last_detection,
            "runtime": {
                "state": self.runtime_state,
                "simulated": self.is_simulated,
                "runtime_enabled": self.settings.runtime_enabled,
                "inference_fps_target": self.settings.inference_fps,
                "measured_fps": self._measured_fps,
                "inference_latency_ms": round(
                    sum(self._inference_times) / len(self._inference_times), 2
                )
                if self._inference_times
                else None,
                "last_detection_at": iso(self._last_detection_at)
                if self._last_detection_at
                else None,
            },
            "updated_at": iso(),
        }

    def _session_payload(self) -> dict[str, Any] | None:
        snapshot = self._engine.snapshot()
        if snapshot is None:
            return None
        completed_steps = sum(
            1 for record in snapshot.completed if record.status == StepRecordStatus.COMPLETED
        )
        finished = snapshot.status != SessionStatus.RUNNING
        return {
            "id": snapshot.session_id,
            "station_id": snapshot.station_id,
            "status": str(snapshot.status),
            "trigger": self._session_trigger,
            "started_at": iso(snapshot.started_at),
            "finished_at": iso(self._session_finished_at)
            if finished and self._session_finished_at
            else None,
            "total_steps": len(snapshot.steps),
            "completed_steps": completed_steps,
            "anomaly_count": self._engine.anomaly_count,
            "compliance": self._engine.compliance,
            "end_reason": snapshot.end_reason,
        }

    @property
    def runtime_state(self) -> str:
        if not self.settings.runtime_enabled:
            return "DISABLED"
        if self._detector.status == DetectorStatus.ERROR:
            return "DEGRADED"
        if self._engine.is_running:
            return "RUNNING"
        return "IDLE"

    @property
    def is_simulated(self) -> bool:
        return bool(self._detector.simulated or self._camera.describe().get("simulated"))

    async def system_status(self) -> dict[str, Any]:
        async with self._lock:
            return self._system_status_locked()

    def _system_status_locked(self) -> dict[str, Any]:
        snapshot = self._engine.snapshot()
        steps = self._engine.steps
        return {
                "backend": {
                    "status": "UP",
                    "version": self.settings.app_version,
                    "environment": self.settings.env,
                    "started_at": iso(self._started_at),
                    "uptime_seconds": int((now() - self._started_at).total_seconds()),
                    "pid": os.getpid(),
                    "python": sys.version.split()[0],
                },
                "runtime": {
                    "state": self.runtime_state,
                    "simulated": self.is_simulated,
                    "enabled": self.settings.runtime_enabled,
                    "measured_fps": self._measured_fps,
                    "inference_fps_target": self.settings.inference_fps,
                },
                "model": {
                    **self._detector.describe(),
                    "selection_reason": self._detector_reason,
                },
                "camera": self._camera.describe(),
                "database": {
                    "status": "UP" if self._db.query_one("SELECT 1") else "ERROR",
                    "path": str(self._db.path),
                    "size_bytes": self._db.size_bytes(),
                },
                "realtime": {
                    "ws_clients": self._hub.client_count,
                    "telemetry_interval_ms": self.settings.ws_telemetry_interval_ms,
                },
                "sop": {
                    "station_id": self.settings.station_id,
                    "station_name": self.settings.station_name,
                    "steps_total": len(steps),
                    "enabled_steps": sum(1 for step in steps if step.enabled),
                    "active_session_id": snapshot.session_id
                    if snapshot and snapshot.status == SessionStatus.RUNNING
                    else None,
                    "session_status": str(snapshot.status) if snapshot else None,
                    "pending_config": self._pending_steps is not None,
                    "config_note": self._config_note,
                },
                "recent_errors": log_buffer.snapshot(12),
            }

    def safe_config(self) -> dict[str, Any]:
        return {
            "station_id": self.settings.station_id,
            "station_name": self.settings.station_name,
            "inference_mode": self.settings.inference_mode,
            "model_path": str(self.settings.model_file),
            "model_device": self.settings.model_device,
            "model_conf": self.settings.model_conf,
            "camera_mode": self.settings.camera_mode,
            "camera_index": self.settings.camera_index,
            "camera_resolution": f"{self.settings.camera_width}x{self.settings.camera_height}",
            "inference_fps": self.settings.inference_fps,
            "detection_stable_frames": self.settings.detection_stable_frames,
            "detection_reset_ms": self.settings.detection_reset_ms,
            "fail_on_sequence_error": self.settings.fail_on_sequence_error,
            "fail_on_timeout": self.settings.fail_on_timeout,
            "session_max_seconds": self.settings.session_max_seconds,
            "auto_start_session": self.settings.auto_start_session,
            "database_path": str(self.settings.database_file),
            "log_dir": str(self.settings.logs_dir),
            "telemetry_interval_ms": self.settings.ws_telemetry_interval_ms,
        }


__all__ = ["RuntimeService", "EventType", "SessionStatus"]
