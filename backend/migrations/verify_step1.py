"""
Step 1 acceptance tests.
Run: python migrations/verify_step1.py
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import json
from app.db import init_db_pool, get_db_cursor
from app.jobs.job_store import create_job, get_job, list_jobs, mark_stale_jobs_failed, upsert_item, get_job_items

init_db_pool()
PASS = True

def check(label, condition, got=None):
    global PASS
    if condition:
        print(f"  [PASS] {label}")
    else:
        print(f"  [FAIL] {label}" + (f" — got: {got}" if got is not None else ""))
        PASS = False

print("\n=== Step 1 Acceptance Tests ===\n")

# ── Test 1: RLS enabled on both tables ───────────────────────────────────────
print("1. RLS enabled on audit_jobs and audit_items")
with get_db_cursor() as cur:
    cur.execute(
        "SELECT relname, relrowsecurity FROM pg_class WHERE relname IN ('audit_jobs','audit_items') ORDER BY relname;"
    )
    rows = {r[0]: r[1] for r in cur.fetchall()}
check("audit_items has RLS enabled", rows.get('audit_items') is True, rows.get('audit_items'))
check("audit_jobs has RLS enabled",  rows.get('audit_jobs') is True,  rows.get('audit_jobs'))

# ── Test 2: UNIQUE constraint on (job_id, seq_no) ────────────────────────────
print("\n2. UNIQUE constraint on audit_items(job_id, seq_no)")
with get_db_cursor() as cur:
    cur.execute("""
        SELECT COUNT(*) FROM pg_constraint c
        JOIN pg_class t ON c.conrelid = t.oid
        WHERE t.relname = 'audit_items' AND c.contype = 'u';
    """)
    uq_count = cur.fetchone()[0]
check("UNIQUE constraint exists on audit_items", uq_count >= 1, uq_count)

# ── Test 3: create_job ────────────────────────────────────────────────────────
print("\n3. create_job()")
j = create_job(['tender.pdf', 'boq.xlsx'], doc_type='gem_bid')
check("create_job returns id",         'id' in j and len(j['id']) == 36)
check("create_job status=pending",     j['status'] == 'pending', j.get('status'))
check("create_job filenames correct",  j['filenames'] == ['tender.pdf', 'boq.xlsx'], j.get('filenames'))
check("create_job doc_type correct",   j['doc_type'] == 'gem_bid', j.get('doc_type'))
job_id = j['id']

# ── Test 4: get_job ───────────────────────────────────────────────────────────
print("\n4. get_job()")
fetched = get_job(job_id)
check("get_job returns same id",    fetched is not None and fetched['id'] == job_id)
check("get_job returns pending",    fetched['status'] == 'pending')
check("get_job None on bad id",     get_job('00000000-0000-0000-0000-000000000000') is None)

# ── Test 5: upsert_item + get_job_items ──────────────────────────────────────
print("\n5. upsert_item() + get_job_items()")
upsert_item(job_id, {
    'seq_no': 1,
    'item_id': '1',
    'description': 'Ordinary Portland Cement 43 grade conforming to IS 269:2015',
    'quantity': '500',
    'unit': 'bags',
    'status': 'compliant',
    'badge_color': 'green',
    'findings': [{'code': 'COMPLIANT', 'severity': 'info', 'message': 'OK'}],
    'cited_standards': [],
    'recommended_standards': [],
    'source_tier': 'AUTHORITATIVE',
    'page_refs': [1],
    'processing_ms': 42.5,
})
items = get_job_items(job_id)
check("get_job_items returns 1 item",   len(items) == 1, len(items))
check("item seq_no correct",            items[0]['seq_no'] == 1)
check("item status correct",            items[0]['status'] == 'compliant')
check("item findings is list",          isinstance(items[0]['findings'], list))

# Upsert again (ON CONFLICT DO UPDATE)
upsert_item(job_id, {
    'seq_no': 1, 'item_id': '1', 'description': 'Same item updated',
    'status': 'outdated', 'badge_color': 'red', 'findings': [],
    'cited_standards': [], 'recommended_standards': [],
    'page_refs': [], 'processing_ms': 99.0,
})
items2 = get_job_items(job_id)
check("upsert ON CONFLICT updates (not duplicates)", len(items2) == 1)
check("upsert updated status", items2[0]['status'] == 'outdated', items2[0]['status'])

# ── Test 6: list_jobs ─────────────────────────────────────────────────────────
print("\n6. list_jobs()")
jobs = list_jobs(limit=5)
check("list_jobs returns list",   isinstance(jobs, list))
check("list_jobs contains our job", any(j2['id'] == job_id for j2 in jobs))

# ── Test 7: mark_stale_jobs_failed (pending → failed) ────────────────────────
print("\n7. mark_stale_jobs_failed() — marks ALL running + pending")
# Create another pending job
j2 = create_job(['other.pdf'])
j2_id = j2['id']
# Manually set one to running
with get_db_cursor() as cur:
    cur.execute("UPDATE audit_jobs SET status='running' WHERE id=%s;", (job_id,))
# Both job_id (running) and j2_id (pending) should be marked failed
count = mark_stale_jobs_failed()
check("mark_stale_jobs_failed count >= 2", count >= 2, count)
check("running job now failed",  get_job(job_id)['status'] == 'failed',  get_job(job_id)['status'])
check("pending job now failed",  get_job(j2_id)['status'] == 'failed',   get_job(j2_id)['status'])

# Second call: no stale jobs remain
count2 = mark_stale_jobs_failed()
check("second call returns 0",  count2 == 0, count2)

# ── Summary ───────────────────────────────────────────────────────────────────
print(f"\n{'='*50}")
if PASS:
    print("  RESULT: [ALL PASS] Step 1 acceptance tests passed.")
else:
    print("  RESULT: [FAILURES ABOVE] Fix before proceeding.")
print(f"{'='*50}\n")
sys.exit(0 if PASS else 1)
