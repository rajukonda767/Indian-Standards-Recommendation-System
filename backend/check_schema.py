import sys
sys.path.insert(0, r"C:\Users\devag\.gemini\antigravity\scratch\standards\backend")
from app.db import get_db_cursor

with get_db_cursor() as cur:
    cur.execute("""
        SELECT table_name, column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name IN ('audit_jobs', 'audit_items')
        ORDER BY table_name, ordinal_position;
    """)
    for r in cur.fetchall():
        print(f"{r[0]:<15} | {r[1]:<25} | {r[2]}")
