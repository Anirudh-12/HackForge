import sqlite3

conn = sqlite3.connect('data/hackforge.db')
cursor = conn.cursor()

cursor.execute("SELECT * FROM projects WHERE id IN ('prj_07', 'prj_41')")
for r in cursor.fetchall():
    print(r)

cursor.execute("SELECT * FROM projects WHERE title = 'Quantum Leap AI'")
for r in cursor.fetchall():
    print(r)
