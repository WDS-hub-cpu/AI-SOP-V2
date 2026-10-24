"""SOP 规则引擎（纯内存状态机，不依赖数据库/网络/模型）。

规则：
- 步骤必须按配置顺序执行；
- 重复执行已完成步骤 -> REPEATED_STEP（告警，不推进流程）；
- 检测到后续步骤而当前步骤未完成 -> SKIPPED_STEP + ORDER_ERROR；
- 当前步骤超时 -> STEP_TIMEOUT；
- 会话总时长超限 -> SESSION_TIMEOUT；
- 全部步骤完成 -> FLOW_COMPLETED；存在任何告警则合规=false。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

from app.core.timeutil import now
from app.domain.enums import (
    EventType,
    SessionStatus,
    Severity,
    StepRecordStatus,
)
from app.domain.models import EngineEvent, SessionSnapshot, SopStep, StepExecution


@dataclass(slots=True)
class EngineOutcome:
    events: list[EngineEvent] = field(default_factory=list)
    step_records: list[StepExecution] = field(default_factory=list)
    session_started: bool = False
    session_finished: bool = False


@dataclass(slots=True)
class _SessionState:
    session_id: str
    station_id: str
    steps: list[SopStep]
    started_at: datetime
    step_started_at: datetime
    status: SessionStatus = SessionStatus.RUNNING
    current_index: int = 0
    completed: list[StepExecution] = field(default_factory=list)
    anomalies: list[EngineEvent] = field(default_factory=list)
    end_reason: str | None = None


class SopEngine:
    def __init__(
        self,
        steps: list[SopStep],
        *,
        station_id: str,
        fail_on_sequence_error: bool = True,
        fail_on_timeout: bool = True,
        session_max_seconds: int = 300,
    ) -> None:
        self.station_id = station_id
        self.fail_on_sequence_error = fail_on_sequence_error
        self.fail_on_timeout = fail_on_timeout
        self.session_max_seconds = session_max_seconds
        self._steps = self._normalize(steps)
        self._state: _SessionState | None = None

    # ---------- 配置 ----------
    @staticmethod
    def _normalize(steps: list[SopStep]) -> list[SopStep]:
        return sorted((s for s in steps if s.enabled), key=lambda s: s.order)

    def set_steps(self, steps: list[SopStep]) -> None:
        """仅在空闲时替换步骤配置，避免运行中的会话被篡改。"""
        if self.is_running:
            raise ValueError("会话运行中，不能替换 SOP 配置")
        self._steps = self._normalize(steps)

    @property
    def steps(self) -> list[SopStep]:
        return list(self._steps)

    @property
    def is_running(self) -> bool:
        return self._state is not None and self._state.status == SessionStatus.RUNNING

    @property
    def has_session(self) -> bool:
        return self._state is not None

    # ---------- 会话控制 ----------
    def start(self, *, trigger: str = "auto", at: datetime | None = None) -> EngineOutcome:
        if self.is_running:
            raise ValueError("已有运行中的会话")
        if not self._steps:
            raise ValueError("没有启用的 SOP 步骤，无法开始会话")
        timestamp = at or now()
        self._state = _SessionState(
            session_id=uuid4().hex,
            station_id=self.station_id,
            steps=list(self._steps),
            started_at=timestamp,
            step_started_at=timestamp,
        )
        event = EngineEvent(
            type=EventType.FLOW_STARTED,
            severity=Severity.INFO,
            message=f"流程开始，共 {len(self._steps)} 个步骤（触发方式：{trigger}）",
            at=timestamp,
        )
        return EngineOutcome(events=[event], session_started=True)

    def abort(self, reason: str, at: datetime | None = None) -> EngineOutcome:
        if not self.is_running:
            return EngineOutcome()
        timestamp = at or now()
        state = self._state
        assert state is not None
        event = EngineEvent(
            type=EventType.SESSION_ABORTED,
            severity=Severity.WARNING,
            message=f"会话被终止：{reason}",
            at=timestamp,
        )
        state.anomalies.append(event)
        state.status = SessionStatus.ABORTED
        state.end_reason = reason
        return EngineOutcome(events=[event], session_finished=True)

    def clear(self) -> None:
        if self.is_running:
            raise ValueError("运行中的会话不能清除")
        self._state = None

    # ---------- 规则判断 ----------
    def handle_detection(
        self,
        gesture: str,
        confidence: float,
        at: datetime | None = None,
    ) -> EngineOutcome:
        timestamp = at or now()
        outcome = EngineOutcome()
        state = self._state
        if state is None or state.status != SessionStatus.RUNNING:
            return outcome

        # 检测到来时先结算一次超时，避免超时步骤仍然被判定为正确
        timeout_outcome = self._check_timeouts(timestamp)
        if timeout_outcome.events:
            outcome.events.extend(timeout_outcome.events)
            outcome.step_records.extend(timeout_outcome.step_records)
            outcome.session_finished = timeout_outcome.session_finished
            if state.status != SessionStatus.RUNNING:
                return outcome

        gesture_key = (gesture or "").strip().upper()
        matches = [i for i, step in enumerate(state.steps) if step.gesture == gesture_key]
        if not matches:
            return outcome
        index = matches[0]
        current = state.steps[state.current_index]

        if index == state.current_index:
            elapsed_ms = int((timestamp - state.step_started_at).total_seconds() * 1000)
            record = StepExecution(
                order=current.order,
                name=current.name,
                gesture=current.gesture,
                status=StepRecordStatus.COMPLETED,
                started_at=state.step_started_at,
                finished_at=timestamp,
                duration_ms=max(elapsed_ms, 0),
                confidence=round(float(confidence), 4),
            )
            state.completed.append(record)
            outcome.step_records.append(record)
            outcome.events.append(
                EngineEvent(
                    type=EventType.STEP_COMPLETED,
                    severity=Severity.INFO,
                    message=f"步骤 {current.order}「{current.name}」完成，用时 {elapsed_ms / 1000:.1f}s",
                    at=timestamp,
                    step_order=current.order,
                    step_name=current.name,
                )
            )
            state.current_index += 1
            state.step_started_at = timestamp

            if state.current_index >= len(state.steps):
                state.status = SessionStatus.COMPLETED
                state.end_reason = "全部步骤完成"
                outcome.events.append(
                    EngineEvent(
                        type=EventType.FLOW_COMPLETED,
                        severity=Severity.INFO,
                        message="SOP 流程完成"
                        + ("（无异常）" if not state.anomalies else "（存在异常，判定为不合规）"),
                        at=timestamp,
                    )
                )
                outcome.session_finished = True
            return outcome

        if index < state.current_index:
            event = EngineEvent(
                type=EventType.REPEATED_STEP,
                severity=Severity.WARNING,
                message=(
                    f"检测到已完成步骤 {state.steps[index].order}"
                    f"「{state.steps[index].name}」的重复动作，当前应执行步骤 {current.order}"
                ),
                at=timestamp,
                step_order=state.steps[index].order,
                step_name=state.steps[index].name,
            )
            state.anomalies.append(event)
            outcome.events.append(event)
            return outcome

        # 检测到后续步骤：当前步骤被跳过 / 顺序错误
        detected = state.steps[index]
        severity = Severity.CRITICAL if current.required else Severity.WARNING
        skipped = EngineEvent(
            type=EventType.SKIPPED_STEP,
            severity=severity,
            message=f"步骤 {current.order}「{current.name}」未执行",
            at=timestamp,
            step_order=current.order,
            step_name=current.name,
        )
        order_error = EngineEvent(
            type=EventType.ORDER_ERROR,
            severity=severity,
            message=(
                f"顺序错误：期望步骤 {current.order}「{current.name}」，"
                f"实际检测到步骤 {detected.order}「{detected.name}」"
            ),
            at=timestamp,
            step_order=detected.order,
            step_name=detected.name,
        )
        state.anomalies.extend([skipped, order_error])
        outcome.events.extend([skipped, order_error])

        if current.required and self.fail_on_sequence_error:
            record = StepExecution(
                order=current.order,
                name=current.name,
                gesture=current.gesture,
                status=StepRecordStatus.SKIPPED,
                started_at=state.step_started_at,
                finished_at=timestamp,
                duration_ms=int((timestamp - state.step_started_at).total_seconds() * 1000),
            )
            outcome.step_records.append(record)
            state.status = SessionStatus.FAILED
            state.end_reason = f"步骤 {current.order} 被跳过（顺序错误）"
            outcome.events.append(
                EngineEvent(
                    type=EventType.FLOW_FAILED,
                    severity=Severity.CRITICAL,
                    message=f"流程判定失败：{state.end_reason}",
                    at=timestamp,
                )
            )
            outcome.session_finished = True
        return outcome

    def tick(self, at: datetime | None = None) -> EngineOutcome:
        return self._check_timeouts(at or now())

    def _check_timeouts(self, timestamp: datetime) -> EngineOutcome:
        outcome = EngineOutcome()
        state = self._state
        if state is None or state.status != SessionStatus.RUNNING:
            return outcome

        if (timestamp - state.started_at).total_seconds() >= self.session_max_seconds:
            event = EngineEvent(
                type=EventType.SESSION_TIMEOUT,
                severity=Severity.CRITICAL,
                message=f"会话超过最大时长 {self.session_max_seconds}s，流程终止",
                at=timestamp,
            )
            state.anomalies.append(event)
            state.status = SessionStatus.FAILED
            state.end_reason = "会话超时"
            outcome.events.extend(
                [
                    event,
                    EngineEvent(
                        type=EventType.FLOW_FAILED,
                        severity=Severity.CRITICAL,
                        message="流程判定失败：会话超时",
                        at=timestamp,
                    ),
                ]
            )
            outcome.session_finished = True
            return outcome

        current = state.steps[state.current_index]
        elapsed = (timestamp - state.step_started_at).total_seconds()
        if elapsed < current.timeout_seconds:
            return outcome

        record = StepExecution(
            order=current.order,
            name=current.name,
            gesture=current.gesture,
            status=StepRecordStatus.TIMEOUT,
            started_at=state.step_started_at,
            finished_at=timestamp,
            duration_ms=int(elapsed * 1000),
        )
        state.completed.append(record)
        outcome.step_records.append(record)
        event = EngineEvent(
            type=EventType.STEP_TIMEOUT,
            severity=Severity.CRITICAL,
            message=(
                f"步骤 {current.order}「{current.name}」超时："
                f"已等待 {elapsed:.1f}s，上限 {current.timeout_seconds}s"
            ),
            at=timestamp,
            step_order=current.order,
            step_name=current.name,
        )
        state.anomalies.append(event)
        outcome.events.append(event)

        if self.fail_on_timeout:
            state.status = SessionStatus.FAILED
            state.end_reason = f"步骤 {current.order} 超时"
            outcome.events.append(
                EngineEvent(
                    type=EventType.FLOW_FAILED,
                    severity=Severity.CRITICAL,
                    message=f"流程判定失败：{state.end_reason}",
                    at=timestamp,
                )
            )
            outcome.session_finished = True
            return outcome

        state.current_index += 1
        state.step_started_at = timestamp
        if state.current_index >= len(state.steps):
            state.status = SessionStatus.COMPLETED
            state.end_reason = "全部步骤完成（含超时步骤）"
            outcome.events.append(
                EngineEvent(
                    type=EventType.FLOW_COMPLETED,
                    severity=Severity.INFO,
                    message="SOP 流程结束，但存在超时异常，判定为不合规",
                    at=timestamp,
                )
            )
            outcome.session_finished = True
        return outcome

    # ---------- 快照 ----------
    @property
    def anomaly_count(self) -> int:
        if not self._state:
            return 0
        return sum(
            1 for e in self._state.anomalies if e.severity in (Severity.WARNING, Severity.CRITICAL)
        )

    @property
    def compliance(self) -> bool | None:
        state = self._state
        if state is None:
            return None
        if state.status == SessionStatus.RUNNING:
            return None
        return state.status == SessionStatus.COMPLETED and self.anomaly_count == 0

    @property
    def current_step(self) -> SopStep | None:
        state = self._state
        if state is None or state.status != SessionStatus.RUNNING:
            return None
        if state.current_index >= len(state.steps):
            return None
        return state.steps[state.current_index]

    @property
    def step_elapsed_seconds(self) -> float | None:
        state = self._state
        if state is None or state.status != SessionStatus.RUNNING:
            return None
        return max((now() - state.step_started_at).total_seconds(), 0.0)

    def snapshot(self) -> SessionSnapshot | None:
        state = self._state
        if state is None:
            return None
        return SessionSnapshot(
            session_id=state.session_id,
            station_id=state.station_id,
            status=state.status,
            started_at=state.started_at,
            current_index=state.current_index,
            steps=list(state.steps),
            completed=list(state.completed),
            anomalies=list(state.anomalies),
            step_started_at=state.step_started_at,
            end_reason=state.end_reason,
        )
