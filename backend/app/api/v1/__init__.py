"""v1 API 路由聚合。"""

from fastapi import APIRouter

from app.api.v1 import dashboard, events, health, history, monitor, sop, system, ws

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(dashboard.router)
api_router.include_router(monitor.router)
api_router.include_router(sop.router)
api_router.include_router(events.router)
api_router.include_router(history.router)
api_router.include_router(system.router)
api_router.include_router(ws.router)

__all__ = ["api_router"]
