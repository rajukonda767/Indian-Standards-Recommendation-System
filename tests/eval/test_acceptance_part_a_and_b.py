# -*- coding: utf-8 -*-
"""
tests/eval/test_acceptance_part_a_and_b.py
=========================================
Comprehensive Acceptance Suite:
PART A:
  1. Plain Statement on 61.359s Benchmark (MISS) & Re-run with Parallelized Worker Pool
  2. Rebuilt 40-Item Synthetic Set with Full Status Distribution and Badge Colors
  3. Real Database Standard with certification_verified=False & Unverified Finding Verification
  4. Confirmation of Findings Carrying severity='error'

PART B:
  1. DOCX Adapter Execution & Tier Tracking (sample_tender_spec.docx)
  2. XLSX Adapter Execution & Item Building (sample_boq_schedule.xlsx)
  3. Upload Limits Enforcement (Size Limit & Row/Page Count Limit Verification)
"""
import sys, os, time, json
sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
sys.path.insert(0, r'C:\Users\devag\.gemini\antigravity\scratch\standards\backend')

from app.db import get_db_cursor
from app.adapters import get_adapter_for_file
from app.adapters.docx_adapter import DocxAdapter
from app.adapters.xlsx_adapter import XlsxAdapter
from app.parsers.mention_extractor import extract_mentions, load_db_sets
from app.parsers.item_builder import ItemBuilder, AuditItem, ItemField, SourceRef
from app.parsers.verbatim_verifier import VerbatimQuoteVerifier
from app.parsers.standard_resolver import StandardResolver
from app.parsers.finding_assembler import FindingAssembler, FindingCode, ItemFinding, AuditedItem
from app.parsers.scorer import calculate_audit_scores
from app.jobs.job_store import create_job, get_job, list_jobs, get_job_items
from app.jobs.runner import launch_audit_job, run_audit_sync, rerun_single_item

load_db_sets()

print("=" * 115)
print("COMPREHENSIVE ACCEPTANCE SUITE: PART A (BENCHMARK & FINDINGS) & PART B (DOCX/XLSX & LIMITS)")
print("=" * 115)


# ══════════════════════════════════════════════════════════════════════════════
# PART A.1: BENCHMARK TIMING ANALYSIS & RE-RUN WITH PARALLEL WORKERS
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "#" * 115)
print("PART A.1: BENCHMARK TIMING ANALYSIS & PARALLEL WORKER POOL EXECUTION")
print("#" * 115)

benchmark_statement = """Plain Statement on Initial Benchmark Result:
- Initial Wall-Clock Time: 61.359s vs the <=60s target.
- Honest Assessment     : 61.359s was a MISS, not a success.
- Root Cause Analysis   : The initial implementation of `run_audit_sync` executed item audits sequentially in a
  single-threaded loop. For each of the 40 items, 2-4 synchronous round trips were made across the remote Supabase
  connection (standard lookup, keys lookup, lineage lookup, QCO mandate lookup, item upsert, done increment),
  accumulating ~1,534 ms of latency per item (40 * 1.534s = 61.359s).
- Remedy Implemented    : In `backend/app/jobs/runner.py`, item-level audit execution is now parallelized across a
  `ThreadPoolExecutor(max_workers=6)` coupled with an expanded DB connection pool (`maxconn=20` in `app/db.py`).
  Multiple items now execute I/O concurrently."""

print(benchmark_statement)


# ══════════════════════════════════════════════════════════════════════════════
# PART A.2 & A.4: REBUILT 40-ITEM SYNTHETIC SET (EXERCISING ALL CODES & BADGES)
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "#" * 115)
print("PART A.2 & A.4: REBUILT 40-ITEM SET (SUPERSEDED, OUTDATED, CONFLICT, MISSING, CANNOT_VERIFY)")
print("#" * 115)

# Build a comprehensive 40-item procurement tender designed to exercise:
# - Currency < 100% (outdated and superseded citations)
# - Severity = 'error' (SUPERSEDED, TITLE_SPEC_INCONSISTENT, CITATION_MISSING)
# - All badge colors: green, yellow, orange, red, gray, purple
rebuilt_bank = [
    # 1. Superseded edition: IS 7098 (Part 1):1988 (superseded by 2025) -> status: superseded, badge: red, severity: error
    {"desc": "Power Cable 1.1kV XLPE", "spec": "Conforming to IS 7098 (Part 1):1988 specification", "qty": "3000", "unit": "MTR", "code": "CBL-SUP-01"},
    # 2. Superseded edition: IS 1554 (Part 1):1976 (superseded by 1988) -> status: superseded, badge: red, severity: error
    {"desc": "Heavy Duty PVC Control Cable", "spec": "Conforming to IS 1554 (Part 1):1976 specification", "qty": "2000", "unit": "MTR", "code": "CBL-SUP-02"},
    # 3. Outdated edition: IS 1786:1985 (latest is 2008) -> status: outdated, badge: orange, severity: warning
    {"desc": "High Strength TMT Steel Rebars", "spec": "Steel bars conforming to IS 1786:1985", "qty": "50", "unit": "MT", "code": "STL-OUT-01"},
    # 4. Outdated edition: IS 456:1978 (latest is 2000) -> status: outdated, badge: orange, severity: warning
    {"desc": "RCC Structural Concrete", "spec": "Design strictly per IS 456:1978 code of practice", "qty": "200", "unit": "CUM", "code": "CIV-OUT-02"},
    # 5. Conflict (Insulation Mismatch): PVC INSULATED vs XLPE INSULATED -> status: conflict, badge: red, severity: error
    {"desc": "PVC INSULATED Copper Wire 1.1kV", "spec": "XLPE INSULATED POWER CABLE TO IS 7098 (Part 1):2025", "qty": "1500", "unit": "MTR", "code": "CBL-CON-01"},
    # 6. Missing citation: No standard cited -> status: missing, badge: gray, severity: error
    {"desc": "Fabricated Mild Steel Support Brackets and Clamps", "spec": "High quality galvanized steel accessories for cable tray mounting", "qty": "500", "unit": "NOS", "code": "SUP-MIS-01"},
    # 7. Unmapped Foreign Standard: DIN 99999 -> status: cannot_verify, badge: purple, severity: warning
    {"desc": "Imported Specialized Valve", "spec": "Manufactured strictly to DIN 99999 standard specification", "qty": "10", "unit": "NOS", "code": "VAL-UNK-01"},
    # 8. Compliant: Current active standard with mandatory ISI mark stipulated -> status: compliant, badge: green
    {"desc": "Ordinary Portland Cement 53 Grade", "spec": "Conforming to IS 269:2015 with valid BIS license and ISI mark on every bag", "qty": "5000", "unit": "BAG", "code": "CMT-OK-01"},
    # 9. Compliant: Mild Steel Seamless Pipes with ISI mark -> status: compliant, badge: green
    {"desc": "Mild Steel Tubes Heavy Grade", "spec": "Conforming to IS 1239 (Part 1):2004 carrying standard ISI mark", "qty": "2000", "unit": "MTR", "code": "PIP-OK-02"},
    # 10. Incomplete: Undated citation without year -> status: incomplete, badge: yellow, severity: warning
    {"desc": "CBLE: PVC FRLS 1.1KV: CU-STR: 1CX1.5SQMM", "spec": "POWER CABLE :SPECIFICATION/VOLTAGE GRADE- IS : 7098 XLPE CU STRANDED", "qty": "4000", "unit": "MTR", "code": "CBL-NOYR-01"},
]

forty_items_rebuilt = []
for i in range(40):
    tmpl = rebuilt_bank[i % len(rebuilt_bank)]
    num = i + 1
    forty_items_rebuilt.append({
        "item_id": f"ITEM-{num:03d}",
        "seq_no": num,
        "description": f"{tmpl['desc']} [Item #{num}]",
        "technical_spec": tmpl["spec"],
        "quantity": tmpl["qty"],
        "unit": tmpl["unit"],
        "material_code": f"{tmpl['code']}-{num:02d}",
    })

print(f"Constructed 40-item tender with deliberate distribution across all status codes and badge tiers.")

# Launch Parallel Background Audit Run
print(f"\nLaunching Parallel Background Audit Job (40 Items)...")
t0_run = time.perf_counter()
rebuilt_job_id = launch_audit_job(raw_items=forty_items_rebuilt, doc_type="gem")
print(f"Created Job ID: {rebuilt_job_id}")

# Progressive Poll Loop
poll_cnt = 0
seen_prog = set()
while True:
    time.sleep(0.4)
    poll_cnt += 1
    job_st = get_job(rebuilt_job_id)
    if not job_st:
        continue
    status = job_st["status"]
    done_c = job_st.get("done_items", 0)
    total_c = job_st.get("total_items", 40)

    if done_c > len(seen_prog) or status in ("done", "error"):
        print(f"  [Poll #{poll_cnt:02d}] Status: {status:<8} | Progress: {done_c}/{total_c} items completed")
        seen_prog.add(done_c)

    if status in ("done", "error"):
        break

t1_run = time.perf_counter()
rebuilt_wall_clock = round(t1_run - t0_run, 3)

# Telemetry Output
print(f"\nParallel Run Telemetry Summary:")
print(f"  • Job ID                  : {rebuilt_job_id}")
print(f"  • Status                  : {job_st['status'].upper()}")
print(f"  • Total Items             : {job_st['total_items']}")
print(f"  • NEW ACTUAL Wall-Clock   : {rebuilt_wall_clock} seconds (~{rebuilt_wall_clock/40*1000:.1f} ms/item)")
print(f"  • Target <=60s Met        : {'YES! ✓' if rebuilt_wall_clock <= 60.0 else 'NO'}")
print(f"  • Coverage Score          : {job_st.get('coverage', 0.0):.1f}% ({job_st.get('coverage_denominator')} denominator)")
print(f"  • Currency Score          : {job_st.get('currency', 0.0):.1f}% ({job_st.get('currency_denominator')} denominator)")
print(f"  • QCO Compliance Score    : {job_st.get('qco_compliance', 0.0):.1f}% ({job_st.get('qco_denominator')} denominator)")

# Verify Database Items, Status Distribution & Badge Colors
all_db_items = get_job_items(rebuilt_job_id)
assert len(all_db_items) == 40, f"Expected 40 items in DB, got {len(all_db_items)}"

status_tally = {}
badge_tally = {}
error_findings_found = []

for it in all_db_items:
    st = it["status"]
    bg = it["badge_color"]
    status_tally[st] = status_tally.get(st, 0) + 1
    badge_tally[bg] = badge_tally.get(bg, 0) + 1
    for f in it.get("findings", []):
        if f.get("severity") == "error":
            error_findings_found.append((it["seq_no"], f.get("code"), f.get("message")))

print(f"\nActual Observed Status Distribution:")
for s, c in sorted(status_tally.items()):
    print(f"  • {s.upper():<16}: {c} items")

print(f"\nActual Observed Badge Colors Produced:")
for b, c in sorted(badge_tally.items()):
    print(f"  • {b.upper():<10}: {c} items")

# Assert all badge colors are present
assert "green" in badge_tally, "Missing green badge!"
assert "yellow" in badge_tally, "Missing yellow badge!"
assert "orange" in badge_tally, "Missing orange badge!"
assert "red" in badge_tally, "Missing red badge!"
assert "gray" in badge_tally, "Missing gray badge!"
assert "purple" in badge_tally, "Missing purple badge!"

# Assert Currency < 100%
assert job_st.get("currency") < 100.0, f"Currency should be < 100%, got {job_st.get('currency')}%"

# Assert Findings with severity='error'
print(f"\nPART A.4: Findings Verified Carrying severity='error' ({len(error_findings_found)} total instances):")
for seq, code, msg in error_findings_found[:4]:
    print(f"  • [ERROR] Item {seq:02d}: {code:<25} | {msg}")
assert len(error_findings_found) > 0, "No findings with severity='error' found!"
print("Severity='error' actively produced and verified! ✓")


# ══════════════════════════════════════════════════════════════════════════════
# PART A.3: REAL DB STANDARD WITH certification_verified=False
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "#" * 115)
print("PART A.3: REAL DB STANDARD WITH certification_verified=False")
print("#" * 115)

with get_db_cursor() as cur:
    cur.execute("""
        SELECT s.id, s.standard_number, s.base_key, s.certification, s.qco_ministry, s.certification_verified
        FROM standards s
        WHERE s.base_key = 'IS7098(PART2)'
        LIMIT 1;
    """)
    r_unver = cur.fetchone()
    print("Database Record for IS 7098 (Part 2):")
    print(f"  • ID                     : {r_unver[0]}")
    print(f"  • Standard Number        : {r_unver[1]}")
    print(f"  • Certification Type     : {r_unver[3]}")
    print(f"  • QCO Ministry           : {r_unver[4]}")
    print(f"  • certification_verified : {r_unver[5]} (boolean)")
    assert r_unver[5] is False, "certification_verified should be False for IS 7098 (Part 2)!"

# Resolve an item citing this unverified standard
unver_item = AuditItem(
    item_id="UNVER-01",
    seq_no=1,
    description=ItemField("Medium Voltage HT Power Cable 11kV", SourceRef("Tender", 1, 0, "AUTHORITATIVE")),
    technical_spec=ItemField("Conforming to IS 7098 (Part 2):2011 for 11kV working voltage", SourceRef("Tender", 1, 0, "AUTHORITATIVE")),
)

resolver = StandardResolver()
mentions_unver = extract_mentions(unver_item.technical_spec.value, source_block_tier="AUTHORITATIVE")
res_unver_list = [resolver.resolve_mention(m, unver_item.technical_spec.value) for m in mentions_unver]
audited_unver = FindingAssembler.assemble_item(unver_item, res_unver_list, "Tender", 1)

print(f"\nResolved Item Findings for IS 7098 (Part 2):")
for f in audited_unver.findings:
    print(f"  • [{f.severity.upper()}] {f.code.value:<22} | {f.message}")

cert_finding = next((f for f in audited_unver.findings if f.code == FindingCode.CERT_NOT_MENTIONED), None)
assert cert_finding is not None, "Expected CERT_NOT_MENTIONED finding for unverified standard!"
assert "certification status not verified, check bis portal" in cert_finding.message.lower(), (
    f"Expected 'not verified, check BIS portal' message, got: {cert_finding.message}"
)
print("Unverified certification finding verified: does not assert mandatory/voluntary as settled fact! ✓")


# ══════════════════════════════════════════════════════════════════════════════
# PART A.5: WORKER EXCEPTION ISOLATION & HANG PROTECTION VERIFICATION
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "#" * 115)
print("PART A.5: ROOT-CAUSE EXCEPTION ON ITEM 9 & WORKER EXCEPTION ISOLATION TEST")
print("#" * 115)

root_cause_explanation = """Investigation of Item 9 Stall / Unhandled Exception:
1. Root-Cause Exception on Item 9:
   `AttributeError: 'NoneType' object has no attribute 'part_resolution_source'` at `standard_resolver.py:380`.
2. Why it occurred:
   In `StandardResolver._resolve_indian_key`, lines 455-546 were indented under `if not rows:`. When rows WERE
   found in PostgreSQL (e.g. for `IS 1786` on item 9), the block was skipped and the function returned `None`.
   Line 380 attempted to assign `res.part_resolution_source`, throwing `AttributeError`.
3. Why the Job Hung:
   Worker threads in `ThreadPoolExecutor` were executing `_process_item` without a surrounding `try...except`.
   When item 9 crashed, `upsert_item` and `increment_done` were never called. Concurrently, connection pool
   contention occurred with 6 threads competing for 5 connections.
4. Architectural Remedy:
   a. Indentation error in `_resolve_indian_key` corrected.
   b. `_process_item` in `runner.py` now wraps all execution in `try...except Exception as exc:`. On failure,
      it logs the exception, records an AuditedItem with status='cannot_verify', finding='CANNOT_VERIFY',
      severity='error', badge_color='purple', upserts the item to DB, and increments `done_items`.
   c. Added 30-second per-item timeout and 180-second overall job timeout. If any item or the job times out,
      remaining items are marked as 'cannot_verify: timeout' and the job finalizes as 'done' (partial),
      guaranteeing a job is NEVER stuck indefinitely in 'running'."""
print(root_cause_explanation)

# Prove worker exception isolation with a forced-failure test
print("\nRunning Forced Worker Exception Isolation Test:")
broken_item_set = [
    {"description": "Valid Item 1", "technical_spec": "Conforming to IS 269:2015 with ISI mark", "quantity": "100", "unit": "BAG", "material_code": "OK-01"},
    {"description": "Broken Item Forced Exception", "technical_spec": "BROKEN_TEST_TRIGGER", "quantity": "10", "unit": "NOS", "material_code": "ERR-02"},
    {"description": "Valid Item 3", "technical_spec": "Conforming to IS 1239 (Part 1):2004 with ISI mark", "quantity": "50", "unit": "MTR", "material_code": "OK-03"},
]

from unittest.mock import patch
orig_extract = extract_mentions
def mock_extract(text, **kwargs):
    if "BROKEN_TEST_TRIGGER" in text:
        raise RuntimeError("Simulated critical worker parser crash on item 2!")
    return orig_extract(text, **kwargs)

with patch("app.jobs.runner.extract_mentions", side_effect=mock_extract):
    iso_job_id = launch_audit_job(raw_items=broken_item_set, doc_type="gem")
    print(f"Launched 3-item test job with forced item 2 failure (Job ID: {iso_job_id})...")
    
    poll_iso = 0
    while True:
        time.sleep(0.3)
        poll_iso += 1
        j_st = get_job(iso_job_id)
        if not j_st:
            continue
        if j_st["status"] in ("done", "error"):
            break
        if poll_iso > 60:
            break

iso_items = get_job_items(iso_job_id)
print(f"Job Status: {j_st['status'].upper()} | Done Items: {j_st.get('done_items')}/{j_st.get('total_items')}")
assert j_st["status"] == "done", f"Expected job to finish with 'done', got {j_st['status']}"
assert len(iso_items) == 3, f"Expected 3 items in DB, got {len(iso_items)}"

item2_db = next(it for it in iso_items if it["seq_no"] == 2)
print(f"Item 2 Status     : {item2_db['status'].upper()}")
print(f"Item 2 Badge Color: {item2_db['badge_color']}")
print(f"Item 2 Findings   : {item2_db['findings']}")
assert item2_db["status"] == "cannot_verify", f"Expected cannot_verify, got {item2_db['status']}"
assert item2_db["badge_color"] == "purple", f"Expected purple badge, got {item2_db['badge_color']}"
assert any("Simulated critical worker parser crash" in f.get("message", "") for f in item2_db["findings"])
print("Forced worker exception test passed: job advanced, did not hang, and item 2 recorded as cannot_verify! ✓")


# ══════════════════════════════════════════════════════════════════════════════
# PART B.1 & B.2: DOCX & XLSX ADAPTERS REAL RUN ON CONSTRUCTED FIXTURES
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "#" * 115)
print("PART B.1: DOCX ADAPTER TEST ON CONSTRUCTED FIXTURE (sample_tender_spec.docx)")
print("#" * 115)

DOCX_FIXTURE = r"C:\Users\devag\.gemini\antigravity\scratch\standards\tests\fixtures\sample_tender_spec.docx"
print("Note: sample_tender_spec.docx is a constructed real-structured DOCX fixture (not a user tender).")

docx_adapter = get_adapter_for_file(DOCX_FIXTURE)
print(f"Selected Adapter for .docx: {docx_adapter.__class__.__name__}")
assert isinstance(docx_adapter, DocxAdapter)

docx_blocks = docx_adapter.extract_blocks(DOCX_FIXTURE)
print(f"Extracted {len(docx_blocks)} PageBlocks from DOCX document:")
gtc_blocks = [b for b in docx_blocks if b.tier == "CONTEXT_ONLY"]
spec_blocks = [b for b in docx_blocks if b.tier == "AUTHORITATIVE"]
print(f"  • GTC Boilerplate Blocks (CONTEXT_ONLY): {len(gtc_blocks)}")
print(f"  • Specification Blocks (AUTHORITATIVE) : {len(spec_blocks)}")
assert len(gtc_blocks) > 0, "Expected GTC blocks with CONTEXT_ONLY tier!"
assert len(spec_blocks) > 0, "Expected Spec blocks with AUTHORITATIVE tier!"

docx_ext_result = ItemBuilder.build_items_from_blocks(docx_blocks, "SampleDOCX")
print(f"Parsed {len(docx_ext_result.items)} Items via ItemBuilder from DOCX table:")
for it in docx_ext_result.items:
    print(f"  Item {it.item_id}: code={it.material_code.value if it.material_code else 'N/A'} desc={repr(it.description.value[:45])} spec={repr(it.technical_spec.value[:45])}")
assert len(docx_ext_result.items) == 3, f"Expected 3 items from DOCX table, got {len(docx_ext_result.items)}"
print("DOCX Adapter and ItemBuilder pipeline verified! ✓")


print("\n" + "#" * 115)
print("PART B.2: XLSX ADAPTER TEST ON CONSTRUCTED FIXTURE (sample_boq_schedule.xlsx)")
print("#" * 115)

XLSX_FIXTURE = r"C:\Users\devag\.gemini\antigravity\scratch\standards\tests\fixtures\sample_boq_schedule.xlsx"
print("Note: sample_boq_schedule.xlsx is a constructed real-structured XLSX fixture (not a user tender).")

xlsx_adapter = get_adapter_for_file(XLSX_FIXTURE)
print(f"Selected Adapter for .xlsx: {xlsx_adapter.__class__.__name__}")
assert isinstance(xlsx_adapter, XlsxAdapter)

xlsx_blocks = xlsx_adapter.extract_blocks(XLSX_FIXTURE)
print(f"Extracted {len(xlsx_blocks)} PageBlocks from XLSX spreadsheet:")
for b in xlsx_blocks:
    print(f"  [p{b.page_no} b{b.block_idx:02d}] {b.text}")

xlsx_ext_result = ItemBuilder.build_items_from_blocks(xlsx_blocks, "SampleXLSX")
print(f"\nParsed {len(xlsx_ext_result.items)} Items via ItemBuilder from XLSX BoQ:")
for it in xlsx_ext_result.items:
    print(f"  Item {it.item_id}: code={it.material_code.value if it.material_code else 'N/A'} desc={repr(it.description.value[:45])} qty={it.quantity.value if it.quantity else 'N/A'} {it.unit.value if it.unit else ''}")
assert len(xlsx_ext_result.items) == 4, f"Expected 4 items from XLSX BoQ, got {len(xlsx_ext_result.items)}"
print("XLSX Adapter and ItemBuilder pipeline verified! ✓")


# ══════════════════════════════════════════════════════════════════════════════
# PART B.3: UPLOAD LIMITS ENFORCEMENT (SIZE LIMIT & ROW/PAGE LIMIT)
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "#" * 115)
print("PART B.3: UPLOAD LIMITS ENFORCEMENT VERIFICATION")
print("#" * 115)

from app.routers.audit_v2 import validate_file_limits, MAX_FILE_SIZE_BYTES, MAX_ROWS_PER_SPREADSHEET
from fastapi import HTTPException

# Test 1: File size limit check (file > 25MB)
oversized_dummy_path = os.path.join(r"C:\Users\devag\.gemini\antigravity\scratch\standards\tests\fixtures", "dummy_oversized.bin")
# Simulate file size check with real stat check
with open(oversized_dummy_path, "wb") as f:
    f.truncate(26 * 1024 * 1024)  # 26 MB

print(f"1. Testing file size limit (26MB dummy file > 25MB limit):")
size_err_caught = False
try:
    validate_file_limits(oversized_dummy_path)
except HTTPException as e:
    size_err_caught = True
    print(f"   Status Code: {e.status_code}")
    print(f"   Error Detail: '{e.detail}'")
    assert e.status_code == 413, f"Expected HTTP 413 for oversized file, got {e.status_code}"
    assert "exceeds the maximum upload size limit" in e.detail

assert size_err_caught is True, "Oversized file limit did not raise HTTPException!"
os.remove(oversized_dummy_path)
print("   Oversized file correctly rejected with HTTP 413 without silent truncation! ✓")

# Test 2: Row count limit check (spreadsheet > 5000 rows)
oversized_xlsx_path = os.path.join(r"C:\Users\devag\.gemini\antigravity\scratch\standards\tests\fixtures", "dummy_oversized_rows.xlsx")
import openpyxl
wb_large = openpyxl.Workbook()
ws_large = wb_large.active
ws_large.cell(row=5005, column=1, value="Exceeding row")
wb_large.save(oversized_xlsx_path)

print(f"\n2. Testing spreadsheet row count limit (5,005 rows > 5,000 limit):")
row_err_caught = False
try:
    validate_file_limits(oversized_xlsx_path)
except HTTPException as e:
    row_err_caught = True
    print(f"   Status Code: {e.status_code}")
    print(f"   Error Detail: '{e.detail}'")
    assert e.status_code == 400, f"Expected HTTP 400 for row count violation, got {e.status_code}"
    assert "exceeds the maximum limit of 5000 rows" in e.detail

assert row_err_caught is True, "Row count limit did not raise HTTPException!"
os.remove(oversized_xlsx_path)
print("   Oversized spreadsheet correctly rejected with HTTP 400 without silent truncation! ✓")

print("\n" + "=" * 115)
print("ALL ACCEPTANCE SUITE CHECKS (PART A & PART B) COMPLETED WITH 100% SUCCESS ✓")
print("=" * 115 + "\n")
