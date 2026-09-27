from __future__ import annotations

from sqlalchemy.orm import Session, joinedload

from src.models import Event, EventMember, Project, Team, TeamMember, Track, User


def default_event(db: Session) -> Event | None:
    return db.get(Event, "evt_01") or db.query(Event).order_by(Event.id).first()


def get_event(db: Session, event_id: str) -> Event | None:
    return db.get(Event, event_id)


def user_team(db: Session, user_id: str, event_id: str) -> Team | None:
    return (
        db.query(Team)
        .join(TeamMember, TeamMember.team_id == Team.id)
        .filter(Team.event_id == event_id, TeamMember.user_id == user_id)
        .first()
    )


def gallery_projects(db: Session, event_id: str, q: str | None = None, track_id: str | None = None):
    query = (
        db.query(Project)
        .options(joinedload(Project.team), joinedload(Project.track))
        .filter(Project.event_id == event_id, Project.is_draft.is_(False), Project.is_disqualified.is_(False))
    )
    if q:
        like = f"%{q}%"
        query = query.filter(Project.title.ilike(like) | Project.summary.ilike(like))
    if track_id:
        query = query.filter(Project.track_id == track_id)
    return query.order_by(Project.title.asc()).all()


def event_tracks(db: Session, event_id: str) -> list[Track]:
    return db.query(Track).filter(Track.event_id == event_id).order_by(Track.name.asc()).all()


def upsert_membership(db: Session, event_id: str, user_id: str, role: str) -> EventMember:
    member = (
        db.query(EventMember)
        .filter(EventMember.event_id == event_id, EventMember.user_id == user_id)
        .first()
    )
    if member:
        return member
    member = EventMember(event_id=event_id, user_id=user_id, role=role)
    db.add(member)
    return member
