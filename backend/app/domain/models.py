"""领域数据对象（与 HTTP Schema、数据库行解耦）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.domain.enums import EventType, SessionStatus, Severity, StepRecordStatus


@dataclass(frozen=True, slots=True)
class SopStep:
    order: int
    name: str
    gesture: str
    description: str = ""
    timeout_seconds: int = 20
    enabled: bool = True
    required: bool = True


@dataclass(slots=True)
class StepExecution:
    order: int
    name: str
    gesture: str
    status: StepRecordStatus
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    confidence: float | None = None


@dataclass(frozen=True, slots=True)
class EngineEvent:
    type: EventType
    severity: Severity
    message: str
    at: datetime
    step_order: int | None = None
    step_name: str | None = None


@dataclass(slots=True)
class Detection:
    gesture: str | None
    label: str | None
    confidence: float
    simulated: bool
    inference_ms: float = 0.0
    boxes: list[dict] = field(default_factory=list)


@dataclass(slots=True)
class Box:
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float
    label: str
    gesture: str | None = None

    def as_dict(self) -> dict:
        return {
            "x1": round(self.x1, 4),
            "y1": round(self.y1, 4),
            "x2": round(self.x2, 4),
            "y2": round(self.y2, 4),
            "confidence": round(self.confidence, 4),
            "label": self.label,
            "gesture": self.gesture,
        }


@dataclass(slots=True)
class SessionSnapshot:
    """状态机对外暴露的只读快照。"""

    session_id: str
    station_id: str
    status: SessionStatus
    started_at: datetime
    current_index: int
    steps: list[SopStep]
    completed: list[StepExecution]
    anomalies: list[EngineEvent]
    step_started_at: datetime
    end_reason: str | None = None
