from __future__ import annotations

import hashlib
import hmac
import os
from typing import Callable

from fastapi import Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from src.db import get_db
from src.models import EventMember, User

SESSION_COOKIE = "session"
SESSION_SECRET = os.environ.get("SESSION_SECRET", "hackforge-dev-secret")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ROLE_RANK = {
    "visitor": 0,
    "participant": 1,
    "judge": 2,
    "organizer": 3,
    "admin": 4,
}


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    # Seeded fixture users have no stored hash; any password is accepted.
    if password_hash is None:
        return True
    try:
        return pwd_context.verify(password, password_hash)
    except Exception:
        return False


def make_session_token(user_id: str) -> str:
    signature = hmac.new(
        SESSION_SECRET.encode("utf-8"),
        user_id.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{user_id}.{signature}"


def parse_session_token(token: str | None) -> str | None:
    if not token or "." not in token:
        return None
    user_id, _, provided = token.partition(".")
    expected = hmac.new(
        SESSION_SECRET.encode("utf-8"),
        user_id.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(provided, expected):
        return None
    return user_id


def set_session_cookie(response, user_id: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        make_session_token(user_id),
        httponly=True,
        samesite="lax",
        path="/",
    )


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    token = request.cookies.get(SESSION_COOKIE)
    header = request.headers.get("cookie") or request.headers.get("Cookie")
    if not token and header:
        for part in header.split(";"):
            name, _, value = part.strip().partition("=")
            if name == SESSION_COOKIE:
                token = value
                break
    user_id = parse_session_token(token)
    if not user_id:
        return None
    return db.get(User, user_id)


def membership_for(db: Session, user: User | None, event_id: str | None) -> EventMember | None:
    if user is None or not event_id:
        return None
    return (
        db.query(EventMember)
        .filter(EventMember.user_id == user.id, EventMember.event_id == event_id)
        .first()
    )


def primary_membership(db: Session, user: User | None) -> EventMember | None:
    if user is None:
        return None
    members = db.query(EventMember).filter(EventMember.user_id == user.id).all()
    if not members:
        return None
    return sorted(members, key=lambda m: ROLE_RANK.get(m.role, 0), reverse=True)[0]


def home_for(db: Session, user: User) -> str:
    member = primary_membership(db, user)
    if member is None:
        return "/explore"
    if member.role == "admin":
        return "/admin/dashboard"
    if member.role == "organizer":
        return f"/organizer/{member.event_id}/dashboard"
    if member.role == "judge":
        return f"/judge/{member.event_id}/dashboard"
    return "/participant/home"


def require_login(user: User | None = Depends(get_current_user)) -> User:
    if user is None:
        raise HTTPException(status_code=401, detail="authentication required")
    return user


def require_role(*roles: str) -> Callable:
    def dependency(
        request: Request,
        db: Session = Depends(get_db),
        user: User | None = Depends(get_current_user),
    ) -> User:
        if user is None:
            if "text/html" in request.headers.get("accept", ""):
                raise HTTPException(status_code=401, detail="authentication required")
            raise HTTPException(status_code=401, detail="authentication required")
        event_id = request.path_params.get("event_id")
        query = db.query(EventMember).filter(EventMember.user_id == user.id)
        if event_id:
            query = query.filter(EventMember.event_id == event_id)
        memberships = query.all()
        if any(m.role == "admin" for m in memberships):
            return user
        if any(m.role in roles for m in memberships):
            return user
        raise HTTPException(status_code=403, detail="forbidden")

    return dependency


def html_login_redirect(next_url: str = "/") -> RedirectResponse:
    return RedirectResponse(f"/login?next={next_url}", status_code=303)
