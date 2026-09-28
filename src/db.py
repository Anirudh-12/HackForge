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
