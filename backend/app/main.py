"""FastAPI 应用入口。

启动方式（在 backend 目录）：
    ..\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1 import api_router
from app.core.config import Settings, get_settings
from app.core.container import Container
from app.core.errors import AppError
from app.core.logging import setup_logging
from app.core.responses import current_request_id, fail, set_request_id
from app.core.timeutil import iso

logger = logging.getLogger(__name__)

CONSOLE_FILE = Path(__file__).resolve().parent / "static" / "console.html"


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or get_settings()
    setup_logging(config)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        container = Container.build(config)
        app.state.container = container
        await container.runtime.start()
        logger.info(
            "%s v%s 已启动：http://%s:%d%s（环境=%s）",
            config.app_name,
            config.app_version,
            config.host,
            config.port,
            config.api_prefix,
            config.env,
        )
        try:
            yield
        finally:
            await container.runtime.stop()
            logger.info("服务已关闭")

    app = FastAPI(
        title=config.app_name,
        version=config.app_version,
        description=(
            "前后端分离的工业 AI SOP 监控系统。"
            "SOP 合规判定完全由后端规则引擎执行；模拟数据会显式标注 simulated=true。"
        ),
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Process-Time-Ms"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid4().hex[:12]
        set_request_id(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("未捕获的请求异常：%s %s", request.method, request.url.path)
            raise
        elapsed_ms = (time.perf_counter() - started) * 1000
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.1f}"
        if not request.url.path.endswith("/stream"):
            logger.info(
                "%s %s -> %s (%.1fms) rid=%s",
                request.method,
                request.url.path,
                response.status_code,
                elapsed_ms,
                request_id,
            )
        return response

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        level = logging.WARNING if exc.http_status < 500 else logging.ERROR
        logger.log(level, "%s: %s", exc.__class__.__name__, exc.message, extra={"details": exc.details})
        return JSONResponse(
            status_code=exc.http_status,
            content=fail(
                exc.code,
                exc.message,
                details=exc.details,
                request_id=current_request_id(),
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        details = [
            {"loc": list(err.get("loc", [])), "msg": err.get("msg", ""), "type": err.get("type", "")}
            for err in exc.errors()
        ]
        logger.warning("请求参数校验失败：%s %s %s", request.method, request.url.path, details)
        return JSONResponse(
            status_code=422,
            content=fail(42200, "请求参数不合法", details=details, request_id=current_request_id()),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, exc: StarletteHTTPException):
        mapping = {401: 40100, 403: 40300, 404: 40400, 405: 40500}
        code = mapping.get(exc.status_code, exc.status_code * 100)
        return JSONResponse(
            status_code=exc.status_code,
            content=fail(code, str(exc.detail), request_id=current_request_id()),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception):
        logger.exception("服务器内部错误：%s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content=fail(50000, "服务器内部错误", request_id=current_request_id()),
        )

    app.include_router(api_router, prefix=config.api_prefix)

    @app.get("/", include_in_schema=False)
    def root():
        """后端自托管控制台（无需前端构建产物）。"""
        return _console_response(config)

    @app.get("/console", include_in_schema=False)
    def console():
        return _console_response(config)

    return app


def _console_response(config: Settings):
    if CONSOLE_FILE.exists():
        return FileResponse(
            CONSOLE_FILE,
            media_type="text/html",
            headers={"Cache-Control": "no-store"},
        )
    logger.error("后端控制台页面缺失：%s", CONSOLE_FILE)
    return JSONResponse(
        status_code=503,
        content={
            "code": 50300,
            "message": "后端控制台页面缺失",
            "data": {
                "name": config.app_name,
                "version": config.app_version,
                "docs": "/docs",
                "api": config.api_prefix,
            },
            "timestamp": iso(),
        },
    )


app = create_app()


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    current = get_settings()
    uvicorn.run("app.main:app", host=current.host, port=current.port, reload=False)
