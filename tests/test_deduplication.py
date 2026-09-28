import pytest
from src.auth import make_session_token
from src.db import SessionLocal
from src.models import Event, Track, RubricCriteria, Team, Project, PairwiseComparison

def test_prevent_duplicate_event_creation(client, auth_cookies):
    # Try creating an event with a name that already exists (evt_01 name: "Sample Hack 2026")
    resp = client.post(
        "/organizer/events",
        data={"name": "Sample Hack 2026"},
        cookies=auth_cookies["organizer"],
    )
    assert resp.status_code == 400
    assert "already exists" in resp.text.lower()

def test_prevent_duplicate_track_creation(client, auth_cookies):
    # Try adding a track with a name that already exists in evt_01
    resp = client.post(
        "/organizer/evt_01/tracks",
        data={"name": "Developer tools", "prize": "$1,000"},
        cookies=auth_cookies["organizer"],
    )
    assert resp.status_code == 400
    assert "already exists" in resp.text.lower()

def test_prevent_duplicate_rubric_creation(client, auth_cookies):
    # evt_06 is upcoming so rubric editing is unlocked
    resp = client.post(
        "/organizer/evt_06/rubric",
        data={"name": "Architecture & Scalability", "weight": "10"},
        cookies=auth_cookies["organizer"],
    )
    assert resp.status_code == 400
    assert "already exists" in resp.text.lower()

def test_prevent_duplicate_team_name_in_event(client):
    # Create valid session cookie for usr_bob who doesn't lead a team in evt_01
    bob_cookie = {"session": make_session_token("usr_bob")}
    resp = client.post(
        "/participant/evt_01/team",
        data={"action": "create", "name": "AmberSwitch"},
        cookies=bob_cookie,
    )
    assert resp.status_code == 400
    assert "already exists in this hackathon" in resp.text

def test_pairwise_comparison_deduplication(client, auth_cookies):
    # Submitting pairwise comparison multiple times between the same projects
    client.cookies.set("session", auth_cookies["judge_a"]["session"])
    try:
        resp1 = client.post(
            "/judge/evt_01/pairwise",
            data={"winner_id": "prj_01", "loser_id": "prj_02"},
            follow_redirects=True,
        )
        assert resp1.status_code == 200

        # Change decision or resubmit
        resp2 = client.post(
            "/judge/evt_01/pairwise",
            data={"winner_id": "prj_02", "loser_id": "prj_01"},
            follow_redirects=True,
        )
        assert resp2.status_code == 200

        db = SessionLocal()
        comps = db.query(PairwiseComparison).filter_by(
            event_id="evt_01",
            judge_id="jdg_01",
        ).all()
        # Find comparisons between prj_01 and prj_02
        relevant = [
            c for c in comps
            if {c.winner_project_id, c.loser_project_id} == {"prj_01", "prj_02"}
        ]
        assert len(relevant) == 1
        assert relevant[0].winner_project_id == "prj_02"
        assert relevant[0].loser_project_id == "prj_01"
        db.close()
    finally:
        client.cookies.clear()
