import json
import sqlite3
from pathlib import Path

fixtures = json.loads(Path('fixtures.json').read_text(encoding='utf-8'))
fixture_team_ids = {t['id'] for t in fixtures.get('teams', [])}
fixture_proj_ids = {p['id'] for p in fixtures.get('projects', [])}

conn = sqlite3.connect('data/hackforge.db')
cursor = conn.cursor()

# Check teams in evt_01
cursor.execute("SELECT id, name FROM teams WHERE event_id = 'evt_01'")
evt_01_teams = cursor.fetchall()
non_fixture_teams = [t for t in evt_01_teams if t[0] not in fixture_team_ids]
print("Non-fixture teams in evt_01:", non_fixture_teams)

# Check projects in evt_01
cursor.execute("SELECT id, team_id, title FROM projects WHERE event_id = 'evt_01'")
evt_01_projs = cursor.fetchall()
non_fixture_projs = [p for p in evt_01_projs if p[0] not in fixture_proj_ids]
print("Non-fixture projects in evt_01:", non_fixture_projs)
