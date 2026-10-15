"""Datetime helpers.

SQLite returns naive datetimes while PostgreSQL returns aware ones, so every
comparison in the analysis code goes through :func:`as_utc`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime


def as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def hours_between(first: datetime | None, second: datetime | None) -> float | None:
    a, b = as_utc(first), as_utc(second)
    if a is None or b is None:
        return None
    return abs((a - b).total_seconds()) / 3600.0


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        return as_utc(datetime.fromisoformat(text))
    except ValueError:
        pass
    try:
        return as_utc(parsedate_to_datetime(value.strip()))
    except (TypeError, ValueError, OverflowError):
        pass
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z", "%Y-%m-%d"):
        try:
            return as_utc(datetime.strptime(text, fmt))
        except ValueError:
            continue
    return None
