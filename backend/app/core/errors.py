"""统一业务异常。"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """所有可预期业务异常的基类。"""

    code: int = 50000
    http_status: int = 500
    message: str = "服务器内部错误"

    def __init__(
        self,
        message: str | None = None,
        *,
        details: Any = None,
        code: int | None = None,
    ) -> None:
        self.message = message or self.message
        self.details = details
        if code is not None:
            self.code = code
        super().__init__(self.message)


class ValidationError(AppError):
    code = 42200
    http_status = 422
    message = "请求参数不合法"


class NotFoundError(AppError):
    code = 40400
    http_status = 404
    message = "资源不存在"


class ConflictError(AppError):
    code = 40900
    http_status = 409
    message = "当前状态不允许该操作"


class ServiceUnavailableError(AppError):
    code = 50300
    http_status = 503
    message = "依赖服务暂不可用"
