from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    # Null password_hash means a seeded fixture/test user: any password is accepted.
    password_hash: Mapped[str | None] = mapped_column(String, nullable=True)

    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    github_url: Mapped[str | None] = mapped_column(String, nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String, nullable=True)
    skills: Mapped[str | None] = mapped_column(String, nullable=True)

    memberships: Mapped[list[EventMember]] = relationship(back_populates="user")
    team_memberships: Mapped[list[TeamMember]] = relationship(back_populates="user")


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    submissions_open: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submissions_close: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    judging_open: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    judging_close: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    results_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    banner_image_path: Mapped[str | None] = mapped_column(String, nullable=True)
    description_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    rules_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)

    tracks: Mapped[list[Track]] = relationship(back_populates="event")
    teams: Mapped[list[Team]] = relationship(back_populates="event")
    projects: Mapped[list[Project]] = relationship(back_populates="event")
    members: Mapped[list[EventMember]] = relationship(back_populates="event")

    @property
    def status_info(self):
        from src.timeutil import utcnow, as_utc
        now = utcnow()
        
        j_close = as_utc(self.judging_close)
        j_open = as_utc(self.judging_open)
        s_close = as_utc(self.submissions_close)
        s_open = as_utc(self.submissions_open)
        
        if self.results_published:
            return {"text": "Results Live", "progress": 100, "color": "var(--success)"}
        elif j_close and now > j_close:
            return {"text": "Judging Stopped", "progress": 80, "color": "#1e3a8a"}
        elif j_open and now > j_open:
            return {"text": "Judging Started", "progress": 60, "color": "#7c3aed"}
        elif s_close and now > s_close:
            return {"text": "Submissions Closed", "progress": 40, "color": "var(--warning)"}
        elif s_open and now > s_open:
            return {"text": "Submissions Open", "progress": 20, "color": "var(--accent)"}
        else:
            return {"text": "Not Started", "progress": 0, "color": "var(--text-muted)"}


class EventMember(Base):
    __tablename__ = "event_members"
    __table_args__ = (UniqueConstraint("event_id", "user_id", name="uq_event_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String, nullable=False)
    looking_for_team: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    skills_offered: Mapped[str | None] = mapped_column(Text, nullable=True)

    event: Mapped[Event] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="memberships")


class Track(Base):
    __tablename__ = "tracks"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    prize: Mapped[str | None] = mapped_column(Text, nullable=True)

    event: Mapped[Event] = relationship(back_populates="tracks")
    projects: Mapped[list[Project]] = relationship(back_populates="track")


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    invite_token: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)

    event: Mapped[Event] = relationship(back_populates="teams")
    members: Mapped[list[TeamMember]] = relationship(back_populates="team")
    project: Mapped[Project | None] = relationship(back_populates="team", uselist=False)


class TeamMember(Base):
    __tablename__ = "team_members"
    __table_args__ = (UniqueConstraint("team_id", "user_id", name="uq_team_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    team: Mapped[Team] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="team_memberships")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), nullable=False, index=True)
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id"), nullable=False, index=True)
    track_id: Mapped[str | None] = mapped_column(ForeignKey("tracks.id"), nullable=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    repo_url: Mapped[str | None] = mapped_column(String, nullable=True)
    demo_url: Mapped[str | None] = mapped_column(String, nullable=True)
    cover_image_path: Mapped[str | None] = mapped_column(String, nullable=True)
    screenshots: Mapped[str | None] = mapped_column(Text, nullable=True)
    tech_stack: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_draft: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_disqualified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    event: Mapped[Event] = relationship(back_populates="projects")
    team: Mapped[Team] = relationship(back_populates="project")
    track: Mapped[Track | None] = relationship(back_populates="projects")


class RubricCriteria(Base):
    __tablename__ = "rubric_criteria"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    weight: Mapped[int] = mapped_column(Integer, nullable=False)


class JudgeTrack(Base):
    __tablename__ = "judge_tracks"
    __table_args__ = (UniqueConstraint("event_id", "judge_id", "track_id", name="uq_judge_track"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), nullable=False, index=True)
    judge_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    track_id: Mapped[str] = mapped_column(ForeignKey("tracks.id"), nullable=False, index=True)


class Score(Base):
    __tablename__ = "scores"
    __table_args__ = (UniqueConstraint("judge_id", "project_id", "criteria_id", name="uq_score"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), nullable=False, index=True)
    judge_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    criteria_id: Mapped[str] = mapped_column(ForeignKey("rubric_criteria.id"), nullable=False)
    value: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    actor_id: Mapped[str | None] = mapped_column(String, nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class JudgeInvitation(Base):
    __tablename__ = "judge_invitations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String, nullable=False, index=True)
    track_ids: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String, default="pending", nullable=False)

    event: Mapped[Event] = relationship()

class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    action_link: Mapped[str | None] = mapped_column(String, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped[User] = relationship()

