"""摄像头采集：独立线程采集，与推理、业务逻辑解耦。

支持三种来源：
- device：真实摄像头（OpenCV VideoCapture）
- synthetic：带明显水印的模拟画面（不是真实摄像头画面）
- auto：优先真实摄像头，失败后切换模拟画面并记录原因
"""

from __future__ import annotations

import logging
import sys
import threading
import time
from datetime import datetime
from typing import Any

import numpy as np

from app.core.config import Settings
from app.core.timeutil import iso, now

try:  # OpenCV 可选：缺少时摄像头状态明确为 ERROR
    import cv2

    HAS_CV2 = True
except Exception:  # pragma: no cover
    cv2 = None  # type: ignore[assignment]
    HAS_CV2 = False

logger = logging.getLogger(__name__)


class CameraStatus:
    CONNECTED = "CONNECTED"
    SIMULATED = "SIMULATED"
    DISCONNECTED = "DISCONNECTED"
    OFF = "OFF"
    ERROR = "ERROR"


class CameraManager:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._capture: Any = None

        self._source = "none"
        self._status = CameraStatus.OFF
        self._message = "摄像头未启动"
        self._synthetic = False
        self._frame: np.ndarray | None = None
        self._jpeg: bytes | None = None
        self._last_frame_at: datetime | None = None
        self._hint: str | None = None

        self._frame_count = 0
        self._fps_window_start = time.monotonic()
        self._measured_fps = 0.0
        self._background: np.ndarray | None = None

    # ---------- 生命周期 ----------
    def start(self) -> None:
        self._stop.clear()
        self._open_source()
        self._thread = threading.Thread(target=self._run, name="camera-capture", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        self._thread = None
        if self._capture is not None:
            try:
                self._capture.release()
            except Exception:  # pragma: no cover
                pass
        self._capture = None

    def restart(self) -> dict[str, Any]:
        self.stop()
        self._synthetic = False
        self._source = "none"
        self._status = CameraStatus.OFF
        self._message = "正在重新连接摄像头…"
        self._frame = None
        self._jpeg = None
        self._last_frame_at = None
        self.start()
        logger.info("摄像头已重启：%s", self._message)
        return self.describe()

    # ---------- 数据访问 ----------
    def latest_frame(self) -> np.ndarray | None:
        with self._lock:
            return None if self._frame is None else self._frame.copy()

    def latest_jpeg(self) -> bytes | None:
        with self._lock:
            return self._jpeg

    def set_hint(self, hint: str | None) -> None:
        with self._lock:
            self._hint = hint

    # ---------- 来源选择 ----------
    def _open_source(self) -> None:
        mode = self._settings.camera_mode
        if mode == "off":
            self._status = CameraStatus.OFF
            self._source = "off"
            self._message = "配置 SOP_CAMERA_MODE=off，摄像头已关闭"
            return

        if not HAS_CV2:
            self._status = CameraStatus.ERROR
            self._source = "none"
            self._message = "OpenCV 未安装，无法采集画面"
            logger.error(self._message)
            return

        if mode in ("auto", "device"):
            if self._try_device():
                self._status = CameraStatus.CONNECTED
                self._source = "device"
                self._synthetic = False
                self._message = f"摄像头已连接（索引 {self._settings.camera_index}）"
                return
            if mode == "device":
                self._status = CameraStatus.ERROR
                self._source = "none"
                self._message = f"无法打开摄像头索引 {self._settings.camera_index}"
                logger.error(self._message)
                return
            self._synthetic = True
            self._status = CameraStatus.SIMULATED
            self._source = "synthetic"
            self._message = (
                f"未检测到可用摄像头（索引 {self._settings.camera_index}），已切换为模拟画面"
            )
            logger.warning(self._message)
            return

        self._synthetic = True
        self._status = CameraStatus.SIMULATED
        self._source = "synthetic"
        self._message = "配置为模拟画面（非真实摄像头）"

    def _try_device(self) -> bool:
        if cv2 is None:
            return False
        backend = cv2.CAP_DSHOW if sys.platform == "win32" else 0
        capture = cv2.VideoCapture(self._settings.camera_index, backend)
        if not capture.isOpened():
            capture.release()
            return False
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, self._settings.camera_width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self._settings.camera_height)
        capture.set(cv2.CAP_PROP_FPS, self._settings.camera_fps)
        for _ in range(3):
            ok, frame = capture.read()
            if ok and frame is not None:
                self._capture = capture
                self._store_frame(frame)
                return True
        capture.release()
        return False

    def _fallback_to_synthetic(self, reason: str) -> None:
        if self._capture is not None:
            try:
                self._capture.release()
            except Exception:  # pragma: no cover
                pass
        self._capture = None
        self._synthetic = True
        self._source = "synthetic"
        self._status = CameraStatus.SIMULATED
        self._message = reason
        logger.warning(reason)

    # ---------- 采集线程 ----------
    def _run(self) -> None:
        interval = 1.0 / max(self._settings.camera_fps, 1.0)
        failures = 0
        while not self._stop.is_set():
            started = time.monotonic()
            frame: np.ndarray | None = None
            status_now = self._status
            message_now = self._message

            if self._capture is not None:
                ok, captured = self._capture.read()
                if ok and captured is not None:
                    failures = 0
                    frame = captured
                    status_now = CameraStatus.CONNECTED
                    message_now = f"摄像头已连接（索引 {self._settings.camera_index}）"
                else:
                    failures += 1
                    if failures >= 20 and self._settings.camera_mode == "auto":
                        self._fallback_to_synthetic("摄像头读取持续失败，已切换为模拟画面")
                        status_now = CameraStatus.SIMULATED
                        message_now = self._message
                    else:
                        status_now = CameraStatus.DISCONNECTED
                        message_now = "摄像头信号中断，正在重试…"
            elif self._synthetic:
                frame = self._render_synthetic()
                status_now = CameraStatus.SIMULATED
                message_now = self._message

            if frame is not None:
                self._store_frame(frame)
            with self._lock:
                self._status = status_now
                self._message = message_now

            elapsed = time.monotonic() - started
            self._stop.wait(max(interval - elapsed, 0.01))

    def _store_frame(self, frame: np.ndarray) -> None:
        encoded: bytes | None = None
        if cv2 is not None:
            ok, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
            if ok:
                encoded = buffer.tobytes()
        with self._lock:
            self._frame = frame
            if encoded is not None:
                self._jpeg = encoded
            self._last_frame_at = now()
            self._frame_count += 1
            elapsed = time.monotonic() - self._fps_window_start
            if elapsed >= 1.0:
                self._measured_fps = round(self._frame_count / elapsed, 1)
                self._frame_count = 0
                self._fps_window_start = time.monotonic()

    # ---------- 模拟画面 ----------
    def _render_synthetic(self) -> np.ndarray:
        assert cv2 is not None
        width, height = self._settings.camera_width, self._settings.camera_height
        if self._background is None or self._background.shape[1] != width:
            self._background = self._build_background(width, height)
        frame = self._background.copy()

        # 扫描线
        scan_y = int((time.monotonic() * 90) % height)
        cv2.line(frame, (0, scan_y), (width, scan_y), (90, 70, 30), 2)

        with self._lock:
            hint = self._hint
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(
            frame,
            "SIMULATED CAMERA FEED",
            (48, 90),
            cv2.FONT_HERSHEY_DUPLEX,
            1.15,
            (0, 170, 255),
            2,
            cv2.LINE_AA,
        )
        cv2.putText(
            frame,
            "NO REAL CAMERA SIGNAL - DEMO ONLY",
            (48, 132),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.62,
            (120, 160, 220),
            1,
            cv2.LINE_AA,
        )
        cv2.putText(
            frame,
            f"{self._settings.station_id}  |  {timestamp}",
            (48, height - 108),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.72,
            (200, 220, 240),
            1,
            cv2.LINE_AA,
        )
        cv2.putText(
            frame,
            "SOP VISION MONITOR / v2",
            (48, height - 64),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (110, 140, 175),
            1,
            cv2.LINE_AA,
        )
        if hint:
            cv2.putText(
                frame,
                f"SIM DETECTION: {hint}",
                (48, height - 170),
                cv2.FONT_HERSHEY_DUPLEX,
                0.8,
                (80, 220, 160),
                2,
                cv2.LINE_AA,
            )

        # 右上角水印框
        cv2.rectangle(frame, (width - 250, 44), (width - 48, 96), (0, 120, 200), -1)
        cv2.putText(
            frame,
            "SIMULATION",
            (width - 226, 78),
            cv2.FONT_HERSHEY_DUPLEX,
            0.62,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
        return frame

    @staticmethod
    def _build_background(width: int, height: int) -> np.ndarray:
        assert cv2 is not None
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:] = (32, 20, 12)
        for x in range(0, width, 80):
            cv2.line(frame, (x, 0), (x, height), (44, 32, 22), 1)
        for y in range(0, height, 80):
            cv2.line(frame, (0, y), (width, y), (44, 32, 22), 1)
        cv2.rectangle(frame, (24, 24), (width - 24, height - 24), (70, 48, 30), 2)
        return frame

    # ---------- 状态 ----------
    def describe(self) -> dict[str, Any]:
        with self._lock:
            last_frame = self._last_frame_at
            stale = (
                last_frame is None
                or (now() - last_frame).total_seconds() > 3
            )
            return {
                "status": self._status,
                "source": self._source,
                "simulated": self._synthetic,
                "connected": self._status == CameraStatus.CONNECTED and not stale,
                "stale": stale,
                "index": self._settings.camera_index,
                "resolution": f"{self._settings.camera_width}x{self._settings.camera_height}",
                "target_fps": self._settings.camera_fps,
                "measured_fps": self._measured_fps,
                "last_frame_at": iso(last_frame) if last_frame else None,
                "message": self._message,
            }
