import sys
sys.path.insert(0, r"C:\Users\devag\.gemini\antigravity\scratch\standards\backend")
from app.db import get_db_cursor

with get_db_cursor() as cur:
    cur.execute("SELECT standard_number, base_key, supersedes_older FROM standards WHERE base_key IN ('IS1786', 'IS456', 'IS7098(PART1)', 'IS1554(PART1)');")
    for r in cur.fetchall():
        print(r)
