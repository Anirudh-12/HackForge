from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def parse_iso_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip().replace("Z", "+00:00")
    return as_utc(datetime.fromisoformat(text))


def submissions_open(event) -> bool:
    now = utcnow()
    opens = as_utc(event.submissions_open)
    closes = as_utc(event.submissions_close)
    if opens and now < opens:
        return False
    return not (closes and now >= closes)


def registrations_open(event) -> bool:
    now = utcnow()
    opens = as_utc(getattr(event, "registrations_open", None))
    closes = as_utc(getattr(event, "registrations_close", None))
    if opens and now < opens:
        return False
    return not (closes and now >= closes)
