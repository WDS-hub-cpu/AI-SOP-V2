-- 工业 AI SOP 数据库结构（SQLite / WAL）
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sop_steps (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    step_order      INTEGER NOT NULL UNIQUE,
    name            TEXT    NOT NULL,
    expected_gesture TEXT   NOT NULL,
    description     TEXT    NOT NULL DEFAULT '',
    timeout_seconds INTEGER NOT NULL DEFAULT 20,
    enabled         INTEGER NOT NULL DEFAULT 1,
    required        INTEGER NOT NULL DEFAULT 1,
    updated_at      TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS sop_sessions (
    id              TEXT PRIMARY KEY,
    station_id      TEXT NOT NULL,
    station_name    TEXT NOT NULL,
    status          TEXT NOT NULL,
    trigger         TEXT NOT NULL DEFAULT 'auto',
    started_at      TEXT NOT NULL,
    finished_at     TEXT,
    total_steps     INTEGER NOT NULL DEFAULT 0,
    completed_steps INTEGER NOT NULL DEFAULT 0,
    anomaly_count   INTEGER NOT NULL DEFAULT 0,
    compliance      INTEGER,
    end_reason      TEXT
);

CREATE INDEX IF NOT EXISTS idx_sessions_started  ON sop_sessions(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_station  ON sop_sessions(station_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_status   ON sop_sessions(status, started_at DESC);

CREATE TABLE IF NOT EXISTS sop_step_records (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    step_order  INTEGER NOT NULL,
    step_name   TEXT NOT NULL,
    gesture     TEXT NOT NULL,
    status      TEXT NOT NULL,
    confidence  REAL,
    started_at  TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    duration_ms INTEGER NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sop_sessions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_step_records_session ON sop_step_records(session_id, step_order);

CREATE TABLE IF NOT EXISTS sop_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT,
    station_id  TEXT NOT NULL,
    event_type  TEXT NOT NULL,
    severity    TEXT NOT NULL,
    step_order  INTEGER,
    step_name   TEXT,
    message     TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'OPEN',
    created_at  TEXT NOT NULL,
    handled_at  TEXT,
    handled_by  TEXT,
    FOREIGN KEY (session_id) REFERENCES sop_sessions(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_events_created ON sop_events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_status  ON sop_events(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_session ON sop_events(session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_events_type    ON sop_events(event_type, created_at DESC);
