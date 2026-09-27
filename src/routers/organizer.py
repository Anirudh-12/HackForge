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
from src.timeutil import as_utc, parse_iso_utc, utcnow

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
    return templates.TemplateResponse(
        request=request,
        name="organizer/events.html",
        context=base_context(all_events=db.query(Event).all(), 
            request=request,
            event=events[0] if events else None,
            user=user,
            role="organizer",
            events=events,
        ),
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
    db.add(
        AuditLog(
            event_id=event.id,
            actor_id=user.id,
            message=f"{user.name} created event {event.name}",
            created_at=utcnow(),
        )
    )
    db.commit()
    return RedirectResponse(f"/organizer/{event.id}/event", status_code=303)


from src.models import JudgeTrack, Score

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
    
    # Progress Dashboard Stats
    tracks = event_tracks(db, event_id)
    track_map = {t.id: t for t in tracks}
    
    judge_tracks = db.query(JudgeTrack).filter_by(event_id=event_id).all()
    # Map track_id to list of judge_ids
    track_judges = {}
    for jt in judge_tracks:
        track_judges.setdefault(jt.track_id, []).append(jt.judge_id)
        
    unique_judges = set(jt.judge_id for jt in judge_tracks)
    
    scores = db.query(Score).filter_by(event_id=event_id).all()
    
    # Pre-calculate who scored what: (project_id, judge_id) -> bool
    scored_pairs = set((s.project_id, s.judge_id) for s in scores)
    
    total_reviews_assigned = 0
    total_reviews_completed = 0
    
    project_stats = []
    
    submitted_projects = [p for p in projects if not p.is_draft and not p.is_disqualified]
    
    for p in submitted_projects:
        p_track = track_map.get(p.track_id)
        p_judges = track_judges.get(p.track_id, [])
        
        reviews_total = len(p_judges)
        reviews_done = sum(1 for j in p_judges if (p.id, j) in scored_pairs)
        
        total_reviews_assigned += reviews_total
        total_reviews_completed += reviews_done
        
        if reviews_total == 0:
            status = "No judges"
        elif reviews_done == reviews_total:
            status = "Complete"
        else:
            status = f"Awaiting {reviews_total - reviews_done}"
            
        project_stats.append({
            "project": p,
            "track_name": p_track.name if p_track else "Untracked",
            "reviews_done": reviews_done,
            "reviews_total": reviews_total,
            "status": status,
            "complete": reviews_done == reviews_total and reviews_total > 0
        })
        
    # Sort projects: incomplete first, then by track
    project_stats.sort(key=lambda x: (x["complete"], x["track_name"], x["project"].title))
    
    reviews_percent = int((total_reviews_completed / total_reviews_assigned * 100)) if total_reviews_assigned > 0 else 0
    reviews_awaiting = total_reviews_assigned - total_reviews_completed
    
    now = utcnow()
    subs_complete = event.submissions_close and now > as_utc(event.submissions_close)
    assign_complete = total_reviews_assigned > 0
    judging_complete = total_reviews_assigned > 0 and total_reviews_completed == total_reviews_assigned

    return templates.TemplateResponse(
        request=request,
        name="organizer/dashboard.html",
        context=base_context(
            all_events=db.query(Event).all(), 
            request=request,
            event=event,
            user=user,
            role="organizer",
            project_count=len(submitted_projects),
            judge_count=len(unique_judges),
            total_reviews_assigned=total_reviews_assigned,
            total_reviews_completed=total_reviews_completed,
            reviews_percent=reviews_percent,
            reviews_awaiting=reviews_awaiting,
            project_stats=project_stats,
            subs_complete=subs_complete,
            assign_complete=assign_complete,
            judging_complete=judging_complete,
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
    return templates.TemplateResponse(
        request=request,
        name="organizer/event.html",
        context=base_context(all_events=db.query(Event).all(), request=request, event=event, user=user, role="organizer"),
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
    db.add(
        AuditLog(
            event_id=event.id,
            actor_id=user.id,
            message=f"{user.name} updated event dates for {event.name}",
            created_at=utcnow(),
        )
    )
    db.commit()
    return RedirectResponse(f"/organizer/{event_id}/event", status_code=303)


@router.get("/organizer/{event_id}/teams")
def get_teams(
    event_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("organizer", "admin")),
):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    teams = db.query(Team).filter(Team.event_id == event_id).all()
    
    return templates.TemplateResponse(
        request=request,
        name="organizer/teams.html",
        context=base_context(
            all_events=db.query(Event).all(),
            request=request,
            event=event,
            user=user,
            role="organizer",
            teams=teams,
        ),
    )


@router.get("/organizer/{event_id}/projects")
def get_projects(
    event_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("organizer", "admin")),
):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    projects = db.query(Project).filter(Project.event_id == event_id).all()
    
    return templates.TemplateResponse(
        request=request,
        name="organizer/projects.html",
        context=base_context(
            all_events=db.query(Event).all(),
            request=request,
            event=event,
            user=user,
            role="organizer",
            projects=projects,
        ),
    )


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
    return templates.TemplateResponse(
        request=request,
        name="organizer/tracks.html",
        context=base_context(all_events=db.query(Event).all(), 
            request=request,
            event=event,
            user=user,
            role="organizer",
            tracks=event_tracks(db, event_id),
        ),
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
    db.add(
        Track(
            id=new_id("trk"),
            event_id=event_id,
            name=name.strip(),
            prize=prize.strip() or None,
        )
    )
    db.add(
        AuditLog(
            event_id=event_id,
            actor_id=user.id,
            message=f"{user.name} added track {name.strip()}",
            created_at=utcnow(),
        )
    )
    db.commit()
    return RedirectResponse(f"/organizer/{event_id}/tracks", status_code=303)


import csv
import io

from fastapi.responses import Response


@router.get("/organizer/{event_id}/results")
def results_page(
    event_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("organizer", "admin")),
):
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="event not found")
        
    from src.queries import compute_results
    results = compute_results(db, event.id)
    
    return templates.TemplateResponse(
        request=request,
        name="organizer/results.html",
        context=base_context(all_events=db.query(Event).all(), 
            request=request,
            event=event,
            user=user,
            role="organizer",
            results=results,
        ),
    )


@router.get("/api/export.csv")
def export_csv(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("organizer", "admin")),
):
    event = db.query(Event).first()
    if not event:
        raise HTTPException(status_code=404, detail="No event found")

    from src.queries import compute_results
    results = compute_results(db, event.id)
    
    # We need to collect all unique judge IDs that have scored something
    all_judge_ids = set()
    for res in results:
        all_judge_ids.update(res["judge_raw_scores"].keys())
    
    all_judge_ids = list(all_judge_ids)
    
    judges = db.query(User).filter(User.id.in_(all_judge_ids)).all() if all_judge_ids else []
    judge_map = {j.id: j.name for j in judges}

    output = io.StringIO()
    writer = csv.writer(output)

    headers = [
        "project_id",
        "title",
        "track",
        "team",
        "raw_score",
        "normalized_score",
        "reviews_count",
    ] + [judge_map.get(jid, jid) for jid in all_judge_ids]
    writer.writerow(headers)

    for res in results:
        p = res["project"]
        row = [
            p.id, p.title, p.track.name if p.track else "", p.team.name if p.team else "",
            f"{res['raw_score']:.2f}",
            f"{res['normalized_score']:.2f}",
            res['reviews_count']
        ]
        
        for jid in all_judge_ids:
            score = res["judge_raw_scores"].get(jid)
            if score is not None:
                row.append(f"{score:.2f}")
            else:
                row.append("")
        writer.writerow(row)

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="results.csv"'},
    )


from src.models import JudgeTrack

@router.get("/organizer/{event_id}/judges")
def judges_page(
    event_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("organizer", "admin")),
):
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="event not found")
        
    # Get all judges assigned to this event
    judge_tracks = db.query(JudgeTrack).filter(JudgeTrack.event_id == event_id).all()
    judge_ids = list(set(jt.judge_id for jt in judge_tracks))
    
    # We want to show judges with their assigned tracks
    judges_data = []
    if judge_ids:
        judges = db.query(User).filter(User.id.in_(judge_ids)).all()
        tracks_by_id = {t.id: t for t in event_tracks(db, event_id)}
        
        for j in judges:
            j_tracks = [jt for jt in judge_tracks if jt.judge_id == j.id]
            assigned_tracks = [tracks_by_id.get(jt.track_id) for jt in j_tracks if jt.track_id in tracks_by_id]
            judges_data.append({
                "user": j,
                "tracks": [t for t in assigned_tracks if t is not None]
            })
            
    from src.models import JudgeInvitation
    pending_invitations = db.query(JudgeInvitation).filter_by(event_id=event_id, status="pending").all()
    tracks_by_id = {t.id: t for t in event_tracks(db, event_id)}
    
    invitations_data = []
    for inv in pending_invitations:
        t_ids = inv.track_ids.split(",") if inv.track_ids else []
        assigned_tracks = [tracks_by_id.get(tid) for tid in t_ids if tid in tracks_by_id]
        invitations_data.append({
            "invitation": inv,
            "tracks": assigned_tracks
        })
            
    return templates.TemplateResponse(
        request=request,
        name="organizer/judges.html",
        context=base_context(all_events=db.query(Event).all(), 
            request=request,
            event=event,
            user=user,
            role="organizer",
            judges=judges_data,
            invitations=invitations_data,
            all_tracks=event_tracks(db, event_id),
        ),
    )


@router.post("/organizer/{event_id}/judges")
def invite_judge(
    event_id: str,
    email: str = Form(...),
    track_ids: list[str] = Form(default=[]),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("organizer", "admin")),
):
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="event not found")
        
    email_norm = email.strip().lower()
    if not email_norm:
        return RedirectResponse(f"/organizer/{event_id}/judges", status_code=303)
        
    from src.models import JudgeInvitation, JudgeTrack, EventMember
    
    # Check if the user is already a judge for this event
    target_user = db.query(User).filter(User.email == email_norm).first()
    if target_user:
        existing_judge = db.query(EventMember).filter_by(event_id=event_id, user_id=target_user.id, role="judge").first()
        if existing_judge:
            # Already a judge, assign to new tracks directly
            for t_id in track_ids:
                if t_id:
                    existing_jt = db.query(JudgeTrack).filter_by(event_id=event_id, judge_id=target_user.id, track_id=t_id).first()
                    if not existing_jt:
                        db.add(JudgeTrack(event_id=event_id, judge_id=target_user.id, track_id=t_id))
            
            db.add(AuditLog(
                event_id=event.id,
                actor_id=user.id,
                message=f"{user.name} assigned existing judge {email_norm} to additional tracks",
                created_at=utcnow(),
            ))
            db.commit()
            return RedirectResponse(f"/organizer/{event_id}/judges", status_code=303)
    
    # Check if already invited
    existing_inv = db.query(JudgeInvitation).filter_by(event_id=event_id, email=email_norm, status="pending").first()
    if existing_inv:
        current_tracks = set(existing_inv.track_ids.split(",")) if existing_inv.track_ids else set()
        for t_id in track_ids:
            if t_id:
                current_tracks.add(t_id)
        existing_inv.track_ids = ",".join(current_tracks)
    else:
        inv = JudgeInvitation(
            id=new_id("inv"),
            event_id=event_id,
            email=email_norm,
            track_ids=",".join([t for t in track_ids if t]),
            status="pending"
        )
        db.add(inv)
        
    db.add(AuditLog(
        event_id=event.id,
        actor_id=user.id,
        message=f"{user.name} invited judge {email_norm}",
        created_at=utcnow(),
    ))
    db.commit()
    return RedirectResponse(f"/organizer/{event_id}/judges", status_code=303)


@router.post("/organizer/{event_id}/judges/invitation/{invitation_id}/revoke")
def revoke_invitation(
    event_id: str,
    invitation_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("organizer", "admin")),
):
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="event not found")
        
    from src.models import JudgeInvitation
    inv = db.query(JudgeInvitation).filter_by(event_id=event_id, id=invitation_id).first()
    if inv:
        db.delete(inv)
        db.add(AuditLog(
            event_id=event.id,
            actor_id=user.id,
            message=f"{user.name} revoked judge invitation for {inv.email}",
            created_at=utcnow(),
        ))
        db.commit()
    return RedirectResponse(f"/organizer/{event_id}/judges", status_code=303)


from src.models import RubricCriteria, Score

@router.get("/organizer/{event_id}/rubric")
def rubric_page(
    event_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("organizer", "admin")),
):
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="event not found")
        
    criteria = db.query(RubricCriteria).filter_by(event_id=event_id).all()
    has_scores = db.query(Score).filter_by(event_id=event_id).first() is not None
    
    return templates.TemplateResponse(
        request=request,
        name="organizer/rubric.html",
        context=base_context(all_events=db.query(Event).all(), 
            request=request,
            event=event,
            user=user,
            role="organizer",
            criteria=criteria,
            total_weight=sum(c.weight for c in criteria),
            has_scores=has_scores,
        ),
    )


@router.post("/organizer/{event_id}/rubric")
def add_rubric_criteria(
    event_id: str,
    name: str = Form(...),
    weight: int = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("organizer", "admin")),
):
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="event not found")
        
    has_scores = db.query(Score).filter_by(event_id=event_id).first() is not None
    if has_scores:
        raise HTTPException(status_code=400, detail="Cannot edit rubric after judging has started")
        
    db.add(RubricCriteria(
        id=new_id("cr"),
        event_id=event_id,
        name=name.strip(),
        weight=weight,
    ))
    db.add(AuditLog(
        event_id=event.id,
        actor_id=user.id,
        message=f"{user.name} added rubric criteria {name.strip()}",
        created_at=utcnow(),
    ))
    db.commit()
    return RedirectResponse(f"/organizer/{event_id}/rubric", status_code=303)


@router.post("/organizer/{event_id}/rubric/{criteria_id}/remove")
def remove_rubric_criteria(
    event_id: str,
    criteria_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("organizer", "admin")),
):
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="event not found")
        
    has_scores = db.query(Score).filter_by(event_id=event_id).first() is not None
    if has_scores:
        raise HTTPException(status_code=400, detail="Cannot edit rubric after judging has started")
        
    crit = db.query(RubricCriteria).filter_by(event_id=event_id, id=criteria_id).first()
    if crit:
        db.delete(crit)
        db.add(AuditLog(
            event_id=event.id,
            actor_id=user.id,
            message=f"{user.name} removed rubric criteria {crit.name}",
            created_at=utcnow(),
        ))
        db.commit()
    return RedirectResponse(f"/organizer/{event_id}/rubric", status_code=303)
@router.post("/organizer/{event_id}/judges/{judge_id}/remove")
def remove_judge(
    event_id: str,
    judge_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("organizer", "admin")),
):
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="event not found")
        
    judge_tracks = db.query(JudgeTrack).filter_by(event_id=event_id, judge_id=judge_id).all()
    for jt in judge_tracks:
        db.delete(jt)
        
    from src.models import EventMember
    member = db.query(EventMember).filter_by(event_id=event_id, user_id=judge_id, role="judge").first()
    if member:
        db.delete(member)
    
    db.add(AuditLog(
        event_id=event.id,
        actor_id=user.id,
        message=f"{user.name} removed judge {judge_id} completely from event",
        created_at=utcnow(),
    ))
    db.commit()
    return RedirectResponse(f"/organizer/{event_id}/judges", status_code=303)

