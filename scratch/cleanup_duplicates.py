import sqlite3

from src.db import SessionLocal
from src.routers.judge import sync_pairwise_scores


def cleanup():
    conn = sqlite3.connect("data/hackforge.db")
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")

    real_events = "'evt_01', 'evt_02', 'evt_03', 'evt_04', 'evt_05', 'evt_06', 'evt_07', 'evt_08', 'evt_09', 'evt_10'"

    print("Starting database de-duplication and cleanup...")

    # 1. Delete child records of junk test events
    cursor.execute(f"DELETE FROM tracks WHERE event_id NOT IN ({real_events})")
    print(f"Deleted {cursor.rowcount} junk tracks")

    cursor.execute(f"DELETE FROM rubric_criteria WHERE event_id NOT IN ({real_events})")
    print(f"Deleted {cursor.rowcount} junk rubric criteria")

    cursor.execute(f"DELETE FROM event_members WHERE event_id NOT IN ({real_events})")
    print(f"Deleted {cursor.rowcount} junk event members")

    cursor.execute(f"DELETE FROM audit_logs WHERE event_id NOT IN ({real_events})")
    print(f"Deleted {cursor.rowcount} junk audit logs")

    # 2. Delete the junk test events themselves
    cursor.execute(f"DELETE FROM events WHERE id NOT IN ({real_events})")
    print(f"Deleted {cursor.rowcount} junk events")

    # 3. Delete orphan test users
    cursor.execute("DELETE FROM users WHERE id IN ('jdg_identical', 'jdg_single')")
    print(f"Deleted {cursor.rowcount} orphan test users")

    # 4. Delete duplicate test projects and teams in evt_01
    cursor.execute("DELETE FROM projects WHERE id IN ('prj_acf1e6eb', 'prj_fe3c2bb3')")
    print(f"Deleted {cursor.rowcount} duplicate test projects")

    cursor.execute(
        "DELETE FROM team_members WHERE team_id IN ('tm_9464eec8', 'tm_9490af39', 'tm_00f46f98')"
    )
    print(f"Deleted {cursor.rowcount} team member rows for test teams")

    cursor.execute(
        "DELETE FROM teams WHERE id IN ('tm_9464eec8', 'tm_9490af39', 'tm_00f46f98')"
    )
    print(f"Deleted {cursor.rowcount} duplicate test teams")

    # 5. Delete duplicate pairwise comparisons (keep highest ID per event_id, judge_id, winner_project_id, loser_project_id)
    cursor.execute("""
        DELETE FROM pairwise_comparisons
        WHERE id NOT IN (
            SELECT MAX(id)
            FROM pairwise_comparisons
            GROUP BY event_id, judge_id, winner_project_id, loser_project_id
        )
    """)
    print(f"Deleted {cursor.rowcount} duplicate pairwise comparisons")

    # 6. Delete redundant duplicate audit logs on real events
    cursor.execute(f"""
        DELETE FROM audit_logs
        WHERE event_id IN ({real_events})
        AND id NOT IN (
            SELECT MIN(id)
            FROM audit_logs
            WHERE event_id IN ({real_events})
            GROUP BY event_id, actor_id, message
        )
    """)
    print(f"Deleted {cursor.rowcount} redundant duplicate audit logs")

    conn.commit()
    conn.close()

    # 7. Resync pairwise scores for jdg_01 on evt_01
    db = SessionLocal()
    try:
        sync_pairwise_scores(db, "evt_01", "jdg_01")
        print("Resynced pairwise scores for jdg_01 on evt_01.")
    finally:
        db.close()

    print("Cleanup completed successfully!")


if __name__ == "__main__":
    cleanup()
