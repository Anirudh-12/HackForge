import sys
import os

sys.path.insert(0, os.path.abspath("."))
import json

from src.auth import make_session_token
from src.main import app
from starlette.testclient import TestClient

client = TestClient(app)

# Authentication tokens for different personas
org_cookie = {"session": make_session_token("org_1")}
judge_a_cookie = {"session": make_session_token("jdg_01")}
judge_b_cookie = {"session": make_session_token("jdg_02")}
participant_cookie = {"session": make_session_token("prt_1")}
admin_cookie = {"session": make_session_token("adm_1")}

results = []


def test_endpoint(
    name, method, url, status_expected, cookies=None, json_data=None, data=None
):
    headers = {}
    if method == "GET":
        resp = client.get(url, cookies=cookies, headers=headers)
    elif method == "POST":
        resp = client.post(
            url, cookies=cookies, json=json_data, data=data, headers=headers
        )
    elif method == "DELETE":
        resp = client.delete(url, cookies=cookies, headers=headers)
    else:
        raise ValueError(f"Unknown method {method}")

    passed = (
        resp.status_code in status_expected
        if isinstance(status_expected, (list, tuple, set))
        else resp.status_code == status_expected
    )
    status_str = (
        "PASS"
        if passed
        else f"FAIL (got {resp.status_code}, expected {status_expected})"
    )
    results.append((name, method, url, passed, resp.status_code, resp.text[:100]))
    print(f"[{status_str}] {method} {url} -> {resp.status_code}")
    return resp


print("=== 1. T1 CORE & PUBLIC ENDPOINTS ===")
test_endpoint("OpenAPI Schema", "GET", "/openapi.json", 200)
test_endpoint("Swagger Docs", "GET", "/docs", 200)
test_endpoint("ReDoc Docs", "GET", "/redoc", 200)
test_endpoint("Interactive API Docs Hub", "GET", "/api/docs", 200)
test_endpoint("Public Gallery", "GET", "/projects", 200)
test_endpoint("Public Gallery Search", "GET", "/projects?q=platform", 200)
test_endpoint("Public Project Detail", "GET", "/projects/prj_01", 200)
test_endpoint("Explore Hackathons", "GET", "/explore", 200)
test_endpoint("Event Detail", "GET", "/events/evt_01", 200)
test_endpoint("User Avatar SVG", "GET", "/users/prt_1/avatar.svg", 200)
test_endpoint("Public Community Vote Page", "GET", "/vote", 200)
test_endpoint("Login Page", "GET", "/login", 200)
test_endpoint("Register Page", "GET", "/register", 200)

print("\n=== 2. T2 JUDGING & ROLE ISOLATION ENDPOINTS ===")
test_endpoint(
    "Judge sees own scores", "GET", "/api/judge/scores", 200, cookies=judge_a_cookie
)
test_endpoint(
    "Judge cannot see peer scores (403)",
    "GET",
    "/api/judge/scores?judge=jdg_01",
    403,
    cookies=judge_b_cookie,
)
test_endpoint(
    "Participant blocked from judge scores (403)",
    "GET",
    "/api/judge/scores",
    403,
    cookies=participant_cookie,
)
test_endpoint(
    "Visitor blocked from judge scores (401)", "GET", "/api/judge/scores", 401
)
test_endpoint(
    "Organizer Export CSV Leaderboard",
    "GET",
    "/api/export.csv",
    200,
    cookies=org_cookie,
)
test_endpoint(
    "Judge Dashboard", "GET", "/judge/evt_01/dashboard", 200, cookies=judge_a_cookie
)
test_endpoint(
    "Judge Project Evaluation View",
    "GET",
    "/judge/evt_01/project/prj_01",
    200,
    cookies=judge_a_cookie,
)
test_endpoint(
    "Judge Pairwise Evaluation View",
    "GET",
    "/judge/evt_01/pairwise",
    200,
    cookies=judge_a_cookie,
)
test_endpoint(
    "Organizer Progress Dashboard",
    "GET",
    "/organizer/evt_01/dashboard",
    200,
    cookies=org_cookie,
)
test_endpoint(
    "Organizer Rubric Config",
    "GET",
    "/organizer/evt_01/rubric",
    200,
    cookies=org_cookie,
)
test_endpoint(
    "Organizer Judges List", "GET", "/organizer/evt_01/judges", 200, cookies=org_cookie
)
test_endpoint(
    "Organizer Tracks List", "GET", "/organizer/evt_01/tracks", 200, cookies=org_cookie
)
test_endpoint(
    "Organizer Projects List",
    "GET",
    "/organizer/evt_01/projects",
    200,
    cookies=org_cookie,
)
test_endpoint(
    "Organizer Teams List", "GET", "/organizer/evt_01/teams", 200, cookies=org_cookie
)
test_endpoint(
    "Organizer Results & Normalization",
    "GET",
    "/organizer/evt_01/results",
    200,
    cookies=org_cookie,
)

print("\n=== 3. T3 PUBLIC & COMMUNITY ENDPOINTS ===")
test_endpoint("List Project Comments", "GET", "/api/projects/prj_01/comments", 200)
test_endpoint(
    "Post Comment as Participant",
    "POST",
    "/api/projects/prj_01/comments",
    200,
    cookies=participant_cookie,
    json_data={"content": "Automated verification comment"},
)
test_endpoint(
    "Visitor Cannot Post Comment (401)",
    "POST",
    "/api/projects/prj_01/comments",
    401,
    json_data={"content": "Anon test"},
)
test_endpoint(
    "Project Vote Status",
    "GET",
    "/api/projects/prj_01/vote-status",
    200,
    cookies=participant_cookie,
)
test_endpoint(
    "Cast Community Vote",
    "POST",
    "/api/projects/prj_01/vote",
    [200, 403],
    cookies=participant_cookie,
)
test_endpoint(
    "Delete Community Vote",
    "DELETE",
    "/api/projects/prj_01/vote",
    200,
    cookies=participant_cookie,
)
test_endpoint("Visitor Cannot Vote (401)", "POST", "/api/projects/prj_01/vote", 401)
test_endpoint(
    "Organizer Audit Log API",
    "GET",
    "/api/events/evt_01/audit",
    200,
    cookies=org_cookie,
)
test_endpoint(
    "Organizer Audit Log UI", "GET", "/organizer/evt_01/audit", 200, cookies=org_cookie
)
test_endpoint(
    "Organizer Audit CSV Export",
    "GET",
    "/organizer/evt_01/audit/export.csv",
    200,
    cookies=org_cookie,
)
test_endpoint(
    "Organizer Audit JSON Export",
    "GET",
    "/organizer/evt_01/audit/export.json",
    200,
    cookies=org_cookie,
)

print("\n=== 4. T4 STRETCH ENDPOINTS ===")
# 4.1 Webhooks
wh_res = test_endpoint(
    "Organizer Create Webhook",
    "POST",
    "/api/events/evt_01/webhooks",
    200,
    cookies=org_cookie,
    json_data={
        "target_url": "https://example.com/webhook",
        "events": "project.submitted",
    },
)
if wh_res.status_code == 200:
    sub_id = wh_res.json()["id"]
    test_endpoint(
        "Organizer List Webhooks",
        "GET",
        "/api/events/evt_01/webhooks",
        200,
        cookies=org_cookie,
    )
    test_endpoint(
        "Organizer Ping Webhook",
        "POST",
        f"/api/events/evt_01/webhooks/{sub_id}/test",
        200,
        cookies=org_cookie,
    )
    test_endpoint(
        "Organizer Delete Webhook",
        "DELETE",
        f"/api/events/evt_01/webhooks/{sub_id}",
        200,
        cookies=org_cookie,
    )

# 4.2 Certificates
cert_gen = test_endpoint(
    "Organizer Bulk Generate Certificates",
    "POST",
    "/api/events/evt_01/certificates/generate",
    200,
    cookies=org_cookie,
)
test_endpoint(
    "Participant Certificate Page",
    "GET",
    "/participant/evt_01/certificate",
    200,
    cookies=participant_cookie,
)
test_endpoint(
    "Judge Certificate Page",
    "GET",
    "/judge/evt_01/certificate",
    200,
    cookies=judge_a_cookie,
)

# 4.3 Signed Judge Participation Record
rec_res = test_endpoint(
    "Judge Signed Participation Record",
    "GET",
    "/api/judge/evt_01/record",
    200,
    cookies=judge_a_cookie,
)
if rec_res.status_code == 200:
    rec_id = rec_res.json()["id"]
    test_endpoint(
        "Public Record Verification Page", "GET", f"/verify/record/{rec_id}", 200
    )

# 4.4 Embeddable Gallery Widget
test_endpoint(
    "Public Embeddable Gallery Widget", "GET", "/embed/gallery/evt_01?theme=dark", 200
)

# 4.5 Bulk Import & Export
test_endpoint(
    "Full Event Archival JSON Export",
    "GET",
    "/api/events/evt_01/export/full.json",
    200,
    cookies=org_cookie,
)
test_endpoint(
    "Projects CSV Export",
    "GET",
    "/api/events/evt_01/export/projects.csv",
    200,
    cookies=org_cookie,
)
test_endpoint(
    "Bulk Import Projects",
    "POST",
    "/api/events/evt_01/import/projects",
    200,
    cookies=org_cookie,
    json_data=[
        {
            "title": "Verification Importer Project",
            "summary": "Importer verification test",
        }
    ],
)

print("\n=== 5. NOTIFICATIONS & PARTICIPANT WORKFLOW ENDPOINTS ===")
test_endpoint(
    "Notifications List", "GET", "/api/notifications/", 200, cookies=participant_cookie
)
test_endpoint(
    "Notifications Unread Count",
    "GET",
    "/api/notifications/unread_count",
    200,
    cookies=participant_cookie,
)
test_endpoint(
    "Participant Home", "GET", "/participant/home", 200, cookies=participant_cookie
)
test_endpoint(
    "Participant Registrations",
    "GET",
    "/participant/registrations",
    200,
    cookies=participant_cookie,
)
test_endpoint(
    "Participant Event Dashboard",
    "GET",
    "/participant/evt_01/dashboard",
    200,
    cookies=participant_cookie,
)
test_endpoint(
    "Participant Team View",
    "GET",
    "/participant/evt_01/team",
    200,
    cookies=participant_cookie,
)
test_endpoint(
    "Participant Matchmaking View",
    "GET",
    "/participant/evt_01/matchmaking",
    200,
    cookies=participant_cookie,
)
test_endpoint(
    "Participant Profile View", "GET", "/profile", 200, cookies=participant_cookie
)
test_endpoint(
    "Admin Dashboard View", "GET", "/admin/dashboard", 200, cookies=admin_cookie
)

passed_count = sum(1 for r in results if r[3])
total_count = len(results)
print(f"\n==========================================")
print(f"SUMMARY: {passed_count}/{total_count} API endpoints verified successfully!")
print(f"==========================================")
if passed_count != total_count:
    sys.exit(1)
