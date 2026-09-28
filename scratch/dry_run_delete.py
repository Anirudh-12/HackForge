import sqlite3

conn = sqlite3.connect('data/hackforge.db')
cursor = conn.cursor()

real_events = ("'evt_01', 'evt_02', 'evt_03', 'evt_04', 'evt_05', 'evt_06', 'evt_07', 'evt_08', 'evt_09', 'evt_10'")

print("=== Dry-run duplicate deletions ===")

# 1. Test events and child records
cursor.execute(f"SELECT count(*) FROM events WHERE id NOT IN ({real_events})")
print(f"Junk events to delete: {cursor.fetchone()[0]}")

cursor.execute(f"SELECT count(*) FROM tracks WHERE event_id NOT IN ({real_events})")
print(f"Junk tracks to delete: {cursor.fetchone()[0]}")

cursor.execute(f"SELECT count(*) FROM rubric_criteria WHERE event_id NOT IN ({real_events})")
print(f"Junk rubric criteria to delete: {cursor.fetchone()[0]}")

cursor.execute(f"SELECT count(*) FROM event_members WHERE event_id NOT IN ({real_events})")
print(f"Junk event members to delete: {cursor.fetchone()[0]}")

cursor.execute(f"SELECT count(*) FROM audit_logs WHERE event_id NOT IN ({real_events})")
print(f"Junk audit logs to delete: {cursor.fetchone()[0]}")

# 2. Duplicate pairwise comparisons
cursor.execute("""
    SELECT count(*) FROM pairwise_comparisons
    WHERE id NOT IN (
        SELECT MAX(id)
        FROM pairwise_comparisons
        GROUP BY event_id, judge_id, winner_project_id, loser_project_id
    )
""")
print(f"Duplicate pairwise comparisons to delete: {cursor.fetchone()[0]}")

# 3. Duplicate test projects and teams in evt_01
cursor.execute("SELECT count(*) FROM projects WHERE id IN ('prj_acf1e6eb', 'prj_fe3c2bb3')")
print(f"Duplicate test projects to delete: {cursor.fetchone()[0]}")

cursor.execute("SELECT count(*) FROM teams WHERE id IN ('tm_9464eec8', 'tm_9490af39', 'tm_00f46f98')")
print(f"Duplicate/orphan test teams to delete: {cursor.fetchone()[0]}")

cursor.execute("SELECT count(*) FROM team_members WHERE team_id IN ('tm_9464eec8', 'tm_9490af39', 'tm_00f46f98')")
print(f"Team member rows to delete: {cursor.fetchone()[0]}")

# 4. Redundant audit logs on legitimate events
cursor.execute(f"""
    SELECT count(*) FROM audit_logs
    WHERE event_id IN ({real_events})
    AND id NOT IN (
        SELECT MIN(id)
        FROM audit_logs
        WHERE event_id IN ({real_events})
        GROUP BY event_id, actor_id, message
    )
""")
print(f"Redundant duplicate audit logs to delete: {cursor.fetchone()[0]}")

# 5. Orphan users
cursor.execute("SELECT count(*) FROM users WHERE id IN ('jdg_identical', 'jdg_single')")
print(f"Orphan test users to delete: {cursor.fetchone()[0]}")
