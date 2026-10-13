import sys
sys.path.insert(0, r"C:\Users\devag\.gemini\antigravity\scratch\standards\backend")
from app.db import get_db_cursor

with get_db_cursor() as cur:
    cur.execute("""
        SELECT id, standard_number, base_key, title, certification, qco_ministry, certification_verified
        FROM standards
        WHERE certification_verified = FALSE AND (certification IS NOT NULL OR qco_ministry IS NOT NULL)
        LIMIT 10;
    """)
    rows = cur.fetchall()
    print(f"Found {len(rows)} standards with certification_verified=False and non-null cert/qco:")
    for r in rows:
        print(f"ID={r[0]} | num='{r[1]}' | base='{r[2]}' | cert='{r[4]}' | qco='{r[5]}' | ver={r[6]}")

    if not rows:
        # Check any standard where certification is populated or what values certification takes
        cur.execute("SELECT DISTINCT certification, certification_verified, COUNT(*) FROM standards GROUP BY certification, certification_verified;")
        print("Certification counts:")
        for r in cur.fetchall():
            print(r)
