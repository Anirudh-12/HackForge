import json
import sqlite3
from pathlib import Path

fixtures = json.loads(Path('fixtures.json').read_text(encoding='utf-8'))
fixture_user_ids = {u['id'] for u in fixtures.get('judges', [])}
for t in fixtures.get('teams', []):
    for m in t.get('members', []):
        fixture_user_ids.add(m.split('@')[0])
        fixture_user_ids.add(f"usr_{m.split('@')[0]}")
fixture_user_ids.update({'prt_1', 'org_1', 'adm_1', 'jdg_01', 'jdg_02', 'jdg_03', 'jdg_04', 'jdg_05'})

conn = sqlite3.connect('data/hackforge.db')
cursor = conn.cursor()

cursor.execute("SELECT id, email, name FROM users")
all_users = cursor.fetchall()
print(f"Total users: {len(all_users)}")

# Check users belonging to the 10 real events
cursor.execute("""
    SELECT DISTINCT user_id FROM event_members 
    WHERE event_id IN ('evt_01', 'evt_02', 'evt_03', 'evt_04', 'evt_05', 'evt_06', 'evt_07', 'evt_08', 'evt_09', 'evt_10')
""")
legit_user_ids = {r[0] for r in cursor.fetchall()}
legit_user_ids.update(fixture_user_ids)

orphan_users = [u for u in all_users if u[0] not in legit_user_ids]
print(f"Users only associated with test/junk events or orphans: {len(orphan_users)}")
for u in orphan_users[:15]:
    print(u)
