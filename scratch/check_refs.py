import sqlite3

conn = sqlite3.connect('data/hackforge.db')
cursor = conn.cursor()

def check_refs(proj_id):
    print(f"Checking refs for {proj_id}:")
    for t, col in [('scores', 'project_id'), ('votes', 'project_id'), ('comments', 'project_id'), 
                   ('pairwise_comparisons', 'winner_project_id'), ('pairwise_comparisons', 'loser_project_id')]:
        cursor.execute(f"SELECT count(*) FROM {t} WHERE {col} = ?", (proj_id,))
        cnt = cursor.fetchone()[0]
        if cnt > 0:
            print(f"  {t}.{col}: {cnt}")

check_refs('prj_acf1e6eb')
check_refs('prj_fe3c2bb3')

for tm in ['tm_9464eec8', 'tm_9490af39', 'tm_alice_1', 'tm_00f46f98']:
    print(f"\nChecking team {tm}:")
    cursor.execute("SELECT * FROM teams WHERE id = ?", (tm,))
    print("  team:", cursor.fetchall())
    cursor.execute("SELECT * FROM team_members WHERE team_id = ?", (tm,))
    print("  members:", cursor.fetchall())
    cursor.execute("SELECT * FROM team_join_requests WHERE team_id = ?", (tm,))
    print("  join_requests:", cursor.fetchall())
    cursor.execute("SELECT id, title FROM projects WHERE team_id = ?", (tm,))
    print("  projects:", cursor.fetchall())
