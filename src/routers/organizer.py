from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from src.auth import require_role
from src.context import base_context
from src.db import get_db
from src.templating import templates
from src.models import AuditLog, Event, Project, Team, Track, User
from src.queries import event_tracks
from src.seed import new_id
from src.timeutil import parse_iso_utc, utcnow

router = APIRouter()


def _dt(value: str | None):
    if not value:
        return None
    if "T" in value and len(value) == 16:
        value = value + ":00Z"
    elif "T" in value and not value.endswith("Z") and "+" not in value:
        value = value + "Z"
    return parse_iso_utc(value)


@router.get("/organizer/events")
def list_events(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("organizer", "admin")),
):
    events = db.query(Event).order_by(Event.name.asc()).all()
    return templates.TemplateResponse(request=request, name="organizer/events.html", context=
        base_context(request=request, event=events[0] if events else None, user=user, role="organizer", events=events),
    )


@router.post("/organizer/events")
def create_event(
    request: Request,
    name: str = Form(...),
    submissions_open: str = Form(""),
    submissions_close: str = Form(""),
    judging_open: str = Form(""),
    judging_close: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("organizer", "admin")),
):
    event = Event(
        id=new_id("evt"),
        name=name.strip(),
        submissions_open=_dt(submissions_open),
        submissions_close=_dt(submissions_close),
        judging_open=_dt(judging_open),
        judging_close=_dt(judging_close),
        results_published=False,
    )
    db.add(event)
    db.flush()
    from src.queries import upsert_membership

    upsert_membership(db, event.id, user.id, "organizer")
    db.add(AuditLog(event_id=event.id, actor_id=user.id, message=f"{user.name} created event {event.name}", created_at=utcnow()))
    db.commit()
    return RedirectResponse(f"/organizer/{event.id}/event", status_code=303)


@router.get("/organizer/{event_id}/dashboard")
def dashboard(
    event_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("organizer", "admin")),
):
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="event not found")
    projects = db.query(Project).filter(Project.event_id == event_id).all()
    submitted = sum(1 for p in projects if not p.is_draft)
    teams = db.query(Team).filter(Team.event_id == event_id).count()
    return templates.TemplateResponse(request=request, name="organizer/dashboard.html", context=
        base_context(
            request=request,
            event=event,
            user=user,
            role="organizer",
            project_count=len(projects),
            submitted_count=submitted,
            draft_count=len(projects) - submitted,
            team_count=teams,
            tracks=event_tracks(db, event_id),
        ),
    )


@router.get("/organizer/{event_id}/event")
def event_settings(
    event_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("organizer", "admin")),
):
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="event not found")
    return templates.TemplateResponse(request=request, name="organizer/event.html", context=
        base_context(request=request, event=event, user=user, role="organizer"),
    )


@router.post("/organizer/{event_id}/event")
def save_event(
    event_id: str,
    name: str = Form(...),
    submissions_open: str = Form(""),
    submissions_close: str = Form(""),
    judging_open: str = Form(""),
    judging_close: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("organizer", "admin")),
):
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="event not found")
    event.name = name.strip()
    event.submissions_open = _dt(submissions_open)
    event.submissions_close = _dt(submissions_close)
    event.judging_open = _dt(judging_open)
    event.judging_close = _dt(judging_close)
    db.add(AuditLog(event_id=event.id, actor_id=user.id, message=f"{user.name} updated event dates for {event.name}", created_at=utcnow()))
    db.commit()
    return RedirectResponse(f"/organizer/{event_id}/event", status_code=303)


@router.get("/organizer/{event_id}/tracks")
def tracks_page(
    event_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("organizer", "admin")),
):
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="event not found")
    return templates.TemplateResponse(request=request, name="organizer/tracks.html", context=
        base_context(request=request, event=event, user=user, role="organizer", tracks=event_tracks(db, event_id)),
    )


@router.post("/organizer/{event_id}/tracks")
def add_track(
    event_id: str,
    name: str = Form(...),
    prize: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("organizer", "admin")),
):
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="event not found")
    db.add(Track(id=new_id("trk"), event_id=event_id, name=name.strip(), prize=prize.strip() or None))
    db.add(AuditLog(event_id=event_id, actor_id=user.id, message=f"{user.name} added track {name.strip()}", created_at=utcnow()))
    db.commit()
    return RedirectResponse(f"/organizer/{event_id}/tracks", status_code=303)
