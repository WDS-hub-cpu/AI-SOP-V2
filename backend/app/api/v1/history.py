"""历史记录接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_container
from app.core.container import Container
from app.core.errors import NotFoundError
from app.core.responses import PageData, PageMeta, ok
from app.core.timeutil import parse_iso, to_local_iso

router = APIRouter(prefix="/history", tags=["history"])


def _decorate(session: dict) -> dict:
    payload = dict(session)
    payload["compliance"] = (
        None if session.get("compliance") is None else bool(session["compliance"])
    )
    duration = None
    if session.get("finished_at"):
        try:
            duration = (
                parse_iso(session["finished_at"]) - parse_iso(session["started_at"])
            ).total_seconds()
        except ValueError:
            duration = None
    payload["duration_seconds"] = round(duration, 1) if duration is not None else None
    return payload


@router.get("/sessions")
def list_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(15, ge=1, le=100),
    station_id: str | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    container: Container = Depends(get_container),
) -> dict:
    items, total = container.session_repo.list_sessions(
        page=page,
        page_size=page_size,
        station_id=station_id,
        status=status,
        date_from=to_local_iso(date_from),
        date_to=to_local_iso(date_to),
    )
    return ok(
        PageData[dict](
            items=[_decorate(item) for item in items],
            meta=PageMeta.build(page, page_size, total),
        ).model_dump()
    )


@router.get("/sessions/{session_id}")
def session_detail(session_id: str, container: Container = Depends(get_container)) -> dict:
    session = container.session_repo.get(session_id)
    if session is None:
        raise NotFoundError(f"会话 {session_id} 不存在")
    return ok(
        {
            "session": _decorate(session),
            "steps": container.session_repo.step_records(session_id),
            "events": container.event_repo.for_session(session_id),
        }
    )
