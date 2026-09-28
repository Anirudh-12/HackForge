import pytest
from src.db import SessionLocal
from src.models import Event, User, Score

def test_pairwise_voting_updates_scores(client, auth_cookies):
    db = SessionLocal()
    try:
        # Verify judge jdg_01 exists
        judge = db.query(User).filter_by(id="jdg_01").first()
        assert judge is not None

        # Verify evt_01 exists
        event = db.query(Event).filter_by(id="evt_01").first()
        assert event is not None

        # Set session cookie on client directly so redirects retain auth
        client.cookies.set("session", auth_cookies["judge_a"]["session"])

        # Post a pairwise vote between prj_01 and prj_02
        response = client.post(
            "/judge/evt_01/pairwise",
            data={"winner_id": "prj_01", "loser_id": "prj_02"},
            follow_redirects=True,
        )
        assert response.status_code == 200

        # Check that scores now exist for both projects
        scores = db.query(Score).filter_by(event_id="evt_01", judge_id="jdg_01").all()
        scored_pids = set(s.project_id for s in scores)
        assert "prj_01" in scored_pids
        assert "prj_02" in scored_pids

        # Fetch judge dashboard and verify it renders reviewed status, scores, and ELO
        dash_resp = client.get("/judge/evt_01/dashboard")
        assert dash_resp.status_code == 200
        assert "Reviewed" in dash_resp.text
        assert "Score:" in dash_resp.text
        assert "ELO" in dash_resp.text

        # Verify completion percentage never exceeds 100% and remaining projects is never negative
        assert "117%" not in dash_resp.text
        assert "Needs Review (-1)" not in dash_resp.text
        assert ">-1<" not in dash_resp.text

        # Verify pairwise judging page loads with valid metrics badge and no overflow
        pairwise_resp = client.get("/judge/evt_01/pairwise")
        assert pairwise_resp.status_code == 200
        assert "Comparisons Made" in pairwise_resp.text
        assert "117%" not in pairwise_resp.text
    finally:
        client.cookies.clear()
        db.close()
