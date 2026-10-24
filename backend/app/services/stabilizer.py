"""检测结果稳定器：连续 N 帧同一手势才确认，避免抖动误触发。"""

from __future__ import annotations

from datetime import datetime

from app.domain.models import Detection


class GestureStabilizer:
    def __init__(
        self,
        *,
        min_confidence: float = 0.5,
        stable_frames: int = 3,
        reset_ms: int = 500,
        release_frames: int = 2,
    ) -> None:
        self.min_confidence = min_confidence
        self.stable_frames = max(1, stable_frames)
        self.reset_ms = max(reset_ms, 0)
        self.release_frames = max(1, release_frames)
        self._candidate: str | None = None
        self._count = 0
        self._emitted: str | None = None
        self._empty_frames = 0
        self._last_seen: datetime | None = None

    def update(self, detection: Detection, at: datetime) -> str | None:
        gesture = detection.gesture
        if gesture is None or detection.confidence < self.min_confidence:
            self._empty_frames += 1
            self._last_seen = at
            # 必须观察到连续「无手势」帧，才允许同一手势再次触发；
            # 这样不依赖推理帧率，也不会因偶发丢帧产生重复步骤告警。
            if self._empty_frames >= self.release_frames:
                self._candidate = None
                self._count = 0
                self._emitted = None
            return None

        gesture = gesture.upper()
        self._empty_frames = 0
        if self._last_seen and self._gap_ms(at) > self.reset_ms:
            self._candidate = None
            self._count = 0

        if gesture == self._candidate:
            self._count += 1
        else:
            self._candidate = gesture
            self._count = 1

        self._last_seen = at
        if self._count >= self.stable_frames and gesture != self._emitted:
            self._emitted = gesture
            return gesture
        return None

    def reset(self) -> None:
        self._candidate = None
        self._count = 0
        self._emitted = None
        self._empty_frames = 0
        self._last_seen = None

    def _gap_ms(self, at: datetime) -> float:
        assert self._last_seen is not None
        return (at - self._last_seen).total_seconds() * 1000
