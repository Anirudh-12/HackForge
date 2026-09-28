import sqlite3

con = sqlite3.connect('data/hackforge.db')
cur = con.cursor()
cur.execute("DELETE FROM team_members WHERE user_id = 'fifth_member_probe'")
cur.execute("DELETE FROM users WHERE id = 'fifth_member_probe'")
cur.execute("DELETE FROM votes WHERE user_id = 'prt_1'")
con.commit()
print("Cleaned. Remaining tm_01:", cur.execute("SELECT id, user_id FROM team_members WHERE team_id = 'tm_01'").fetchall())
con.close()
