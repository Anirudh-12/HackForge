from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from src.auth import (
    get_current_user,
    home_for,
    set_session_cookie,
    verify_password,
    primary_membership,
    hash_password,
)
from src.context import base_context
from src.db import get_db
from src.templating import templates
from src.models import User, EventMember, TeamMember, Project, AuditLog
from src.queries import default_event, upsert_membership
from src.seed import new_id
from src.timeutil import utcnow

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
def register_form(request: Request, next: str = "", db: Session = Depends(get_db)):
    return templates.TemplateResponse(request=request, name="register.html", context=
        base_context(request=request, event=default_event(db), user=None, role="visitor", next=next, error=None),
    )


@router.post("/register")
def register(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    next: str = Form(""),
    db: Session = Depends(get_db),
):
    email_norm = email.strip().lower()
    existing_user = db.query(User).filter(User.email == email_norm).first()
    if existing_user:
        if existing_user.password_hash is not None:
            return templates.TemplateResponse(request=request, name="register.html", context=
                base_context(
                    request=request,
                    event=default_event(db),
                    user=None,
                    role="visitor",
                    next=next,
                    error="An account with that email already exists.",
                ),
                status_code=400,
            )
        else:
            # Complete registration for invited user
            existing_user.name = name.strip() or email_norm
            existing_user.password_hash = hash_password(password)
            user = existing_user
    else:
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
    dest = next if next and next.startswith("/") else home_for(db, user)
    if dest in ("/", "/login", "/register"):
        dest = home_for(db, user)
    response = RedirectResponse(dest, status_code=303)
    set_session_cookie(response, user.id)
    return response


@router.get("/profile")
def profile(request: Request, user: User | None = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user:
        return RedirectResponse("/login", status_code=303)

    # Compute actual highest role
    pm = primary_membership(db, user)
    user_role = pm.role if pm else "participant"

    # Load projects the user is involved with via team memberships
    user_teams = db.query(TeamMember).filter(TeamMember.user_id == user.id).all()
    team_ids = [tm.team_id for tm in user_teams]
    projects = db.query(Project).filter(Project.team_id.in_(team_ids)).all() if team_ids else []

    # Load hackathons/events user is registered for
    user_memberships = db.query(EventMember).filter(EventMember.user_id == user.id).all()
    registered_events = [m.event for m in user_memberships if m.event]

    # Load user's recent activity logs
    recent_activity = (
        db.query(AuditLog)
        .filter(AuditLog.actor_id == user.id)
        .order_by(AuditLog.created_at.desc())
        .limit(20)
        .all()
    )

    return templates.TemplateResponse(
        request=request,
        name="profile.html",
        context=base_context(
            request=request,
            event=default_event(db),
            user=user,
            role=user_role,
            user_role=user_role,
            projects=projects,
            registered_events=registered_events,
            recent_activity=recent_activity,
            error=None,
        ),
    )


@router.post("/profile")
def update_profile(
    request: Request,
    name: str = Form(None),
    bio: str = Form(""),
    github_url: str = Form(""),
    linkedin_url: str = Form(""),
    skills: str = Form(""),
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not user:
        return RedirectResponse("/login", status_code=303)

    if name and name.strip():
        user.name = name.strip()
    user.bio = bio.strip()
    user.github_url = github_url.strip()
    user.linkedin_url = linkedin_url.strip()
    user.skills = skills.strip()

    db.add(
        AuditLog(
            actor_id=user.id,
            message=f"{user.name} updated profile settings",
            created_at=utcnow(),
        )
    )
    db.commit()

    return RedirectResponse("/profile#settings", status_code=303)

@router.post("/logout")
def logout():
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie("session", path="/")
    return response
