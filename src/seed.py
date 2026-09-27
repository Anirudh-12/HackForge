from __future__ import annotations

import json
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from src.auth import make_session_token
from src.models import (
    AuditLog,
    Event,
    EventMember,
    JudgeTrack,
    Project,
    RubricCriteria,
    Score,
    Team,
    TeamMember,
    Track,
    User,
)
from src.timeutil import parse_iso_utc, utcnow

ROOT = Path(__file__).resolve().parent.parent
FIXTURES_PATH = ROOT / "fixtures.json"
TOML_PATH = ROOT / ".dogfood.toml"


def _user(db: Session, user_id: str, email: str, name: str) -> User:
    existing = db.get(User, user_id) or db.query(User).filter(User.email == email).first()
    if existing:
        return existing
    user = User(id=user_id, email=email, name=name, password_hash=None)
    db.add(user)
    db.flush()
    return user


def _member(db: Session, event_id: str, user_id: str, role: str) -> None:
    exists = (
        db.query(EventMember)
        .filter(EventMember.event_id == event_id, EventMember.user_id == user_id)
        .first()
    )
    if exists:
        return
    db.add(EventMember(event_id=event_id, user_id=user_id, role=role))


def _audit(db: Session, event_id: str, message: str) -> None:
    db.add(AuditLog(event_id=event_id, actor_id="seed", message=message, created_at=utcnow()))


def seed(db: Session) -> None:
    if db.get(Event, "evt_01"):
        _write_toml(db)
        _print_logins(db)
        return

    data = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))
    event_data = data["event"]
    event = Event(
        id=event_data["id"],
        name=event_data["name"],
        submissions_open=parse_iso_utc("2026-02-01T00:00:00Z"),
        submissions_close=parse_iso_utc(event_data.get("submissions_close")),
        judging_open=parse_iso_utc("2026-03-01T18:00:00Z"),
        judging_close=parse_iso_utc("2026-03-08T18:00:00Z"),
        results_published=False,
    )
    db.add(event)
    db.flush()

    for track in data.get("tracks") or []:
        db.add(
            Track(
                id=track["id"],
                event_id=event.id,
                name=track["name"],
                prize=track.get("prize"),
            )
        )

    organizer = _user(db, "org_1", "organizer@hackforge.local", "Organizer")
    admin = _user(db, "adm_1", "admin@hackforge.local", "Admin")
    _member(db, event.id, organizer.id, "organizer")
    _member(db, event.id, admin.id, "admin")

    for judge in data.get("judges") or []:
        user = _user(db, judge["id"], judge["email"], judge["name"])
        _member(db, event.id, user.id, "judge")
        for track_id in judge.get("tracks") or []:
            db.add(JudgeTrack(event_id=event.id, judge_id=user.id, track_id=track_id))

    first_participant_id = None
    for team in data.get("teams") or []:
        db.add(Team(id=team["id"], event_id=event.id, name=team["name"], invite_token=None))
        db.flush()
        for index, email in enumerate(team.get("members") or []):
            local = email.split("@")[0]
            if first_participant_id is None:
                user_id = "prt_1"
                first_participant_id = user_id
            else:
                user_id = f"usr_{local}"
            user = _user(db, user_id, email, local)
            _member(db, event.id, user.id, "participant")
            db.add(TeamMember(team_id=team["id"], user_id=user.id))

    for project in data.get("projects") or []:
        db.add(
            Project(
                id=project["id"],
                event_id=event.id,
                team_id=project["team"],
                track_id=project.get("track"),
                title=project.get("title") or "",
                summary=project.get("summary") or "",
                repo_url=project.get("repo_url"),
                demo_url=project.get("demo_url"),
                is_draft=False,
                submitted_at=parse_iso_utc(project.get("submitted_at")),
                is_disqualified=False,
            )
        )

    weights = {"functionality": 40, "quality": 30, "innovation": 30}
    for name, weight in weights.items():
        db.add(
            RubricCriteria(
                id=f"{event.id}:{name}",
                event_id=event.id,
                name=name.title(),
                weight=weight,
            )
        )
    db.flush()

    for score in data.get("scores") or []:
        judge_id = score.get("judge")
        project_id = score.get("project")
        comment = score.get("comment")
        for criterion, value in (score.get("criteria") or {}).items():
            db.add(
                Score(
                    event_id=event.id,
                    judge_id=judge_id,
                    project_id=project_id,
                    criteria_id=f"{event.id}:{criterion}",
                    value=int(value),
                    comment=comment,
                )
            )

    _audit(db, event.id, "Seeded Sample Hack 2026 from fixtures.json")
    db.commit()
    _write_toml(db)
    _print_logins(db)


def _print_logins(db: Session) -> None:
    rows = [
        ("organizer", "org_1"),
        ("judge_a", "jdg_01"),
        ("judge_b", "jdg_02"),
        ("participant", "prt_1"),
        ("admin", "adm_1"),
    ]
    print("seeded. test logins:")
    for label, user_id in rows:
        user = db.get(User, user_id)
        if user is None:
            continue
        token = make_session_token(user.id)
        print(f"  {label:12} Cookie: session={token}")
        print(f"               email={user.email}  (any password)")


def _write_toml(db: Session) -> None:
    def cookie(user_id: str) -> str:
        return f"Cookie: session={make_session_token(user_id)}"

    body = f"""[portal]
base_url = "http://localhost:8080"

[tiers]
claimed = ["T1"]
pitch = "Run your hackathon without the spreadsheet chaos."

[auth]
organizer   = "{cookie("org_1")}"
judge_a     = "{cookie("jdg_01")}"
judge_b     = "{cookie("jdg_02")}"
participant = "{cookie("prt_1")}"

[routes]
gallery      = "/projects"
submit       = "/projects/new"
judge_scores = "/api/judge/scores"
peer_scores  = "/api/judge/scores?judge=jdg_01"
csv_export   = "/api/export.csv"
"""
    TOML_PATH.write_text(body, encoding="utf-8")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"
