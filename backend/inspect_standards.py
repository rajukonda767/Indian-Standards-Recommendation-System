import sys
sys.path.insert(0, r"C:\Users\devag\.gemini\antigravity\scratch\standards\backend")
from app.db import get_db_cursor

with get_db_cursor() as cur:
    for base in ['IS694', 'IS7098(PART1)', 'IS1554(PART1)', 'IS456']:
        print(f"\n=================== {base} in standards ===================")
        cur.execute("""
            SELECT s.id, s.standard_number, s.base_number, s.base_key, s.year, s.is_status_label, 
                   s.supersedes_older, s.superseded_by_newer, s.reaffirmation_year, s.equivalent_standard
            FROM standards s
            JOIN standard_keys k ON k.standard_id = s.id
            WHERE k.base_key = %s
            ORDER BY s.year ASC;
        """, (base,))
        rows = cur.fetchall()
        for r in rows:
            print(f"  ID={r[0]}: {r[1]} | year={r[4]} | status={r[5]} | reaff={r[8]} | eq={r[9]} | supersedes={r[6]} | superseded_by={r[7]}")
            # check lineage
            cur.execute("SELECT relationship, related_standard_raw, related_base_number, related_year FROM standard_lineage WHERE standard_id = %s;", (r[0],))
            lineage = cur.fetchall()
            for l in lineage:
                print(f"    Lineage: rel={l[0]}, raw={l[1]}, base={l[2]}, yr={l[3]}")
