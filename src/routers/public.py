import random
from fastapi import APIRouter, Depends, Request
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from src.auth import get_current_user, membership_for
from src.context import base_context, role_for
from src.db import get_db
from src.templating import templates
from src.models import Event, Project, User, Track, Vote, Comment, TeamMember
from src.queries import default_event, event_tracks, gallery_projects, user_team

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

from fastapi.responses import Response
import hashlib

@router.get("/users/{user_id}/avatar.svg")
def user_avatar(user_id: str):
    # Deterministic Avatar Generator based on user_id
    h = int(hashlib.md5(user_id.encode('utf-8')).hexdigest(), 16)
    
    # Pick a vibrant background color
    bg_colors = [
        "#f43f5e", "#d946ef", "#8b5cf6", "#6366f1", "#3b82f6", 
        "#0ea5e9", "#14b8a6", "#10b981", "#84cc16", "#eab308", "#f97316"
    ]
    bg = bg_colors[h % len(bg_colors)]
    
    # Generate some simple geometric shapes
    shapes = ""
    for i in range(3):
        h = int(hashlib.md5(f"{user_id}_{i}".encode('utf-8')).hexdigest(), 16)
        x = (h % 100)
        y = ((h // 100) % 100)
        r = 10 + ((h // 10000) % 40)
        opacity = 0.2 + ((h // 1000000) % 6) * 0.1
        shapes += f'<circle cx="{x}" cy="{y}" r="{r}" fill="white" opacity="{opacity}" />'
    
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100%" height="100%">
        <rect width="100" height="100" fill="{bg}" />
        {shapes}
    </svg>'''
    return Response(content=svg, media_type="image/svg+xml")


@router.get("/")
def landing(request: Request, db: Session = Depends(get_db), user: User | None = Depends(get_current_user)):
    event = default_event(db)
    return templates.TemplateResponse(request=request, name="landing.html", context=
        base_context(request=request, event=event, user=user, role="visitor"),
    )

@router.get("/events/{event_id}")
def event_landing(event_id: str, request: Request, db: Session = Depends(get_db), user: User | None = Depends(get_current_user)):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
        
    tracks = db.query(Track).filter(Track.event_id == event_id).all()
    
    return templates.TemplateResponse(request=request, name="event_landing.html", context=
        base_context(
            request=request, 
            event=event, 
            user=user, 
            role=role_for(membership_for(db, user, event.id) if user else None),
            tracks=tracks
        ),
    )

@router.post("/events/{event_id}/join")
def join_event(event_id: str, request: Request, db: Session = Depends(get_db), user: User | None = Depends(get_current_user)):
    if not user:
        return RedirectResponse(f"/login?next=/events/{event_id}", status_code=303)
        
    from src.queries import upsert_membership
    upsert_membership(db, event_id, user.id, "participant")
    db.commit()
    
    return RedirectResponse(f"/participant/{event_id}/dashboard", status_code=303)


@router.get("/events/{event_id}/register")
def registration_wizard(event_id: str, request: Request, db: Session = Depends(get_db), user: User | None = Depends(get_current_user)):
    if not user:
        return RedirectResponse(f"/login?next=/events/{event_id}/register", status_code=303)
        
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404)
        
    # Check if already registered
    membership = membership_for(db, user, event.id)
    if membership:
        return RedirectResponse(f"/participant/{event_id}/dashboard", status_code=303)
        
    return templates.TemplateResponse(request=request, name="register_wizard.html", context=
        base_context(request=request, event=event, user=user, role="visitor")
    )


from fastapi import Form

@router.post("/events/{event_id}/register")
def submit_registration_wizard(
    event_id: str, 
    request: Request, 
    skills_offered: str = Form(""),
    looking_for_team: bool = Form(False),
    team_action: str = Form("solo"),
    team_name: str = Form(""),
    invite_token: str = Form(""),
    db: Session = Depends(get_db), 
    user: User | None = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(f"/login?next=/events/{event_id}/register", status_code=303)
        
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404)
    
    # 1. Register User
    from src.queries import upsert_membership
    member = upsert_membership(db, event_id, user.id, "participant")
    member.skills_offered = skills_offered
    member.looking_for_team = looking_for_team
    db.commit()
    
    # 2. Handle Team
    if team_action == "create" and team_name:
        from src.seed import new_id
        from src.models import Team, TeamMember
        team = Team(id=new_id("team"), event_id=event_id, name=team_name)
        db.add(team)
        db.add(TeamMember(team_id=team.id, user_id=user.id))
        db.commit()
        
    elif team_action == "join" and invite_token:
        from src.models import Team, TeamMember
        # Clean token (in case they pasted full URL)
        invite_token = invite_token.split('/')[-1]
        team = db.query(Team).filter_by(event_id=event_id, invite_token=invite_token).first()
        if team:
            existing = db.query(TeamMember).filter_by(team_id=team.id, user_id=user.id).first()
            if not existing and len(team.members) < 4:
                db.add(TeamMember(team_id=team.id, user_id=user.id))
                db.commit()
                    
    import urllib.parse
    query = urllib.parse.urlencode({"msg": "Registration successful! Welcome to the hackathon.", "msg_type": "success"})
    return RedirectResponse(f"/participant/{event_id}/dashboard?{query}", status_code=303)


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
        
        if j_close and now > j_close:
            completed.append(e)
        elif s_open and now < s_open:
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
    sort: str | None = None,
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

    # Ballot Randomization: if sort == "random", shuffle deterministically per session/user
    if sort == "random":
        user_seed = user.id if user else (request.client.host if request.client else "seed")
        rng = random.Random(user_seed)
        shuffled = list(projects)
        rng.shuffle(shuffled)
        projects = shuffled

    events = db.query(Event).order_by(Event.name.asc()).all()
    tracks = db.query(Track).order_by(Track.name.asc()).all()

    # Extract unique technologies from all projects
    all_techs = set()
    for p in db.query(Project.tech_stack).filter(Project.tech_stack.isnot(None)).all():
        for t in p[0].split(','):
            all_techs.add(t.strip())
    techs = sorted(list(t for t in all_techs if t))

    # Real counts
    vote_counts = dict(
        db.query(Vote.project_id, func.count(Vote.id)).group_by(Vote.project_id).all()
    )
    comment_counts = dict(
        db.query(Comment.project_id, func.count(Comment.id)).group_by(Comment.project_id).all()
    )

    # Results hiding logic
    can_see_votes = {}
    for e in events:
        if e.results_published:
            can_see_votes[e.id] = True
        elif user:
            u_role = role_for(membership_for(db, user, e.id))
            can_see_votes[e.id] = u_role in ("organizer", "admin")
        else:
            can_see_votes[e.id] = False

    user_voted_project_ids = set()
    user_team_project_ids = set()
    if user:
        user_voted_project_ids = set(
            p[0] for p in db.query(Vote.project_id).filter(Vote.user_id == user.id).all()
        )
        user_teams = db.query(TeamMember.team_id).filter(TeamMember.user_id == user.id).subquery()
        user_team_project_ids = set(
            p[0] for p in db.query(Project.id).filter(Project.team_id.in_(user_teams)).all()
        )

    current_role = "visitor"
    if user:
        cur_event = default_event(db)
        current_role = role_for(membership_for(db, user, cur_event.id if cur_event else None))

    return templates.TemplateResponse(request=request, name="gallery.html", context=
        base_context(
            request=request,
            event=default_event(db),
            user=user,
            role=current_role,
            projects=projects,
            events=events,
            tracks=tracks,
            techs=techs,
            q=q or "",
            selected_track=track or "",
            selected_event=event_id or "",
            selected_tech=tech or "",
            selected_sort=sort or "",
            vote_counts=vote_counts,
            comment_counts=comment_counts,
            can_see_votes=can_see_votes,
            user_voted_project_ids=user_voted_project_ids,
            user_team_project_ids=user_team_project_ids,
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
    comments = []
    user_voted = False
    is_own_project = False
    can_vote = False
    vote_reason = None
    vote_count = None
    results_hidden = True

    if project:
        if project.team:
            from src.models import TeamMember, User as U
            members = (
                db.query(U)
                .join(TeamMember, TeamMember.user_id == U.id)
                .filter(TeamMember.team_id == project.team_id)
                .all()
            )

        # Comments
        comments = (
            db.query(Comment)
            .options(joinedload(Comment.user))
            .filter(Comment.project_id == project.id)
            .order_by(Comment.created_at.asc())
            .all()
        )

        user_role = role_for(membership_for(db, user, event.id) if (user and event) else None)
        results_hidden = not (event and event.results_published) and user_role not in ("organizer", "admin")

        if not results_hidden:
            vote_count = db.query(Vote).filter(Vote.project_id == project.id).count()

        if user and event:
            u_team = user_team(db, user.id, event.id)
            is_own_project = bool(u_team and u_team.id == project.team_id)

            # user_voted = did user vote for THIS specific project?
            existing_event_vote = (
                db.query(Vote)
                .filter(Vote.user_id == user.id, Vote.event_id == event.id)
                .first()
            )
            user_voted = existing_event_vote is not None and existing_event_vote.project_id == project.id

            if not getattr(event, 'community_voting_enabled', False):
                can_vote = False
                vote_reason = "Community voting is not enabled for this hackathon"
            elif event.results_published:
                can_vote = False
                vote_reason = "Voting is closed (results published)"
            elif is_own_project:
                can_vote = False
                vote_reason = "Cannot vote for your own team's project"
            elif user_role not in ("participant", "admin"):
                can_vote = False
                vote_reason = "Only registered participants can vote"
            else:
                can_vote = True
                if existing_event_vote and existing_event_vote.project_id != project.id:
                    vote_reason = "You already voted for another project — clicking Vote will move your vote here"
        else:
            can_vote = False
            vote_reason = "Log in as a participant to vote"

    return templates.TemplateResponse(request=request, name="project_detail.html", context=
        base_context(
            request=request,
            event=event,
            user=user,
            role=role_for(membership_for(db, user, event.id) if (event and user) else None),
            project=project,
            members=members,
            comments=comments,
            user_voted=user_voted,
            is_own_project=is_own_project,
            can_vote=can_vote,
            vote_reason=vote_reason,
            vote_count=vote_count,
            results_hidden=results_hidden,
        ),
        status_code=200 if project else 404,
    )


from fastapi import Response
from src.avatar import generate_avatar_svg

@router.get("/users/{user_id}/avatar.svg")
def user_avatar(user_id: str, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    svg_content = generate_avatar_svg(user.email)
    return Response(content=svg_content, media_type="image/svg+xml")

@router.get("/vote")
def community_voting_page(
    request: Request,
    event_id: str | None = None,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    if event_id:
        event = db.get(Event, event_id)
    else:
        from sqlalchemy import true
        event = db.query(Event).filter(Event.community_voting_enabled == true()).first()
        if not event:
            event = default_event(db)
    if not event:
        raise HTTPException(status_code=404, detail="No event found")
    projects_q = (
        db.query(Project)
        .options(joinedload(Project.team), joinedload(Project.track))
        .filter(Project.event_id == event.id, Project.is_draft.is_(False), Project.is_disqualified.is_(False))
    )
    import random as _random
    projects = list(projects_q.all())
    rng = _random.Random(user.id if user else "anon")
    rng.shuffle(projects)
    tracks = event_tracks(db, event.id)
    current_role = role_for(membership_for(db, user, event.id) if user else None)
    user_voted_project_id = None
    if user:
        ev = db.query(Vote).filter(Vote.user_id == user.id, Vote.event_id == event.id).first()
        if ev:
            user_voted_project_id = ev.project_id
    user_team_project_ids = set()
    if user:
        user_teams = db.query(TeamMember.team_id).filter(TeamMember.user_id == user.id).subquery()
        user_team_project_ids = set(p[0] for p in db.query(Project.id).filter(Project.team_id.in_(user_teams)).all())
    vote_counts = {}
    if event.results_published or current_role in ("organizer", "admin"):
        vote_counts = dict(db.query(Vote.project_id, func.count(Vote.id)).filter(Vote.event_id == event.id).group_by(Vote.project_id).all())
    from sqlalchemy import true as _true
    all_voting_events = db.query(Event).filter(Event.community_voting_enabled == _true()).all()
    return templates.TemplateResponse(
        request=request,
        name="community_voting.html",
        context=base_context(
            request=request, event=event, user=user, role=current_role,
            projects=projects, tracks=tracks,
            user_voted_project_id=user_voted_project_id,
            user_team_project_ids=user_team_project_ids,
            vote_counts=vote_counts, all_voting_events=all_voting_events,
        ),
    )
