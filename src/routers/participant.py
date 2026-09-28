from __future__ import annotations

import urllib.parse
import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from src.auth import get_current_user, membership_for, require_role, set_session_cookie
from src.context import base_context, role_for
from src.db import get_db
from src.models import (
    AuditLog,
    Event,
    EventMember,
    Notification,
    Project,
    Team,
    TeamJoinRequest,
    TeamMember,
    User,
)
from src.queries import default_event, event_tracks, user_team
from src.seed import new_id
from src.templating import templates
from src.timeutil import as_utc, is_event_completed, submissions_open, utcnow

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


from src.models import EventMember


@router.get("/participant/home")
def participant_home(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not user:
        return RedirectResponse("/login", status_code=303)

    now = utcnow()

    # 1. Registered Events
    memberships = (
        db.query(EventMember)
        .filter(EventMember.user_id == user.id, EventMember.role == "participant")
        .all()
    )
    registered_event_ids = [m.event_id for m in memberships]

    registered_events = (
        db.query(Event).filter(Event.id.in_(registered_event_ids)).all()
        if registered_event_ids
        else []
    )

    # Associate team/project status for each registered event
    event_statuses = []
    total_submissions = 0
    upcoming_deadlines = []

    for event in registered_events:
        team = user_team(db, user.id, event.id)
        project = None
        if team:
            project = db.query(Project).filter(Project.team_id == team.id).first()

        status = "Registered"
        if project:
            total_submissions += 1
            if project.is_draft:
                status = "Submission in progress"
            else:
                status = "Submitted"

        event_statuses.append(
            {
                "event": event,
                "status": status,
                "project_id": project.id if project else None,
            }
        )

        # Deadlines
        s_close = as_utc(event.submissions_close) if event.submissions_close else None
        if s_close and s_close > now:
            upcoming_deadlines.append(event)

    upcoming_deadlines.sort(key=lambda e: as_utc(e.submissions_close))

    # 2. Recommendations (Events not registered in, that haven't closed yet)
    recommended_events = []
    if registered_event_ids:
        recommended_events = (
            db.query(Event).filter(Event.id.not_in(registered_event_ids)).all()
        )
    else:
        recommended_events = db.query(Event).all()

    valid_recs = []
    for e in recommended_events:
        c = as_utc(e.submissions_close) if e.submissions_close else None
        if not c or c > now:
            valid_recs.append(e)

    # 3. Recent Activity (Audit logs involving user or their teams)
    # Simple approach: fetch audit logs where actor_id == user.id
    activities = (
        db.query(AuditLog)
        .filter(AuditLog.actor_id == user.id)
        .order_by(AuditLog.created_at.desc())
        .limit(5)
        .all()
    )

    return templates.TemplateResponse(
        request=request,
        name="participant/dashboard_new.html",
        context=base_context(
            request=request,
            event=default_event(db),
            user=user,
            role="participant",
            event_statuses=event_statuses,
            total_submissions=total_submissions,
            total_registrations=len(registered_events),
            upcoming_deadlines=upcoming_deadlines,
            recommendations=valid_recs[:3],
            activities=activities,
        ),
    )


@router.get("/participant/registrations")
def participant_registrations(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not user:
        return RedirectResponse(
            "/login?next=/participant/registrations", status_code=303
        )

    now = utcnow()

    # Fetch all event memberships for participant
    memberships = (
        db.query(EventMember)
        .options(joinedload(EventMember.event).joinedload(Event.tracks))
        .filter(EventMember.user_id == user.id, EventMember.role == "participant")
        .all()
    )

    registrations = []
    active_count = 0
    upcoming_count = 0
    completed_count = 0
    submitted_count = 0
    teams_count = 0

    for m in memberships:
        event = m.event
        if not event:
            continue

        team = user_team(db, user.id, event.id)
        project = None
        team_members = []
        if team:
            teams_count += 1
            project = (
                db.query(Project)
                .options(joinedload(Project.track))
                .filter(Project.team_id == team.id)
                .first()
            )
            tm_records = (
                db.query(TeamMember)
                .options(joinedload(TeamMember.user))
                .filter(TeamMember.team_id == team.id)
                .all()
            )
            team_members = [tm.user for tm in tm_records if tm.user]

        # Determine timeline status
        j_close = as_utc(event.judging_close) if event.judging_close else None
        s_open = as_utc(event.submissions_open) if event.submissions_open else None
        s_close = as_utc(event.submissions_close) if event.submissions_close else None

        if event.results_published or (j_close and now > j_close):
            time_status = "completed"
            time_status_label = "Completed"
            status_color = "#6b7280"
            completed_count += 1
        elif s_open and now < s_open:
            time_status = "upcoming"
            time_status_label = "Upcoming"
            status_color = "#10b981"
            upcoming_count += 1
        else:
            time_status = "ongoing"
            time_status_label = "Ongoing"
            status_color = "var(--primary)"
            active_count += 1

        submission_status = "Not Started"
        if project:
            if project.is_draft:
                submission_status = "Submission in progress"
            else:
                submission_status = "Submitted"
                submitted_count += 1

        registrations.append(
            {
                "event": event,
                "membership": m,
                "team": team,
                "team_members": team_members,
                "project": project,
                "time_status": time_status,
                "time_status_label": time_status_label,
                "status_color": status_color,
                "submission_status": submission_status,
            }
        )

    # Sort registrations: ongoing first, upcoming second, completed last
    status_order = {"ongoing": 0, "upcoming": 1, "completed": 2}
    registrations.sort(
        key=lambda r: (status_order.get(r["time_status"], 3), r["event"].name)
    )

    return templates.TemplateResponse(
        request=request,
        name="participant/registrations.html",
        context=base_context(
            request=request,
            event=default_event(db),
            user=user,
            role="participant",
            registrations=registrations,
            total_registrations=len(registrations),
            active_count=active_count,
            upcoming_count=upcoming_count,
            completed_count=completed_count,
            submitted_count=submitted_count,
            teams_count=teams_count,
        ),
    )


@router.get("/registrations")
def registrations_redirect():
    return RedirectResponse("/participant/registrations", status_code=303)


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
        team = (
            db.query(Team)
            .options(joinedload(Team.members).joinedload(TeamMember.user))
            .filter(Team.id == team.id)
            .first()
        )
    return templates.TemplateResponse(
        request=request,
        name="participant/dashboard.html",
        context=base_context(
            request=request,
            event=event,
            user=user,
            role="participant",
            team=team,
            project=project,
        ),
    )


@router.get("/participant/{event_id}/matchmaking")
def matchmaking_page(
    event_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("participant", "organizer", "admin")),
):
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="event not found")

    team = user_team(db, user.id, event_id)
    if team:
        team = (
            db.query(Team)
            .options(
                joinedload(Team.members).joinedload(TeamMember.user),
                joinedload(Team.leader),
            )
            .filter(Team.id == team.id)
            .first()
        )

    membership = (
        db.query(EventMember)
        .filter(EventMember.user_id == user.id, EventMember.event_id == event_id)
        .first()
    )

    # Solo users looking for team
    solo_users = (
        db.query(EventMember)
        .options(joinedload(EventMember.user))
        .filter(
            EventMember.event_id == event_id,
            EventMember.looking_for_team == True,
            EventMember.user_id != user.id,
        )
        .all()
    )

    # Teams looking for members (Teams with < 4 members)
    all_teams = (
        db.query(Team)
        .options(
            joinedload(Team.members).joinedload(TeamMember.user),
            joinedload(Team.leader),
        )
        .filter(Team.event_id == event_id)
        .all()
    )
    open_teams = [
        t for t in all_teams if len(t.members) < 4 and (not team or t.id != team.id)
    ]

    # Incoming join requests for team leader
    incoming_join_requests = []
    is_team_leader = False
    if team:
        leader = team.get_leader(db)
        if leader and leader.id == user.id:
            is_team_leader = True
            incoming_join_requests = (
                db.query(TeamJoinRequest)
                .options(joinedload(TeamJoinRequest.user))
                .filter(
                    TeamJoinRequest.team_id == team.id,
                    TeamJoinRequest.status == "pending",
                )
                .order_by(TeamJoinRequest.created_at.desc())
                .all()
            )

    # My sent requests for applicant
    my_sent_requests = []
    requested_team_ids = set()
    if not team:
        my_sent_requests = (
            db.query(TeamJoinRequest)
            .options(joinedload(TeamJoinRequest.team).joinedload(Team.leader))
            .filter(
                TeamJoinRequest.user_id == user.id,
                TeamJoinRequest.event_id == event_id,
                TeamJoinRequest.status == "pending",
            )
            .order_by(TeamJoinRequest.created_at.desc())
            .all()
        )
        requested_team_ids = {r.team_id for r in my_sent_requests}

    event_completed = is_event_completed(event)
    return templates.TemplateResponse(
        request=request,
        name="participant/matchmaking.html",
        context=base_context(
            request=request,
            event=event,
            user=user,
            role="participant",
            team=team,
            membership=membership,
            solo_users=solo_users,
            open_teams=open_teams,
            incoming_join_requests=incoming_join_requests,
            is_team_leader=is_team_leader,
            my_sent_requests=my_sent_requests,
            requested_team_ids=requested_team_ids,
            event_completed=event_completed,
        ),
    )


@router.post("/participant/{event_id}/matchmaking")
def update_matchmaking(
    event_id: str,
    request: Request,
    looking_for_team: bool = Form(False),
    skills_offered: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("participant", "organizer", "admin")),
):
    membership = (
        db.query(EventMember)
        .filter(EventMember.user_id == user.id, EventMember.event_id == event_id)
        .first()
    )
    if membership:
        membership.looking_for_team = looking_for_team
        membership.skills_offered = skills_offered
        db.commit()
    return RedirectResponse(f"/participant/{event_id}/matchmaking", status_code=303)


@router.post("/participant/{event_id}/invite_user")
def invite_user_to_team(
    event_id: str,
    target_user_id: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("participant", "organizer", "admin")),
):
    event = db.get(Event, event_id)
    if not event or is_event_completed(event):
        query = urllib.parse.urlencode(
            {"msg": "Cannot invite users: this hackathon has concluded.", "msg_type": "error"}
        )
        return RedirectResponse(f"/participant/{event_id}/matchmaking?{query}", status_code=303)
    team = user_team(db, user.id, event_id)
    if not team:
        return RedirectResponse(f"/participant/{event_id}/matchmaking", status_code=303)

    # Ensure team has an invite token
    if not team.invite_token:
        team.invite_token = uuid.uuid4().hex

    db.add(
        Notification(
            id=new_id("notif"),
            user_id=target_user_id,
            message=f"{user.name} has invited you to join their team '{team.name}'.",
            action_link=f"/join/{team.invite_token}",
        )
    )
    db.commit()

    return RedirectResponse(f"/participant/{event_id}/matchmaking", status_code=303)


@router.post("/participant/{event_id}/request_join")
def request_join_team(
    event_id: str,
    request: Request,
    target_team_id: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("participant", "organizer", "admin")),
):
    is_ajax = request.headers.get(
        "x-requested-with"
    ) == "XMLHttpRequest" or "application/json" in request.headers.get("accept", "")

    event = db.get(Event, event_id)
    if event is None:
        if is_ajax:
            return JSONResponse(
                status_code=404, content={"ok": False, "error": "Event not found."}
            )
        raise HTTPException(status_code=404, detail="Event not found.")

    if is_event_completed(event):
        msg = "This hackathon has concluded. Team formation and join requests are closed."
        if is_ajax:
            return JSONResponse(status_code=400, content={"ok": False, "error": msg})
        query = urllib.parse.urlencode({"msg": msg, "msg_type": "error"})
        return RedirectResponse(
            f"/participant/{event_id}/matchmaking?{query}", status_code=303
        )

    team = user_team(db, user.id, event_id)
    if team:
        msg = "You are already a member of a team for this hackathon."
        if is_ajax:
            return JSONResponse(status_code=400, content={"ok": False, "error": msg})
        query = urllib.parse.urlencode({"msg": msg, "msg_type": "error"})
        return RedirectResponse(
            f"/participant/{event_id}/matchmaking?{query}", status_code=303
        )

    target_team = (
        db.query(Team)
        .options(joinedload(Team.members), joinedload(Team.leader))
        .filter_by(id=target_team_id, event_id=event_id)
        .first()
    )
    if not target_team:
        msg = "The requested team could not be found."
        if is_ajax:
            return JSONResponse(status_code=404, content={"ok": False, "error": msg})
        query = urllib.parse.urlencode({"msg": msg, "msg_type": "error"})
        return RedirectResponse(
            f"/participant/{event_id}/matchmaking?{query}", status_code=303
        )

    if len(target_team.members) >= 4:
        msg = f"Team '{target_team.name}' is already full (4/4 members)."
        if is_ajax:
            return JSONResponse(status_code=400, content={"ok": False, "error": msg})
        query = urllib.parse.urlencode({"msg": msg, "msg_type": "error"})
        return RedirectResponse(
            f"/participant/{event_id}/matchmaking?{query}", status_code=303
        )

    leader = target_team.get_leader(db)
    leader_name = leader.name if leader else "the team leader"

    # Upsert or check existing TeamJoinRequest
    existing_req = (
        db.query(TeamJoinRequest)
        .filter_by(team_id=target_team.id, user_id=user.id)
        .first()
    )
    if existing_req and existing_req.status == "pending":
        msg = f"You have already requested to join '{target_team.name}'. The team leader has been notified."
        if is_ajax:
            return JSONResponse(
                content={
                    "ok": True,
                    "message": msg,
                    "status": "pending",
                    "team_id": target_team.id,
                    "team_name": target_team.name,
                    "leader_name": leader_name,
                }
            )
        query = urllib.parse.urlencode({"msg": msg, "msg_type": "info"})
        return RedirectResponse(
            f"/participant/{event_id}/matchmaking?{query}", status_code=303
        )
    elif existing_req:
        existing_req.status = "pending"
        existing_req.created_at = utcnow()
        req_id = existing_req.id
    else:
        req_id = new_id("treq")
        db.add(
            TeamJoinRequest(
                id=req_id,
                team_id=target_team.id,
                user_id=user.id,
                event_id=event_id,
                status="pending",
                created_at=utcnow(),
            )
        )

    # Send in-app notification to the team leader
    if leader:
        db.add(
            Notification(
                id=new_id("notif"),
                user_id=leader.id,
                message=f"{user.name} ({user.email}) has requested to join your team '{target_team.name}'.",
                action_link=f"/participant/{event_id}/matchmaking",
            )
        )

    # Send confirmation notification to the applicant
    db.add(
        Notification(
            id=new_id("notif"),
            user_id=user.id,
            message=f"You requested to join '{target_team.name}'. Request delivered to {leader_name}.",
            action_link=f"/participant/{event_id}/matchmaking",
        )
    )

    db.add(
        AuditLog(
            event_id=event_id,
            actor_id=user.id,
            message=f"{user.name} requested to join team {target_team.name}",
            created_at=utcnow(),
        )
    )
    db.commit()

    success_msg = f"Join request sent to {leader_name}! You will be notified when they review your request."
    if is_ajax:
        return JSONResponse(
            content={
                "ok": True,
                "message": success_msg,
                "status": "pending",
                "team_id": target_team.id,
                "team_name": target_team.name,
                "leader_name": leader_name,
                "request_id": req_id,
            }
        )
    query = urllib.parse.urlencode({"msg": success_msg, "msg_type": "success"})
    return RedirectResponse(
        f"/participant/{event_id}/matchmaking?{query}", status_code=303
    )


@router.post("/participant/{event_id}/requests/{request_id}/accept")
def accept_join_request(
    event_id: str,
    request_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("participant", "organizer", "admin")),
):
    join_req = (
        db.query(TeamJoinRequest)
        .options(joinedload(TeamJoinRequest.team), joinedload(TeamJoinRequest.user))
        .filter_by(id=request_id, event_id=event_id)
        .first()
    )
    if not join_req or join_req.status != "pending":
        query = urllib.parse.urlencode(
            {"msg": "Join request not found or already processed.", "msg_type": "error"}
        )
        return RedirectResponse(
            f"/participant/{event_id}/matchmaking?{query}", status_code=303
        )

    event = db.get(Event, event_id)
    if is_event_completed(event):
        query = urllib.parse.urlencode(
            {"msg": "Cannot accept requests: this hackathon has concluded.", "msg_type": "error"}
        )
        return RedirectResponse(
            f"/participant/{event_id}/matchmaking?{query}", status_code=303
        )

    target_team = join_req.team
    leader = target_team.get_leader(db)
    if leader and leader.id != user.id:
        member_check = (
            db.query(TeamMember)
            .filter_by(team_id=target_team.id, user_id=user.id)
            .first()
        )
        if not member_check:
            raise HTTPException(
                status_code=403,
                detail="Only team leaders or members can accept requests.",
            )

    current_count = db.query(TeamMember).filter_by(team_id=target_team.id).count()
    if current_count >= 4:
        query = urllib.parse.urlencode(
            {
                "msg": "Cannot accept request: your team is already full (4/4).",
                "msg_type": "error",
            }
        )
        return RedirectResponse(
            f"/participant/{event_id}/matchmaking?{query}", status_code=303
        )

    applicant_team = user_team(db, join_req.user_id, event_id)
    if applicant_team:
        join_req.status = "cancelled"
        db.commit()
        query = urllib.parse.urlencode(
            {
                "msg": f"{join_req.user.name} has already joined another team.",
                "msg_type": "warning",
            }
        )
        return RedirectResponse(
            f"/participant/{event_id}/matchmaking?{query}", status_code=303
        )

    db.add(TeamMember(team_id=target_team.id, user_id=join_req.user_id))
    join_req.status = "accepted"

    # Cancel other pending join requests from this applicant in this event
    db.query(TeamJoinRequest).filter(
        TeamJoinRequest.user_id == join_req.user_id,
        TeamJoinRequest.event_id == event_id,
        TeamJoinRequest.status == "pending",
    ).update({"status": "cancelled"})

    # Send notification to applicant
    db.add(
        Notification(
            id=new_id("notif"),
            user_id=join_req.user_id,
            message=f"🎉 You have been accepted into team '{target_team.name}'!",
            action_link=f"/participant/{event_id}/team",
        )
    )

    db.add(
        AuditLog(
            event_id=event_id,
            actor_id=user.id,
            message=f"{user.name} accepted {join_req.user.name} into team {target_team.name}",
            created_at=utcnow(),
        )
    )
    db.commit()

    query = urllib.parse.urlencode(
        {
            "msg": f"Welcome {join_req.user.name} to {target_team.name}!",
            "msg_type": "success",
        }
    )
    return RedirectResponse(
        f"/participant/{event_id}/matchmaking?{query}", status_code=303
    )


@router.post("/participant/{event_id}/requests/{request_id}/decline")
def decline_join_request(
    event_id: str,
    request_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("participant", "organizer", "admin")),
):
    join_req = (
        db.query(TeamJoinRequest)
        .options(joinedload(TeamJoinRequest.team), joinedload(TeamJoinRequest.user))
        .filter_by(id=request_id, event_id=event_id)
        .first()
    )
    if not join_req or join_req.status != "pending":
        query = urllib.parse.urlencode(
            {"msg": "Join request not found or already processed.", "msg_type": "error"}
        )
        return RedirectResponse(
            f"/participant/{event_id}/matchmaking?{query}", status_code=303
        )

    target_team = join_req.team
    leader = target_team.get_leader(db)
    if leader and leader.id != user.id:
        member_check = (
            db.query(TeamMember)
            .filter_by(team_id=target_team.id, user_id=user.id)
            .first()
        )
        if not member_check:
            raise HTTPException(
                status_code=403,
                detail="Only team leaders or members can decline requests.",
            )

    join_req.status = "declined"

    db.add(
        Notification(
            id=new_id("notif"),
            user_id=join_req.user_id,
            message=f"Your request to join team '{target_team.name}' was declined.",
            action_link=f"/participant/{event_id}/matchmaking",
        )
    )

    db.add(
        AuditLog(
            event_id=event_id,
            actor_id=user.id,
            message=f"{user.name} declined join request from {join_req.user.name} for team {target_team.name}",
            created_at=utcnow(),
        )
    )
    db.commit()

    query = urllib.parse.urlencode(
        {"msg": f"Declined request from {join_req.user.name}.", "msg_type": "info"}
    )
    return RedirectResponse(
        f"/participant/{event_id}/matchmaking?{query}", status_code=303
    )


@router.post("/participant/{event_id}/requests/{request_id}/cancel")
@router.post("/participant/{event_id}/cancel_request")
def cancel_join_request(
    event_id: str,
    request: Request,
    request_id: str | None = None,
    target_team_id: str = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("participant", "organizer", "admin")),
):
    query_filter = [
        TeamJoinRequest.user_id == user.id,
        TeamJoinRequest.status == "pending",
    ]
    if request_id:
        query_filter.append(TeamJoinRequest.id == request_id)
    elif target_team_id:
        query_filter.append(TeamJoinRequest.team_id == target_team_id)

    join_req = db.query(TeamJoinRequest).filter(*query_filter).first()
    if join_req:
        join_req.status = "cancelled"
        db.commit()
        msg = "Join request cancelled."
    else:
        msg = "Request not found."

    if request.headers.get(
        "x-requested-with"
    ) == "XMLHttpRequest" or "application/json" in request.headers.get("accept", ""):
        return JSONResponse(content={"ok": True, "message": msg})

    query = urllib.parse.urlencode({"msg": msg, "msg_type": "info"})
    return RedirectResponse(
        f"/participant/{event_id}/matchmaking?{query}", status_code=303
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
    incoming_requests = []
    is_team_leader = False
    if team:
        team = (
            db.query(Team)
            .options(
                joinedload(Team.members).joinedload(TeamMember.user),
                joinedload(Team.leader),
            )
            .filter(Team.id == team.id)
            .first()
        )
        leader = team.get_leader(db)
        if leader and leader.id == user.id:
            is_team_leader = True
            incoming_requests = (
                db.query(TeamJoinRequest)
                .options(joinedload(TeamJoinRequest.user))
                .filter(
                    TeamJoinRequest.team_id == team.id,
                    TeamJoinRequest.status == "pending",
                )
                .order_by(TeamJoinRequest.created_at.desc())
                .all()
            )

    return templates.TemplateResponse(
        request=request,
        name="participant/team.html",
        context=base_context(
            request=request,
            event=event,
            user=user,
            role="participant",
            team=team,
            incoming_requests=incoming_requests,
            is_team_leader=is_team_leader,
            error=error,
            event_completed=is_event_completed(event),
        ),
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
    now = utcnow()

    # Enforce timing rule: Team formation is only allowed before event starts and while not completed
    if action in ("create", "invite"):
        if (event.event_starts and now >= as_utc(event.event_starts)) or is_event_completed(event):
            return templates.TemplateResponse(
                request=request,
                name="participant/team.html",
                context=base_context(
                    request=request,
                    event=event,
                    user=user,
                    role="participant",
                    team=team,
                    event_completed=is_event_completed(event),
                    error="Team formation closed because this hackathon has already started or concluded. You can no longer create teams or generate invite links.",
                ),
                status_code=400,
            )

    if action == "create":
        if team:
            return RedirectResponse(f"/participant/{event_id}/team", status_code=303)
        tname = name.strip() or f"{user.name}'s team"
        existing_team = db.query(Team).filter(Team.event_id == event_id, func.lower(Team.name) == tname.lower()).first()
        if existing_team:
            return templates.TemplateResponse(
                request=request,
                name="participant/team.html",
                context=base_context(
                    request=request,
                    event=event,
                    user=user,
                    role="participant",
                    team=team,
                    error=f"A team named '{tname}' already exists in this hackathon. Please choose a different name.",
                ),
                status_code=400,
            )
        team = Team(
            id=new_id("tm"),
            event_id=event_id,
            name=tname,
            leader_id=user.id,
        )
        db.add(team)
        db.flush()
        db.add(TeamMember(team_id=team.id, user_id=user.id))
        db.add(
            AuditLog(
                event_id=event_id,
                actor_id=user.id,
                message=f"{user.name} created team {team.name}",
                created_at=utcnow(),
            )
        )
        db.commit()
    elif action == "invite" and team:
        if not team.invite_token:
            team.invite_token = uuid.uuid4().hex
            db.add(
                AuditLog(
                    event_id=event_id,
                    actor_id=user.id,
                    message=f"{user.name} generated an invite link for {team.name}",
                    created_at=utcnow(),
                )
            )
            db.commit()
    elif action == "leave" and team:
        db.query(TeamMember).filter(
            TeamMember.team_id == team.id, TeamMember.user_id == user.id
        ).delete()
        db.add(
            AuditLog(
                event_id=event_id,
                actor_id=user.id,
                message=f"{user.name} left team {team.name}",
                created_at=utcnow(),
            )
        )
        if team.leader_id == user.id:
            next_member = (
                db.query(TeamMember)
                .filter_by(team_id=team.id)
                .order_by(TeamMember.id.asc())
                .first()
            )
            team.leader_id = next_member.user_id if next_member else None
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
        return templates.TemplateResponse(
            request=request,
            name="participant/team.html",
            context=base_context(
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
        event = team.event
        now = utcnow()

        # Enforce timing rule: team joining closed after event start or once completed
        if (event.event_starts and now >= as_utc(event.event_starts)) or is_event_completed(event):
            return templates.TemplateResponse(
                request=request,
                name="participant/team.html",
                context=base_context(
                    request=request,
                    event=event,
                    user=user,
                    role="participant",
                    team=None,
                    event_completed=is_event_completed(event),
                    error="Team formation closed because this hackathon has already started or concluded. You can no longer join a team.",
                ),
                status_code=400,
            )

        # Enforce team capacity limit
        max_capacity = getattr(event, "max_team_size", 4) or 4
        current_members = db.query(TeamMember).filter_by(team_id=team.id).count()
        if current_members >= max_capacity:
            return templates.TemplateResponse(
                request=request,
                name="participant/team.html",
                context=base_context(
                    request=request,
                    event=event,
                    user=user,
                    role="participant",
                    team=None,
                    error=f"Cannot join team: '{team.name}' has already reached its maximum capacity of {max_capacity} members.",
                ),
                status_code=400,
            )

        from src.queries import upsert_membership

        upsert_membership(db, team.event_id, user.id, "participant")
        db.add(TeamMember(team_id=team.id, user_id=user.id))
        db.add(
            AuditLog(
                event_id=team.event_id,
                actor_id=user.id,
                message=f"{user.name} joined team {team.name}",
                created_at=utcnow(),
            )
        )
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
        project = (
            db.query(Project)
            .filter(Project.event_id == event.id, Project.team_id == team.id)
            .first()
        )
    return templates.TemplateResponse(
        request=request,
        name="participant/submit.html",
        context=base_context(
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

    title = (
        (payload.get("title") or "").strip()
        if isinstance(payload.get("title"), str)
        else ""
    )
    summary = (
        (payload.get("summary") or "").strip()
        if isinstance(payload.get("summary"), str)
        else ""
    )
    repo_url = (
        (payload.get("repo_url") or "").strip() or None
        if isinstance(payload.get("repo_url"), str)
        else None
    )
    demo_url = (
        (payload.get("demo_url") or "").strip() or None
        if isinstance(payload.get("demo_url"), str)
        else None
    )
    tech_stack = (
        (payload.get("tech_stack") or "").strip()
        if isinstance(payload.get("tech_stack"), str)
        else ""
    )
    track_id = payload.get("track_id") or payload.get("track")
    is_draft = str(payload.get("action") or "").lower() == "draft" or payload.get(
        "is_draft"
    ) in (True, "true", "1", "on")

    import os
    import shutil
    from fastapi import UploadFile

    upload_dir = os.path.join("src", "static", "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    cover_image_path = None
    cover_file = payload.get("cover_image")
    if isinstance(cover_file, UploadFile) and cover_file.filename:
        filename = f"{team.id}_{cover_file.filename}"
        file_path = os.path.join(upload_dir, filename)
        with open(file_path, "wb") as f:
            shutil.copyfileobj(cover_file.file, f)
        cover_image_path = f"/static/uploads/{filename}"

    project = (
        db.query(Project)
        .filter(Project.event_id == event.id, Project.team_id == team.id)
        .first()
    )
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
        project.track_id = track_id if isinstance(track_id, str) else None
    if repo_url is not None:
        project.repo_url = repo_url
    if demo_url is not None:
        project.demo_url = demo_url
    if tech_stack:
        project.tech_stack = tech_stack
    if cover_image_path:
        project.cover_image_path = cover_image_path

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

    if not project.is_draft:
        try:
            from src.webhooks import dispatch_webhook
            dispatch_webhook(
                event.id,
                "project.submitted",
                {
                    "project_id": project.id,
                    "title": project.title,
                    "team_id": team.id,
                    "team_name": team.name,
                },
            )
        except Exception:
            pass

    if wants_json:
        return JSONResponse({"id": project.id, "title": project.title}, status_code=200)
    return RedirectResponse(f"/participant/{event.id}/dashboard", status_code=303)
