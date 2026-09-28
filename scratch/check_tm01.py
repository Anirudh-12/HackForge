import sqlite3

con = sqlite3.connect('data/hackforge.db')
cur = con.cursor()
print(cur.execute("SELECT id, user_id FROM team_members WHERE team_id = 'tm_01'").fetchall())
con.close()
