from __future__ import annotations

import pytest
from src.auth import make_session_token
from starlette.testclient import TestClient


def test_api_core_and_public_endpoints(client: TestClient):
    """Test T1 public and documentation API routes."""
    # OpenAPI & Documentation
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/docs").status_code == 200
    assert client.get("/redoc").status_code == 200
    assert client.get("/api/docs").status_code == 200

    # Public Gallery & Exploration
    assert client.get("/projects").status_code == 200
    assert client.get("/projects?q=platform").status_code == 200
    assert client.get("/projects/prj_01").status_code == 200
    assert client.get("/explore").status_code == 200
    assert client.get("/events/evt_01").status_code == 200
    assert client.get("/users/prt_1/avatar.svg").status_code == 200
    assert client.get("/vote").status_code == 200
    assert client.get("/login").status_code == 200
    assert client.get("/register").status_code == 200


def test_api_judge_and_role_isolation(client: TestClient, auth_cookies):
    """Test T2 judge scoring and role isolation endpoints."""
    # Judge sees own scores
    resp = client.get("/api/judge/scores", cookies=auth_cookies["judge_a"])
    assert resp.status_code == 200

    # Judge blocked from peer scores (403)
    resp = client.get("/api/judge/scores?judge=jdg_01", cookies=auth_cookies["judge_b"])
    assert resp.status_code == 403

    # Participant blocked from judge scores (403)
    resp = client.get("/api/judge/scores", cookies=auth_cookies["participant"])
    assert resp.status_code == 403

    # Visitor blocked from judge scores (401)
    resp = client.get("/api/judge/scores")
    assert resp.status_code == 401

    # Organizer CSV export
    resp = client.get("/api/export.csv", cookies=auth_cookies["organizer"])
    assert resp.status_code == 200
    assert "project_id" in resp.text

    # Judge views
    assert (
        client.get(
            "/judge/evt_01/dashboard", cookies=auth_cookies["judge_a"]
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/judge/evt_01/project/prj_01", cookies=auth_cookies["judge_a"]
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/judge/evt_01/pairwise", cookies=auth_cookies["judge_a"]
        ).status_code
        == 200
    )

    # Organizer dashboard & management views
    assert (
        client.get(
            "/organizer/evt_01/dashboard", cookies=auth_cookies["organizer"]
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/organizer/evt_01/rubric", cookies=auth_cookies["organizer"]
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/organizer/evt_01/judges", cookies=auth_cookies["organizer"]
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/organizer/evt_01/tracks", cookies=auth_cookies["organizer"]
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/organizer/evt_01/projects", cookies=auth_cookies["organizer"]
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/organizer/evt_01/teams", cookies=auth_cookies["organizer"]
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/organizer/evt_01/results", cookies=auth_cookies["organizer"]
        ).status_code
        == 200
    )


def test_api_public_community_and_audit(client: TestClient, auth_cookies):
    """Test T3 comments, voting status, and audit log endpoints."""
    # Comments list
    assert client.get("/api/projects/prj_01/comments").status_code == 200

    # Post comment as participant
    resp = client.post(
        "/api/projects/prj_01/comments",
        json={"content": "Comprehensive endpoint test comment"},
        cookies=auth_cookies["participant"],
    )
    assert resp.status_code == 200

    # Visitor cannot post comment
    assert (
        client.post(
            "/api/projects/prj_01/comments", json={"content": "Anonymous"}
        ).status_code
        == 401
    )

    # Vote status
    assert (
        client.get(
            "/api/projects/prj_01/vote-status", cookies=auth_cookies["participant"]
        ).status_code
        == 200
    )

    # Visitor cannot vote
    assert client.post("/api/projects/prj_01/vote").status_code == 401

    # Delete vote works safely
    assert (
        client.delete(
            "/api/projects/prj_01/vote", cookies=auth_cookies["participant"]
        ).status_code
        == 200
    )

    # Audit API and UI
    assert (
        client.get(
            "/api/events/evt_01/audit", cookies=auth_cookies["organizer"]
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/organizer/evt_01/audit", cookies=auth_cookies["organizer"]
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/organizer/evt_01/audit/export.csv", cookies=auth_cookies["organizer"]
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/organizer/evt_01/audit/export.json", cookies=auth_cookies["organizer"]
        ).status_code
        == 200
    )


def test_api_t4_stretch_suite(client: TestClient, auth_cookies):
    """Test T4 Webhooks, Certificates, Signed Records, Widgets, and Bulk Data."""
    # Webhooks CRUD
    wh_resp = client.post(
        "/api/events/evt_01/webhooks",
        json={
            "target_url": "https://example.com/api-test-hook",
            "events": "project.submitted",
        },
        cookies=auth_cookies["organizer"],
    )
    assert wh_resp.status_code == 200
    sub_id = wh_resp.json()["id"]

    assert (
        client.get(
            "/api/events/evt_01/webhooks", cookies=auth_cookies["organizer"]
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/events/evt_01/webhooks/{sub_id}/test",
            cookies=auth_cookies["organizer"],
        ).status_code
        == 200
    )
    assert (
        client.delete(
            f"/api/events/evt_01/webhooks/{sub_id}", cookies=auth_cookies["organizer"]
        ).status_code
        == 200
    )

    # Certificates
    assert (
        client.post(
            "/api/events/evt_01/certificates/generate",
            cookies=auth_cookies["organizer"],
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/participant/evt_01/certificate", cookies=auth_cookies["participant"]
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/judge/evt_01/certificate", cookies=auth_cookies["judge_a"]
        ).status_code
        == 200
    )

    # Signed Judge Record & Public Verification
    rec_resp = client.get("/api/judge/evt_01/record", cookies=auth_cookies["judge_a"])
    assert rec_resp.status_code == 200
    rec_id = rec_resp.json()["id"]
    assert client.get(f"/verify/record/{rec_id}").status_code == 200

    # Embeddable Gallery Widget
    assert client.get("/embed/gallery/evt_01?theme=dark").status_code == 200

    # Bulk Export and Import
    assert (
        client.get(
            "/api/events/evt_01/export/full.json", cookies=auth_cookies["organizer"]
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/api/events/evt_01/export/projects.csv", cookies=auth_cookies["organizer"]
        ).status_code
        == 200
    )
    import_resp = client.post(
        "/api/events/evt_01/import/projects",
        json=[{"title": "Bulk Ingest Test", "summary": "Bulk ingest test summary"}],
        cookies=auth_cookies["organizer"],
    )
    assert import_resp.status_code == 200


def test_api_participant_and_admin_views(client: TestClient, auth_cookies):
    """Test Notifications, participant dashboard and admin routes."""
    # Notifications
    assert (
        client.get(
            "/api/notifications/", cookies=auth_cookies["participant"]
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/api/notifications/unread_count", cookies=auth_cookies["participant"]
        ).status_code
        == 200
    )

    # Participant Views
    assert (
        client.get("/participant/home", cookies=auth_cookies["participant"]).status_code
        == 200
    )
    assert (
        client.get(
            "/participant/registrations", cookies=auth_cookies["participant"]
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/participant/evt_01/dashboard", cookies=auth_cookies["participant"]
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/participant/evt_01/team", cookies=auth_cookies["participant"]
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/participant/evt_01/matchmaking", cookies=auth_cookies["participant"]
        ).status_code
        == 200
    )
    assert (
        client.get("/profile", cookies=auth_cookies["participant"]).status_code == 200
    )

    # Admin
    admin_cookie = {"session": make_session_token("adm_1")}
    assert client.get("/admin/dashboard", cookies=admin_cookie).status_code == 200
