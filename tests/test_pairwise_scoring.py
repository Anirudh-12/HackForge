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


def test_judge_recusal_removes_score_and_conflict_handling(client, auth_cookies):
    db = SessionLocal()
    try:
        client.cookies.set("session", auth_cookies["judge_a"]["session"])

        from src.models import RubricCriteria
        criteria = db.query(RubricCriteria).filter_by(event_id="evt_01").all()
        assert len(criteria) > 0

        # First, ensure prj_02 is scored normally with a score of 5 on all criteria
        score_data = {f"criteria_{c.id}": "5" for c in criteria}
        score_data["comment"] = "Great project"
        score_resp = client.post(
            "/judge/evt_01/project/prj_02",
            data=score_data,
            follow_redirects=True,
        )
        assert score_resp.status_code == 200

        # Check DB that score exists and conflict_of_interest is False
        db.expire_all()
        scores_before = db.query(Score).filter_by(
            event_id="evt_01", judge_id="jdg_01", project_id="prj_02"
        ).all()
        assert len(scores_before) == len(criteria)
        for s in scores_before:
            assert s.value == 5
            assert s.conflict_of_interest is False

        # Also vote on prj_02 in pairwise
        client.post(
            "/judge/evt_01/pairwise",
            data={"winner_id": "prj_02", "loser_id": "prj_03"},
            follow_redirects=True,
        )

        # Now recuse from prj_02
        recuse_resp = client.post(
            "/judge/evt_01/project/prj_02",
            data={"recuse": "true"},
            follow_redirects=True,
        )
        assert recuse_resp.status_code == 200

        # DB verification: conflict_of_interest is True, value is 0
        db.expire_all()
        recused_scores = db.query(Score).filter_by(
            event_id="evt_01", judge_id="jdg_01", project_id="prj_02"
        ).all()
        assert len(recused_scores) > 0
        for s in recused_scores:
            assert s.conflict_of_interest is True
            assert s.value == 0

        # Verify pairwise comparisons involving prj_02 for this judge were deleted
        from src.models import PairwiseComparison
        from sqlalchemy import or_
        comps = db.query(PairwiseComparison).filter(
            PairwiseComparison.event_id == "evt_01",
            PairwiseComparison.judge_id == "jdg_01",
            or_(
                PairwiseComparison.winner_project_id == "prj_02",
                PairwiseComparison.loser_project_id == "prj_02",
            ),
        ).all()
        assert len(comps) == 0

        # Dashboard check: must show Recused badge, must NOT show numeric score for prj_02
        dash_resp = client.get("/judge/evt_01/dashboard")
        assert dash_resp.status_code == 200
        assert "Recused (Conflict)" in dash_resp.text
        assert "No score submitted" in dash_resp.text

        # Scoring page check: shows recusal notice, and radios are not checked
        score_page_resp = client.get("/judge/evt_01/project/prj_02")
        assert score_page_resp.status_code == 200
        assert "Recused from Project" in score_page_resp.text
        assert ' checked' not in score_page_resp.text and 'checked>' not in score_page_resp.text

        # Re-score prj_02 to verify judge can revoke recusal if needed
        unrecuse_data = {f"criteria_{c.id}": "4" for c in criteria}
        unrecuse_data["comment"] = "Revoked recusal"
        unrecuse_resp = client.post(
            "/judge/evt_01/project/prj_02",
            data=unrecuse_data,
            follow_redirects=True,
        )
        assert unrecuse_resp.status_code == 200
        db.expire_all()
        scores_after = db.query(Score).filter_by(
            event_id="evt_01", judge_id="jdg_01", project_id="prj_02"
        ).all()
        for s in scores_after:
            assert s.conflict_of_interest is False
            assert s.value == 4
    finally:
        client.cookies.clear()
        db.close()


def test_pairwise_reset_comparisons(client, auth_cookies):
    db = SessionLocal()
    try:
        from src.models import PairwiseComparison
        client.cookies.set("session", auth_cookies["judge_a"]["session"])

        # Make a pairwise comparison
        vote_resp = client.post(
            "/judge/evt_01/pairwise",
            data={"winner_id": "prj_01", "loser_id": "prj_02"},
            follow_redirects=True,
        )
        assert vote_resp.status_code == 200

        # Verify comparisons exist in DB
        comps_before = db.query(PairwiseComparison).filter_by(
            event_id="evt_01", judge_id="jdg_01"
        ).count()
        assert comps_before > 0

        # Verify reset button is in pairwise page
        page_resp = client.get("/judge/evt_01/pairwise")
        assert page_resp.status_code == 200
        assert "Reset Comparisons" in page_resp.text

        # Click Reset Comparisons
        reset_resp = client.post(
            "/judge/evt_01/pairwise/reset",
            follow_redirects=True,
        )
        assert reset_resp.status_code == 200
        assert "reset" in str(reset_resp.url).lower() or "reset" in reset_resp.text.lower()

        # Verify comparisons are 0 in DB
        db.expire_all()
        comps_after = db.query(PairwiseComparison).filter_by(
            event_id="evt_01", judge_id="jdg_01"
        ).count()
        assert comps_after == 0

        # Verify auto-generated pairwise score records were cleaned up
        pairwise_scores = db.query(Score).filter_by(
            event_id="evt_01", judge_id="jdg_01"
        ).all()
        for s in pairwise_scores:
            assert not (s.comment and s.comment.startswith("Pairwise ELO:"))
    finally:
        client.cookies.clear()
        db.close()

