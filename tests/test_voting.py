from src.db import SessionLocal
from src.models import Project, TeamMember


def test_participant_can_vote_and_unvote(client, auth_cookies):
    # Cast vote for prj_02 (which is not owned by prt_1)
    res = client.post("/api/projects/prj_02/vote", cookies=auth_cookies["participant"])
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True

    # Vote status for prt_1 should show voted == True
    status_res = client.get("/api/projects/prj_02/vote-status", cookies=auth_cookies["participant"])
    assert status_res.status_code == 200
    assert status_res.json()["voted"] is True

    # Toggle unvote
    del_res = client.delete("/api/projects/prj_02/vote", cookies=auth_cookies["participant"])
    assert del_res.status_code == 200
    assert del_res.json()["voted"] is False


def test_self_voting_is_forbidden(client, auth_cookies):
    # Find prt_1's own project
    db = SessionLocal()
    tm = db.query(TeamMember).filter_by(user_id="prt_1").first()
    own_project = db.query(Project).filter_by(team_id=tm.team_id).first()
    db.close()

    if own_project:
        res = client.post(f"/api/projects/{own_project.id}/vote", cookies=auth_cookies["participant"])
        assert res.status_code == 403
        assert "Self-voting is strictly prohibited" in res.json()["detail"]


def test_visitor_cannot_vote(client):
    res = client.post("/api/projects/prj_02/vote")
    assert res.status_code in (401, 403)


def test_results_hidden_during_voting_window(client, auth_cookies):
    # Results tally must be hidden from visitors and participants
    res_visitor = client.get("/api/projects/prj_02/vote-status")
    assert res_visitor.status_code == 200
    assert res_visitor.json().get("vote_count") is None
    assert res_visitor.json().get("results_hidden") is True

    res_prt = client.get("/api/projects/prj_02/vote-status", cookies=auth_cookies["participant"])
    assert res_prt.status_code == 200
    assert res_prt.json().get("vote_count") is None
    assert res_prt.json().get("results_hidden") is True
