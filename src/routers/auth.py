from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from src.auth import (
    get_current_user,
    home_for,
    set_session_cookie,
    verify_password,
)
from src.context import base_context
from src.db import get_db
from src.templating import templates
from src.models import User
from src.queries import default_event, upsert_membership
from src.seed import new_id
from src.auth import hash_password

router = APIRouter()


@router.get("/login")
def login_form(request: Request, next: str = "/", user: User | None = Depends(get_current_user), db: Session = Depends(get_db)):
    if user:
        return RedirectResponse(home_for(db, user), status_code=303)
    return templates.TemplateResponse(request=request, name="login.html", context=
        base_context(request=request, event=default_event(db), user=None, role="visitor", next=next, error=None),
    )


@router.post("/login")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(""),
    next: str = Form("/"),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == email.strip().lower()).first()
    if user is None:
        user = db.query(User).filter(User.email == email.strip()).first()
    if user is None or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(request=request, name="login.html", context=
            base_context(
                request=request,
                event=default_event(db),
                user=None,
                role="visitor",
                next=next,
                error="Unknown email or password.",
            ),
            status_code=401,
        )
    dest = next if next and next.startswith("/") else home_for(db, user)
    if dest in ("/", "/login"):
        dest = home_for(db, user)
    response = RedirectResponse(dest, status_code=303)
    set_session_cookie(response, user.id)
    return response


@router.get("/register")
def register_form(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(request=request, name="register.html", context=
        base_context(request=request, event=default_event(db), user=None, role="visitor", error=None),
    )


@router.post("/register")
def register(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    email_norm = email.strip().lower()
    if db.query(User).filter(User.email == email_norm).first():
        return templates.TemplateResponse(request=request, name="register.html", context=
            base_context(
                request=request,
                event=default_event(db),
                user=None,
                role="visitor",
                error="An account with that email already exists.",
            ),
            status_code=400,
        )
    user = User(
        id=new_id("usr"),
        email=email_norm,
        name=name.strip() or email_norm,
        password_hash=hash_password(password),
    )
    db.add(user)
    event = default_event(db)
    if event:
        upsert_membership(db, event.id, user.id, "participant")
    db.commit()
    response = RedirectResponse(home_for(db, user), status_code=303)
    set_session_cookie(response, user.id)
    return response


@router.post("/logout")
def logout():
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie("session", path="/")
    return response
