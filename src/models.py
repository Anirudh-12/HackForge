from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
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
    join_requests: Mapped[list[TeamJoinRequest]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    tagline: Mapped[str | None] = mapped_column(String, nullable=True)
    event_starts: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    event_ends: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    registrations_open: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    registrations_close: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    submissions_open: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    submissions_close: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    judging_open: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    judging_close: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    results_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    results_published: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    community_voting_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    community_voting_mode: Mapped[str] = mapped_column(
        String, default="none", nullable=False
    )

    min_team_size: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    max_team_size: Mapped[int] = mapped_column(Integer, default=4, nullable=False)

    banner_image_path: Mapped[str | None] = mapped_column(String, nullable=True)
    description_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    rules_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    prizes_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    side_quests_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    community_voting_prize_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    location: Mapped[str | None] = mapped_column(String, nullable=True)
    format: Mapped[str | None] = mapped_column(String, nullable=True)

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
            return {
                "text": "Submissions Closed",
                "progress": 40,
                "color": "var(--warning)",
            }
        elif s_open and now > s_open:
            return {
                "text": "Submissions Open",
                "progress": 20,
                "color": "var(--accent)",
            }
        else:
            return {"text": "Not Started", "progress": 0, "color": "var(--text-muted)"}

    @property
    def prizes_list(self) -> list[dict]:
        import json

        if not self.prizes_json:
            return []
        try:
            return json.loads(self.prizes_json)
        except Exception:
            return []

    @property
    def side_quests_list(self) -> list[dict]:
        import json

        if not self.side_quests_json:
            return []
        try:
            return json.loads(self.side_quests_json)
        except Exception:
            return []

    @property
    def event_location(self) -> str:
        if self.location:
            return self.location
        loc_map = {
            "evt_01": "San Francisco, CA",
            "evt_02": "Austin, TX",
            "evt_03": "Boston, MA",
            "evt_04": "Bangalore, India",
            "evt_05": "New York, NY",
            "evt_06": "Seattle, WA",
            "evt_07": "Singapore",
            "evt_08": "Berlin, Germany",
            "evt_09": "London, UK",
            "evt_10": "Toronto, Canada",
        }
        return loc_map.get(self.id, "Online / Global")

    @property
    def event_format(self) -> str:
        if self.format:
            return self.format
        fmt_map = {
            "evt_01": "Hybrid",
            "evt_02": "In-Person",
            "evt_03": "Online",
            "evt_04": "In-Person",
            "evt_05": "Online",
            "evt_06": "Online",
            "evt_07": "Hybrid",
            "evt_08": "In-Person",
            "evt_09": "Online",
            "evt_10": "Hybrid",
        }
        return fmt_map.get(self.id, "Online")

    @property
    def prize_pool(self) -> int:
        import re

        total = 0
        for p in self.prizes_list:
            amt = str(p.get("amount", ""))
            nums = re.findall(r"[\d,]+", amt)
            if nums:
                try:
                    total += int(nums[0].replace(",", ""))
                except Exception:
                    pass
        for t in self.tracks:
            if t.prize:
                nums = re.findall(r"[\d,]+", str(t.prize))
                if nums:
                    try:
                        total += int(nums[0].replace(",", ""))
                    except Exception:
                        pass
        return total

    @property
    def prize_pool_display(self) -> str:
        pool = self.prize_pool
        return f"${pool:,}" if pool > 0 else "TBA"


class EventMember(Base):
    __tablename__ = "event_members"
    __table_args__ = (UniqueConstraint("event_id", "user_id", name="uq_event_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(
        ForeignKey("events.id"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String, nullable=False)
    looking_for_team: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    skills_offered: Mapped[str | None] = mapped_column(Text, nullable=True)

    event: Mapped[Event] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="memberships")


class Track(Base):
    __tablename__ = "tracks"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    event_id: Mapped[str] = mapped_column(
        ForeignKey("events.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    prize: Mapped[str | None] = mapped_column(Text, nullable=True)

    event: Mapped[Event] = relationship(back_populates="tracks")
    projects: Mapped[list[Project]] = relationship(back_populates="track")


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    event_id: Mapped[str] = mapped_column(
        ForeignKey("events.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    invite_token: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    leader_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    event: Mapped[Event] = relationship(back_populates="teams")
    members: Mapped[list[TeamMember]] = relationship(
        back_populates="team", cascade="all, delete-orphan"
    )
    project: Mapped[Project | None] = relationship(back_populates="team", uselist=False)
    leader: Mapped[User | None] = relationship(foreign_keys=[leader_id])
    join_requests: Mapped[list[TeamJoinRequest]] = relationship(
        back_populates="team", cascade="all, delete-orphan"
    )

    def get_leader(self, db) -> User | None:
        if self.leader_id:
            u = db.get(User, self.leader_id)
            if u:
                return u
        first_member = (
            db.query(TeamMember)
            .filter_by(team_id=self.id)
            .order_by(TeamMember.id.asc())
            .first()
        )
        if first_member:
            return db.get(User, first_member.user_id)
        return None


class TeamMember(Base):
    __tablename__ = "team_members"
    __table_args__ = (UniqueConstraint("team_id", "user_id", name="uq_team_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[str] = mapped_column(
        ForeignKey("teams.id"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )

    team: Mapped[Team] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="team_memberships")


class TeamJoinRequest(Base):
    __tablename__ = "team_join_requests"
    __table_args__ = (
        UniqueConstraint("team_id", "user_id", name="uq_team_join_request"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    team_id: Mapped[str] = mapped_column(
        ForeignKey("teams.id"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    event_id: Mapped[str] = mapped_column(
        ForeignKey("events.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String, default="pending", nullable=False
    )  # pending, accepted, declined, cancelled
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )

    team: Mapped[Team] = relationship(back_populates="join_requests")
    user: Mapped[User] = relationship(back_populates="join_requests")
    event: Mapped[Event] = relationship()


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    event_id: Mapped[str] = mapped_column(
        ForeignKey("events.id"), nullable=False, index=True
    )
    team_id: Mapped[str] = mapped_column(
        ForeignKey("teams.id"), nullable=False, index=True
    )
    track_id: Mapped[str | None] = mapped_column(ForeignKey("tracks.id"), nullable=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    repo_url: Mapped[str | None] = mapped_column(String, nullable=True)
    demo_url: Mapped[str | None] = mapped_column(String, nullable=True)
    cover_image_path: Mapped[str | None] = mapped_column(String, nullable=True)
    screenshots: Mapped[str | None] = mapped_column(Text, nullable=True)
    tech_stack: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_draft: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_disqualified: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    event: Mapped[Event] = relationship(back_populates="projects")
    team: Mapped[Team] = relationship(back_populates="project")
    track: Mapped[Track | None] = relationship(back_populates="projects")
    votes: Mapped[list[Vote]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    comments: Mapped[list[Comment]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class RubricCriteria(Base):
    __tablename__ = "rubric_criteria"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    event_id: Mapped[str] = mapped_column(
        ForeignKey("events.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    weight: Mapped[int] = mapped_column(Integer, nullable=False)


class JudgeTrack(Base):
    __tablename__ = "judge_tracks"
    __table_args__ = (
        UniqueConstraint("event_id", "judge_id", "track_id", name="uq_judge_track"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(
        ForeignKey("events.id"), nullable=False, index=True
    )
    judge_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    track_id: Mapped[str] = mapped_column(
        ForeignKey("tracks.id"), nullable=False, index=True
    )


class Score(Base):
    __tablename__ = "scores"
    __table_args__ = (
        UniqueConstraint("judge_id", "project_id", "criteria_id", name="uq_score"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(
        ForeignKey("events.id"), nullable=False, index=True
    )
    judge_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id"), nullable=False, index=True
    )
    criteria_id: Mapped[str] = mapped_column(
        ForeignKey("rubric_criteria.id"), nullable=False
    )
    value: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    conflict_of_interest: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    actor_id: Mapped[str | None] = mapped_column(String, nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )


class JudgeInvitation(Base):
    __tablename__ = "judge_invitations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    event_id: Mapped[str] = mapped_column(
        ForeignKey("events.id"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String, nullable=False, index=True)
    track_ids: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String, default="pending", nullable=False)

    event: Mapped[Event] = relationship()


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    action_link: Mapped[str | None] = mapped_column(String, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship()


class PairwiseComparison(Base):
    __tablename__ = "pairwise_comparisons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(
        ForeignKey("events.id"), nullable=False, index=True
    )
    judge_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    winner_project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id"), nullable=False
    )
    loser_project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id"), nullable=False
    )
    criteria_id: Mapped[str | None] = mapped_column(
        ForeignKey("rubric_criteria.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )


class Vote(Base):
    __tablename__ = "votes"
    # One vote per user per event (community voting: pick ONE project)
    __table_args__ = (
        UniqueConstraint("user_id", "event_id", name="uq_vote_user_event"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(
        ForeignKey("events.id"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship()
    project: Mapped[Project] = relationship(back_populates="votes")
    event: Mapped[Event] = relationship()


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(
        ForeignKey("events.id"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id"), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship()
    project: Mapped[Project] = relationship(back_populates="comments")
    event: Mapped[Event] = relationship()


class WebhookSubscription(Base):
    __tablename__ = "webhook_subscriptions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    event_id: Mapped[str] = mapped_column(
        ForeignKey("events.id"), nullable=False, index=True
    )
    target_url: Mapped[str] = mapped_column(String, nullable=False)
    secret: Mapped[str] = mapped_column(String, nullable=False)
    events: Mapped[str] = mapped_column(String, default="*", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )

    event: Mapped[Event] = relationship()


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    subscription_id: Mapped[str] = mapped_column(
        ForeignKey("webhook_subscriptions.id"), nullable=False, index=True
    )
    event_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    event_name: Mapped[str] = mapped_column(String, nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    success: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Certificate(Base):
    __tablename__ = "certificates"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    event_id: Mapped[str] = mapped_column(
        ForeignKey("events.id"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    recipient_name: Mapped[str] = mapped_column(String, nullable=False)
    recipient_type: Mapped[str] = mapped_column(
        String, nullable=False
    )  # "participant" or "judge"
    title: Mapped[str] = mapped_column(String, nullable=False)
    track_name: Mapped[str | None] = mapped_column(String, nullable=True)
    placement: Mapped[str | None] = mapped_column(String, nullable=True)
    verification_code: Mapped[str] = mapped_column(
        String, unique=True, nullable=False, index=True
    )
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped[User] = relationship()
    event: Mapped[Event] = relationship()


class JudgeRecord(Base):
    __tablename__ = "judge_records"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    event_id: Mapped[str] = mapped_column(
        ForeignKey("events.id"), nullable=False, index=True
    )
    judge_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    judge_name: Mapped[str] = mapped_column(String, nullable=False)
    event_name: Mapped[str] = mapped_column(String, nullable=False)
    scores_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tracks_judged: Mapped[str] = mapped_column(String, default="", nullable=False)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    signature: Mapped[str] = mapped_column(String, nullable=False)

    user: Mapped[User] = relationship()
    event: Mapped[Event] = relationship()
