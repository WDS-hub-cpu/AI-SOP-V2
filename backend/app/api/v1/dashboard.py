"""首页仪表盘聚合接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_container
from app.core.container import Container
from app.core.responses import ok

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
async def summary(container: Container = Depends(get_container)) -> dict:
    monitor = await container.runtime.get_monitor_snapshot()
    stats = container.session_repo.today_stats()
    return ok(
        {
            "station": monitor["station"],
            "stats": stats,
            "runtime": monitor["runtime"],
            "session": monitor["session"],
            "current_step": monitor["current_step"],
            "steps": monitor["steps"],
            "recent_events": container.event_repo.recent(6),
            "recent_sessions": container.session_repo.recent_sessions(5),
            "system": {
                "model_status": container.detector.status,
                "model_simulated": container.detector.simulated,
                "camera_status": container.camera.describe()["status"],
                "camera_simulated": container.camera.describe()["simulated"],
                "simulated": container.runtime.is_simulated,
                "ws_clients": container.hub.client_count,
            },
            "updated_at": monitor["updated_at"],
        }
    )
