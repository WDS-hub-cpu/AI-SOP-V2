"""SOP 步骤配置接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_container
from app.core.container import Container
from app.core.responses import ok
from app.schemas.sop import StepListRequest, to_domain, to_output, validate_steps

router = APIRouter(prefix="/sop", tags=["sop"])


@router.get("/steps")
async def list_steps(container: Container = Depends(get_container)) -> dict:
    system = await container.runtime.system_status()
    return ok(
        {
            "items": to_output(container.sop_repo.list_steps()),
            "note": system["sop"]["config_note"] or "配置由后端持久化，运行中的会话不受影响",
            "pending_config": system["sop"]["pending_config"],
        }
    )


@router.put("/steps")
async def save_steps(
    payload: StepListRequest,
    container: Container = Depends(get_container),
) -> dict:
    validate_steps(payload.steps)
    domain_steps = to_domain(payload.steps)
    container.sop_repo.replace_steps(domain_steps)
    result = await container.runtime.apply_steps(domain_steps)
    return ok(
        {
            "items": to_output(container.sop_repo.list_steps()),
            "note": result["note"],
            "pending_config": not result["applied"],
        }
    )


@router.post("/steps/reset")
async def reset_steps(container: Container = Depends(get_container)) -> dict:
    steps = container.sop_repo.reset_to_defaults()
    result = await container.runtime.apply_steps(steps)
    return ok(
        {
            "items": to_output(steps),
            "note": result["note"],
            "pending_config": not result["applied"],
        }
    )
