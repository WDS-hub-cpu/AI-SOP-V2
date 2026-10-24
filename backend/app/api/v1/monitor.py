"""实时监控：快照、MJPEG 视频流、会话控制。"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response, StreamingResponse

from app.api.deps import get_container
from app.core.container import Container
from app.core.errors import ServiceUnavailableError
from app.core.responses import ok
from app.schemas.monitor import SessionStopRequest

router = APIRouter(prefix="/monitor", tags=["monitor"])

_BOUNDARY = "frame"


@router.get("/current")
async def current(container: Container = Depends(get_container)) -> dict:
    return ok(await container.runtime.get_monitor_snapshot())


@router.get("/frame")
def frame(container: Container = Depends(get_container)) -> Response:
    jpeg = container.camera.latest_jpeg()
    if not jpeg:
        raise ServiceUnavailableError("暂无可用的摄像头画面")
    return Response(
        content=jpeg,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/stream")
def stream(request: Request, container: Container = Depends(get_container)) -> StreamingResponse:
    if container.camera.latest_jpeg() is None:
        raise ServiceUnavailableError("暂无可用的摄像头画面")

    async def generator():
        interval = 1.0 / max(min(container.settings.camera_fps, 15), 1.0)
        while True:
            if await request.is_disconnected():
                break
            jpeg = container.camera.latest_jpeg()
            if jpeg:
                yield (
                    f"--{_BOUNDARY}\r\n"
                    f"Content-Type: image/jpeg\r\n"
                    f"Content-Length: {len(jpeg)}\r\n\r\n"
                ).encode("ascii") + jpeg + b"\r\n"
            await asyncio.sleep(interval)

    return StreamingResponse(
        generator(),
        media_type=f"multipart/x-mixed-replace; boundary={_BOUNDARY}",
        headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
    )


@router.post("/session/start")
async def start_session(container: Container = Depends(get_container)) -> dict:
    return ok(await container.runtime.start_session_manual())


@router.post("/session/stop")
async def stop_session(
    payload: SessionStopRequest,
    container: Container = Depends(get_container),
) -> dict:
    return ok(await container.runtime.stop_session_manual(payload.reason))
