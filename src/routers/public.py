from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session, joinedload

from src.auth import get_current_user, membership_for
from src.context import base_context, role_for
from src.db import get_db
from src.templating import templates
from src.models import Event, Project, User, Track
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


@router.get("/explore")
def explore(request: Request, db: Session = Depends(get_db), user: User | None = Depends(get_current_user)):
    from src.timeutil import utcnow, as_utc
    events = db.query(Event).all()
    now = utcnow()
    
    upcoming = []
    ongoing = []
    completed = []
    
    for e in events:
        if e.results_published:
            completed.append(e)
            continue
            
        j_close = as_utc(e.judging_close)
        s_open = as_utc(e.submissions_open)
        
        if s_open and now < s_open:
            upcoming.append(e)
        else:
            ongoing.append(e)
            
    # Also fetch judge invitations if user is logged in
    invitations = []
    if user:
        from src.models import JudgeInvitation
        invitations = db.query(JudgeInvitation).filter_by(email=user.email, status="pending").all()
        
    return templates.TemplateResponse(request=request, name="explore.html", context=
        base_context(
            request=request,
            event=default_event(db),
            user=user,
            role="participant" if user else "visitor",
            upcoming=upcoming,
            ongoing=ongoing,
            completed=completed,
            invitations=invitations
        ),
    )


from fastapi.responses import RedirectResponse
from fastapi import HTTPException

@router.post("/invitations/{invitation_id}/accept")
def accept_invitation(invitation_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from src.models import JudgeInvitation, JudgeTrack
    from src.queries import upsert_membership
    if not user:
        raise HTTPException(status_code=401)
        
    inv = db.query(JudgeInvitation).filter_by(id=invitation_id, email=user.email).first()
    if not inv or inv.status != "pending":
        raise HTTPException(status_code=404)
        
    inv.status = "accepted"
    upsert_membership(db, inv.event_id, user.id, "judge")
    
    if inv.track_ids:
        for t_id in inv.track_ids.split(","):
            existing = db.query(JudgeTrack).filter_by(event_id=inv.event_id, judge_id=user.id, track_id=t_id).first()
            if not existing:
                db.add(JudgeTrack(event_id=inv.event_id, judge_id=user.id, track_id=t_id))
                
    db.commit()
    return RedirectResponse(f"/judge/{inv.event_id}/dashboard", status_code=303)


@router.post("/invitations/{invitation_id}/decline")
def decline_invitation(invitation_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from src.models import JudgeInvitation
    if not user:
        raise HTTPException(status_code=401)
        
    inv = db.query(JudgeInvitation).filter_by(id=invitation_id, email=user.email).first()
    if not inv or inv.status != "pending":
        raise HTTPException(status_code=404)
        
    inv.status = "declined"
    db.commit()
    return RedirectResponse("/explore", status_code=303)



@router.get("/projects")
def gallery(
    request: Request,
    q: str | None = None,
    track: str | None = None,
    event_id: str | None = None,
    tech: str | None = None,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    query = (
        db.query(Project)
        .options(joinedload(Project.team), joinedload(Project.track), joinedload(Project.event))
        .filter(Project.is_draft.is_(False), Project.is_disqualified.is_(False))
    )
    if event_id:
        query = query.filter(Project.event_id == event_id)
    if q:
        like = f"%{q}%"
        query = query.filter(Project.title.ilike(like) | Project.summary.ilike(like))
    if track:
        query = query.filter(Project.track_id == track)
    if tech:
        like_tech = f"%{tech}%"
        query = query.filter(Project.tech_stack.ilike(like_tech))

    projects = query.order_by(Project.title.asc()).all()
    
    events = db.query(Event).order_by(Event.name.asc()).all()
    tracks = db.query(Track).order_by(Track.name.asc()).all()

    # Extract unique technologies from all projects
    all_techs = set()
    for p in db.query(Project.tech_stack).filter(Project.tech_stack.isnot(None)).all():
        for t in p[0].split(','):
            all_techs.add(t.strip())
    techs = sorted(list(t for t in all_techs if t))

    return templates.TemplateResponse(request=request, name="gallery.html", context=
        base_context(
            request=request,
            event=default_event(db),
            user=user,
            role="visitor",
            projects=projects,
            events=events,
            tracks=tracks,
            techs=techs,
            q=q or "",
            selected_track=track or "",
            selected_event=event_id or "",
            selected_tech=tech or "",
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
