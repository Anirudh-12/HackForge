import os
import re
import shutil
import tempfile
from pathlib import Path

# Isolate test database so test runs never pollute data/hackforge.db
TEST_DIR = Path(tempfile.mkdtemp(prefix="hackforge_test_"))
TEST_DB = TEST_DIR / "test_hackforge.db"
os.environ["DATA_DIR"] = str(TEST_DIR)
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.auth import make_session_token


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    from src.db import init_db, SessionLocal
    from src.seed import seed
    init_db()
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()
    yield
    try:
        if TEST_DIR.exists():
            shutil.rmtree(TEST_DIR, ignore_errors=True)
    except Exception:
        pass


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def auth_cookies():
    # Helper to generate valid HMAC session cookies for test roles
    return {
        "organizer": {"session": make_session_token("org_1")},
        "judge_a": {"session": make_session_token("jdg_01")},
        "judge_b": {"session": make_session_token("jdg_02")},
        "participant": {"session": make_session_token("prt_1")},
        "participant_2": {"session": make_session_token("prt_2")},
    }
