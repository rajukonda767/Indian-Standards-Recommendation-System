# -*- coding: utf-8 -*-
"""
Investigate and fix:
1. Why IS2000 and IS2 are in fam_num set (causing KEEP for THIS/ANALYSIS)
2. normalize_base for IS 8376:2026 P case
3. IS/IEC/TR62051 vs DB base_number discrepancy
"""
import sys, os, re
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'C:\Users\devag\.gemini\antigravity\scratch\standards\backend')
os.chdir(r'C:\Users\devag\.gemini\antigravity\scratch\standards\backend')
from app.db import init_db_pool, get_db_cursor
init_db_pool()

with get_db_cursor() as cur:
    # Why does IS2000 appear in DB?
    cur.execute("SELECT standard_number, base_number FROM standards WHERE base_number LIKE 'IS2000%' LIMIT 5;")
    rows = cur.fetchall()
    print("IS2000* in DB:", rows)

    # Why does IS2 appear?
    cur.execute("SELECT standard_number, base_number FROM standards WHERE base_number LIKE 'IS2' OR base_number = 'IS2' LIMIT 5;")
    rows2 = cur.fetchall()
    print("IS2 in DB (exact):", rows2)

    # Is IS2 in the family+num set?
    cur.execute("SELECT standard_number, base_number FROM standards WHERE base_number ~ '^IS2[^0-9]' OR base_number = 'IS2' LIMIT 3;")
    print("IS2 prefix variants:", cur.fetchall())

    # Check what IS 6882:2026 P and IS 8376:2026 P actually are
    cur.execute("SELECT standard_number, base_number FROM standards WHERE base_number LIKE 'IS6882%' OR base_number LIKE 'IS8376%';")
    print("IS6882/IS8376 rows:", cur.fetchall())

    # IS/IEC/TR 62051 details
    cur.execute("SELECT standard_number, base_number FROM standards WHERE standard_number LIKE '%/IEC/TR 62051%';")
    print("IS/IEC/TR 62051:", cur.fetchall())

    # IS 19257 P - what is it?
    cur.execute("SELECT standard_number, base_number FROM standards WHERE base_number = 'IS19257P';")
    print("IS19257P:", cur.fetchall())

# normalize_base fix for IS 8376:2026 P
# The issue: after stripping ':2026', we get 'IS 8376 P'
# The 'P' seems to be part of the standard_number as a suffix meaning 'Provisional'
# Strategy: if only a single uppercase letter remains as suffix after year strip, treat it as a suffix tag
def normalize_base_v2(standard_number: str) -> str:
    s = standard_number.strip()
    # Strip one or more year-colon suffixes at end
    s = re.sub(r'(?:\s*:\s*(?:19|20)\d{2})+\s*$', '', s)
    # Convert ': Part N' -> '(PARTN)'
    s = re.sub(r'\s*:\s*Part\s*(\d+)', r'(PART\1)', s, flags=re.IGNORECASE)
    # Convert ': Sec N' -> '/SECN'
    s = re.sub(r'\s*:\s*Sec(?:tion)?\s*(\d+)', r'/SEC\1', s, flags=re.IGNORECASE)
    # Remove all whitespace
    s = re.sub(r'\s+', '', s)
    return s.upper()

print("\n--- normalize_base_v2 on edge cases ---")
cases = [
    "IS 8376:2026 P",    # trailing P after year strip = IS8376 P -> IS8376P via space-removal? No, year was :2026 so after strip: "IS 8376 P" -> spaces removed -> "IS8376P"
    "IS 6882:2026 P",
    "IS 6560:2017:2017",
    "IS 17017 : Part 24 : 2021",
    "IS 19257 P:2025",   # year ':2025' at end -> strip -> "IS 19257 P" -> spaces -> "IS19257P"
    "IS/IEC/TR 62051:Part 1 : 2004",
    "IS 6398):Part 2):2020",  # this is malformed data; best effort
]
for s in cases:
    print(f"  {s!r} -> {normalize_base_v2(s)!r}")
