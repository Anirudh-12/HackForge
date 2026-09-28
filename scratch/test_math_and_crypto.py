import sys
sys.path.insert(0, ".")
import math
from src.queries import compute_results
from src.db import SessionLocal
from src.models import (
    Event, User, Project, Team, TeamMember, Track, RubricCriteria, Score,
    PairwiseComparison, JudgeRecord
)
from src.webhooks import generate_judge_record_signature, verify_judge_record_signature
from datetime import datetime, timezone

db = SessionLocal()

print("=== MATHEMATICAL NORMALIZATION AUDIT ===")

# Test normalization proof on evt_01
results_01 = compute_results(db, "evt_01")
print(f"evt_01 results count: {len(results_01)}")
first = results_01[0]
last = results_01[-1]
print(f"Top project: {first['project'].title} | Raw: {first['raw_score']:.2f} | Norm: {first['normalized_score']:.2f} | ELO: {first['elo_score']:.1f}")
print(f"Bottom project: {last['project'].title} | Raw: {last['raw_score']:.2f} | Norm: {last['normalized_score']:.2f} | ELO: {last['elo_score']:.1f}")

# Check edge case: Judge gives identical scores to all projects (stdev = 0)
# Create a test event with 3 projects and 1 judge who gives 5 to all
test_evt = Event(id="test_norm_evt", name="Norm Test Event")
db.add(test_evt)
trk = Track(id="trk_norm_test", event_id="test_norm_evt", name="Track A")
db.add(trk)
crit = RubricCriteria(id="crit_norm_test", event_id="test_norm_evt", name="Quality", weight=100)
db.add(crit)

j1 = User(id="jdg_identical", email="identical@test.local", name="Judge Flat")
db.add(j1)

for i in range(3):
    t = Team(id=f"tm_norm_{i}", event_id="test_norm_evt", name=f"Team {i}")
    db.add(t)
    p = Project(id=f"prj_norm_{i}", event_id="test_norm_evt", team_id=t.id, track_id=trk.id, title=f"Project {i}", is_draft=False)
    db.add(p)
    # Judge gives identical score of 4 to every project
    s = Score(event_id="test_norm_evt", judge_id=j1.id, project_id=p.id, criteria_id=crit.id, value=4, conflict_of_interest=False)
    db.add(s)

db.commit()

res_identical = compute_results(db, "test_norm_evt")
print("\nEdge Case 1: Judge gives identical scores to all projects (stdev=0):")
for r in res_identical:
    print(f"Project: {r['project'].title} | Raw: {r['raw_score']} | Norm: {r['normalized_score']}")

# Check edge case 2: Judge reviews only 1 project (N=1)
t_single = Team(id="tm_single", event_id="test_norm_evt", name="Team Single")
db.add(t_single)
p_single = Project(id="prj_single", event_id="test_norm_evt", team_id=t_single.id, track_id=trk.id, title="Project Single", is_draft=False)
db.add(p_single)
j_single = User(id="jdg_single", email="single@test.local", name="Judge Single")
db.add(j_single)
db.add(Score(event_id="test_norm_evt", judge_id=j_single.id, project_id=p_single.id, criteria_id=crit.id, value=10, conflict_of_interest=False))
db.commit()

res_single = compute_results(db, "test_norm_evt")
p_single_res = [r for r in res_single if r['project'].id == "prj_single"][0]
print(f"\nEdge Case 2: Judge reviews only 1 project (N=1, raw=10): Norm: {p_single_res['normalized_score']}")

# Clean up test event
db.query(Score).filter_by(event_id="test_norm_evt").delete()
db.query(Project).filter_by(event_id="test_norm_evt").delete()
db.query(Team).filter_by(event_id="test_norm_evt").delete()
db.query(RubricCriteria).filter_by(event_id="test_norm_evt").delete()
db.query(Track).filter_by(event_id="test_norm_evt").delete()
db.query(Event).filter_by(id="test_norm_evt").delete()
db.commit()

print("\n=== CRYPTOGRAPHIC TAMPERING AUDIT ===")
now = datetime.now(timezone.utc)
sig = generate_judge_record_signature("jdg_01", "evt_01", 14, now)
print(f"Generated signature: {sig[:20]}...")

# 1. Valid verification
valid = verify_judge_record_signature(sig, "jdg_01", "evt_01", 14, now)
print("Valid signature verification:", valid)

# 2. Tampered score count
tampered_scores = verify_judge_record_signature(sig, "jdg_01", "evt_01", 15, now)
print("Tampered score count (14 -> 15) verification:", tampered_scores)

# 3. Tampered judge ID
tampered_judge = verify_judge_record_signature(sig, "jdg_02", "evt_01", 14, now)
print("Tampered judge ID verification:", tampered_judge)

# 4. Tampered event ID
tampered_event = verify_judge_record_signature(sig, "jdg_01", "evt_02", 14, now)
print("Tampered event ID verification:", tampered_event)

# 5. Tampered timestamp
tampered_time = verify_judge_record_signature(sig, "jdg_01", "evt_01", 14, now.replace(year=2025))
print("Tampered timestamp verification:", tampered_time)

# 6. Tampered signature
tampered_sig = verify_judge_record_signature(sig[:-4] + "ffff", "jdg_01", "evt_01", 14, now)
print("Tampered signature string verification:", tampered_sig)

db.close()
