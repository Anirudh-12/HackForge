import json
import urllib.request
import urllib.error
import urllib.parse
import hmac
import hashlib
import time
import sys

sys.path.insert(0, ".")

BASE_URL = "http://127.0.0.1:8080"


# Helpers
def make_token(user_id, secret="hackforge-dev-secret"):
    sig = hmac.new(
        secret.encode("utf-8"), user_id.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return f"{user_id}.{sig}"


SESSIONS = {
    "organizer": f"session={make_token('org_1')}",
    "admin": f"session={make_token('adm_1')}",
    "judge_a": f"session={make_token('jdg_01')}",
    "judge_b": f"session={make_token('jdg_02')}",
    "participant": f"session={make_token('prt_1')}",
    # user without team
    "solo_user": f"session={make_token('solo_test_user')}",
}


def req(path, method="GET", role=None, data=None, content_type="application/json"):
    url = BASE_URL + path
    headers = {}
    if role and role in SESSIONS:
        headers["Cookie"] = SESSIONS[role]
    elif role and role.startswith("session="):
        headers["Cookie"] = role

    encoded_data = None
    if data is not None:
        if content_type == "application/json":
            encoded_data = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json"
        elif content_type == "application/x-www-form-urlencoded":
            encoded_data = urllib.parse.urlencode(data).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"

    request = urllib.request.Request(
        url, data=encoded_data, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return 0, str(e)


results = {}

print("=== STARTING AUDIT PROBES ===")

# 1. TEAM FORMATION TIMING RULE PROBES
# In evt_01, event_starts is 2026-02-05T00:00:00Z (in the past).
print("\n--- 1. TEAM FORMATION TIMING PROBES ---")
# Create a new test user in db
from src.db import SessionLocal
from src.models import (
    Certificate,
    Comment,
    Event,
    EventMember,
    JudgeRecord,
    Project,
    RubricCriteria,
    Score,
    Team,
    TeamMember,
    User,
    Vote,
)

db = SessionLocal()
u = db.get(User, "solo_test_1")
if not u:
    u = User(id="solo_test_1", email="solo1@test.local", name="Solo One")
    db.add(u)
    db.commit()

# Ensure solo_test_1 is registered as participant in evt_01
em = db.query(EventMember).filter_by(event_id="evt_01", user_id="solo_test_1").first()
if not em:
    db.add(EventMember(event_id="evt_01", user_id="solo_test_1", role="participant"))
    db.commit()

# Make sure solo_test_1 is NOT in any team
tms = db.query(TeamMember).filter_by(user_id="solo_test_1").all()
for tm in tms:
    db.delete(tm)
db.commit()
db.close()

solo_cookie = f"session={make_token('solo_test_1')}"

# Probe: Attempt to create team in evt_01 after event_starts has passed
status, body = req(
    "/participant/evt_01/team",
    method="POST",
    role=solo_cookie,
    data={"action": "create", "name": "Late Team"},
    content_type="application/x-www-form-urlencoded",
)
results["team_create_after_event_start"] = {"status": status, "body": body[:200]}
print("Team create after event_starts passed:", status)

# Check if team was actually created in DB
db = SessionLocal()
created_team = db.query(Team).filter_by(event_id="evt_01", name="Late Team").first()
print(
    "Did backend create team in database despite event start passed?:",
    created_team is not None,
)
results["backend_created_team_after_event_start"] = created_team is not None

# Probe: Join via invite link on an event that has started
# First, generate invite token for a team in evt_01
team_evt01 = db.query(Team).filter_by(event_id="evt_01").first()
if not team_evt01.invite_token:
    team_evt01.invite_token = "test_invite_token_evt01"
    db.commit()
inv_token = team_evt01.invite_token

# Second test user
u2 = db.get(User, "solo_test_2")
if not u2:
    u2 = User(id="solo_test_2", email="solo2@test.local", name="Solo Two")
    db.add(u2)
    db.commit()
db.close()

solo2_cookie = f"session={make_token('solo_test_2')}"
status, body = req(f"/join/{inv_token}", method="GET", role=solo2_cookie)
results["join_via_invite_after_event_start"] = {"status": status, "body": body[:200]}
print("Join via invite token after event_starts passed:", status)

db = SessionLocal()
is_member = (
    db.query(TeamMember).filter_by(team_id=team_evt01.id, user_id="solo_test_2").first()
    is not None
)
print(
    "Did backend allow joining team via invite link after event start passed?:",
    is_member,
)
results["backend_allowed_join_after_event_start"] = is_member

# 2. 5th MEMBER / TEAM SIZE LIMIT PROBE
print("\n--- 2. TEAM SIZE LIMIT PROBES (1-4 members) ---")
# Fill team_evt01 to 4 members
existing_count = db.query(TeamMember).filter_by(team_id=team_evt01.id).count()
print(f"Current members in team {team_evt01.name}: {existing_count}")
for i in range(existing_count + 1, 5):
    uid = f"filler_user_{i}"
    if not db.get(User, uid):
        db.add(User(id=uid, email=f"{uid}@test.local", name=f"Filler {i}"))
    db.add(TeamMember(team_id=team_evt01.id, user_id=uid))
db.commit()
members_at_4 = db.query(TeamMember).filter_by(team_id=team_evt01.id).count()
print(f"Team now has {members_at_4} members (should be 4).")

# Now attempt 5th member via invite token /join/{token}
u5 = db.get(User, "fifth_member_probe")
if not u5:
    db.add(User(id="fifth_member_probe", email="fifth@test.local", name="Fifth Member"))
    db.commit()
fifth_cookie = f"session={make_token('fifth_member_probe')}"

status, body = req(f"/join/{inv_token}", method="GET", role=fifth_cookie)
results["join_full_team_via_invite"] = {"status": status, "body": body[:200]}
print("Status when 5th member joins via invite token:", status)

db.expire_all()
members_after_5th = db.query(TeamMember).filter_by(team_id=team_evt01.id).count()
print(f"Members in team after 5th member joined: {members_after_5th}")
results["fifth_member_joined_successfully"] = members_after_5th > 4

# 3. DEADLINE ENFORCEMENT
print("\n--- 3. DEADLINE ENFORCEMENT PROBES ---")
# evt_01 submissions_close has passed (2026-03-01)
status, body = req(
    "/projects/new",
    method="POST",
    role="participant",
    data={"title": "Late Project", "summary": "Probe"},
)
results["submit_after_deadline"] = {"status": status, "body": body[:200]}
print("POST /projects/new after deadline:", status)

# 4. JUDGE ROLE ISOLATION
print("\n--- 4. JUDGE ROLE ISOLATION PROBES ---")
status_a, _ = req("/api/judge/scores", role="judge_a")
print("Judge A reading own scores:", status_a)
status_peer, body_peer = req("/api/judge/scores?judge=jdg_01", role="judge_b")
print("Judge B reading Judge A's scores:", status_peer)
status_part, _ = req("/api/judge/scores", role="participant")
print("Participant reading judge scores:", status_part)
status_org_peer, body_org_peer = req("/api/judge/scores?judge=jdg_01", role="organizer")
print(
    "Organizer reading peer scores via /api/judge/scores?judge=jdg_01:", status_org_peer
)

results["judge_a_own_scores"] = status_a
results["judge_b_peer_scores"] = status_peer
results["participant_judge_scores"] = status_part
results["organizer_judge_scores"] = status_org_peer

# 5. COMMUNITY VOTING & ANTI-ABUSE
print("\n--- 5. COMMUNITY VOTING PROBES ---")
# Find a project in evt_01
proj_1 = db.query(Project).filter_by(event_id="evt_01", is_draft=False).first()
print(f"Target project for voting: {proj_1.id} ({proj_1.title})")

# Visitor vote
status_vis, body_vis = req(f"/api/projects/{proj_1.id}/vote", method="POST")
print("Visitor voting:", status_vis)

# Participant voting for proj_1
# Let's check participant's team
prt_user = db.get(User, "prt_1")
from src.queries import user_team

p_team = user_team(db, "prt_1", "evt_01")
print(
    "Participant team:", p_team.id if p_team else None, "Project team:", proj_1.team_id
)

# If proj_1 is own project, test self-vote
if p_team and p_team.id == proj_1.team_id:
    status_self, body_self = req(
        f"/api/projects/{proj_1.id}/vote", method="POST", role="participant"
    )
    print("Self-vote attempt:", status_self, body_self[:100])
    results["self_vote_status"] = status_self
    # Pick other project
    other_proj = (
        db.query(Project)
        .filter(
            Project.event_id == "evt_01",
            Project.team_id != p_team.id,
            Project.is_draft == False,
        )
        .first()
    )
else:
    other_proj = proj_1

# Vote for other project
status_vote1, body_vote1 = req(
    f"/api/projects/{other_proj.id}/vote", method="POST", role="participant"
)
print("Valid participant vote:", status_vote1, body_vote1[:100])

# Vote status - check results hidden
status_vstat, body_vstat = req(
    f"/api/projects/{other_proj.id}/vote-status", role="participant"
)
print("Vote status while results unpublished:", body_vstat[:200])

# Toggle vote (vote again for same project -> should unvote)
status_toggle, body_toggle = req(
    f"/api/projects/{other_proj.id}/vote", method="POST", role="participant"
)
print("Toggle vote (unvote):", status_toggle, body_toggle[:100])

# Rate limiting probe: 12 rapid votes
print("Testing rate limit (10 votes/min limit)...")
rate_statuses = []
for i in range(12):
    st, _ = req(
        f"/api/projects/{other_proj.id}/vote", method="POST", role="participant"
    )
    rate_statuses.append(st)
print("12 Rapid vote statuses:", rate_statuses)
results["vote_rate_limit_triggered"] = 429 in rate_statuses

# 6. COMMENTS & XSS PROBES
print("\n--- 6. COMMENTS & XSS PROBES ---")
xss_payload = {"content": "<script>alert('xss')</script><b>Bold Comment</b>"}
status_c, body_c = req(
    f"/api/projects/{other_proj.id}/comments",
    method="POST",
    role="participant",
    data=xss_payload,
)
print("Post comment with script tag:", status_c)
print("Comment response body:", body_c[:200])
results["comment_xss_escaped"] = "&lt;script&gt;" in body_c or "<script>" not in body_c

# 7. T4 STRETCH PROBES
print("\n--- 7. T4 STRETCH PROBES ---")
# Webhook creation
wh_payload = {
    "target_url": "http://127.0.0.1:9999/webhook",
    "events": "project.submitted,score.submitted",
}
status_wh, body_wh = req(
    "/api/events/evt_01/webhooks", method="POST", role="organizer", data=wh_payload
)
print("Create webhook as organizer:", status_wh)
status_wh_unauth, _ = req(
    "/api/events/evt_01/webhooks", method="POST", role="participant", data=wh_payload
)
print("Create webhook as participant (should be 403):", status_wh_unauth)

# Certificates generation
status_cert_gen, body_cert_gen = req(
    "/api/events/evt_01/certificates/generate", method="POST", role="organizer"
)
print("Generate certificates as organizer:", status_cert_gen, body_cert_gen[:100])

# Certificate metadata & SVG download
from src.models import Certificate

cert = db.query(Certificate).filter_by(event_id="evt_01").first()
if cert:
    status_c_meta, body_c_meta = req(f"/api/certificates/{cert.id}")
    print("Get certificate metadata:", status_c_meta)
    status_c_svg, body_c_svg = req(f"/api/certificates/{cert.id}/download")
    print("Download certificate SVG:", status_c_svg, body_c_svg[:60])
    status_c_ver, body_c_ver = req(f"/verify/certificate/{cert.verification_code}")
    print("Public certificate verification:", status_c_ver)
    status_c_bad, _ = req("/verify/certificate/FAKE-CODE-999")
    print("Tampered/Fake certificate verification (should be 404):", status_c_bad)

# Signed judge record
status_jrec, body_jrec = req("/api/judge/evt_01/record", role="judge_a")
print("Generate signed judge record:", status_jrec, body_jrec[:120])
from src.models import JudgeRecord

jrec = db.query(JudgeRecord).filter_by(event_id="evt_01", judge_id="jdg_01").first()
if jrec:
    status_jver, _ = req(f"/verify/record/{jrec.id}")
    print("Verify judge record publicly:", status_jver)

# Embeddable gallery widget
status_embed, body_embed = req("/embed/gallery/evt_01?theme=dark")
print("Embed gallery widget:", status_embed)

# Full JSON export
status_exp_json, body_exp_json = req(
    "/api/events/evt_01/export/full.json", role="organizer"
)
print("Full JSON export:", status_exp_json, f"{len(body_exp_json)} bytes")

# Projects CSV export
status_exp_csv, body_exp_csv = req(
    "/api/events/evt_01/export/projects.csv", role="organizer"
)
print("Projects CSV export:", status_exp_csv, f"{len(body_exp_csv)} bytes")

# Bulk import projects
bulk_payload = [
    {
        "title": "Quantum Leap AI",
        "summary": "Distributed quantum simulation engine",
        "tech_stack": "Rust, WebAssembly, Python",
        "repo_url": "https://github.com/example/quantum-leap",
    }
]
status_imp, body_imp = req(
    "/api/events/evt_01/import/projects",
    method="POST",
    role="organizer",
    data=bulk_payload,
)
print("Bulk import projects as organizer:", status_imp, body_imp[:100])

# 8. OPENAPI & DOCS PROBES
print("\n--- 8. OPENAPI & DOCS PROBES ---")
status_openapi, body_openapi = req("/openapi.json")
print("OpenAPI JSON:", status_openapi)
status_docs, _ = req("/docs")
print("Swagger UI /docs:", status_docs)
status_redoc, _ = req("/redoc")
print("ReDoc /redoc:", status_redoc)
status_apihub, _ = req("/api/docs")
print("Role-based API Documentation Portal /api/docs:", status_apihub)

db.close()
print("\n=== AUDIT SUITE PROBES FINISHED ===")
