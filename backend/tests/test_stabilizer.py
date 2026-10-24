"""检测稳定器测试。"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.domain.models import Detection
from app.services.stabilizer import GestureStabilizer

BASE = datetime(2026, 1, 1, 8, 0, 0)


def detection(gesture: str | None, confidence: float = 0.9) -> Detection:
    return Detection(gesture=gesture, label=gesture, confidence=confidence, simulated=True)


def test_requires_stable_frames() -> None:
    stabilizer = GestureStabilizer(stable_frames=3, reset_ms=500)
    assert stabilizer.update(detection("ONE"), BASE) is None
    assert stabilizer.update(detection("ONE"), BASE + timedelta(milliseconds=200)) is None
    assert stabilizer.update(detection("ONE"), BASE + timedelta(milliseconds=400)) == "ONE"


def test_low_confidence_is_rejected() -> None:
    stabilizer = GestureStabilizer(min_confidence=0.5, stable_frames=2, reset_ms=500)
    assert stabilizer.update(detection("ONE", 0.3), BASE) is None
    assert stabilizer.update(detection("ONE", 0.3), BASE + timedelta(milliseconds=200)) is None


def test_short_gap_does_not_repeat_same_gesture() -> None:
    stabilizer = GestureStabilizer(stable_frames=2, reset_ms=300)
    at = BASE
    for _ in range(2):
        stabilizer.update(detection("ONE"), at)
        at += timedelta(milliseconds=200)
    assert stabilizer.update(detection("ONE"), at + timedelta(milliseconds=700)) is None


def test_gap_allows_new_cycle_after_release() -> None:
    stabilizer = GestureStabilizer(stable_frames=2, reset_ms=300, release_frames=2)
    at = BASE
    assert stabilizer.update(detection("ONE"), at) is None
    assert stabilizer.update(detection("ONE"), at + timedelta(milliseconds=200)) == "ONE"

    # 仅仅时间过去不够，必须观察到「无手势」帧
    at = BASE + timedelta(seconds=3)
    assert stabilizer.update(detection("ONE"), at) is None
    assert stabilizer.update(detection("ONE"), at + timedelta(milliseconds=200)) is None

    # 连续两帧无手势后，允许同一手势再次触发
    stabilizer.update(detection(None), at + timedelta(milliseconds=400))
    assert stabilizer.update(detection(None), at + timedelta(milliseconds=600)) is None
    stabilizer.update(detection("ONE"), at + timedelta(milliseconds=800))
    assert stabilizer.update(detection("ONE"), at + timedelta(milliseconds=1000)) == "ONE"


def test_same_gesture_does_not_repeat_without_release() -> None:
    stabilizer = GestureStabilizer(stable_frames=2, reset_ms=300, release_frames=2)
    at = BASE
    for _ in range(2):
        stabilizer.update(detection("ONE"), at)
        at += timedelta(milliseconds=200)
    assert stabilizer.update(detection("ONE"), at) is None
    assert stabilizer.update(detection("ONE"), at + timedelta(milliseconds=200)) is None
    assert stabilizer.update(detection("ONE"), at + timedelta(seconds=2)) is None


def test_gesture_change_emits_new_gesture() -> None:
    stabilizer = GestureStabilizer(stable_frames=2, reset_ms=300)
    stabilizer.update(detection("ONE"), BASE)
    assert stabilizer.update(detection("ONE"), BASE + timedelta(milliseconds=200)) == "ONE"
    assert stabilizer.update(detection("TWO"), BASE + timedelta(milliseconds=400)) is None
    assert stabilizer.update(detection("TWO"), BASE + timedelta(milliseconds=600)) == "TWO"
