import sqlite3

conn = sqlite3.connect('data/hackforge.db')
cursor = conn.cursor()

def check_table(title, query):
    print(f"=== {title} ===")
    cursor.execute(query)
    rows = cursor.fetchall()
    if not rows:
        print("No duplicates found.")
    for r in rows:
        print(r)
    print()

# 1. Events
check_table("Events by name", """
    SELECT name, count(*), group_concat(id, ', ')
    FROM events
    GROUP BY name
    HAVING count(*) > 1
""")

# 2. Users
check_table("Users by email", """
    SELECT email, count(*), group_concat(id, ', ')
    FROM users
    GROUP BY email
    HAVING count(*) > 1
""")

# 3. Teams
check_table("Teams by event_id, name", """
    SELECT event_id, name, count(*), group_concat(id, ', ')
    FROM teams
    GROUP BY event_id, name
    HAVING count(*) > 1
""")

# 4. Team Members
check_table("Team Members by team_id, user_id", """
    SELECT team_id, user_id, count(*), group_concat(id, ', ')
    FROM team_members
    GROUP BY team_id, user_id
    HAVING count(*) > 1
""")

# 5. Projects
check_table("Projects by event_id, title", """
    SELECT event_id, title, count(*), group_concat(id, ', ')
    FROM projects
    GROUP BY event_id, title
    HAVING count(*) > 1
""")

check_table("Projects by event_id, team_id", """
    SELECT event_id, team_id, count(*), group_concat(id, ', ')
    FROM projects
    GROUP BY event_id, team_id
    HAVING count(*) > 1
""")

# 6. Event Members
check_table("Event Members by event_id, user_id", """
    SELECT event_id, user_id, count(*), group_concat(id, ', ')
    FROM event_members
    GROUP BY event_id, user_id
    HAVING count(*) > 1
""")

# 7. Tracks
check_table("Tracks by event_id, name", """
    SELECT event_id, name, count(*), group_concat(id, ', ')
    FROM tracks
    GROUP BY event_id, name
    HAVING count(*) > 1
""")

# 8. Rubric Criteria
check_table("Rubric Criteria by event_id, name", """
    SELECT event_id, name, count(*), group_concat(id, ', ')
    FROM rubric_criteria
    GROUP BY event_id, name
    HAVING count(*) > 1
""")

# 9. Judge Tracks
check_table("Judge Tracks by event_id, judge_id, track_id", """
    SELECT event_id, judge_id, track_id, count(*), group_concat(id, ', ')
    FROM judge_tracks
    GROUP BY event_id, judge_id, track_id
    HAVING count(*) > 1
""")

# 10. Scores
check_table("Scores by event_id, judge_id, project_id, criteria_id", """
    SELECT event_id, judge_id, project_id, criteria_id, count(*), group_concat(id, ', ')
    FROM scores
    GROUP BY event_id, judge_id, project_id, criteria_id
    HAVING count(*) > 1
""")

# 11. Pairwise Comparisons
check_table("Pairwise Comparisons", """
    SELECT event_id, judge_id, winner_project_id, loser_project_id, criteria_id, count(*), group_concat(id, ', ')
    FROM pairwise_comparisons
    GROUP BY event_id, judge_id, winner_project_id, loser_project_id, criteria_id
    HAVING count(*) > 1
""")

# 12. Certificates
check_table("Certificates by event_id, user_id, recipient_type", """
    SELECT event_id, user_id, recipient_type, count(*), group_concat(id, ', ')
    FROM certificates
    GROUP BY event_id, user_id, recipient_type
    HAVING count(*) > 1
""")

# 13. Audit logs
check_table("Audit logs identical", """
    SELECT event_id, actor_id, message, count(*), group_concat(id, ', ')
    FROM audit_logs
    GROUP BY event_id, actor_id, message
    HAVING count(*) > 1
    LIMIT 10
""")

# 14. Team Join Requests
check_table("Team Join Requests by team_id, user_id", """
    SELECT team_id, user_id, count(*), group_concat(id, ', ')
    FROM team_join_requests
    GROUP BY team_id, user_id
    HAVING count(*) > 1
""")
