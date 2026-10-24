"""会话与步骤记录仓储。"""

from __future__ import annotations

from typing import Any

from app.core.timeutil import iso, today_bounds
from app.db.database import Database
from app.domain.enums import EventType, SessionStatus, Severity
from app.domain.models import StepExecution


class SessionRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    # ---------- 写入 ----------
    def create(
        self,
        *,
        session_id: str,
        station_id: str,
        station_name: str,
        trigger: str,
        started_at: str,
        total_steps: int,
    ) -> None:
        self.db.execute(
            """
            INSERT INTO sop_sessions
                (id, station_id, station_name, status, trigger, started_at, total_steps)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                station_id,
                station_name,
                SessionStatus.RUNNING,
                trigger,
                started_at,
                total_steps,
            ),
        )

    def finish(
        self,
        *,
        session_id: str,
        status: SessionStatus,
        finished_at: str,
        completed_steps: int,
        anomaly_count: int,
        compliance: bool,
        end_reason: str | None,
    ) -> None:
        self.db.execute(
            """
            UPDATE sop_sessions
               SET status = ?, finished_at = ?, completed_steps = ?,
                   anomaly_count = ?, compliance = ?, end_reason = ?
             WHERE id = ?
            """,
            (
                status,
                finished_at,
                completed_steps,
                anomaly_count,
                1 if compliance else 0,
                end_reason,
                session_id,
            ),
        )

    def add_step_record(self, session_id: str, record: StepExecution) -> None:
        self.db.execute(
            """
            INSERT INTO sop_step_records
                (session_id, step_order, step_name, gesture, status,
                 confidence, started_at, finished_at, duration_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                record.order,
                record.name,
                record.gesture,
                record.status,
                record.confidence,
                iso(record.started_at),
                iso(record.finished_at),
                record.duration_ms,
            ),
        )

    def close_stale_running(self) -> int:
        """服务重启后，把上一次进程遗留的 RUNNING 会话标记为中断。"""
        with self.db.connect() as conn:
            cursor = conn.execute(
                """
                UPDATE sop_sessions
                   SET status = ?, finished_at = ?, end_reason = ?
                 WHERE status = ?
                """,
                (
                    SessionStatus.ABORTED,
                    iso(),
                    "后端服务重启，会话已中断",
                    SessionStatus.RUNNING,
                ),
            )
            return int(cursor.rowcount)

    # ---------- 查询 ----------
    def get(self, session_id: str) -> dict[str, Any] | None:
        row = self.db.query_one("SELECT * FROM sop_sessions WHERE id = ?", (session_id,))
        return dict(row) if row else None

    def active(self, station_id: str) -> dict[str, Any] | None:
        row = self.db.query_one(
            """
            SELECT * FROM sop_sessions
             WHERE station_id = ? AND status = ?
             ORDER BY started_at DESC LIMIT 1
            """,
            (station_id, SessionStatus.RUNNING),
        )
        return dict(row) if row else None

    def list_sessions(
        self,
        *,
        page: int,
        page_size: int,
        station_id: str | None = None,
        status: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        where, params = [], []
        if station_id:
            where.append("station_id = ?")
            params.append(station_id)
        if status:
            where.append("status = ?")
            params.append(status)
        if date_from:
            where.append("started_at >= ?")
            params.append(date_from)
        if date_to:
            where.append("started_at <= ?")
            params.append(date_to)
        clause = f"WHERE {' AND '.join(where)}" if where else ""

        total_row = self.db.query_one(
            f"SELECT COUNT(*) AS c FROM sop_sessions {clause}", params
        )
        total = int(total_row["c"]) if total_row else 0
        rows = self.db.query_all(
            f"""
            SELECT * FROM sop_sessions
            {clause}
            ORDER BY started_at DESC
            LIMIT ? OFFSET ?
            """,
            [*params, page_size, (page - 1) * page_size],
        )
        return [dict(row) for row in rows], total

    def step_records(self, session_id: str) -> list[dict[str, Any]]:
        rows = self.db.query_all(
            """
            SELECT * FROM sop_step_records
             WHERE session_id = ?
             ORDER BY step_order ASC, id ASC
            """,
            (session_id,),
        )
        return [dict(row) for row in rows]

    def today_stats(self) -> dict[str, Any]:
        start, end = today_bounds()
        row = self.db.query_one(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END) AS completed,
                SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) AS failed,
                SUM(CASE WHEN status = 'COMPLETED' AND compliance = 1 THEN 1 ELSE 0 END)
                    AS compliant
            FROM sop_sessions
            WHERE started_at >= ? AND started_at < ?
            """,
            (start, end),
        )
        total = int(row["total"] or 0)
        completed = int(row["completed"] or 0)
        compliant = int(row["compliant"] or 0)

        operations_row = self.db.query_one(
            """
            SELECT COUNT(*) AS c
              FROM sop_step_records r
              JOIN sop_sessions s ON s.id = r.session_id
             WHERE s.started_at >= ? AND s.started_at < ?
            """,
            (start, end),
        )
        anomalies_row = self.db.query_one(
            """
            SELECT COUNT(*) AS c FROM sop_events
             WHERE created_at >= ? AND created_at < ?
               AND severity IN ('WARNING', 'CRITICAL')
            """,
            (start, end),
        )
        open_row = self.db.query_one(
            """
            SELECT COUNT(*) AS c FROM sop_events
             WHERE status != 'RESOLVED' AND severity IN ('WARNING', 'CRITICAL')
            """
        )
        avg_row = self.db.query_one(
            """
            SELECT AVG((julianday(finished_at) - julianday(started_at)) * 86400.0) AS avg_s
              FROM sop_sessions
             WHERE started_at >= ? AND started_at < ? AND status = 'COMPLETED'
            """,
            (start, end),
        )

        return {
            "sessions_total": total,
            "sessions_completed": completed,
            "sessions_failed": int(row["failed"] or 0),
            "compliant_sessions": compliant,
            "compliance_rate": round(compliant / completed * 100, 1) if completed else None,
            "compliance_samples": completed,
            "operations": int(operations_row["c"] or 0) if operations_row else 0,
            "anomalies_today": int(anomalies_row["c"] or 0) if anomalies_row else 0,
            "open_anomalies": int(open_row["c"] or 0) if open_row else 0,
            "avg_cycle_seconds": round(float(avg_row["avg_s"]), 1)
            if avg_row and avg_row["avg_s"]
            else None,
        }

    def recent_sessions(self, limit: int = 8) -> list[dict[str, Any]]:
        rows = self.db.query_all(
            "SELECT * FROM sop_sessions ORDER BY started_at DESC LIMIT ?", (limit,)
        )
        return [dict(row) for row in rows]


class EventRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def add(
        self,
        *,
        session_id: str | None,
        station_id: str,
        event_type: EventType | str,
        severity: Severity | str,
        message: str,
        step_order: int | None,
        step_name: str | None,
        created_at: str,
        status: str,
    ) -> int:
        return self.db.execute(
            """
            INSERT INTO sop_events
                (session_id, station_id, event_type, severity, step_order,
                 step_name, message, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                station_id,
                str(event_type),
                str(severity),
                step_order,
                step_name,
                message,
                status,
                created_at,
            ),
        )

    def update_status(self, event_id: int, status: str, handled_at: str) -> bool:
        with self.db.connect() as conn:
            cursor = conn.execute(
                "UPDATE sop_events SET status = ?, handled_at = ? WHERE id = ?",
                (status, handled_at, event_id),
            )
            return cursor.rowcount > 0

    def get(self, event_id: int) -> dict[str, Any] | None:
        row = self.db.query_one("SELECT * FROM sop_events WHERE id = ?", (event_id,))
        return dict(row) if row else None

    def list_events(
        self,
        *,
        page: int,
        page_size: int,
        station_id: str | None = None,
        status: str | None = None,
        severity: str | None = None,
        event_type: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        anomalies_only: bool = True,
    ) -> tuple[list[dict[str, Any]], int]:
        where, params = [], []
        if anomalies_only:
            where.append("severity IN ('WARNING', 'CRITICAL')")
        if station_id:
            where.append("station_id = ?")
            params.append(station_id)
        if status:
            where.append("status = ?")
            params.append(status)
        if severity:
            where.append("severity = ?")
            params.append(severity)
        if event_type:
            where.append("event_type = ?")
            params.append(event_type)
        if date_from:
            where.append("created_at >= ?")
            params.append(date_from)
        if date_to:
            where.append("created_at <= ?")
            params.append(date_to)
        clause = f"WHERE {' AND '.join(where)}" if where else ""

        total_row = self.db.query_one(
            f"SELECT COUNT(*) AS c FROM sop_events {clause}", params
        )
        total = int(total_row["c"]) if total_row else 0
        rows = self.db.query_all(
            f"""
            SELECT * FROM sop_events
            {clause}
            ORDER BY created_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            [*params, page_size, (page - 1) * page_size],
        )
        return [dict(row) for row in rows], total

    def for_session(self, session_id: str) -> list[dict[str, Any]]:
        rows = self.db.query_all(
            "SELECT * FROM sop_events WHERE session_id = ? ORDER BY created_at ASC, id ASC",
            (session_id,),
        )
        return [dict(row) for row in rows]

    def recent(self, limit: int = 5) -> list[dict[str, Any]]:
        rows = self.db.query_all(
            """
            SELECT * FROM sop_events
             WHERE severity IN ('WARNING', 'CRITICAL')
             ORDER BY created_at DESC, id DESC LIMIT ?
            """,
            (limit,),
        )
        return [dict(row) for row in rows]

    def open_count(self) -> int:
        row = self.db.query_one(
            """
            SELECT COUNT(*) AS c FROM sop_events
             WHERE status != 'RESOLVED' AND severity IN ('WARNING', 'CRITICAL')
            """
        )
        return int(row["c"] or 0) if row else 0
