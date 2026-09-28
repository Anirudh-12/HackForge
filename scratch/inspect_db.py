import sqlite3

conn = sqlite3.connect('data/hackforge.db')
cursor = conn.cursor()

print("--- Sample Events ---")
cursor.execute("SELECT id, name, count(*) FROM events GROUP BY id HAVING count(*) > 1")
dup_ids = cursor.fetchall()
print("Duplicate event IDs (if any):", dup_ids)

cursor.execute("SELECT id, name FROM events LIMIT 25")
for r in cursor.fetchall():
    print(r)

print("\n--- Event name counts ---")
cursor.execute("SELECT name, count(*) c FROM events GROUP BY name ORDER BY c DESC LIMIT 15")
for r in cursor.fetchall():
    print(r)

print("\n--- Sample Users ---")
cursor.execute("SELECT email, count(*) c FROM users GROUP BY email ORDER BY c DESC LIMIT 10")
for r in cursor.fetchall():
    print(r)

print("\n--- Sample Tracks ---")
cursor.execute("SELECT event_id, name, count(*) c FROM tracks GROUP BY event_id, name ORDER BY c DESC LIMIT 10")
for r in cursor.fetchall():
    print(r)

print("\n--- Sample Teams ---")
cursor.execute("SELECT event_id, name, count(*) c FROM teams GROUP BY event_id, name ORDER BY c DESC LIMIT 10")
for r in cursor.fetchall():
    print(r)

print("\n--- Sample Projects ---")
cursor.execute("SELECT event_id, title, count(*) c FROM projects GROUP BY event_id, title ORDER BY c DESC LIMIT 10")
for r in cursor.fetchall():
    print(r)

print("\n--- Sample Scores ---")
cursor.execute("SELECT judge_id, project_id, criteria_id, count(*) c FROM scores GROUP BY judge_id, project_id, criteria_id ORDER BY c DESC LIMIT 10")
for r in cursor.fetchall():
    print(r)

print("\n--- Sample Certificates ---")
cursor.execute("SELECT event_id, user_id, recipient_type, count(*) c FROM certificates GROUP BY event_id, user_id, recipient_type ORDER BY c DESC LIMIT 10")
for r in cursor.fetchall():
    print(r)
