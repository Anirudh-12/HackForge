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
    judge_tracks = db.query(JudgeTrack).filter_by(event_id=event_id).all()
    judges = db.query(User).filter(User.id.in_([jt.judge_id for jt in judge_tracks])).all() if judge_tracks else []
    
    scores = db.query(Score).filter_by(event_id=event_id).all()
    
    # How many judges have submitted at least one score
    judges_with_scores = set(s.judge_id for s in scores)
    
    # For each track, compute progress
    track_stats = []
    
    total_projects = 0
    total_fully_scored = 0
    
    for t in tracks:
        t_projects = [p for p in projects if p.track_id == t.id and not p.is_draft and not p.is_disqualified]
        t_judges = [jt.judge_id for jt in judge_tracks if jt.track_id == t.id]
        
        fully_scored = 0
        for p in t_projects:
            # A project is fully scored if ALL assigned judges have scored it
            # We count distinct criteria? No, "at least one score" is usually enough to say a judge has scored a project.
            p_scores = [s for s in scores if s.project_id == p.id]
            p_judges_who_scored = set(s.judge_id for s in p_scores)
            
            # If every judge assigned to this track has scored it
            if t_judges and all(j in p_judges_who_scored for j in t_judges):
                fully_scored += 1
            elif not t_judges:
                # If no judges assigned, it can't be scored
                pass
                
        # For each judge in this track, their completion count
        j_stats = []
        for j_id in t_judges:
            j_name = next((j.name for j in judges if j.id == j_id), j_id)
            # How many projects in this track did this judge score?
            j_scored = sum(1 for p in t_projects if any(s.project_id == p.id and s.judge_id == j_id for s in scores))
            j_stats.append({"name": j_name, "scored": j_scored, "total": len(t_projects)})
            
        track_stats.append({
            "track": t,
            "project_count": len(t_projects),
            "fully_scored": fully_scored,
            "unscored": len(t_projects) - fully_scored,
            "judge_stats": j_stats,
            "no_judges": len(t_judges) == 0
        })
        
        total_projects += len(t_projects)
        total_fully_scored += fully_scored

    return templates.TemplateResponse(
        request=request,
        name="organizer/dashboard.html",
        context=base_context(all_events=db.query(Event).all(), 
            request=request,
            event=event,
            user=user,
            role="organizer",
            project_count=len(projects),
            submitted_count=submitted,
            draft_count=len(projects) - submitted,
            team_count=teams,
            tracks=tracks,
            track_stats=track_stats,
            total_projects=total_projects,
            total_fully_scored=total_fully_scored,
            percent_complete=int((total_fully_scored / total_projects * 100) if total_projects else 0),
            total_judges=len(judges),
            judges_active=len(judges_with_scores)
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
            
    return templates.TemplateResponse(
        request=request,
        name="organizer/judges.html",
        context=base_context(all_events=db.query(Event).all(), 
            request=request,
            event=event,
            user=user,
            role="organizer",
            judges=judges_data,
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
        
    # Find or create user
    judge_user = db.query(User).filter(User.email == email_norm).first()
    if not judge_user:
        judge_user = User(
            id=new_id("usr"),
            email=email_norm,
            name=email_norm,
            password_hash=None, # Pending invite
        )
        db.add(judge_user)
        db.flush()
        
    # Make sure they have the judge role in this event
    from src.queries import upsert_membership
    upsert_membership(db, event.id, judge_user.id, "judge")
    
    # Assign tracks
    for track_id in track_ids:
        existing = db.query(JudgeTrack).filter_by(
            event_id=event_id, judge_id=judge_user.id, track_id=track_id
        ).first()
        if not existing:
            db.add(JudgeTrack(event_id=event_id, judge_id=judge_user.id, track_id=track_id))
            
    db.add(AuditLog(
        event_id=event.id,
        actor_id=user.id,
        message=f"{user.name} invited/assigned judge {judge_user.email}",
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
        
    # Optionally remove the judge membership if they have no tracks?
    # Spec: "Removing a judge from a track removes their queue without touching their existing scores"
    # We will just delete the JudgeTrack assignment.
    
    db.add(AuditLog(
        event_id=event.id,
        actor_id=user.id,
        message=f"{user.name} removed judge {judge_id} from all tracks",
        created_at=utcnow(),
    ))
    db.commit()
    return RedirectResponse(f"/organizer/{event_id}/judges", status_code=303)

