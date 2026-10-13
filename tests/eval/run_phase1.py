# -*- coding: utf-8 -*-
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'C:\Users\devag\.gemini\antigravity\scratch\standards\backend')
os.chdir(r'C:\Users\devag\.gemini\antigravity\scratch\standards\backend')
from app.db import init_db_pool; init_db_pool()
import schemas
print('RecommendResponse fields:', list(schemas.RecommendResponse.model_fields.keys()))
from services.retrieval import retrieve_recommendations
from services.extraction import extract_spec
from app.services.embedding import EmbeddingService
EmbeddingService.get_instance()
import time

ITEMS = [
    (1, 'OPC 43 grade cement conforming to IS 269:2015'),
    (2, 'PVC insulated copper conductor wire IS 694'),
    (3, 'Fe 500D TMT reinforcement bars for construction'),
    (4, 'PVC insulated power cable 1.1kV as per IS 7098 (Part 1)'),
]

print('\n' + '='*80)
print('PHASE 1 RUN FOR ITEMS 1-4')
print('='*80)

for seq, desc in ITEMS:
    print(f'\n--- Item {seq}: {desc} ---')
    t0 = time.time()
    spec, conf = extract_spec(desc)
    print(f'  extract_spec ({round((time.time()-t0)*1000)}ms, conf={conf:.2f}):')
    print(f'    {spec.model_dump(exclude_none=True)}')
    t1 = time.time()
    result, timings = retrieve_recommendations(desc, spec)
    elapsed = round((time.time()-t1)*1000)
    # Get candidates via correct field name
    # RecommendResponse fields: status, primary, allied, candidates, ...
    cands = getattr(result, 'primary', None) or getattr(result, 'candidates', None) or []
    print(f'  Top-5 from primary/candidates ({elapsed}ms):')
    for i, c in enumerate(cands[:5], 1):
        bn = getattr(c, 'base_number', getattr(c, 'standard_number', getattr(c, 'id', '?')))
        sc = getattr(c, 'final_score', getattr(c, 'score', getattr(c, 'similarity', 0)))
        ti = getattr(c, 'title', '')[:70]
        cert = getattr(c, 'certification', '')
        print(f'    {i}. [{sc:.3f}] {bn}  {ti}  [cert={cert}]')


# IS 7098 Part 1 DB entry
print('\n--- IS 7098 (Part 1) DB title/scope for contradiction check ---')
from app.db import get_db_cursor
with get_db_cursor() as cur:
    cur.execute(
        "SELECT standard_number, title, virtual_scope "
        "FROM standards WHERE base_number='IS7098(PART1)' ORDER BY year DESC LIMIT 1"
    )
    row = cur.fetchone()
    sn, title, scope = row
    print(f'  standard_number: {sn}')
    print(f'  title: {title}')
    print(f'  virtual_scope (first 500): {(scope or "")[:500]}')

# Contradiction module check
try:
    from services.contradiction import check_contradiction
    r = check_contradiction('PVC insulated power cable 1.1kV', title, scope or '')
    print(f'  check_contradiction: {r}')
except ModuleNotFoundError:
    print('  services.contradiction module not found — expected, will be implemented in Step 7b')
except AttributeError as e:
    print(f'  contradiction module exists but: {e}')

# equivalent_standard inverse map analysis
print('\n--- equivalent_standard: key on number+part+section, one-to-many ---')
with get_db_cursor() as cur:
    cur.execute(
        "SELECT standard_number, base_number, equivalent_standard "
        "FROM standards WHERE equivalent_standard IS NOT NULL AND equivalent_standard != '' "
        "AND (equivalent_standard ILIKE '%IEC%' OR equivalent_standard ILIKE '%ISO%') "
        "ORDER BY base_number LIMIT 15"
    )
    rows = cur.fetchall()
    for r in rows:
        print(f'  {r[1]:<30} equiv={r[2]}')
    cur.execute("SELECT COUNT(*) FROM standards WHERE equivalent_standard LIKE '%IEC 6059%'")
    typo_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM standards WHERE equivalent_standard LIKE '%IEC 60598%'")
    correct_count = cur.fetchone()[0]
    print(f'\n  IEC 6059 (typo) occurrences: {typo_count}')
    print(f'  IEC 60598 (correct) occurrences: {correct_count}')
