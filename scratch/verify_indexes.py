from src.db import init_db, engine
from sqlalchemy import text

init_db()
with engine.connect() as conn:
    res = conn.execute(text("SELECT name, tbl_name FROM sqlite_master WHERE type='index' AND sql LIKE '%UNIQUE%'")).fetchall()
    print("Unique indexes in DB:")
    for r in res:
        print(" ", r)
