# -*- coding: utf-8 -*-
"""
Round-trip grammar check: normalize_base over all 5585 rows.
Grammar pattern: ^IS(/[A-Z]+)*\d+(\(PART\d+(/SEC\d+)?\))?$
Also computes base_key for IS):7779 ( (Part 1/Sec 1)):1975.
Then populates the base_key column.
"""
import sys, os, re
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'C:\Users\devag\.gemini\antigravity\scratch\standards\backend')
os.chdir(r'C:\Users\devag\.gemini\antigravity\scratch\standards\backend')
from app.db import init_db_pool, get_db_cursor
init_db_pool()

GRAMMAR_RE = re.compile(
    r'^(?:'
    r'IS(?:/[A-Z]+)*'                # IS, IS/IEC, IS/IEC/IEEE, IS/IEC/TR
    r'|SP|NBC|NPE|IS/ISO|IS/IEC/TR'  # other IS families
    r')'
    r'\d+'                           # number
    r'(?:\(PART\d+(?:/SEC\d+)?\))?'  # optional (PARTn) or (PARTn/SECm)
    r'$'
)

def normalize_base(standard_number: str) -> str:
    s = standard_number.strip()
    s = re.sub(r'(?:\s*:\s*(?:19|20)\d{2})+\s*$', '', s)   # strip year(s) at end
    s = re.sub(r'\s*:\s*Part\s*(\d+)', r'(PART\1)', s, flags=re.IGNORECASE)
    s = re.sub(r'\s*:\s*Sec(?:tion)?\s*(\d+)', r'/SEC\1', s, flags=re.IGNORECASE)
    s = re.sub(r'\s+', '', s)
    return s.upper()

# Edge case test
BAD_STD = "IS):7779 ( (Part 1/Sec 1)):1975"
print(f"normalize_base({BAD_STD!r}) = {normalize_base(BAD_STD)!r}")
print(f"  grammar match: {bool(GRAMMAR_RE.match(normalize_base(BAD_STD)))}")
print()

# Round-trip on all rows
with get_db_cursor() as cur:
    cur.execute("SELECT id, standard_number, base_number FROM standards ORDER BY standard_number;")
    all_rows = cur.fetchall()

total = len(all_rows)
grammar_fails = []       # (std_num, computed_key, reason)
roundtrip_mismatches = []

for row_id, std_num, base_num in all_rows:
    computed = normalize_base(std_num)
    rt_match = (computed == base_num)
    gm_match = bool(GRAMMAR_RE.match(computed))

    if not rt_match:
        roundtrip_mismatches.append((std_num, base_num, computed))
    if not gm_match:
        grammar_fails.append((std_num, computed))

print(f"Total rows: {total}")
print(f"Round-trip matches: {total - len(roundtrip_mismatches)} / {total}")
print(f"Grammar fails (computed key): {len(grammar_fails)}")
print()

if grammar_fails:
    print("Grammar-failing computed keys (all):")
    print(f"  {'standard_number':<50} {'computed_base_key'}")
    print(f"  {'-'*50} {'-'*40}")
    for sn, ck in grammar_fails[:40]:
        print(f"  {sn!r:<50} {ck!r}")
    if len(grammar_fails) > 40:
        print(f"  ... and {len(grammar_fails)-40} more")

print()
print("Round-trip mismatches (first 10):")
for sn, bn, ck in roundtrip_mismatches[:10]:
    print(f"  DB={bn!r}  computed={ck!r}  from={sn!r}")

# Populate base_key column
print("\n--- Populating base_key column ---")
with get_db_cursor() as cur:
    cur.execute("ALTER TABLE standards ADD COLUMN IF NOT EXISTS base_key TEXT;")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_standards_base_key ON standards(base_key);")
    print("Column + index created.")
    updated = 0
    for row_id, std_num, _ in all_rows:
        computed = normalize_base(std_num)
        cur.execute("UPDATE standards SET base_key = %s WHERE id = %s;", (computed, row_id))
        updated += 1
    print(f"Updated {updated} rows.")
    cur.execute("SELECT COUNT(*) FROM standards WHERE base_key IS NOT NULL;")
    print(f"Populated: {cur.fetchone()[0]} rows have base_key.")
    # Verify a few
    cur.execute("SELECT standard_number, base_key FROM standards WHERE standard_number IN ('IS 694:2010','IS 456:2000','IS 302 (Part 2/Sec 16):2026','IS/IEC/IEEE 60079 (Part 30/Sec 1):2015');")
    print("Spot-check after populate:")
    for r in cur.fetchall():
        print(f"  {r[0]!r} -> {r[1]!r}")
