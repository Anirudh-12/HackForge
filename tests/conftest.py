import re
import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.auth import make_session_token


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
