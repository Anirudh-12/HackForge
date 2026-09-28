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


def is_event_completed(event) -> bool:
    if not event:
        return False
    if getattr(event, "results_published", False):
        return True
    now = utcnow()
    j_close = as_utc(getattr(event, "judging_close", None))
    if j_close and now > j_close:
        return True
    e_ends = as_utc(getattr(event, "event_ends", None))
    if e_ends and now > e_ends:
        return True
    return False


def submissions_open(event) -> bool:
    now = utcnow()
    opens = as_utc(event.submissions_open)
    closes = as_utc(event.submissions_close)
    if opens and now < opens:
        return False
    return not (closes and now >= closes)


def registrations_open(event) -> bool:
    if is_event_completed(event):
        return False
    now = utcnow()
    opens = as_utc(getattr(event, "registrations_open", None))
    closes = as_utc(getattr(event, "registrations_close", None))
    if opens and now < opens:
        return False
    return not (closes and now >= closes)
