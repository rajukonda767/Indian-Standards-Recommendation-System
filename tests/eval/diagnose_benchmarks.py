# -*- coding: utf-8 -*-
"""
tests/eval/diagnose_benchmarks.py
=================================
Diagnoses the 61s -> 110s regression with isolated, transparent comparative benchmarks:
1. Clarifies Original 40-item Set vs Rebuilt Diverse 40-item Set.
2. Re-runs the ORIGINAL 40-item set through the parallel runner and reports real wall-clock time.
3. Re-runs the REBUILT diverse set separately and reports its time, breaking out individual item contributions.
4. Reports misses as misses explicitly, without bundling into false success statements.
"""
import sys, os, time, json
sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
sys.path.insert(0, r'C:\Users\devag\.gemini\antigravity\scratch\standards\backend')

from app.db import init_db_pool, get_db_cursor
from app.parsers.mention_extractor import load_db_sets
from app.jobs.job_store import create_job, get_job, get_job_items
from app.jobs.runner import launch_audit_job

load_db_sets()
init_db_pool(10, 20)

print("=" * 115)
print("BENCHMARK REGRESSION DIAGNOSIS: ORIGINAL 40-ITEM SET vs REBUILT DIVERSE 40-ITEM SET")
print("=" * 115)


# ══════════════════════════════════════════════════════════════════════════════
# QUESTION 1: CONFLATION CLARIFICATION
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "#" * 115)
print("1. CLARIFICATION ON BENCHMARK DATASETS (ORIGINAL vs REBUILT DIVERSE)")
print("#" * 115)

clarification_statement = """Clarification on Dataset Conflation:
• 61.359s Run : Executed against the ORIGINAL 40-item synthetic set (synthetic_bank from
  `tests/eval/test_job_runner_40_items.py`). All 40 items cited valid/active standards (IS 7098,
  IS 1554, IS 694, IS 1786, IS 269, IS 1239, IEC 60227). It had ZERO intentional timeouts,
  ZERO non-standard entries, and ran through a single-threaded sequential loop.
• 110.948s Run: Executed against the REBUILT DIVERSE 40-item set (rebuilt_bank from
  `tests/eval/test_acceptance_part_a_and_b.py`). This set introduced deliberate edge cases:
  superseded editions (IS 7098:1988, IS 1554:1976), outdated editions (IS 1786:1985, IS 456:1978),
  material conflicts (PVC vs XLPE), missing citations, foreign standards (DIN 99999), and
  unverified standards.
• CONCLUSION  : The 110.948s run was NOT run against the original 40 items. They were two
  completely different datasets. The previous report conflated the dataset change with
  parallelization overhead."""

print(clarification_statement)


# ══════════════════════════════════════════════════════════════════════════════
# RUN 1: ORIGINAL 40-ITEM BENCHMARK THROUGH PARALLEL RUNNER
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "#" * 115)
print("2. RUN 1: ORIGINAL 40-ITEM SET THROUGH PARALLEL RUNNER")
print("#" * 115)

original_synthetic_bank = [
    # IS 7098 (Part 1) Power cables (XLPE 1.1kV)
    {"desc": "CBLE: PVC FRLS 1.1KV: CU-STR: 1CX1.5SQMM", "spec": "POWER CABLE :SPECIFICATION/VOLTAGE GRADE- IS : 7098 XLPE CU STRANDED", "qty": "5000", "unit": "MTR", "code": "CBL-1001"},
    {"desc": "CBLE: PVC 1.1KV: CU-STR: 1CX2.5SQMM", "spec": "POWER CABLE (PART-1):SPECIFICATION/VOLTAGE GRADE-IS : 7098 XLPE INSULATED", "qty": "3500", "unit": "MTR", "code": "CBL-1002"},
    {"desc": "CBLE: PVC 1.1KV AR FRLS: CU-STR: 3CX2.5SQMM", "spec": "CONTROL CABLE :SPECIFICATION/VOLTAGE GRADE-IS : 7098 XLPE", "qty": "2000", "unit": "MTR", "code": "CBL-1003"},
    # IS 1554 (Part 1) PVC control cables
    {"desc": "Control Cable 4 Core x 1.5 sq mm Copper", "spec": "Conforming to IS 1554 (Part 1):1988 with PVC outer sheath", "qty": "1500", "unit": "MTR", "code": "CBL-2001"},
    {"desc": "Heavy Duty Control Cable 10C x 2.5 sq mm", "spec": "Conforming to IS 1554 (Part 1)", "qty": "800", "unit": "MTR", "code": "CBL-2002"},
    # IS 694 Building wiring
    {"desc": "PVC Insulated Copper Wire 1.5 sq mm Single Core", "spec": "House wiring copper cable conforming to IS 694:2010", "qty": "10000", "unit": "MTR", "code": "WIR-3001"},
    {"desc": "PVC Flexible Cable 3 Core 2.5 sq mm", "spec": "Conforming strictly to IS 694", "qty": "4000", "unit": "MTR", "code": "WIR-3002"},
    # IS 1786 TMT Steel Bars
    {"desc": "High Strength Deformed Steel Bars Fe 500D 12mm", "spec": "Thermo-Mechanically Treated bars conforming to IS 1786:2008", "qty": "50", "unit": "MT", "code": "STL-4001"},
    {"desc": "TMT Rebars Fe 550D 16mm", "spec": "Conforming to IS 1786", "qty": "75", "unit": "MT", "code": "STL-4002"},
    # IS 269 Cement
    {"desc": "Ordinary Portland Cement 53 Grade", "spec": "High strength OPC cement conforming to IS 269:2015 in 50kg bags", "qty": "2000", "unit": "BAG", "code": "CMT-5001"},
    # IS 1239 Steel Tubes & Pipes
    {"desc": "Mild Steel Seamless Tubes Heavy Grade 50mm NB", "spec": "Conforming to IS 1239 (Part 1):2004 with screwed ends", "qty": "1200", "unit": "MTR", "code": "PIP-6001"},
    {"desc": "Malleable Cast Iron Pipe Fittings 50mm Elbows", "spec": "Conforming to IS 1239 (Part 2)", "qty": "300", "unit": "NOS", "code": "PIP-6002"},
    # International Equivalent Standard (IEC 60227 -> IS 694)
    {"desc": "Single Core PVC Wire 4 sq mm", "spec": "Conforming to IEC 60227 for electrical installations", "qty": "2500", "unit": "MTR", "code": "INT-7001"},
]

forty_items_original = []
for i in range(40):
    tmpl = original_synthetic_bank[i % len(original_synthetic_bank)]
    num = i + 1
    forty_items_original.append({
        "item_id": f"ITEM-{num:03d}",
        "seq_no": num,
        "description": f"{tmpl['desc']} [Batch #{num}]",
        "technical_spec": tmpl["spec"],
        "quantity": tmpl["qty"],
        "unit": tmpl["unit"],
        "material_code": f"{tmpl['code']}-{num:02d}",
    })

print(f"Launching Original 40-Item Benchmark through Parallel Runner (6 workers, pre-warmed pool)...")
t0_orig = time.perf_counter()
orig_job_id = launch_audit_job(raw_items=forty_items_original, doc_type="gem")
print(f"Created Job ID: {orig_job_id}")

poll_cnt = 0
seen_prog = set()
while True:
    time.sleep(0.3)
    poll_cnt += 1
    st = get_job(orig_job_id)
    if not st:
        continue
    status = st["status"]
    done_c = st.get("done_items", 0)
    total_c = st.get("total_items", 40)
    if done_c > len(seen_prog) or status in ("done", "error"):
        print(f"  [Poll #{poll_cnt:02d}] Status: {status:<8} | Progress: {done_c}/{total_c} items completed")
        seen_prog.add(done_c)
    if status in ("done", "error"):
        break

t1_orig = time.perf_counter()
orig_wall_clock = round(t1_orig - t0_orig, 3)

orig_db_items = get_job_items(orig_job_id)
orig_ms_list = [it.get("processing_ms", 0.0) for it in orig_db_items]
orig_timeouts = [it for it in orig_db_items if it["status"] == "cannot_verify" and any("timed out" in f.get("message", "") for f in it.get("findings", []))]

print(f"\nOriginal 40-Item Parallel Run Telemetry:")
print(f"  • Job ID                    : {orig_job_id}")
print(f"  • Status                    : {st['status'].upper()}")
print(f"  • Total Items Audited       : {len(orig_db_items)}/40")
print(f"  • Items Timed Out           : {len(orig_timeouts)}")
print(f"  • ACTUAL Wall-Clock Time    : {orig_wall_clock} seconds (~{orig_wall_clock/40*1000:.1f} ms/item)")
print(f"  • Previous Sequential Time  : 61.359 seconds")
print(f"  • Target <=60s Met?         : {'YES! [PASS]' if orig_wall_clock <= 60.0 else 'NO - MISS [FAIL]'}")
print(f"  • Coverage Score            : {st.get('coverage', 0.0):.1f}%")
print(f"  • Currency Score            : {st.get('currency', 0.0):.1f}%")
print(f"  • QCO Compliance Score      : {st.get('qco_compliance', 0.0):.1f}%")


# ══════════════════════════════════════════════════════════════════════════════
# RUN 2: REBUILT DIVERSE 40-ITEM BENCHMARK (DETAILED TIMING BREAKOUT)
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "#" * 115)
print("3. RUN 2: REBUILT DIVERSE 40-ITEM SET THROUGH PARALLEL RUNNER (BREAKOUT ANALYSIS)")
print("#" * 115)

rebuilt_bank = [
    {"desc": "Power Cable 1.1kV XLPE", "spec": "Conforming to IS 7098 (Part 1):1988 specification", "qty": "3000", "unit": "MTR", "code": "CBL-SUP-01"},
    {"desc": "Heavy Duty PVC Control Cable", "spec": "Conforming to IS 1554 (Part 1):1988 specification", "qty": "2000", "unit": "MTR", "code": "CBL-SUP-02"},
    {"desc": "High Strength TMT Steel Rebars", "spec": "Steel bars conforming to IS 1786:1985", "qty": "50", "unit": "MT", "code": "STL-OUT-01"},
    {"desc": "RCC Structural Concrete", "spec": "Design strictly per IS 456:1978 code of practice", "qty": "200", "unit": "CUM", "code": "CIV-OUT-02"},
    {"desc": "PVC INSULATED Copper Wire 1.1kV", "spec": "XLPE INSULATED POWER CABLE TO IS 7098 (Part 1):2025", "qty": "1500", "unit": "MTR", "code": "CBL-CON-01"},
    {"desc": "Fabricated Mild Steel Support Brackets and Clamps", "spec": "High quality galvanized steel accessories for cable tray mounting", "qty": "500", "unit": "NOS", "code": "SUP-MIS-01"},
    {"desc": "Imported Specialized Valve", "spec": "Manufactured strictly to DIN 99999 standard specification", "qty": "10", "unit": "NOS", "code": "VAL-UNK-01"},
    {"desc": "Ordinary Portland Cement 53 Grade", "spec": "Conforming to IS 269:2015 with valid BIS license and ISI mark on every bag", "qty": "5000", "unit": "BAG", "code": "CMT-OK-01"},
    {"desc": "Mild Steel Tubes Heavy Grade", "spec": "Conforming to IS 1239 (Part 1):2004 carrying standard ISI mark", "qty": "2000", "unit": "MTR", "code": "PIP-OK-02"},
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

print(f"Launching Rebuilt Diverse 40-Item Benchmark through Parallel Runner...")
t0_reb = time.perf_counter()
reb_job_id = launch_audit_job(raw_items=forty_items_rebuilt, doc_type="gem")
print(f"Created Job ID: {reb_job_id}")

poll_cnt2 = 0
seen_prog2 = set()
while True:
    time.sleep(0.3)
    poll_cnt2 += 1
    st2 = get_job(reb_job_id)
    if not st2:
        continue
    status = st2["status"]
    done_c = st2.get("done_items", 0)
    total_c = st2.get("total_items", 40)
    if done_c > len(seen_prog2) or status in ("done", "error"):
        print(f"  [Poll #{poll_cnt2:02d}] Status: {status:<8} | Progress: {done_c}/{total_c} items completed")
        seen_prog2.add(done_c)
    if status in ("done", "error"):
        break

t1_reb = time.perf_counter()
reb_wall_clock = round(t1_reb - t0_reb, 3)

reb_db_items = get_job_items(reb_job_id)
reb_timeouts = [it for it in reb_db_items if it["status"] == "cannot_verify" and any("timed out" in f.get("message", "") for f in it.get("findings", []))]
reb_non_timeout = [it for it in reb_db_items if it not in reb_timeouts]

print(f"\nRebuilt Diverse 40-Item Parallel Run Telemetry:")
print(f"  • Job ID                    : {reb_job_id}")
print(f"  • Status                    : {st2['status'].upper()}")
print(f"  • Total Items Audited       : {len(reb_db_items)}/40")
print(f"  • TOTAL Wall-Clock Time     : {reb_wall_clock} seconds")
print(f"  • Items Timed Out           : {len(reb_timeouts)}")
if reb_timeouts:
    timeout_items_str = ", ".join(f"Item #{it['seq_no']} ({it['item_id']})" for it in reb_timeouts)
    print(f"  • Timed-Out Items List      : {timeout_items_str}")
    print(f"  • Contribution Breakout     : {len(reb_non_timeout)} items completed in non-timeout processing; {len(reb_timeouts)} item(s) hit timeout.")
else:
    print(f"  • Contribution Breakout     : 40/40 items completed successfully with zero timeouts!")
print(f"  • Target <=60s Met?         : {'YES! [PASS]' if reb_wall_clock <= 60.0 else 'NO - MISS [FAIL]'}")

status_counts = {}
badge_counts = {}
for it in reb_db_items:
    status_counts[it["status"]] = status_counts.get(it["status"], 0) + 1
    badge_counts[it["badge_color"]] = badge_counts.get(it["badge_color"], 0) + 1

print(f"\nRebuilt Diverse Status Distribution:")
for s, c in sorted(status_counts.items()):
    print(f"  • {s.upper():<16}: {c} items")

print(f"\nRebuilt Diverse Badge Colors:")
for b, c in sorted(badge_counts.items()):
    print(f"  • {b.upper():<10}: {c} items")


# ══════════════════════════════════════════════════════════════════════════════
# 4. FINAL HONEST SUMMARY (REPORTING MISSES AS MISSES EXPLICITLY)
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 115)
print("EXPLICIT BENCHMARK SUMMARY & PERFORMANCE TARGET EVALUATION")
print("=" * 115)
print(f"1. ORIGINAL 40-Item Set Wall-Clock : {orig_wall_clock}s (vs <=60.0s target)")
if orig_wall_clock <= 60.0:
    print("   -> ORIGINAL RUN RESULT: MET TARGET (PASS) ✓")
else:
    print("   -> ORIGINAL RUN RESULT: MISS (FAIL) ✗")

print(f"2. REBUILT 40-Item Diverse Set     : {reb_wall_clock}s (vs <=60.0s target)")
if reb_wall_clock <= 60.0:
    print("   -> REBUILT RUN RESULT  : MET TARGET (PASS) ✓")
else:
    print("   -> REBUILT RUN RESULT  : MISS (FAIL) ✗")
print("=" * 115 + "\n")
