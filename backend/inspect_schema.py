import sys
sys.path.insert(0, r"C:\Users\devag\.gemini\antigravity\scratch\standards\backend")
from app.db import get_db_cursor

with get_db_cursor() as cur:
    for tbl in ['standards', 'standard_keys', 'standard_lineage']:
        cur.execute(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{tbl}' ORDER BY ordinal_position;")
        cols = cur.fetchall()
        print(f"=== {tbl} ===")
        for c in cols:
            print(f"  {c[0]}: {c[1]}")
