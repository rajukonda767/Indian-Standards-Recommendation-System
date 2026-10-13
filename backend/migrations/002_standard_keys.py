# -*- coding: utf-8 -*-
"""
backend/migrations/002_standard_keys.py
=======================================
Creates and populates the standard_keys table.
Expands multi-part range standards (Part 1 to N, Part 1 and 2) into individual
discrete base_keys so every cited part resolves directly to the parent standard.
"""
import sys, os, re
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'C:\Users\devag\.gemini\antigravity\scratch\standards\backend')
os.chdir(r'C:\Users\devag\.gemini\antigravity\scratch\standards\backend')

from app.db import init_db_pool, get_db_cursor
init_db_pool()
import psycopg2.extras

# Canonical normalizer function
HYPHEN_PART_RE = re.compile(r'-(\d{1,2})$')

def normalize_base(s: str) -> str:
    s = s.strip()
    s = re.sub(r'[\s:]+P\s*$', '', s, flags=re.IGNORECASE)
    s = re.sub(r'(?:[\s:\-]+(?:19|20)\d{2})+\s*$', '', s)
    if re.match(r'^IS\s+\d+\s*-\s*\d{2}$', s, flags=re.I):
        s = re.sub(r'-\s*\d{2}$', '', s)
    s = re.sub(r'[\s:]+P\s*$', '', s, flags=re.IGNORECASE)
    s = re.sub(r'[\s:,\(]+(?:Part|Pt)\.?[ \t\-]*(\d+)', r'(PART\1', s, flags=re.IGNORECASE)
    s = re.sub(r'[\s:/]+(?:Sec(?:tion)?|S)\.?[ \t\-]*(\d+)', r'/SEC\1', s, flags=re.IGNORECASE)
    if '(PART' in s.upper() and not re.search(r'\(PART[^)]*\)', s, flags=re.I):
        s = re.sub(r'(\(PART\d+(?:/SEC\d+)?)', r'\1)', s, flags=re.I)
    if re.match(r'^IS/(?:IEC|ISO|IEEE)', s, flags=re.I):
        m = re.search(r'-(\d{1,2})$', s)
        if m:
            s = s[:m.start()] + f'(PART{m.group(1)})'
    s = re.sub(r'[\s\)]+$', ')', s) if '(PART' in s.upper() else s
    s = re.sub(r'\s+', '', s).upper()
    s = re.sub(r'\(\(', '(', s)
    s = re.sub(r'\)\)', ')', s)
    return s

GRAMMAR_RE = re.compile(
    r'^(?:IS(?:/[A-Z]+)*|SP|NBC|NPE)'
    r'\d+'
    r'(?:\(PART\d+(?:/SEC\d+)?\))?'
    r'$'
)

print("=" * 80)
print("EXPANDING MULTI-PART RANGE STANDARDS INTO standard_keys TABLE")
print("=" * 80)

# Check active in-transaction sessions
with get_db_cursor() as cur:
    cur.execute("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() AND state LIKE '%transaction%';")
    tx_count = cur.fetchone()[0]
    print(f"Active in-transaction sessions: {tx_count} (Must be 0)")
    assert tx_count == 0, "Stray open transaction detected!"

    # Create table & index
    cur.execute("""
        CREATE TABLE IF NOT EXISTS standard_keys (
            id SERIAL PRIMARY KEY,
            standard_id INT NOT NULL REFERENCES standards(id) ON DELETE CASCADE,
            base_key TEXT NOT NULL,
            is_primary BOOLEAN DEFAULT FALSE,
            is_range_expansion BOOLEAN DEFAULT FALSE
        );
        CREATE INDEX IF NOT EXISTS idx_standard_keys_base_key ON standard_keys(base_key);
        CREATE INDEX IF NOT EXISTS idx_standard_keys_standard_id ON standard_keys(standard_id);
    """)
    cur.execute("TRUNCATE TABLE standard_keys;")
    print("Table standard_keys created and truncated.")

    # Fetch all rows from standards
    cur.execute("SELECT id, standard_number, base_number FROM standards ORDER BY id;")
    all_rows = cur.fetchall()

keys_to_insert = []
range_expanded_count = 0

# Range patterns:
# e.g. "IS 4020 (Part 1 to 16):1998"
# e.g. "IS 7779 (Part 5/Sec 1 to 3):1997"
# e.g. "IS 14399 (Part 1 and 2):1996"
PART_RANGE_RE = re.compile(r'^(IS\s*\d+)\s*\(\s*Part\s*(\d+)\s*(?:to|To)\s*(\d+)\s*\)', re.I)
PART_SEC_RANGE_RE = re.compile(r'^(IS\s*\d+)\s*\(\s*Part\s*(\d+)\s*/\s*Sec(?:tion)?\s*(\d+)\s*(?:to|To)\s*(\d+)\s*\)', re.I)
PART_AND_RE = re.compile(r'^(IS\s*\d+)\s*\(\s*Part\s*(\d+)\s*(?:and|&)\s*(\d+)\s*\)', re.I)

for row_id, sn, bn in all_rows:
    # 1. Check if it's a Part range: Part X to Y
    m_p_sec = PART_SEC_RANGE_RE.search(sn)
    m_range = PART_RANGE_RE.search(sn)
    m_and   = PART_AND_RE.search(sn)

    if m_p_sec:
        prefix = re.sub(r'\s+', '', m_p_sec.group(1)).upper()
        p = int(m_p_sec.group(2))
        s_start = int(m_p_sec.group(3))
        s_end = int(m_p_sec.group(4))
        for sec in range(s_start, s_end + 1):
            key = f"{prefix}(PART{p}/SEC{sec})"
            keys_to_insert.append((row_id, key, False, True))
            range_expanded_count += 1
        # Also add unversioned base prefix
        keys_to_insert.append((row_id, prefix, True, False))

    elif m_range:
        prefix = re.sub(r'\s+', '', m_range.group(1)).upper()
        p_start = int(m_range.group(2))
        p_end = int(m_range.group(3))
        for p in range(p_start, p_end + 1):
            key = f"{prefix}(PART{p})"
            keys_to_insert.append((row_id, key, False, True))
            range_expanded_count += 1
        # Also add unversioned base prefix
        keys_to_insert.append((row_id, prefix, True, False))

    elif m_and:
        prefix = re.sub(r'\s+', '', m_and.group(1)).upper()
        p1 = int(m_and.group(2))
        p2 = int(m_and.group(3))
        for p in (p1, p2):
            key = f"{prefix}(PART{p})"
            keys_to_insert.append((row_id, key, False, True))
            range_expanded_count += 1
        keys_to_insert.append((row_id, prefix, True, False))

    else:
        # Standard non-range row
        ck = normalize_base(sn)
        if GRAMMAR_RE.match(ck):
            keys_to_insert.append((row_id, ck, True, False))
        else:
            # Fallback bare number if possible
            m_bare = re.match(r'^(IS\s*\d+)', sn, re.I)
            if m_bare:
                bare = re.sub(r'\s+', '', m_bare.group(1)).upper()
                keys_to_insert.append((row_id, bare, True, False))

print(f"Total keys generated: {len(keys_to_insert)}")
print(f"Total range expanded entries generated: {range_expanded_count}")

# Batch insert into standard_keys
with get_db_cursor() as cur:
    psycopg2.extras.execute_batch(
        cur,
        "INSERT INTO standard_keys (standard_id, base_key, is_primary, is_range_expansion) VALUES (%s, %s, %s, %s);",
        keys_to_insert,
        page_size=1000
    )

    # Verification queries
    print("\n--- FINAL VERIFICATION QUERY COUNTS ---")
    cur.execute("SELECT count(*) FROM standard_keys;")
    total_keys = cur.fetchone()[0]
    print(f"Total rows in standard_keys: {total_keys}")

    cur.execute("SELECT is_range_expansion, count(*) FROM standard_keys GROUP BY is_range_expansion;")
    for row in cur.fetchall():
        print(f"  is_range_expansion={row[0]}: {row[1]} rows")

    cur.execute("SELECT count(DISTINCT standard_id) FROM standard_keys;")
    distinct_stds = cur.fetchone()[0]
    print(f"Distinct standards indexed: {distinct_stds} / 5585")

    # Test resolving a range-expanded key:
    test_range_keys = ["IS4020(PART3)", "IS4020(PART16)", "IS14399(PART2)", "IS7779(PART5/SEC2)"]
    print("\nTesting resolution of range-expanded keys:")
    for tk in test_range_keys:
        cur.execute("""
            SELECT s.standard_number, s.title, sk.is_range_expansion 
            FROM standard_keys sk 
            JOIN standards s ON s.id = sk.standard_id 
            WHERE sk.base_key = %s LIMIT 1;
        """, (tk,))
        res = cur.fetchone()
        if res:
            print(f"  {tk:<22} -> DB Standard: {res[0]} (is_range_expansion={res[2]}) PASS ✓")
        else:
            print(f"  {tk:<22} -> NOT FOUND FAIL ✗")

print("\n" + "=" * 80)
print("standard_keys TABLE MIGRATION COMPLETE")
print("=" * 80)
