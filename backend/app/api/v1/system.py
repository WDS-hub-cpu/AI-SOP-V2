"""系统状态、运行维护与模拟注入接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_container
from app.core.container import Container
from app.core.logging import log_buffer
from app.core.responses import ok
from app.core.timeutil import iso
from app.schemas.monitor import SimulationRequest

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/status")
async def status(container: Container = Depends(get_container)) -> dict:
    payload = await container.runtime.system_status()
    payload["server_time"] = iso()
    payload["api_prefix"] = container.settings.api_prefix
    return ok(payload)


@router.get("/config")
def config(container: Container = Depends(get_container)) -> dict:
    return ok(container.runtime.safe_config())


@router.get("/logs")
def logs(
    limit: int = Query(50, ge=1, le=200),
    container: Container = Depends(get_container),
) -> dict:
    return ok({"items": log_buffer.snapshot(limit)})


@router.post("/model/reload")
async def reload_model(container: Container = Depends(get_container)) -> dict:
    return ok(await container.runtime.reload_model())


@router.post("/camera/reconnect")
async def reconnect_camera(container: Container = Depends(get_container)) -> dict:
    return ok(await container.runtime.reconnect_camera())


@router.post("/simulation")
async def simulate(
    payload: SimulationRequest,
    container: Container = Depends(get_container),
) -> dict:
    return ok(await container.runtime.simulate(payload.action, payload.gesture))
