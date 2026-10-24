"""异常事件接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_container
from app.core.container import Container
from app.core.errors import ConflictError, NotFoundError
from app.core.responses import PageData, PageMeta, ok
from app.core.timeutil import iso, to_local_iso
from app.schemas.monitor import EventStatusRequest

router = APIRouter(prefix="/events", tags=["events"])


@router.get("")
def list_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    station_id: str | None = None,
    status: str | None = None,
    severity: str | None = None,
    event_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    include_info: bool = False,
    container: Container = Depends(get_container),
) -> dict:
    items, total = container.event_repo.list_events(
        page=page,
        page_size=page_size,
        station_id=station_id,
        status=status,
        severity=severity,
        event_type=event_type,
        date_from=to_local_iso(date_from),
        date_to=to_local_iso(date_to),
        anomalies_only=not include_info,
    )
    return ok(
        PageData[dict](
            items=items,
            meta=PageMeta.build(page, page_size, total),
        ).model_dump()
    )


@router.post("/{event_id}/status")
def update_event_status(
    event_id: int,
    payload: EventStatusRequest,
    container: Container = Depends(get_container),
) -> dict:
    event = container.event_repo.get(event_id)
    if event is None:
        raise NotFoundError(f"异常事件 {event_id} 不存在")
    if event["status"] == "RESOLVED" and payload.status == "ACKED":
        raise ConflictError("已解决的异常不能回退为已确认")
    container.event_repo.update_status(event_id, payload.status, iso())
    return ok(container.event_repo.get(event_id))
