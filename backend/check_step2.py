# -*- coding: utf-8 -*-
import sys, os, re, json
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'C:\Users\devag\.gemini\antigravity\scratch\standards\backend')
os.chdir(r'C:\Users\devag\.gemini\antigravity\scratch\standards\backend')
from app.db import init_db_pool, get_db_cursor
init_db_pool()

# ---- Routes ----
print("\n=== REGISTERED ROUTES ===")
from app.main import app
from fastapi.routing import APIRoute
for r in app.routes:
    if isinstance(r, APIRoute):
        print(f"  {sorted(r.methods)} {r.path}")

# ---- base_number analysis ----
print("\n=== BASE_NUMBER ANALYSIS ===")
with get_db_cursor() as cur:
    cur.execute("SELECT COUNT(*) FROM standards;")
    print("Total standards:", cur.fetchone()[0])
    cur.execute("SELECT COUNT(*) FROM standards WHERE base_number IS NOT NULL;")
    print("base_number populated:", cur.fetchone()[0])

    malformed_sql = """
        SELECT standard_number, base_number FROM standards
        WHERE base_number ~ '[)]{2}|[(]{2}|[:]'
        LIMIT 10;
    """
    cur.execute(malformed_sql)
    rows = cur.fetchall()
    print(f"Malformed base_number rows: {len(rows)}")
    for r in rows:
        print(f"  {r[0]!r} -> {r[1]!r}")

    gold_checks = [
        ("IS2202(PART1)",              "IS 2202 Part 1"),
        ("IS302(PART2/SEC16)",         "IS 302 (Part 2/Sec 16)"),
        ("IS302",                      "IS 302 base"),
        ("IS456",                      "IS 456 (2000)"),
        ("IS/IEC60947-2",              "IS/IEC 60947-2 (hyphen)"),
        ("IS/IEC60947(PART2)",         "IS/IEC 60947 (Part 2)"),
        ("IS/IEC/IEEE60079(PART30/SEC1)", "IS/IEC/IEEE 60079 (Part 30/Sec 1)"),
        ("IS1100",                     "IS 1100 (false-positive check)"),
        ("IS2016",                     "IS 2016 (alt check)"),
    ]
    print("\nGold-set DB presence checks:")
    for base_num, label in gold_checks:
        cur.execute(
            "SELECT standard_number, year, is_status_label FROM standards WHERE base_number=%s ORDER BY year DESC LIMIT 2;",
            (base_num,)
        )
        rows2 = cur.fetchall()
        print(f"  [{base_num}] {label}: {rows2 if rows2 else 'NOT IN DB'}")

# ---- normalize_base verification ----
print("\n=== NORMALIZE_BASE VERIFICATION ===")
def normalize_base(s):
    s = s.strip()
    s = re.sub(r'\s*:\s*(?:19|20)\d{2}\s*$', '', s)
    s = re.sub(r'\s+', '', s)
    return s.upper()

sample_pairs = [
    ("IS 15284 (Part 2):2026",       "IS15284(PART2)"),
    ("IS 1885 (Part 55):1981",       "IS1885(PART55)"),
    ("IS/IEC/IEEE 60079 (Part 30/Sec 1)", "IS/IEC/IEEE60079(PART30/SEC1)"),
    ("IS/ISO 7240 (Part 7):2023",    "IS/ISO7240(PART7)"),
    ("IS 456:2000",                  "IS456"),
    ("SP 7:2026",                    "SP7"),
    ("IS 2202 (Part 1):1999",        "IS2202(PART1)"),
    ("IS 302 (Part 2/Sec 16):2026",  "IS302(PART2/SEC16)"),
]
for inp, expected in sample_pairs:
    got = normalize_base(inp)
    ok = got == expected
    print(f"  {'OK' if ok else 'FAIL'}: {inp!r} -> {got!r} (expected {expected!r})")

# ---- equivalent_standard confirmation ----
print("\n=== EQUIVALENT_STANDARD COLUMN ===")
with get_db_cursor() as cur:
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='standards' AND column_name='equivalent_standard';")
    print("Column exists:", cur.fetchone() is not None)
    cur.execute("""
        SELECT COUNT(*) FROM standards
        WHERE equivalent_standard IS NOT NULL
          AND equivalent_standard NOT IN ('Indigenous','nan','Not Equivalent','');
    """)
    print("Non-trivial values:", cur.fetchone()[0])
