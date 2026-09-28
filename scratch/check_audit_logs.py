import sqlite3

conn = sqlite3.connect('data/hackforge.db')
cursor = conn.cursor()

cursor.execute("""
    SELECT event_id, actor_id, message, count(*), min(id), group_concat(id)
    FROM audit_logs
    GROUP BY event_id, actor_id, message
    HAVING count(*) > 1
""")
dups = cursor.fetchall()
total_dup_rows = sum(r[3] - 1 for r in dups)
print(f"Duplicate audit log message groups: {len(dups)}")
print(f"Total redundant audit log rows: {total_dup_rows}")
for r in dups[:10]:
    print(r[:4])
