"""统一响应格式与分页结构。"""

from __future__ import annotations

from contextvars import ContextVar
from datetime import datetime
from math import ceil
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")

_request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)


def set_request_id(value: str | None) -> None:
    _request_id_ctx.set(value)


def current_request_id() -> str | None:
    return _request_id_ctx.get()


class ApiResponse(BaseModel, Generic[T]):
    code: int = 0
    message: str = "ok"
    data: T | None = None
    request_id: str | None = None
    timestamp: datetime = Field(default_factory=datetime.now)


class PageMeta(BaseModel):
    page: int
    page_size: int
    total: int
    pages: int

    @classmethod
    def build(cls, page: int, page_size: int, total: int) -> "PageMeta":
        return cls(
            page=page,
            page_size=page_size,
            total=total,
            pages=ceil(total / page_size) if page_size else 0,
        )


class PageData(BaseModel, Generic[T]):
    items: list[T]
    meta: PageMeta


def ok(data: T | None = None, request_id: str | None = None) -> dict:
    """返回统一成功响应（字典，便于直接作为 FastAPI 响应体）。"""
    return ApiResponse[T](
        code=0,
        message="ok",
        data=data,
        request_id=request_id or current_request_id(),
    ).model_dump(mode="json")


def fail(
    code: int,
    message: str,
    *,
    details: object = None,
    request_id: str | None = None,
) -> dict:
    """异常处理器使用：返回可直接序列化的字典。"""
    return {
        "code": code,
        "message": message,
        "data": None,
        "details": details,
        "request_id": request_id,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }
