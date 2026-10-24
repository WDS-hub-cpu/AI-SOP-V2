"""领域枚举：状态机、事件、记录状态。"""

from __future__ import annotations

from enum import StrEnum


class SessionStatus(StrEnum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ABORTED = "ABORTED"


class SessionTrigger(StrEnum):
    AUTO = "auto"
    MANUAL = "manual"


class StepRecordStatus(StrEnum):
    COMPLETED = "COMPLETED"
    TIMEOUT = "TIMEOUT"
    SKIPPED = "SKIPPED"


class Severity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class EventType(StrEnum):
    FLOW_STARTED = "FLOW_STARTED"
    STEP_COMPLETED = "STEP_COMPLETED"
    FLOW_COMPLETED = "FLOW_COMPLETED"
    FLOW_FAILED = "FLOW_FAILED"
    SKIPPED_STEP = "SKIPPED_STEP"
    REPEATED_STEP = "REPEATED_STEP"
    ORDER_ERROR = "ORDER_ERROR"
    STEP_TIMEOUT = "STEP_TIMEOUT"
    SESSION_TIMEOUT = "SESSION_TIMEOUT"
    SESSION_ABORTED = "SESSION_ABORTED"


class EventStatus(StrEnum):
    OPEN = "OPEN"
    ACKED = "ACKED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


ANOMALY_EVENT_TYPES: tuple[str, ...] = (
    EventType.SKIPPED_STEP,
    EventType.REPEATED_STEP,
    EventType.ORDER_ERROR,
    EventType.STEP_TIMEOUT,
    EventType.SESSION_TIMEOUT,
    EventType.SESSION_ABORTED,
)
