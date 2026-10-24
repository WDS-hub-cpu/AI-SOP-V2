"""健康检查：存活/就绪，供部署探针使用。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_container
from app.core.container import Container
from app.core.errors import ServiceUnavailableError
from app.core.responses import ok
from app.core.timeutil import iso, now
from app.inference.base import DetectorStatus

router = APIRouter(tags=["health"])


@router.get("/health")
def health(container: Container = Depends(get_container)) -> dict:
    camera = container.camera.describe()
    return ok(
        {
            "status": "UP",
            "version": container.settings.app_version,
            "environment": container.settings.env,
            "time": iso(),
            "database": {
                "status": "UP" if container.db.path.exists() else "DOWN",
                "path": str(container.db.path),
            },
            "model": {
                "status": container.detector.status,
                "simulated": container.detector.simulated,
                "error": container.detector.error,
            },
            "camera": {
                "status": camera["status"],
                "simulated": camera["simulated"],
                "connected": camera["connected"],
            },
            "runtime": {
                "state": container.runtime.runtime_state,
                "simulated": container.runtime.is_simulated,
            },
        }
    )


@router.get("/health/live")
def live() -> dict:
    return ok({"status": "alive", "time": iso()})


@router.get("/health/ready")
def ready(container: Container = Depends(get_container)) -> dict:
    try:
        db_ok = container.db.query_one("SELECT 1") is not None
    except Exception as exc:  # pragma: no cover
        raise ServiceUnavailableError("数据库不可用", details=str(exc)) from exc
    if not db_ok:
        raise ServiceUnavailableError("数据库不可用")

    model = container.detector
    model_ready = model.status in (DetectorStatus.READY, DetectorStatus.MOCK)
    return ok(
        {
            "status": "READY",
            "time": iso(now()),
            "checks": {
                "database": "UP",
                "runtime": "UP" if container.settings.runtime_enabled else "DISABLED",
                "model": str(model.status),
                "camera": container.camera.describe()["status"],
            },
            "model_ready": model_ready,
            "simulated": container.runtime.is_simulated,
        }
    )
