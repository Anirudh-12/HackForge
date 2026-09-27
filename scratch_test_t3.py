import urllib.request
import urllib.error
import json
import re

base = "http://127.0.0.1:8080"

with open(".dogfood.toml", encoding="utf-8") as f:
    text = f.read()

prt_cookie = re.search(r'participant\s*=\s*"Cookie:\s*([^"]+)"', text).group(1)
org_cookie = re.search(r'organizer\s*=\s*"Cookie:\s*([^"]+)"', text).group(1)
jdg_cookie = re.search(r'judge_a\s*=\s*"Cookie:\s*([^"]+)"', text).group(1)

print("Participant cookie:", prt_cookie[:20] + "...")

# 1. Test get comments (public)
req = urllib.request.Request(f"{base}/api/projects/prj_01/comments")
with urllib.request.urlopen(req) as resp:
    print("GET comments status:", resp.status)
    comments = json.loads(resp.read().decode())
    print("Initial comments count:", len(comments))

# 2. Test post comment as participant
req = urllib.request.Request(
    f"{base}/api/projects/prj_01/comments",
    data=json.dumps({"content": "Incredible architecture and clean implementation!"}).encode(),
    headers={"Cookie": prt_cookie, "Content-Type": "application/json", "Accept": "application/json"},
    method="POST"
)
with urllib.request.urlopen(req) as resp:
    print("POST comment status:", resp.status)
    comment_data = json.loads(resp.read().decode())
    print("Posted comment id:", comment_data.get("id"), "author:", comment_data.get("author", {}).get("name"))
    comment_id = comment_data["id"]

# 3. Test vote status as visitor (should be hidden)
req = urllib.request.Request(f"{base}/api/projects/prj_01/vote-status")
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read().decode())
    print("Visitor vote status:", data)
    assert data.get("vote_count") is None, "Results leaking to visitor!"

# 4. Test vote status as participant
req = urllib.request.Request(f"{base}/api/projects/prj_01/vote-status", headers={"Cookie": prt_cookie})
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read().decode())
    print("Participant vote status:", data)

# 5. Test cast vote as participant
req = urllib.request.Request(
    f"{base}/api/projects/prj_01/vote",
    data=b"{}",
    headers={"Cookie": prt_cookie, "Content-Type": "application/json", "Accept": "application/json"},
    method="POST"
)
with urllib.request.urlopen(req) as resp:
    vdata = json.loads(resp.read().decode())
    print("Vote response:", vdata)
    assert vdata.get("voted") is True

# 6. Test delete vote as participant
req = urllib.request.Request(
    f"{base}/api/projects/prj_01/vote",
    headers={"Cookie": prt_cookie, "Accept": "application/json"},
    method="DELETE"
)
with urllib.request.urlopen(req) as resp:
    del_data = json.loads(resp.read().decode())
    print("Delete vote response:", del_data)
    assert del_data.get("voted") is False

# 7. Delete the test comment
req = urllib.request.Request(
    f"{base}/api/projects/prj_01/comments/{comment_id}",
    headers={"Cookie": prt_cookie, "Accept": "application/json"},
    method="DELETE"
)
with urllib.request.urlopen(req) as resp:
    del_cdata = json.loads(resp.read().decode())
    print("Delete comment response:", del_cdata)

# 8. Test Self-Voting Prevention (Anti-Abuse)
from src.db import SessionLocal
from src.models import TeamMember, Project, AuditLog
db = SessionLocal()
tm = db.query(TeamMember).filter_by(user_id="prt_1").first()
own_proj = db.query(Project).filter_by(team_id=tm.team_id).first()
if own_proj:
    print(f"Testing self-voting refusal for project {own_proj.id} ({own_proj.title})...")
    req = urllib.request.Request(
        f"{base}/api/projects/{own_proj.id}/vote",
        data=b"{}",
        headers={"Cookie": prt_cookie, "Content-Type": "application/json", "Accept": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req) as resp:
            print("FAILED: Self-voting was allowed!")
            exit(1)
    except urllib.error.HTTPError as e:
        print(f"SUCCESS: Self-voting blocked with HTTP {e.code}: {e.read().decode()}")
        assert e.code == 403

# 9. Verify AuditLog has records
logs = db.query(AuditLog).filter(AuditLog.actor_id == "prt_1").all()
print(f"Audit log entries created for prt_1: {len(logs)}")
assert len(logs) > 0
for l in logs[-3:]:
    print(f"  - [{l.created_at}] {l.message}")

# 10. Test Randomized Ballot Ordering
req = urllib.request.Request(f"{base}/projects?sort=random")
with urllib.request.urlopen(req) as resp:
    html = resp.read().decode()
    print("Randomized gallery HTML response length:", len(html), "Status:", resp.status)
    assert resp.status == 200

print("\n>>> ALL T3 CHECKS COMPLETED SUCCESSFULLY! <<<")
