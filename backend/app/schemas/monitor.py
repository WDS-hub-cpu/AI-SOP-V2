"""监控与会话相关 Schema。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SessionStopRequest(BaseModel):
    reason: str = Field(default="操作员手动终止", max_length=200)


class SimulationRequest(BaseModel):
    action: Literal["gesture", "skip", "repeat", "wrong_order", "timeout", "reset"]
    gesture: Literal["ONE", "TWO", "THREE", "FOUR", "FIVE"] | None = None


class EventStatusRequest(BaseModel):
    status: Literal["ACKED", "RESOLVED"]
