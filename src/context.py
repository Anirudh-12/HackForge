from __future__ import annotations

from src.models import Event, EventMember, User
from src.timeutil import submissions_open


def base_context(
    *,
    event: Event | None = None,
    user: User | None = None,
    role: str | None = None,
    **extra,
) -> dict:
    ctx = {
        "event": event,
        "user": user,
        "role": role or "visitor",
        "submissions_are_open": submissions_open(event) if event else False,
    }
    ctx.update(extra)
    return ctx


def role_for(membership: EventMember | None) -> str:
    return membership.role if membership else "visitor"
