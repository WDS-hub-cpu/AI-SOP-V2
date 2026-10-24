"""时间工具：统一使用带时区的本地时间。"""

from __future__ import annotations

from datetime import datetime, timedelta


def now() -> datetime:
    return datetime.now().astimezone()


def iso(value: datetime | None = None) -> str:
    return (value or now()).isoformat(timespec="seconds")


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def to_local_iso(value: str | None) -> str | None:
    """把任意时区的 ISO 时间统一成本地时区字符串，便于 SQLite 文本比较。"""
    if not value:
        return None
    try:
        return parse_iso(value).astimezone().isoformat(timespec="seconds")
    except ValueError:
        return value


def today_bounds() -> tuple[str, str]:
    start = now().replace(hour=0, minute=0, second=0, microsecond=0)
    return iso(start), iso(start + timedelta(days=1))


def days_ago_bounds(days: int) -> tuple[str, str]:
    start = now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days)
    return iso(start), iso(start + timedelta(days=days + 1))
