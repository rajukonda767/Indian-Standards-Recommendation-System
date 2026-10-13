# -*- coding: utf-8 -*-
import sys, os, re
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'C:\Users\devag\.gemini\antigravity\scratch\standards\backend')
os.chdir(r'C:\Users\devag\.gemini\antigravity\scratch\standards\backend')
from app.db import init_db_pool, get_db_cursor; init_db_pool()

GRAMMAR_RE = re.compile(
    r'^(?:IS(?:/[A-Z]+)*|SP|NBC|NPE)'
    r'\d+'
    r'(?:\(PART\d+(?:/SEC\d+)?\))?'
    r'$'
)

def normalize_base(standard_number):
    s = standard_number.strip()
    s = re.sub(r'(?:\s*:\s*(?:19|20)\d{2})+\s*$', '', s)
    s = re.sub(r'\s*:\s*Part\s*(\d+)', r'(PART\1)', s, flags=re.IGNORECASE)
    s = re.sub(r'\s*:\s*Sec(?:tion)?\s*(\d+)', r'/SEC\1', s, flags=re.IGNORECASE)
    s = re.sub(r'\s+', '', s)
    return s.upper()

bad_std = 'IS):7779 ( (Part 1/Sec 1)):1975'
computed = normalize_base(bad_std)
print(f'Edge case: {computed!r}  grammar: {bool(GRAMMAR_RE.match(computed))}')

with get_db_cursor() as cur:
    cur.execute('SELECT id, standard_number, base_number FROM standards')
    all_rows = cur.fetchall()

total = len(all_rows)
gram_fails = []
rt_mis = []
for row_id, sn, bn in all_rows:
    ck = normalize_base(sn)
    if ck != bn:
        rt_mis.append((sn, bn, ck))
    if not GRAMMAR_RE.match(ck):
        gram_fails.append((sn, ck))

print(f'Total: {total}  RT mismatches: {len(rt_mis)}  Grammar fails: {len(gram_fails)}')
if gram_fails:
    print('Grammar-failing computed keys (first 30):')
    for sn, ck in gram_fails[:30]:
        print(f'  {sn!r:<55} -> {ck!r}')
if len(gram_fails) > 30:
    print(f'  ... and {len(gram_fails)-30} more')

# Check base_key
with get_db_cursor() as cur:
    cur.execute('SELECT COUNT(*) FROM standards WHERE base_key IS NOT NULL')
    populated = cur.fetchone()[0]
    print(f'base_key populated: {populated}/{total}')
    if populated == 0:
        # Populate now
        print('Populating base_key...')
        cur.execute('ALTER TABLE standards ADD COLUMN IF NOT EXISTS base_key TEXT')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_standards_base_key ON standards(base_key)')
        vals = [(normalize_base(sn), rid) for rid, sn, _ in all_rows]
        cur.executemany('UPDATE standards SET base_key=%s WHERE id=%s', vals)
        print(f'Updated {len(vals)} rows')
        cur.execute('SELECT COUNT(*) FROM standards WHERE base_key IS NOT NULL')
        populated = cur.fetchone()[0]
        print(f'base_key populated: {populated}/{total}')
    # Spot-check
    cur.execute(
        "SELECT standard_number, base_key FROM standards "
        "WHERE standard_number IN ('IS 694:2010','IS 456:2000','IS 302 (Part 2/Sec 16):2026') "
        "ORDER BY standard_number"
    )
    print('Spot-check:')
    for r in cur.fetchall():
        print(f'  {r[0]!r} -> {r[1]!r}')
