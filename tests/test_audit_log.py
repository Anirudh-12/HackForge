from fastapi.testclient import TestClient
from src.auth import make_session_token
from src.db import SessionLocal
from src.main import app
from src.models import AuditLog, Event, Project, RubricCriteria, Score


def test_audit_log_redirect():
    client = TestClient(app)
    token = make_session_token("org_1")
    client.cookies.set("session", token)

    res = client.get("/organizer/audit", follow_redirects=False)
    assert res.status_code in (302, 307)
    assert "/organizer/" in res.headers["location"]
    assert "/audit" in res.headers["location"]


def test_audit_log_page_renders_for_organizer():
    client = TestClient(app)
    token = make_session_token("org_1")
    client.cookies.set("session", token)

    res = client.get("/organizer/evt_01/audit")
    assert res.status_code == 200
    assert "Audit Log" in res.text
    assert "Compliance Ledger" in res.text
    assert "Immutable Append-Only Ledger" in res.text
    assert "audit-row" in res.text


def test_audit_log_role_isolation():
    client = TestClient(app)
    # Participant should be forbidden or redirected
    p_token = make_session_token("prt_1")
    client.cookies.set("session", p_token)

    res = client.get("/organizer/evt_01/audit", follow_redirects=False)
    assert res.status_code in (403, 302, 303, 307)


def test_audit_log_category_and_search_filters():
    client = TestClient(app)
    token = make_session_token("org_1")
    client.cookies.set("session", token)

    # Filter by category voting
    res = client.get("/organizer/evt_01/audit?category=voting")
    assert res.status_code == 200
    assert "Community Votes" in res.text

    # Search keyword
    res_search = client.get("/organizer/evt_01/audit?q=priya1")
    assert res_search.status_code == 200
    assert "priya1" in res_search.text


def test_audit_log_exports():
    client = TestClient(app)
    token = make_session_token("org_1")
    client.cookies.set("session", token)

    # CSV Export
    csv_res = client.get("/organizer/evt_01/audit/export.csv")
    assert csv_res.status_code == 200
    assert "text/csv" in csv_res.headers.get("content-type", "")
    lines = csv_res.text.strip().splitlines()
    assert len(lines) > 1
    assert "Entry ID" in lines[0]
    assert "Ledger SHA256 Checksum" in lines[0]

    # JSON Export
    json_res = client.get("/organizer/evt_01/audit/export.json")
    assert json_res.status_code == 200
    data = json_res.json()
    assert "records" in data
    assert data["integrity_status"] == "VALID_SEQUENTIAL_CHAIN"
    assert len(data["records"]) > 0


def test_audit_log_rest_api():
    client = TestClient(app)
    token = make_session_token("org_1")
    client.cookies.set("session", token)

    res = client.get("/api/events/evt_01/audit?per_page=5")
    assert res.status_code == 200
    data = res.json()
    assert data["event_id"] == "evt_01"
    assert "total" in data
    assert len(data["records"]) <= 5


def test_judge_scoring_creates_audit_log():
    client = TestClient(app)
    j_token = make_session_token("jdg_01")
    client.cookies.set("session", j_token)

    db = SessionLocal()
    crit = db.query(RubricCriteria).filter_by(event_id="evt_01").first()
    project = db.query(Project).filter_by(event_id="evt_01").first()
    db.close()

    if crit and project:
        form_data = {
            f"criteria_{crit.id}": "5",
            "comment": "Outstanding technical implementation",
        }
        res = client.post(
            f"/judge/evt_01/project/{project.id}", data=form_data, follow_redirects=True
        )
        assert res.status_code == 200

        # Now verify audit log has an entry for this scoring
        client.cookies.set("session", make_session_token("org_1"))
        audit_res = client.get(f"/organizer/evt_01/audit?q={project.title}")
        assert audit_res.status_code == 200
        assert project.title in audit_res.text
