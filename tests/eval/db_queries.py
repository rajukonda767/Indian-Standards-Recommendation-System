# -*- coding: utf-8 -*-
"""
DB queries for Step 2 corrections:
- Mandatory cert query for items 1-4
- 5 equivalent_standard rows
- normalize_base round-trip on all 5585 rows
- main.py diff (manual since git not on PATH)
"""
import sys, os, re
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'C:\Users\devag\.gemini\antigravity\scratch\standards\backend')
os.chdir(r'C:\Users\devag\.gemini\antigravity\scratch\standards\backend')
from app.db import init_db_pool, get_db_cursor
init_db_pool()

# ── 1. Mandatory-cert query for items 1-4 ────────────────────────────────────
print("\n=== MANDATORY-CERT QUERY FOR ITEMS 1-4 ===")
with get_db_cursor() as cur:
    targets = ['IS269', 'IS694', 'IS7098(PART1)', 'IS1786', 'IS432(PART1)']
    cur.execute("""
        SELECT base_number, certification, certification_verified, qco_ministry,
               is_status_label
        FROM standards
        WHERE base_number = ANY(%s)
        ORDER BY base_number;
    """, (targets,))
    rows = cur.fetchall()
    print(f"{'base_number':<25} {'certification':<20} {'verified':<10} {'qco_ministry':<15} {'status'}")
    print('-'*85)
    for r in rows:
        print(f"  {str(r[0]):<23} {str(r[1]):<20} {str(r[2]):<10} {str(r[3]):<15} {str(r[4])}")
    if not rows:
        print("  (no rows returned — check base_number values)")

# ── 2. Five equivalent_standard rows (IEC/ISO mapping) ───────────────────────
print("\n=== 5 EQUIVALENT_STANDARD ROWS ===")
with get_db_cursor() as cur:
    cur.execute("""
        SELECT standard_number, base_number, equivalent_standard
        FROM standards
        WHERE equivalent_standard ILIKE '%IEC%' OR equivalent_standard ILIKE '%ISO%'
        ORDER BY standard_number
        LIMIT 5;
    """)
    rows = cur.fetchall()
    print(f"{'standard_number':<40} {'base_number':<30} {'equivalent_standard'}")
    print('-'*100)
    for r in rows:
        print(f"  {str(r[0]):<38} {str(r[1]):<30} {str(r[2])}")

# ── 3. normalize_base round-trip on all 5585 rows ────────────────────────────
print("\n=== NORMALIZE_BASE ROUND-TRIP (all 5585 rows) ===")

def normalize_base(standard_number: str) -> str:
    """
    Canonical base_key from standard_number.
    - Strip year suffix(es): ': 2021', ':2021', etc. (+ handles double years)
    - Convert ': Part N' -> '(PARTN)' for colon-Part notation
    - Convert ': Sec N'  -> '/SECN'  for colon-Sec notation inside Part
    - Remove all remaining whitespace
    - Uppercase
    """
    s = standard_number.strip()
    # Strip one or more year suffixes at end (handles IS 6560:2017:2017)
    s = re.sub(r'(?:\s*:\s*(?:19|20)\d{2})+\s*$', '', s)
    # Strip trailing garbage: single uppercase letters after year (IS 8376:2026 P -> P remains after year strip)
    # If only " P" or " S" etc. remains at end after the year, strip it
    s = re.sub(r'\s+[A-Z]$', '', s)
    # Convert ': Part N' -> '(PARTN)'
    s = re.sub(r'\s*:\s*Part\s*(\d+)', r'(PART\1)', s, flags=re.IGNORECASE)
    # Convert ': Sec N' -> '/SECN' (for cases like 'IS X : Part N : Sec M')
    s = re.sub(r'\s*:\s*Sec(?:tion)?\s*(\d+)', r'/SEC\1', s, flags=re.IGNORECASE)
    # Remove all remaining whitespace
    s = re.sub(r'\s+', '', s)
    return s.upper()

with get_db_cursor() as cur:
    cur.execute("SELECT standard_number, base_number FROM standards ORDER BY standard_number;")
    all_rows = cur.fetchall()

total = len(all_rows)
mismatches = []
for std_num, base_num in all_rows:
    computed = normalize_base(std_num)
    if computed != base_num:
        mismatches.append((std_num, base_num, computed))

print(f"Total rows: {total}")
print(f"Matches (computed == base_number): {total - len(mismatches)}")
print(f"Mismatches: {len(mismatches)}")
if mismatches:
    print("\nMismatch samples (first 20):")
    print(f"  {'standard_number':<45} {'base_number (DB)':<30} {'computed base_key'}")
    print(f"  {'-'*45} {'-'*30} {'-'*30}")
    for s, b, c in mismatches[:20]:
        print(f"  {s!r:<45} {b!r:<30} {c!r}")
    if len(mismatches) > 20:
        print(f"  ... and {len(mismatches)-20} more")

# Verify our known good cases
print("\nKnown-good pair verification:")
known = [
    ("IS 15284 (Part 2):2026",             "IS15284(PART2)"),
    ("IS 1885 (Part 55):1981",             "IS1885(PART55)"),
    ("IS/IEC/IEEE 60079 (Part 30/Sec 1):2015", "IS/IEC/IEEE60079(PART30/SEC1)"),
    ("IS/ISO 7240 (Part 7):2023",          "IS/ISO7240(PART7)"),
    ("IS 456:2000",                         "IS456"),
    ("SP 7:2026",                           "SP7"),
    ("IS 2202 (Part 1):2023",              "IS2202(PART1)"),
    ("IS 302 (Part 2/Sec 16):2026",        "IS302(PART2/SEC16)"),
    ("IS 17017 : Part 24 : 2021",          "IS17017(PART24)"),  # was failing
    ("IS 6560:2017:2017",                  "IS6560"),           # was failing
    ("IS 8376:2026 P",                     "IS8376P"),          # edge case with suffix
]
for inp, expected in known:
    got = normalize_base(inp)
    ok = 'OK' if got == expected else 'FAIL'
    print(f"  [{ok}] {inp!r} -> {got!r}  (expected {expected!r})")

# ── 4. main.py diff (manual — git not on PATH) ────────────────────────────────
print("\n=== MAIN.PY DIFF (Step 1 changes) ===")
print("""
--- a/backend/app/main.py
+++ b/backend/app/main.py
@@ -13,7 +13,8 @@
 from app.config import settings
 from app.db import init_db_pool, close_db_pool, get_db_cursor
 from app.services.embedding import embedding_service
-from app.routers import recommend_router, standards_router, audit_router
+from app.routers import recommend_router, standards_router, audit_router, audit_v2_router
+from app.jobs.job_store import mark_stale_jobs_failed
 
 # Ensure UTF-8 output on Windows
@@ -36,6 +37,10 @@
     # 1. Initialize database connection pool
     init_db_pool()
 
+    # 1a. Mark ALL running/pending audit jobs as failed (server restart mid-job)
+    stale_count = mark_stale_jobs_failed()
+    logger.info(f"Startup: {stale_count} stale audit job(s) marked failed.")
+
     # 2. Warm up local GPU embedding model (BAAI/bge-m3 on RTX 3050)
@@ -84,6 +89,7 @@
 app.include_router(phase1_recommend_router, prefix=settings.API_PREFIX)
 app.include_router(standards_router, prefix=settings.API_PREFIX)
 app.include_router(audit_router, prefix=settings.API_PREFIX)
+app.include_router(audit_v2_router, prefix=settings.API_PREFIX)  # Step 1: read-only jobs
 
--- a/backend/app/routers/__init__.py
+++ b/backend/app/routers/__init__.py
@@ -1,3 +1,4 @@
 from app.routers.recommend import router as recommend_router
 from app.routers.standards import router as standards_router
 from app.routers.audit import router as audit_router
+from app.routers.audit_v2 import router as audit_v2_router
""")
