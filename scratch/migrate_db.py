import sqlite3

con = sqlite3.connect('data/hackforge.db')
cur = con.cursor()
cols = [r[1] for r in cur.execute('PRAGMA table_info(events)').fetchall()]
print('Existing cols:', cols)

if 'min_team_size' not in cols:
    print('Adding min_team_size...')
    cur.execute('ALTER TABLE events ADD COLUMN min_team_size INTEGER DEFAULT 1')

if 'max_team_size' not in cols:
    print('Adding max_team_size...')
    cur.execute('ALTER TABLE events ADD COLUMN max_team_size INTEGER DEFAULT 4')

if 'community_voting_mode' not in cols:
    print('Adding community_voting_mode...')
    cur.execute("ALTER TABLE events ADD COLUMN community_voting_mode TEXT DEFAULT 'none'")

con.commit()
con.close()
print('Migration finished.')
