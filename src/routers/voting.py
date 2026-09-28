from __future__ import annotations

import html
import time
from collections import defaultdict
from datetime import datetime, timezone
from threading import Lock

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from src.auth import get_current_user, require_login
from src.db import get_db
from src.models import (
    AuditLog,
    Comment,
    Event,
    EventMember,
    Project,
    Team,
    TeamMember,
    User,
    Vote,
)
from src.queries import user_team
from src.timeutil import utcnow

router = APIRouter(prefix="/api/projects", tags=["voting"])

# Thread-safe in-memory rate limiting tracker
_rate_limit_lock = Lock()
_user_action_timestamps: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(
    user_id: str, action: str, max_requests: int, window_seconds: float
) -> None:
    now = time.time()
    key = f"{user_id}:{action}"
    with _rate_limit_lock:
        timestamps = _user_action_timestamps[key]
        cutoff = now - window_seconds
        valid_timestamps = [t for t in timestamps if t > cutoff]
        if len(valid_timestamps) >= max_requests:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded for {action}. Please try again later.",
            )
        valid_timestamps.append(now)
        _user_action_timestamps[key] = valid_timestamps


def _get_user_role(db: Session, user: User | None, event_id: str) -> str:
    if not user:
        return "visitor"
    membership = (
        db.query(EventMember)
        .filter(EventMember.user_id == user.id, EventMember.event_id == event_id)
        .first()
    )
    if not membership:
        any_admin = (
            db.query(EventMember)
            .filter(EventMember.user_id == user.id, EventMember.role == "admin")
            .first()
        )
        return "admin" if any_admin else "visitor"
    return membership.role


# ---------------------------------------------------------------------------
# Community Voting Endpoints
# ---------------------------------------------------------------------------


@router.get("/{project_id}/vote-status")
def get_vote_status(
    project_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    event = project.event

    # Community voting must be enabled on the event
    if not getattr(event, "community_voting_enabled", False):
        return {
            "voted": False,
            "can_vote": False,
            "reason": "Community voting is not enabled for this hackathon",
            "results_hidden": not event.results_published,
            "community_voting_enabled": False,
        }

    if not user:
        return {
            "voted": False,
            "can_vote": False,
            "reason": "Login required to vote",
            "results_hidden": not event.results_published,
            "community_voting_enabled": True,
        }

    role = _get_user_role(db, user, event.id)
    if role not in ("participant", "admin"):
        return {
            "voted": False,
            "can_vote": False,
            "reason": "Only participants can cast community votes",
            "results_hidden": not event.results_published,
            "community_voting_enabled": True,
        }

    # Check if own project
    team = user_team(db, user.id, event.id)
    if team and team.id == project.team_id:
        return {
            "voted": False,
            "can_vote": False,
            "is_own_project": True,
            "reason": "Cannot vote for your own project",
            "results_hidden": not event.results_published,
            "community_voting_enabled": True,
        }

    if event.results_published:
        return {
            "voted": False,
            "can_vote": False,
            "reason": "Voting is closed (results published)",
            "results_hidden": False,
            "community_voting_enabled": True,
        }

    # Check if this user already voted in this event (for any project)
    existing_vote = (
        db.query(Vote)
        .filter(Vote.user_id == user.id, Vote.event_id == event.id)
        .first()
    )

    voted_for_this = existing_vote is not None and existing_vote.project_id == project.id
    already_voted_elsewhere = existing_vote is not None and existing_vote.project_id != project.id

    data = {
        "voted": voted_for_this,
        # You can always move your vote to another project
        "can_vote": True,
        "already_voted_project_id": existing_vote.project_id if existing_vote else None,
        "reason": "You already voted for another project — clicking Vote will move your vote here" if already_voted_elsewhere else None,
        "results_hidden": not event.results_published,
        "community_voting_enabled": True,
    }

    # Only reveal vote tally if results are published or user is organizer/admin
    if event.results_published or role in ("organizer", "admin"):
        total_votes = db.query(Vote).filter(Vote.project_id == project.id).count()
        data["vote_count"] = total_votes
    else:
        data["vote_count"] = None

    return data


@router.post("/{project_id}/vote")
def cast_or_toggle_vote(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.is_draft or project.is_disqualified:
        raise HTTPException(
            status_code=400, detail="Cannot vote for draft or disqualified projects"
        )

    event = project.event

    # Community voting must be enabled
    if not getattr(event, "community_voting_enabled", False):
        raise HTTPException(
            status_code=403,
            detail="Community voting is not enabled for this hackathon",
        )

    if event.results_published:
        raise HTTPException(
            status_code=400, detail="Voting closed: results have already been published"
        )

    # Anti-abuse: Role check — must be participant in this event (or admin)
    role = _get_user_role(db, user, event.id)
    if role not in ("participant", "admin"):
        raise HTTPException(
            status_code=403,
            detail="Community voting is restricted to authenticated event participants",
        )

    # Anti-abuse: Prevent self-voting
    team = user_team(db, user.id, event.id)
    if team and team.id == project.team_id:
        raise HTTPException(
            status_code=403,
            detail="Self-voting is strictly prohibited: you cannot vote for your own team's project",
        )

    # Anti-abuse: Rate limit vote actions (max 10 per minute)
    _check_rate_limit(user.id, "vote", max_requests=10, window_seconds=60.0)

    # Check if user already voted in this event
    existing_vote = (
        db.query(Vote)
        .filter(Vote.user_id == user.id, Vote.event_id == event.id)
        .first()
    )

    if existing_vote:
        if existing_vote.project_id == project.id:
            # Toggle: remove vote (unvote)
            db.delete(existing_vote)
            db.add(
                AuditLog(
                    event_id=event.id,
                    actor_id=user.id,
                    message=f"User {user.name} ({user.id}) removed community vote from project '{project.title}' ({project.id})",
                    created_at=utcnow(),
                )
            )
            db.commit()
            return {
                "success": True,
                "voted": False,
                "project_id": project.id,
                "message": "Vote removed",
            }
        else:
            # Move vote from old project to this one
            old_project_id = existing_vote.project_id
            existing_vote.project_id = project.id
            existing_vote.created_at = utcnow()
            db.add(
                AuditLog(
                    event_id=event.id,
                    actor_id=user.id,
                    message=f"User {user.name} ({user.id}) moved community vote from '{old_project_id}' to project '{project.title}' ({project.id})",
                    created_at=utcnow(),
                )
            )
            db.commit()
            return {
                "success": True,
                "voted": True,
                "project_id": project.id,
                "message": "Vote moved to this project",
            }

    # Cast new vote
    new_vote = Vote(
        event_id=event.id,
        user_id=user.id,
        project_id=project.id,
        created_at=utcnow(),
    )
    db.add(new_vote)
    db.add(
        AuditLog(
            event_id=event.id,
            actor_id=user.id,
            message=f"User {user.name} ({user.id}) cast community vote for project '{project.title}' ({project.id})",
            created_at=utcnow(),
        )
    )
    db.commit()

    return {
        "success": True,
        "voted": True,
        "project_id": project.id,
        "message": "Vote cast successfully",
    }


@router.delete("/{project_id}/vote")
def delete_vote(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    existing_vote = (
        db.query(Vote)
        .filter(Vote.user_id == user.id, Vote.event_id == project.event_id)
        .first()
    )
    if not existing_vote or existing_vote.project_id != project.id:
        return {
            "success": True,
            "voted": False,
            "project_id": project.id,
            "message": "No active vote for this project",
        }

    db.delete(existing_vote)
    db.add(
        AuditLog(
            event_id=project.event_id,
            actor_id=user.id,
            message=f"User {user.name} ({user.id}) revoked community vote for project '{project.title}' ({project.id})",
            created_at=utcnow(),
        )
    )
    db.commit()
    return {
        "success": True,
        "voted": False,
        "project_id": project.id,
        "message": "Vote removed",
    }


# ---------------------------------------------------------------------------
# Project Comments Endpoints
# ---------------------------------------------------------------------------


@router.get("/{project_id}/comments")
def list_comments(
    project_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    comments = (
        db.query(Comment)
        .options(joinedload(Comment.user))
        .filter(Comment.project_id == project_id)
        .order_by(Comment.created_at.asc())
        .all()
    )

    user_role = _get_user_role(db, user, project.event_id) if user else "visitor"

    return [
        {
            "id": c.id,
            "content": c.content,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "author": {
                "id": c.user.id,
                "name": c.user.name,
                "avatar_url": f"/users/{c.user.id}/avatar.svg",
            },
            "can_delete": bool(
                user and (user.id == c.user_id or user_role in ("organizer", "admin"))
            ),
        }
        for c in comments
    ]


@router.post("/{project_id}/comments")
async def add_comment(
    project_id: str,
    request: Request,
    content: str = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Handle JSON or Form body
    if content is None:
        try:
            body = await request.json()
            content = body.get("content", "")
        except Exception:
            content = ""

    cleaned = (content or "").strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail="Comment content cannot be empty")
    if len(cleaned) > 2000:
        raise HTTPException(
            status_code=400, detail="Comment exceeds maximum length of 2000 characters"
        )

    # Anti-abuse: Rate limit comments (max 10 comments per 5 minutes per user)
    _check_rate_limit(user.id, "comment", max_requests=10, window_seconds=300.0)

    # Sanitize content against XSS
    safe_content = html.escape(cleaned)

    comment = Comment(
        event_id=project.event_id,
        user_id=user.id,
        project_id=project.id,
        content=safe_content,
        created_at=utcnow(),
    )
    db.add(comment)
    db.add(
        AuditLog(
            event_id=project.event_id,
            actor_id=user.id,
            message=f"User {user.name} ({user.id}) posted comment on project '{project.title}' ({project.id})",
            created_at=utcnow(),
        )
    )
    db.commit()
    db.refresh(comment)

    # If submitted via traditional HTML form, redirect back
    accept = request.headers.get("accept", "")
    content_type = request.headers.get("content-type", "")
    if "application/x-www-form-urlencoded" in content_type and "text/html" in accept:
        return RedirectResponse(f"/projects/{project_id}#comments", status_code=303)

    return {
        "id": comment.id,
        "content": comment.content,
        "created_at": comment.created_at.isoformat(),
        "author": {
            "id": user.id,
            "name": user.name,
            "avatar_url": f"/users/{user.id}/avatar.svg",
        },
        "can_delete": True,
    }


@router.delete("/{project_id}/comments/{comment_id}")
def delete_comment(
    project_id: str,
    comment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    comment = db.get(Comment, comment_id)
    if not comment or comment.project_id != project_id:
        raise HTTPException(status_code=404, detail="Comment not found")

    user_role = _get_user_role(db, user, comment.event_id)
    if user.id != comment.user_id and user_role not in ("organizer", "admin"):
        raise HTTPException(
            status_code=403, detail="You do not have permission to delete this comment"
        )

    db.delete(comment)
    db.add(
        AuditLog(
            event_id=comment.event_id,
            actor_id=user.id,
            message=f"Comment {comment_id} on project {project_id} deleted by {user.name} ({user.id})",
            created_at=utcnow(),
        )
    )
    db.commit()
    return {"success": True, "deleted_id": comment_id}
