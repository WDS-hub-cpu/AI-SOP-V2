"""SQLite 仓储测试。"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from app.db.database import Database
from app.db.repositories import EventRepository, SessionRepository, SopRepository
from app.domain.enums import EventType, SessionStatus, Severity
from app.domain.models import StepExecution

BASE = datetime(2026, 1, 1, 8, 0, 0)


def build_db(tmp_path: Path) -> Database:
    db = Database(tmp_path / "repo.db")
    db.init()
    return db


def test_sop_seed_and_replace(tmp_path: Path) -> None:
    sop = SopRepository(build_db(tmp_path))
    sop.seed_if_empty()
    steps = sop.list_steps()
    assert len(steps) == 5
    assert steps[0].gesture == "ONE"

    from app.domain.models import SopStep

    sop.replace_steps([SopStep(1, "单步", "ONE", "", 15, True, True)])
    assert len(sop.list_steps()) == 1
    assert sop.list_steps()[0].name == "单步"


def test_session_lifecycle_and_stats(tmp_path: Path) -> None:
    db = build_db(tmp_path)
    sessions = SessionRepository(db)
    events = EventRepository(db)

    sessions.create(
        session_id="s1",
        station_id="TEST-01",
        station_name="测试工位",
        trigger="manual",
        started_at=BASE.isoformat(timespec="seconds"),
        total_steps=5,
    )
    assert sessions.active("TEST-01")["id"] == "s1"

    record = StepExecution(
        order=1,
        name="步骤一",
        gesture="ONE",
        status="COMPLETED",
        started_at=BASE,
        finished_at=BASE + timedelta(seconds=2),
        duration_ms=2000,
        confidence=0.9,
    )
    sessions.add_step_record("s1", record)
    events.add(
        session_id="s1",
        station_id="TEST-01",
        event_type=EventType.STEP_TIMEOUT,
        severity=Severity.CRITICAL,
        message="测试超时",
        step_order=1,
        step_name="步骤一",
        created_at=(BASE + timedelta(seconds=3)).isoformat(timespec="seconds"),
        status="OPEN",
    )

    sessions.finish(
        session_id="s1",
        status=SessionStatus.FAILED,
        finished_at=(BASE + timedelta(seconds=5)).isoformat(timespec="seconds"),
        completed_steps=1,
        anomaly_count=1,
        compliance=False,
        end_reason="步骤超时",
    )

    stored = sessions.get("s1")
    assert stored["status"] == "FAILED"
    assert stored["compliance"] == 0
    assert len(sessions.step_records("s1")) == 1
    assert len(events.for_session("s1")) == 1
    assert sessions.active("TEST-01") is None

    stats = sessions.today_stats()
    assert stats["sessions_total"] >= 0
    assert isinstance(stats["open_anomalies"], int)

    items, total = events.list_events(page=1, page_size=10)
    assert total == 1
    assert items[0]["event_type"] == "STEP_TIMEOUT"

    assert events.update_status(items[0]["id"], "RESOLVED", BASE.isoformat(timespec="seconds"))
    assert events.get(items[0]["id"])["status"] == "RESOLVED"


def test_stale_running_is_closed_on_startup(tmp_path: Path) -> None:
    db = build_db(tmp_path)
    sessions = SessionRepository(db)
    sessions.create(
        session_id="stale",
        station_id="TEST-01",
        station_name="测试工位",
        trigger="auto",
        started_at=BASE.isoformat(timespec="seconds"),
        total_steps=5,
    )
    assert sessions.close_stale_running() == 1
    assert sessions.get("stale")["status"] == "ABORTED"
