import sys, os
sys.path.insert(0, r'C:\Users\devag\.gemini\antigravity\scratch\standards\backend')
os.chdir(r'C:\Users\devag\.gemini\antigravity\scratch\standards\backend')
from app.db import init_db_pool, get_db_cursor
init_db_pool()
with get_db_cursor() as cur:
    cur.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename IN ('audit_jobs','audit_items');"
    )
    print('Existing audit tables:', cur.fetchall())
    cur.execute('SELECT base_number FROM standards WHERE base_number IS NOT NULL LIMIT 3;')
    print('base_number samples:', cur.fetchall())
