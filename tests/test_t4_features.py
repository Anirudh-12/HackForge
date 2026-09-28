from __future__ import annotations

import json

from src.auth import make_session_token
from src.db import SessionLocal
from src.models import (
    Certificate,
    Event,
    EventMember,
    JudgeRecord,
    Project,
    Team,
    TeamMember,
    User,
    WebhookSubscription,
)
from src.webhooks import generate_judge_record_signature, verify_judge_record_signature
from starlette.testclient import TestClient


def test_openapi_schema_and_docs_portal(client: TestClient):
    # Verify raw OpenAPI JSON schema
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    assert schema["info"]["title"] == "HackForge API"
    assert "components" in schema
    assert "securitySchemes" in schema["components"]
    assert "CookieAuth" in schema["components"]["securitySchemes"]
    assert "BearerAuth" in schema["components"]["securitySchemes"]

    # Verify interactive API docs hub
    docs_resp = client.get("/api/docs")
    assert docs_resp.status_code == 200
    assert "HackForge Developer" in docs_resp.text
    assert "Organizer Operations" in docs_resp.text
    assert "Judge Operations" in docs_resp.text
    assert "Participant Operations" in docs_resp.text


def test_webhook_crud_and_permissions(client: TestClient, auth_cookies):
    # Participant should be blocked from creating webhooks
    resp = client.post(
        "/api/events/evt_01/webhooks",
        json={"target_url": "https://example.org/hook", "events": "*"},
        cookies=auth_cookies["participant"],
    )
    assert resp.status_code == 403

    # Organizer creates webhook
    resp = client.post(
        "/api/events/evt_01/webhooks",
        json={
            "target_url": "https://example.org/webhook",
            "events": "project.submitted,vote.cast",
        },
        cookies=auth_cookies["organizer"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["target_url"] == "https://example.org/webhook"
    assert data["secret"].startswith("whsec_")
    sub_id = data["id"]

    # List webhooks
    list_resp = client.get(
        "/api/events/evt_01/webhooks", cookies=auth_cookies["organizer"]
    )
    assert list_resp.status_code == 200
    assert any(s["id"] == sub_id for s in list_resp.json())

    # Test ping
    ping_resp = client.post(
        f"/api/events/evt_01/webhooks/{sub_id}/test", cookies=auth_cookies["organizer"]
    )
    assert ping_resp.status_code == 200
    assert ping_resp.json()["success"] is True

    # Delete webhook
    del_resp = client.delete(
        f"/api/events/evt_01/webhooks/{sub_id}", cookies=auth_cookies["organizer"]
    )
    assert del_resp.status_code == 200
    assert del_resp.json()["success"] is True


def test_certificates_generation_and_public_verification(
    client: TestClient, auth_cookies
):
    # Bulk generate certificates as organizer
    resp = client.post(
        "/api/events/evt_01/certificates/generate", cookies=auth_cookies["organizer"]
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["certificates_generated"] > 0 or data.get("total_certificates", 0) > 0

    # Query one certificate from DB
    db = SessionLocal()
    cert = db.query(Certificate).filter(Certificate.event_id == "evt_01").first()
    assert cert is not None
    cert_id = cert.id
    v_code = cert.verification_code
    r_name = cert.recipient_name
    db.close()

    # Get certificate metadata via API
    cert_data = client.get(f"/api/certificates/{cert_id}").json()
    assert cert_data["verification_code"] == v_code
    assert cert_data["recipient_name"] == r_name

    # Download SVG
    svg_resp = client.get(f"/api/certificates/{cert_id}/download")
    assert svg_resp.status_code == 200
    assert svg_resp.headers["content-type"] == "image/svg+xml"
    assert "<svg" in svg_resp.text
    assert r_name in svg_resp.text

    # Public verification
    verify_resp = client.get(f"/verify/certificate/{v_code}")
    assert verify_resp.status_code == 200
    assert "Verified Certificate" in verify_resp.text
    assert r_name in verify_resp.text

    # Invalid code returns 404
    bad_verify = client.get("/verify/certificate/INVALID-CODE-999")
    assert bad_verify.status_code == 404


def test_signed_judge_participation_records(client: TestClient, auth_cookies):
    # Judge requests their signed record
    resp = client.get("/api/judge/evt_01/record", cookies=auth_cookies["judge_a"])
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_valid"] is True
    assert len(data["signature"]) == 64  # SHA-256 hex string
    assert data["judge_id"] == "jdg_01"

    rec_id = data["id"]

    # Public verification page
    pub_resp = client.get(f"/verify/record/{rec_id}")
    assert pub_resp.status_code == 200
    assert "Verified Record" in pub_resp.text
    assert data["judge_name"] in pub_resp.text

    # Cryptographic anti-tamper test
    is_valid = verify_judge_record_signature(
        data["signature"],
        data["judge_id"],
        data["event_id"],
        data["scores_count"],
        data["issued_at"],
    )
    assert is_valid is True

    # Tampered score count fails verification
    tampered = verify_judge_record_signature(
        data["signature"],
        data["judge_id"],
        data["event_id"],
        data["scores_count"] + 999,
        data["issued_at"],
    )
    assert tampered is False


def test_embeddable_gallery_widget(client: TestClient):
    # Public widget requires no authentication
    resp = client.get("/embed/gallery/evt_01?theme=dark")
    assert resp.status_code == 200
    assert "Project Showcase" in resp.text
    assert "Powered by HackForge" in resp.text
    assert "widgetSearch" in resp.text


def test_bulk_export_and_import(client: TestClient, auth_cookies):
    # Full JSON export
    resp = client.get(
        "/api/events/evt_01/export/full.json", cookies=auth_cookies["organizer"]
    )
    assert resp.status_code == 200
    export_data = resp.json()
    assert "event" in export_data
    assert "projects" in export_data
    assert "scores" in export_data
    assert export_data["projects_count"] > 0

    # Projects CSV export
    csv_resp = client.get(
        "/api/events/evt_01/export/projects.csv", cookies=auth_cookies["organizer"]
    )
    assert csv_resp.status_code == 200
    assert "project_id,title,summary" in csv_resp.text

    # Bulk import new project
    import uuid
    p_id = f"prj_import_{uuid.uuid4().hex[:8]}"
    import_payload = [
        {
            "id": p_id,
            "title": "Autonomous Agent Mesh",
            "summary": "Decentralized consensus framework",
            "tech_stack": "Rust, Tokio",
        }
    ]
    import_resp = client.post(
        "/api/events/evt_01/import/projects",
        json=import_payload,
        cookies=auth_cookies["organizer"],
    )
    assert import_resp.status_code == 200
    assert import_resp.json()["imported_count"] == 1

    # Verify project exists in database
    db = SessionLocal()
    imported_proj = db.get(Project, p_id)
    assert imported_proj is not None
    assert imported_proj.title == "Autonomous Agent Mesh"
    t_id = imported_proj.team_id
    db.delete(imported_proj)
    if t_id:
        team = db.get(Team, t_id)
        if team:
            db.delete(team)
    db.commit()
    db.close()


def test_participation_certificate_only_for_submitted_projects(client: TestClient, auth_cookies):
    import uuid
    db = SessionLocal()
    eid = "evt_01"

    # 1. Create a user who HAS submitted a project
    u_sub = User(id=f"u_sub_{uuid.uuid4().hex[:6]}", email=f"sub_{uuid.uuid4().hex[:4]}@example.com", name="Submitted Participant")
    # 2. Create a user who has a team and draft project (NOT submitted)
    u_draft = User(id=f"u_draft_{uuid.uuid4().hex[:6]}", email=f"draft_{uuid.uuid4().hex[:4]}@example.com", name="Draft Participant")
    # 3. Create a user who has a team with NO project at all
    u_noproj = User(id=f"u_noproj_{uuid.uuid4().hex[:6]}", email=f"noproj_{uuid.uuid4().hex[:4]}@example.com", name="NoProj Participant")
    # 4. Create a user who has NO team at all
    u_noteam = User(id=f"u_noteam_{uuid.uuid4().hex[:6]}", email=f"noteam_{uuid.uuid4().hex[:4]}@example.com", name="NoTeam Participant")

    t_sub = Team(id=f"t_{uuid.uuid4().hex[:6]}", event_id=eid, name="Submitted Team", leader_id=u_sub.id)
    t_draft = Team(id=f"t_{uuid.uuid4().hex[:6]}", event_id=eid, name="Draft Team", leader_id=u_draft.id)
    t_noproj = Team(id=f"t_{uuid.uuid4().hex[:6]}", event_id=eid, name="NoProj Team", leader_id=u_noproj.id)

    p_sub = Project(
        id=f"p_sub_{uuid.uuid4().hex[:6]}",
        event_id=eid,
        team_id=t_sub.id,
        title="Fully Submitted App",
        summary="A real submission",
        cover_image_path="/static/covers/sample.png",
        is_draft=False,
        is_disqualified=False,
    )
    p_draft = Project(
        id=f"p_draft_{uuid.uuid4().hex[:6]}",
        event_id=eid,
        team_id=t_draft.id,
        title="Draft App In Progress",
        summary="Not yet submitted",
        cover_image_path="/static/covers/sample.png",
        is_draft=True,
        is_disqualified=False,
    )

    try:
        for u in [u_sub, u_draft, u_noproj, u_noteam]:
            db.add(u)
            db.add(EventMember(event_id=eid, user_id=u.id, role="participant"))
        db.flush()

        db.add_all([t_sub, t_draft, t_noproj])
        db.flush()

        db.add(TeamMember(team_id=t_sub.id, user_id=u_sub.id))
        db.add(TeamMember(team_id=t_draft.id, user_id=u_draft.id))
        db.add(TeamMember(team_id=t_noproj.id, user_id=u_noproj.id))

        db.add_all([p_sub, p_draft])
        db.commit()

        # Generate certificates as organizer
        resp = client.post(f"/api/events/{eid}/certificates/generate", cookies=auth_cookies["organizer"])
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        # Check Certificate records in DB
        cert_sub = db.query(Certificate).filter_by(event_id=eid, user_id=u_sub.id, recipient_type="participant").first()
        cert_draft = db.query(Certificate).filter_by(event_id=eid, user_id=u_draft.id, recipient_type="participant").first()
        cert_noproj = db.query(Certificate).filter_by(event_id=eid, user_id=u_noproj.id, recipient_type="participant").first()
        cert_noteam = db.query(Certificate).filter_by(event_id=eid, user_id=u_noteam.id, recipient_type="participant").first()

        # ONLY u_sub should have received a certificate!
        assert cert_sub is not None, "Submitted participant MUST receive a certificate"
        assert cert_draft is None, "Participant with draft project MUST NOT receive a certificate"
        assert cert_noproj is None, "Participant with no project MUST NOT receive a certificate"
        assert cert_noteam is None, "Participant with no team MUST NOT receive a certificate"

        # Verify endpoint works for submitted user
        v_resp = client.get(f"/verify/certificate/{cert_sub.verification_code}")
        assert v_resp.status_code == 200
        assert "Verified Certificate" in v_resp.text
        assert u_sub.name in v_resp.text

        # Verify certificate HTML page for submitted user
        sub_cookie = {"session": make_session_token(u_sub.id)}
        page_sub = client.get(f"/participant/{eid}/certificate", cookies=sub_cookie)
        assert page_sub.status_code == 200
        assert "Certificate of Participation" in page_sub.text
        assert u_sub.name in page_sub.text

        # Verify certificate HTML page for draft/unsubmitted user shows submission required notice
        draft_cookie = {"session": make_session_token(u_draft.id)}
        page_draft = client.get(f"/participant/{eid}/certificate", cookies=draft_cookie)
        assert page_draft.status_code == 200
        assert "Project Submission Required" in page_draft.text
        assert 'class="cert-paper"' not in page_draft.text
        assert "Official Hackathon Record of Achievement" not in page_draft.text
        assert "Verification ID:" not in page_draft.text

        # Verify certificate HTML page for user without team
        noteam_cookie = {"session": make_session_token(u_noteam.id)}
        page_noteam = client.get(f"/participant/{eid}/certificate", cookies=noteam_cookie)
        assert page_noteam.status_code == 200
        assert "Project Submission Required" in page_noteam.text

    finally:
        # Clean up created test entities
        c = db.query(Certificate).filter_by(event_id=eid, user_id=u_sub.id).first()
        if c:
            db.delete(c)
        for p in [p_sub, p_draft]:
            p_obj = db.get(Project, p.id)
            if p_obj:
                db.delete(p_obj)
        for t in [t_sub, t_draft, t_noproj]:
            t_obj = db.get(Team, t.id)
            if t_obj:
                db.delete(t_obj)
        for u in [u_sub, u_draft, u_noproj, u_noteam]:
            db.query(EventMember).filter_by(event_id=eid, user_id=u.id).delete()
            u_obj = db.get(User, u.id)
            if u_obj:
                db.delete(u_obj)
        db.commit()
        db.close()

