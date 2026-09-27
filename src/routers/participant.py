from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session, joinedload

from src.auth import get_current_user, membership_for, require_role, set_session_cookie
from src.context import base_context, role_for
from src.db import get_db
from src.templating import templates
from src.models import AuditLog, Event, Project, Team, TeamMember, User
from src.queries import default_event, event_tracks, user_team
from src.seed import new_id
from src.timeutil import submissions_open, utcnow

router = APIRouter()


def _closed_response(request: Request, as_json: bool):
    detail = "submissions are closed"
    if as_json or "application/json" in (request.headers.get("content-type") or ""):
        return JSONResponse({"detail": detail}, status_code=403)
    return JSONResponse({"detail": detail}, status_code=403)


async def _payload(request: Request) -> dict:
    content_type = request.headers.get("content-type") or ""
    if "application/json" in content_type:
        data = await request.json()
        return data if isinstance(data, dict) else {}
    form = await request.form()
    return {key: form.get(key) for key in form}


@router.get("/participant/{event_id}/dashboard")
def participant_dashboard(
    event_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("participant", "organizer", "admin")),
):
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="event not found")
    team = user_team(db, user.id, event_id)
    project = None
    if team:
        project = (
            db.query(Project)
            .options(joinedload(Project.track))
            .filter(Project.team_id == team.id, Project.event_id == event_id)
            .first()
        )
        team = db.query(Team).options(joinedload(Team.members).joinedload(TeamMember.user)).filter(Team.id == team.id).first()
    return templates.TemplateResponse(request=request, name="participant/dashboard.html", context=
        base_context(
            request=request,
            event=event,
            user=user,
            role="participant",
            team=team,
            project=project,
        ),
    )


@router.get("/participant/{event_id}/team")
def team_page(
    event_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("participant", "organizer", "admin")),
    error: str | None = None,
):
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="event not found")
    team = user_team(db, user.id, event_id)
    if team:
        team = db.query(Team).options(joinedload(Team.members).joinedload(TeamMember.user)).filter(Team.id == team.id).first()
    return templates.TemplateResponse(request=request, name="participant/team.html", context=
        base_context(request=request, event=event, user=user, role="participant", team=team, error=error),
    )


@router.post("/participant/{event_id}/team")
def team_action(
    event_id: str,
    request: Request,
    action: str = Form(...),
    name: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("participant", "organizer", "admin")),
):
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="event not found")
    team = user_team(db, user.id, event_id)
    if action == "create":
        if team:
            return RedirectResponse(f"/participant/{event_id}/team", status_code=303)
        team = Team(id=new_id("tm"), event_id=event_id, name=name.strip() or f"{user.name}'s team")
        db.add(team)
        db.flush()
        db.add(TeamMember(team_id=team.id, user_id=user.id))
        db.add(AuditLog(event_id=event_id, actor_id=user.id, message=f"{user.name} created team {team.name}", created_at=utcnow()))
        db.commit()
    elif action == "invite" and team:
        if not team.invite_token:
            team.invite_token = uuid.uuid4().hex
            db.add(AuditLog(event_id=event_id, actor_id=user.id, message=f"{user.name} generated an invite link for {team.name}", created_at=utcnow()))
            db.commit()
    elif action == "leave" and team:
        db.query(TeamMember).filter(TeamMember.team_id == team.id, TeamMember.user_id == user.id).delete()
        db.add(AuditLog(event_id=event_id, actor_id=user.id, message=f"{user.name} left team {team.name}", created_at=utcnow()))
        db.commit()
    return RedirectResponse(f"/participant/{event_id}/team", status_code=303)


@router.get("/join/{token}")
def join_team(
    token: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    team = db.query(Team).filter(Team.invite_token == token).first()
    if team is None:
        raise HTTPException(status_code=404, detail="invite not found")
    if user is None:
        return RedirectResponse(f"/login?next=/join/{token}", status_code=303)
    existing = user_team(db, user.id, team.event_id)
    if existing and existing.id != team.id:
        return templates.TemplateResponse(request=request, name="participant/team.html", context=
            base_context(
                request=request,
                event=team.event,
                user=user,
                role="participant",
                team=existing,
                error="You are already on another team for this event.",
            ),
            status_code=400,
        )
    if existing is None:
        from src.queries import upsert_membership

        upsert_membership(db, team.event_id, user.id, "participant")
        db.add(TeamMember(team_id=team.id, user_id=user.id))
        db.add(AuditLog(event_id=team.event_id, actor_id=user.id, message=f"{user.name} joined team {team.name}", created_at=utcnow()))
        db.commit()
    return RedirectResponse(f"/participant/{team.event_id}/team", status_code=303)


@router.get("/projects/new")
@router.get("/participant/{event_id}/submit")
def submit_form(
    request: Request,
    event_id: str | None = None,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    event = db.get(Event, event_id) if event_id else default_event(db)
    if event is None:
        raise HTTPException(status_code=404, detail="event not found")
    if user is None:
        return RedirectResponse(f"/login?next={request.url.path}", status_code=303)
    team = user_team(db, user.id, event.id)
    project = None
    if team:
        project = db.query(Project).filter(Project.event_id == event.id, Project.team_id == team.id).first()
    return templates.TemplateResponse(request=request, name="participant/submit.html", context=
        base_context(
            request=request,
            event=event,
            user=user,
            role="participant",
            team=team,
            project=project,
            tracks=event_tracks(db, event.id),
            closed=not submissions_open(event),
        ),
    )


@router.post("/projects/new")
@router.post("/participant/{event_id}/submit")
async def submit_project(
    request: Request,
    event_id: str | None = None,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    wants_json = "application/json" in (request.headers.get("content-type") or "")
    if user is None:
        return JSONResponse({"detail": "authentication required"}, status_code=401)

    event = db.get(Event, event_id) if event_id else default_event(db)
    if event is None:
        return JSONResponse({"detail": "event not found"}, status_code=404)

    if not submissions_open(event):
        return _closed_response(request, wants_json)

    payload = await _payload(request)
    team = user_team(db, user.id, event.id)
    if team is None:
        return JSONResponse({"detail": "join or create a team first"}, status_code=400)

    title = (payload.get("title") or "").strip()
    summary = (payload.get("summary") or "").strip()
    repo_url = (payload.get("repo_url") or "").strip() or None
    demo_url = (payload.get("demo_url") or "").strip() or None
    track_id = payload.get("track_id") or payload.get("track")
    is_draft = str(payload.get("action") or "").lower() == "draft" or payload.get("is_draft") in (True, "true", "1", "on")

    project = db.query(Project).filter(Project.event_id == event.id, Project.team_id == team.id).first()
    if project is None:
        project = Project(
            id=new_id("prj"),
            event_id=event.id,
            team_id=team.id,
            title=title or "Untitled",
            summary=summary,
        )
        db.add(project)
    if title:
        project.title = title
    if summary or wants_json:
        project.summary = summary
    if track_id:
        project.track_id = track_id
    if repo_url is not None:
        project.repo_url = repo_url
    if demo_url is not None:
        project.demo_url = demo_url
    project.is_draft = bool(is_draft)
    if not project.is_draft:
        project.submitted_at = utcnow()
    db.add(
        AuditLog(
            event_id=event.id,
            actor_id=user.id,
            message=f"{user.name} {'saved a draft of' if project.is_draft else 'submitted'} {project.title}",
            created_at=utcnow(),
        )
    )
    db.commit()
    if wants_json:
        return JSONResponse({"id": project.id, "title": project.title}, status_code=200)
    return RedirectResponse(f"/participant/{event.id}/dashboard", status_code=303)
