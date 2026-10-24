"""SOP 状态机规则测试（不依赖 IO / 数据库）。"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.domain.enums import EventType, SessionStatus, Severity, StepRecordStatus
from app.domain.models import SopStep
from app.services.sop_engine import SopEngine

BASE = datetime(2026, 1, 1, 8, 0, 0)


def build_steps(timeout: int = 20, required: bool = True) -> list[SopStep]:
    return [
        SopStep(1, "步骤一", "ONE", "", timeout, True, required),
        SopStep(2, "步骤二", "TWO", "", timeout, True, required),
        SopStep(3, "步骤三", "THREE", "", timeout, True, required),
        SopStep(4, "步骤四", "FOUR", "", timeout, True, required),
        SopStep(5, "步骤五", "FIVE", "", timeout, True, required),
    ]


def build_engine(**kwargs) -> SopEngine:
    params = {
        "station_id": "TEST-01",
        "fail_on_sequence_error": True,
        "fail_on_timeout": True,
        "session_max_seconds": 300,
    }
    params.update(kwargs)
    return SopEngine(build_steps(), **params)


def test_complete_flow_is_compliant() -> None:
    engine = build_engine()
    outcome = engine.start(trigger="manual", at=BASE)
    assert outcome.session_started
    assert engine.snapshot().status == SessionStatus.RUNNING

    at = BASE
    for gesture in ("ONE", "TWO", "THREE", "FOUR", "FIVE"):
        at += timedelta(seconds=2)
        outcome = engine.handle_detection(gesture, 0.95, at)

    snapshot = engine.snapshot()
    assert snapshot.status == SessionStatus.COMPLETED
    assert len([r for r in snapshot.completed if r.status == StepRecordStatus.COMPLETED]) == 5
    assert engine.anomaly_count == 0
    assert engine.compliance is True
    assert outcome.session_finished
    assert any(e.type == EventType.FLOW_COMPLETED for e in outcome.events)


def test_skipping_step_fails_and_records_events() -> None:
    engine = build_engine()
    engine.start(trigger="manual", at=BASE)

    outcome = engine.handle_detection("THREE", 0.9, BASE + timedelta(seconds=2))
    snapshot = engine.snapshot()
    types = {e.type for e in outcome.events}

    assert snapshot.status == SessionStatus.FAILED
    assert EventType.SKIPPED_STEP in types
    assert EventType.ORDER_ERROR in types
    assert EventType.FLOW_FAILED in types
    assert engine.anomaly_count == 2
    assert engine.compliance is False
    assert any(r.status == StepRecordStatus.SKIPPED for r in outcome.step_records)


def test_sequence_error_with_optional_step_only_warns() -> None:
    engine = build_engine(fail_on_sequence_error=False)
    engine._steps[0] = SopStep(1, "可选步骤", "ONE", "", 20, True, False)  # 演示用
    engine.start(trigger="manual", at=BASE)

    outcome = engine.handle_detection("THREE", 0.9, BASE + timedelta(seconds=2))
    snapshot = engine.snapshot()

    assert snapshot.status == SessionStatus.RUNNING
    assert snapshot.current_index == 0
    assert any(e.type == EventType.SKIPPED_STEP and e.severity == Severity.WARNING for e in outcome.events)
    assert engine.compliance is None


def test_repeated_step_is_warning_only() -> None:
    engine = build_engine()
    engine.start(trigger="manual", at=BASE)
    engine.handle_detection("ONE", 0.95, BASE + timedelta(seconds=2))

    outcome = engine.handle_detection("ONE", 0.95, BASE + timedelta(seconds=3))
    snapshot = engine.snapshot()

    assert snapshot.status == SessionStatus.RUNNING
    assert snapshot.current_index == 1
    assert engine.anomaly_count == 1
    assert [e.type for e in outcome.events] == [EventType.REPEATED_STEP]


def test_step_timeout_fails_session() -> None:
    engine = build_engine()
    engine.start(trigger="manual", at=BASE)

    outcome = engine.tick(BASE + timedelta(seconds=21))
    snapshot = engine.snapshot()

    assert snapshot.status == SessionStatus.FAILED
    assert snapshot.end_reason is not None and "超时" in snapshot.end_reason
    assert any(e.type == EventType.STEP_TIMEOUT for e in outcome.events)
    assert any(r.status == StepRecordStatus.TIMEOUT for r in outcome.step_records)
    assert engine.compliance is False


def test_timeout_continue_policy_completes_with_low_compliance() -> None:
    engine = build_engine(fail_on_timeout=False)
    engine._steps = build_steps()[:1]  # 单步骤，超时后直接结束
    engine.start(trigger="manual", at=BASE)

    outcome = engine.tick(BASE + timedelta(seconds=25))
    snapshot = engine.snapshot()

    assert snapshot.status == SessionStatus.COMPLETED
    assert engine.anomaly_count == 1
    assert engine.compliance is False
    assert outcome.session_finished


def test_session_timeout() -> None:
    engine = build_engine(session_max_seconds=30)
    engine.start(trigger="manual", at=BASE)

    outcome = engine.tick(BASE + timedelta(seconds=31))
    snapshot = engine.snapshot()

    assert snapshot.status == SessionStatus.FAILED
    assert any(e.type == EventType.SESSION_TIMEOUT for e in outcome.events)


def test_unknown_gesture_is_ignored() -> None:
    engine = build_engine()
    engine.start(trigger="manual", at=BASE)

    outcome = engine.handle_detection("UNKNOWN", 0.9, BASE + timedelta(seconds=1))
    assert outcome.events == []
    assert engine.snapshot().status == SessionStatus.RUNNING


def test_abort_marks_session_aborted() -> None:
    engine = build_engine()
    engine.start(trigger="manual", at=BASE)

    outcome = engine.abort("测试终止", BASE + timedelta(seconds=2))
    snapshot = engine.snapshot()

    assert snapshot.status == SessionStatus.ABORTED
    assert engine.compliance is False
    assert any(e.type == EventType.SESSION_ABORTED for e in outcome.events)
    assert outcome.session_finished


def test_running_session_rejects_config_change() -> None:
    engine = build_engine()
    engine.start(trigger="manual", at=BASE)
    try:
        engine.set_steps(build_steps())
    except ValueError as exc:
        assert "运行中" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("运行中不应允许替换配置")
