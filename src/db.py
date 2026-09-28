from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{DATA_DIR / 'hackforge.db'}")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from src import models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    from sqlalchemy import text
    with engine.connect() as conn:
        try:
            res = conn.execute(text("PRAGMA table_info(events)")).fetchall()
            existing_cols = {row[1] for row in res}
            new_cols = [
                ("tagline", "TEXT"),
                ("event_starts", "DATETIME"),
                ("event_ends", "DATETIME"),
                ("registrations_open", "DATETIME"),
                ("registrations_close", "DATETIME"),
                ("results_date", "DATETIME"),
                ("prizes_json", "TEXT"),
                ("side_quests_json", "TEXT"),
                ("location", "TEXT"),
                ("format", "TEXT"),
            ]
            for col_name, col_type in new_cols:
                if col_name not in existing_cols:
                    conn.execute(text(f"ALTER TABLE events ADD COLUMN {col_name} {col_type}"))
            conn.commit()
        except Exception:
            pass

        try:
            res = conn.execute(text("PRAGMA table_info(teams)")).fetchall()
            existing_team_cols = {row[1] for row in res}
            if "leader_id" not in existing_team_cols:
                conn.execute(text("ALTER TABLE teams ADD COLUMN leader_id TEXT"))
            conn.execute(text("""
                UPDATE teams
                SET leader_id = (
                    SELECT user_id FROM team_members
                    WHERE team_members.team_id = teams.id
                    ORDER BY id ASC LIMIT 1
                )
                WHERE leader_id IS NULL
            """))
            conn.commit()
        except Exception:
            pass

        unique_indexes = [
            ("uq_event_name", "CREATE UNIQUE INDEX IF NOT EXISTS uq_event_name ON events(name)"),
            ("uq_track_event_name", "CREATE UNIQUE INDEX IF NOT EXISTS uq_track_event_name ON tracks(event_id, name)"),
            ("uq_rubric_event_name", "CREATE UNIQUE INDEX IF NOT EXISTS uq_rubric_event_name ON rubric_criteria(event_id, name)"),
            ("uq_pairwise_comparison", "CREATE UNIQUE INDEX IF NOT EXISTS uq_pairwise_comparison ON pairwise_comparisons(event_id, judge_id, winner_project_id, loser_project_id)"),
            ("uq_certificate_event_user_type", "CREATE UNIQUE INDEX IF NOT EXISTS uq_certificate_event_user_type ON certificates(event_id, user_id, recipient_type)"),
            ("uq_judge_record", "CREATE UNIQUE INDEX IF NOT EXISTS uq_judge_record ON judge_records(event_id, judge_id)"),
        ]
        for _, idx_sql in unique_indexes:
            try:
                conn.execute(text(idx_sql))
            except Exception:
                pass
        try:
            conn.commit()
        except Exception:
            pass


