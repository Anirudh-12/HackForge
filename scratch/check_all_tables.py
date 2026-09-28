import sqlite3

conn = sqlite3.connect('data/hackforge.db')
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
tables = [row[0] for row in cursor.fetchall()]

for table in tables:
    cursor.execute(f"PRAGMA table_info({table})")
    cols = [c[1] for c in cursor.fetchall()]
    print(f"\n================ TABLE: {table} (columns: {', '.join(cols)}) ================")
    cursor.execute(f"SELECT count(*) FROM {table}")
    total = cursor.fetchone()[0]
    print(f"Total rows: {total}")

    # Check for rows with test prefixes or test event_ids
    if 'event_id' in cols:
        cursor.execute(f"SELECT count(*) FROM {table} WHERE event_id NOT IN ('evt_01', 'evt_02', 'evt_03', 'evt_04', 'evt_05', 'evt_06', 'evt_07', 'evt_08', 'evt_09', 'evt_10')")
        test_rows = cursor.fetchone()[0]
        print(f"Rows associated with test/junk events (not evt_01..10): {test_rows}")
    elif table == 'events':
        cursor.execute("SELECT count(*) FROM events WHERE id NOT IN ('evt_01', 'evt_02', 'evt_03', 'evt_04', 'evt_05', 'evt_06', 'evt_07', 'evt_08', 'evt_09', 'evt_10')")
        test_rows = cursor.fetchone()[0]
        print(f"Test/junk events: {test_rows}")
