from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session, joinedload

from src.auth import get_current_user, membership_for
from src.context import base_context, role_for
from src.db import get_db
from src.templating import templates
from src.models import Event, Project, User
from src.queries import default_event, event_tracks, gallery_projects

router = APIRouter()

TRACK_COLORS = [
    "#2563eb",
    "#16a34a",
    "#d97706",
    "#dc2626",
    "#7c3aed",
    "#0891b2",
    "#ca8a04",
    "#4b5563",
]


def track_color(track_id: str | None) -> str:
    if not track_id:
        return "#e4e4e4"
    return TRACK_COLORS[sum(ord(c) for c in track_id) % len(TRACK_COLORS)]


@router.get("/")
def landing(request: Request, db: Session = Depends(get_db), user: User | None = Depends(get_current_user)):
    event = default_event(db)
    return templates.TemplateResponse(request=request, name="landing.html", context=
        base_context(request=request, event=event, user=user, role="visitor"),
    )


@router.get("/projects")
def gallery(
    request: Request,
    q: str | None = None,
    track: str | None = None,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    event = default_event(db)
    projects = gallery_projects(db, event.id, q=q, track_id=track) if event else []
    tracks = event_tracks(db, event.id) if event else []
    for project in projects:
        project.color = track_color(project.track_id)
    return templates.TemplateResponse(request=request, name="gallery.html", context=
        base_context(
            request=request,
            event=event,
            user=user,
            role="visitor",
            projects=projects,
            tracks=tracks,
            q=q or "",
            selected_track=track or "",
        ),
    )


@router.get("/projects/{project_id}")
def project_detail(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    project = (
        db.query(Project)
        .options(joinedload(Project.team), joinedload(Project.track), joinedload(Project.event))
        .filter(Project.id == project_id)
        .first()
    )
    event = project.event if project else default_event(db)
    members = []
    if project and project.team:
        members = [m.user for m in project.team.members]
        # load users
        from src.models import TeamMember, User as U

        members = (
            db.query(U)
            .join(TeamMember, TeamMember.user_id == U.id)
            .filter(TeamMember.team_id == project.team_id)
            .all()
        )
    return templates.TemplateResponse(request=request, name="project_detail.html", context=
        base_context(
            request=request,
            event=event,
            user=user,
            role=role_for(membership_for(db, user, event.id) if event else None),
            project=project,
            members=members,
        ),
        status_code=200 if project else 404,
    )
