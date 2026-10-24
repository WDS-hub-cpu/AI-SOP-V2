"""WebSocket 实时通道。"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.timeutil import iso

router = APIRouter(tags=["realtime"])
logger = logging.getLogger(__name__)


@router.websocket("/ws/monitor")
async def monitor_socket(websocket: WebSocket) -> None:
    container = websocket.app.state.container
    hub = container.hub
    await hub.connect(websocket)
    try:
        await websocket.send_json(
            {
                "type": "hello",
                "data": {
                    "system": await container.runtime.system_status(),
                    "snapshot": await container.runtime.get_monitor_snapshot(),
                },
                "ts": iso(),
            }
        )
        while True:
            message = await websocket.receive_text()
            payload: dict = {}
            try:
                parsed = json.loads(message)
                if isinstance(parsed, dict):
                    payload = parsed
            except json.JSONDecodeError:
                payload = {"type": message}
            if payload.get("type") == "ping":
                await websocket.send_json({"type": "pong", "ts": iso()})
    except WebSocketDisconnect:
        logger.debug("WebSocket 客户端主动断开")
    except Exception:
        logger.exception("WebSocket 连接异常")
    finally:
        await hub.disconnect(websocket)
