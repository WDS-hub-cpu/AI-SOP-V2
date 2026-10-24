"""日志初始化：控制台 + 轮转文件 + 内存错误缓冲。"""

from __future__ import annotations

import logging
from collections import deque
from datetime import datetime
from logging.handlers import RotatingFileHandler
from threading import Lock
from typing import Any

from app.core.config import Settings

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


class LogBuffer(logging.Handler):
    """保存最近的 WARNING 及以上日志，供 /system/status 与前端展示。"""

    def __init__(self, capacity: int = 200) -> None:
        super().__init__(level=logging.WARNING)
        self._items: deque[dict[str, Any]] = deque(maxlen=capacity)
        self._lock = Lock()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            item = {
                "time": datetime.fromtimestamp(record.created).isoformat(timespec="seconds"),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }
            with self._lock:
                self._items.append(item)
        except Exception:  # pragma: no cover - 日志处理器不能影响主流程
            self.handleError(record)

    def snapshot(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._items)[-limit:][::-1]


log_buffer = LogBuffer()


def setup_logging(settings: Settings) -> None:
    settings.ensure_directories()
    root = logging.getLogger()
    root.setLevel(settings.log_level.upper())

    if any(getattr(h, "_sop_handler", False) for h in root.handlers):
        return

    formatter = logging.Formatter(_LOG_FORMAT)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console._sop_handler = True  # type: ignore[attr-defined]
    root.addHandler(console)

    file_handler = RotatingFileHandler(
        settings.logs_dir / "backend.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler._sop_handler = True  # type: ignore[attr-defined]
    root.addHandler(file_handler)

    log_buffer.setFormatter(formatter)
    log_buffer._sop_handler = True  # type: ignore[attr-defined]
    root.addHandler(log_buffer)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
