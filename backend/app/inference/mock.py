"""模拟检测器：仅用于前后端联调与规则演示。

重要：该检测器不读取图像内容，也不代表任何真实视觉识别能力。
所有输出都会带 simulated=True，前端必须显示 SIMULATION 标识。
"""

from __future__ import annotations

import threading
import time
from typing import Any

import numpy as np

from app.core.config import Settings
from app.domain.models import Detection
from app.inference.base import BaseDetector, DetectorStatus

_GESTURES = ("ONE", "TWO", "THREE", "FOUR", "FIVE")


class MockDetector(BaseDetector):
    name = "模拟检测器（非真实 AI）"
    simulated = True

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self._scenario = settings.mock_scenario
        self._dwell = max(settings.mock_step_dwell_seconds, 0.5)
        self._rest = max(settings.mock_rest_seconds, 0.3)
        self._lock = threading.Lock()
        self._t0 = time.monotonic()
        self._queue: list[tuple[str | None, float]] = []
        self._inject_started: float | None = None
        self._sequence = self._build_sequence(self._scenario)

    @staticmethod
    def _build_sequence(scenario: str) -> list[str]:
        if scenario == "faulty":
            # 故意包含错序、重复，便于演示规则引擎
            return ["ONE", "THREE", "TWO", "TWO", "FOUR", "FIVE"]
        return list(_GESTURES)

    def load(self) -> None:
        with self._lock:
            self._queue.clear()
            self._inject_started = None
            self._t0 = time.monotonic()
        self.status = DetectorStatus.MOCK
        self.error = None

    def unload(self) -> None:
        self.status = DetectorStatus.UNLOADED

    def predict(self, frame: np.ndarray | None) -> Detection:
        with self._lock:
            gesture = self._next_gesture()
        confidence = 0.9 + (abs(hash(gesture)) % 40) / 1000 if gesture else 0.0
        return Detection(
            gesture=gesture,
            label=f"SIMULATED:{gesture}" if gesture else None,
            confidence=round(confidence, 3),
            simulated=True,
            inference_ms=0.0,
        )

    # ---------- 演示控制 ----------
    def inject_gesture(self, gesture: str, duration: float = 2.0) -> None:
        gesture = gesture.upper()
        if gesture not in _GESTURES:
            raise ValueError(f"不支持的手势：{gesture}")
        with self._lock:
            self._queue = [(gesture, max(duration, 0.5))]
            self._inject_started = time.monotonic()

    def inject_sequence(self, sequence: list[tuple[str | None, float]]) -> None:
        with self._lock:
            self._queue = list(sequence)
            self._inject_started = time.monotonic()

    def pause(self, seconds: float) -> None:
        """注入一段「无检测」时间，用于演示步骤超时。"""
        with self._lock:
            self._queue = [(None, max(seconds, 1.0))]
            self._inject_started = time.monotonic()

    def reset_sequence(self) -> None:
        with self._lock:
            self._queue.clear()
            self._inject_started = None
            self._t0 = time.monotonic()
            self._sequence = self._build_sequence(self._scenario)

    # ---------- 内部 ----------
    def _next_gesture(self) -> str | None:
        if self._queue:
            assert self._inject_started is not None
            elapsed = time.monotonic() - self._inject_started
            offset = 0.0
            for gesture, duration in self._queue:
                if elapsed < offset + duration:
                    return gesture
                offset += duration
            self._queue.clear()
            self._inject_started = None
            self._t0 = time.monotonic()
        return self._timeline_gesture()

    def _timeline_gesture(self) -> str | None:
        elapsed = (time.monotonic() - self._t0) % self._cycle_duration()
        cursor = 0.0
        # 起始静默
        idle = 2.0
        if elapsed < idle:
            return None
        cursor += idle
        for gesture in self._sequence:
            if elapsed < cursor + self._dwell:
                return gesture
            cursor += self._dwell
            if elapsed < cursor + self._rest:
                return None
            cursor += self._rest
        return None

    def _cycle_duration(self) -> float:
        return 2.0 + len(self._sequence) * (self._dwell + self._rest) + 3.0

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "simulated": True,
            "error": self.error,
            "backend": "none",
            "notice": "模拟检测器不读取图像内容，仅用于联调与规则演示，不代表真实 AI 识别结果。",
            "scenario": self._scenario,
            "sequence": self._sequence,
        }
