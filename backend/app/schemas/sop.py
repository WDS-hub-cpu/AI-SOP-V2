"""SOP 配置 Schema 与校验规则。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.core.errors import ValidationError
from app.domain.models import SopStep

GestureName = Literal["ONE", "TWO", "THREE", "FOUR", "FIVE"]


class StepInput(BaseModel):
    order: int = Field(ge=1, le=20, description="步骤顺序，从 1 开始连续递增")
    name: str = Field(min_length=1, max_length=64)
    expected_gesture: GestureName
    description: str = Field(default="", max_length=200)
    timeout_seconds: int = Field(default=20, ge=5, le=600)
    enabled: bool = True
    required: bool = True


class StepListRequest(BaseModel):
    steps: list[StepInput] = Field(min_length=1, max_length=10)


class StepOut(BaseModel):
    order: int
    name: str
    expected_gesture: str
    description: str
    timeout_seconds: int
    enabled: bool
    required: bool


class StepListResponse(BaseModel):
    items: list[StepOut]
    note: str
    pending_config: bool


def to_domain(steps: list[StepInput]) -> list[SopStep]:
    return [
        SopStep(
            order=item.order,
            name=item.name.strip(),
            gesture=item.expected_gesture,
            description=item.description.strip(),
            timeout_seconds=item.timeout_seconds,
            enabled=item.enabled,
            required=item.required,
        )
        for item in sorted(steps, key=lambda s: s.order)
    ]


def validate_steps(steps: list[StepInput]) -> None:
    if not steps:
        raise ValidationError("至少需要配置一个步骤")

    orders = sorted(step.order for step in steps)
    expected_orders = list(range(1, len(steps) + 1))
    if orders != expected_orders:
        raise ValidationError(
            "步骤顺序必须从 1 开始连续递增，不允许重复或跳号",
            details={"orders": orders, "expected": expected_orders},
        )

    enabled = [step for step in steps if step.enabled]
    if not enabled:
        raise ValidationError("至少需要启用一个步骤")

    gestures = [step.expected_gesture for step in enabled]
    duplicates = sorted({g for g in gestures if gestures.count(g) > 1})
    if duplicates:
        raise ValidationError(
            "启用的步骤中不允许重复使用同一手势，否则无法唯一映射步骤",
            details={"duplicated_gestures": duplicates},
        )


def to_output(steps: list[SopStep]) -> list[StepOut]:
    return [
        StepOut(
            order=step.order,
            name=step.name,
            expected_gesture=step.gesture,
            description=step.description,
            timeout_seconds=step.timeout_seconds,
            enabled=step.enabled,
            required=step.required,
        )
        for step in steps
    ]
