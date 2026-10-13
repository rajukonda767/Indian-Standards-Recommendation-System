# -*- coding: utf-8 -*-
"""
tests/eval/run_base_key_fast.py
Fast base_key normalization, grammar validation, reverse round-trip,
and new gold fixtures.
Uses psycopg2.extras.execute_batch for sub-second database update.
"""
import sys, os, re
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'C:\Users\devag\.gemini\antigravity\scratch\standards\backend')
sys.path.insert(0, r'C:\Users\devag\.gemini\antigravity\scratch\standards\tests\eval')
os.chdir(r'C:\Users\devag\.gemini\antigravity\scratch\standards\backend')

from app.db import init_db_pool, get_db_cursor
init_db_pool()
import psycopg2.extras

# ── 1. Canonical normalizer function (SHARED between regex extractor & DB) ────
HYPHEN_PART_RE = re.compile(r'-(\d{1,2})$')

def normalize_base(standard_number: str) -> str:
    """
    Canonical base_key normalizer.
    1. Strip year(s) at end (colon-separated, e.g. :2015 or :2017:2017)
    2. Strip provisional ' P' or ':P' suffix (e.g. IS 8376:2026 P -> IS 8376)
    3. Convert :Part N and :Sec M to (PARTn/SECm)
    4. Convert trailing hyphen-digit to (PARTn) — IS/IEC 60479-3 -> IS/IEC60479(PART3)
    5. Collapse whitespace, UPPERCASE
    """
    s = standard_number.strip()
    # 1. Strip provisional ' P', ':P', 'P' at end
    s = re.sub(r'[\s:]+P\s*$', '', s, flags=re.IGNORECASE)
    # 2. Strip year(s) at end (colon-separated, e.g. :2015 or :2017:2017)
    s = re.sub(r'(?:\s*:\s*(?:19|20)\d{2})+\s*$', '', s)
    # Strip provisional ' P' again in case year preceded it
    s = re.sub(r'[\s:]+P\s*$', '', s, flags=re.IGNORECASE)
    # 3. Colon-Part / colon-Sec
    s = re.sub(r'\s*:\s*Part\s*(\d+)', r'(PART\1)', s, flags=re.IGNORECASE)
    s = re.sub(r'\s*:\s*Sec(?:tion)?\s*(\d+)', r'/SEC\1', s, flags=re.IGNORECASE)
    # 4. Collapse whitespace
    s = re.sub(r'\s+', '', s)
    # 5. Trailing hyphen-digit: IS/IEC 60479-3 -> IS/IEC60479(PART3)
    m = HYPHEN_PART_RE.search(s.upper())
    if m:
        s_up = s.upper()
        s_up = s_up[:m.start()] + f'(PART{m.group(1)})' + s_up[m.end():]
        s = s_up
    else:
        s = s.upper()
    return s

GRAMMAR_RE = re.compile(
    r'^(?:IS(?:/[A-Z]+)*|SP|NBC|NPE)'
    r'\d+'
    r'(?:\(PART\d+(?:/SEC\d+)?\))?'
    r'$'
)

# Unfixable patterns (multi-part ranges, S&T codes, special publication supplements)
UNFIXABLE_RE = re.compile(
    r'[()&]|AND|TO\d|SUPPLEMENT|_|TM:|MMAW|HB',
    re.IGNORECASE
)

print("=" * 80)
print("REQUIREMENT 6: base_key normalization, grammar check & reverse round-trip")
print("=" * 80)

# 1. Spot-check IS 8376:2026 P and hyphen-parts
spot_tests = [
    ("IS 8376:2026 P", "IS8376"),
    ("IS 6882:2026 P", "IS6882"),
    ("IS/IEC 60479-3:1998", "IS/IEC60479(PART3)"),
    ("IS/IEC 62056-46:2007", "IS/IEC62056(PART46)"),
    ("IS 14399 (Part 1 and 2):1996", "IS14399(PART1AND2)"),
    ("IS):7779 ( (Part 1/Sec 1)):1975", "IS):7779((PART1/SEC1))"),
]
print("\nSpot-check results:")
for sn, expected in spot_tests:
    computed = normalize_base(sn)
    gm = bool(GRAMMAR_RE.match(computed))
    print(f"  {sn:<35} -> computed: {computed:<25} grammar: {str(gm):<5} (matches expected: {computed==expected})")

# 2. Fetch all 5585 rows and categorize
with get_db_cursor() as cur:
    cur.execute("SELECT id, standard_number, base_number FROM standards ORDER BY id;")
    all_rows = cur.fetchall()

total = len(all_rows)
valid_rows = []
invalid_rows = []
rt_mismatches = []

for row_id, sn, bn in all_rows:
    ck = normalize_base(sn)
    gm = bool(GRAMMAR_RE.match(ck))
    if gm:
        valid_rows.append((ck, True, row_id))
    else:
        # For unfixable rows: set base_key=NULL, base_key_valid=False
        invalid_rows.append((sn, bn, ck, row_id))

print(f"\nTotal rows in standards: {total}")
print(f"  Grammar valid: {len(valid_rows)} / {total} ({len(valid_rows)/total:.2%})")
print(f"  Grammar invalid (unfixable): {len(invalid_rows)} / {total}")

# 3. Categorize all invalid rows
print(f"\nListing all {len(invalid_rows)} unfixable rows:")
print(f"  {'standard_number':<42} {'computed':<30} {'category'}")
print(f"  {'-'*42} {'-'*30} {'-'*25}")
categories = {}
for sn, bn, ck, row_id in invalid_rows:
    if 'AND' in ck:
        cat = 'Multi-part range (Part 1 and 2)'
    elif re.search(r'TO\d', ck):
        cat = 'Multi-part range (Part 1 to N)'
    elif 'S&T' in ck or '(S&' in ck or '&' in ck:
        cat = 'SP Special Publication suffix (S&T)'
    elif 'SUPPLEMENT' in ck:
        cat = 'SP Supplement'
    elif '_' in ck:
        cat = 'Underscored standard number'
    elif 'TM' in ck or 'IEEE' in ck:
        cat = 'IEEE Trademark suffix'
    elif 'MMAW' in ck or 'HB' in ck:
        cat = 'Handbook / special publication'
    elif '):' in ck or '))' in ck or ')(' in ck:
        cat = 'Malformed parenthesis in DB'
    else:
        cat = 'Other unfixable format'
    categories.setdefault(cat, []).append((sn, ck))
    print(f"  {sn:<42} {ck:<30} {cat}")

print("\nSummary by category:")
for cat, items in categories.items():
    print(f"  {cat:<40}: {len(items)} rows")

# 4. Fast batch DB update
print("\nUpdating DB (setting base_key_valid=True for valid, NULL and False for unfixable)...")
with get_db_cursor() as cur:
    cur.execute("ALTER TABLE standards ADD COLUMN IF NOT EXISTS base_key_valid BOOLEAN DEFAULT TRUE;")
    update_data = []
    for ck, is_val, row_id in valid_rows:
        update_data.append((ck, True, row_id))
    for sn, bn, ck, row_id in invalid_rows:
        update_data.append((None, False, row_id))  # set base_key NULL for unfixable

    psycopg2.extras.execute_batch(
        cur,
        "UPDATE standards SET base_key = %s, base_key_valid = %s WHERE id = %s;",
        update_data,
        page_size=500
    )
    cur.execute("SELECT base_key_valid, count(*) FROM standards GROUP BY base_key_valid;")
    counts = dict(cur.fetchall())
    print(f"  DB updated successfully: valid={counts.get(True, 0)}, invalid (NULL)={counts.get(False, 0)}")

# 5. Reverse round-trip: mention string built from each valid standard_number resolves to that row
print("\nReverse round-trip test (mention string -> base_key -> DB lookup):")
reverse_test_samples = [
    "IS 694:2010",
    "IS 456:2000",
    "IS 269:2015",
    "IS 1786:2008",
    "IS 7098 (Part 1):2025",
    "IS 302 (Part 2/Sec 16):2026",
    "IS/IEC 60947-2",
    "IS 8376:2026 P",
    "IS 6882:2026 P",
    "IS/IEC 60479-3:1998",
]
with get_db_cursor() as cur:
    for mention in reverse_test_samples:
        bk = normalize_base(mention)
        cur.execute("SELECT standard_number, is_status_label, year FROM standards WHERE base_key = %s ORDER BY year DESC LIMIT 1;", (bk,))
        res = cur.fetchone()
        if res:
            print(f"  Mention: {mention:<30} -> base_key: {bk:<22} -> DB: {res[0]} (year {res[2]}, {res[1]}) PASS")
        else:
            print(f"  Mention: {mention:<30} -> base_key: {bk:<22} -> DB: NOT FOUND FAIL")

print("\n" + "=" * 80)
print("REQUIREMENT 7: New gold fixtures & trailing-unit suppressor")
print("=" * 80)

from mention_extractor import extract_mentions, load_db_sets
load_db_sets()

NEW_FIXTURES = [
    ("G-new-01", "BASIS 456 SHALL",     None),
    ("G-new-02", "THIS 694 SHALL BE",   None),
    ("G-new-03", "THE DIAMETER IS 800 MM", None),
    ("G-new-04", "THE LENGTH IS 694 M",  None),
    ("G-new-05", "THIS 2000",            None),
    ("RP-01",    "tested as per IS 694 for PVC cable", "IS694"),
    ("RP-02",    "tested to IS 1786:2008 for rebar",   "IS1786"),
]

print(f"\n  {'Label':<12} {'Input':<40} {'Expected':<12} {'Actual':<25} {'Pass'}")
print(f"  {'-'*12} {'-'*40} {'-'*12} {'-'*25} {'-'*6}")

for label, text, expected in NEW_FIXTURES:
    mentions = [m for m in extract_mentions(text) if m.disposition == 'KEEP']
    actual_keys = ', '.join(m.base_key for m in mentions) if mentions else '(none)'
    exp_str = expected if expected else '(none)'
    if expected is None:
        ok = 'PASS' if not mentions else 'FAIL'
    else:
        ok = 'PASS (role pending 5d)' if any(expected in m.base_key for m in mentions) else 'FAIL'
    print(f"  {label:<12} {text:<40} {exp_str:<12} {actual_keys:<25} {ok}")

