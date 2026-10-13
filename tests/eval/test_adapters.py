# -*- coding: utf-8 -*-
"""
tests/eval/test_adapters.py
===========================
Acceptance test suite for Document Adapters (Step 3).
Tests:
1. GenericPdfAdapter on PDF-1 (Technical Specifications 1)
2. GeMAdapter on PDF-2 (_Uploads_job_45941.pdf):
   - Every block on Page 1, Page 7, Page 8
   - Assertions for IS 694 x2, IS 4989, IS 1554 (CONTEXT_ONLY)
   - Assertion for IS 7098 (Part 1) (CORROBORATING)
   - Real per-page tier summary from adapter output
3. GeMAdapter on third GeM bid (gem_bid_sample3.pdf) for generalization
"""
import sys, os, re
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'C:\Users\devag\.gemini\antigravity\scratch\standards\backend')
sys.path.insert(0, r'C:\Users\devag\.gemini\antigravity\scratch\standards\tests\eval')
os.chdir(r'C:\Users\devag\.gemini\antigravity\scratch\standards\backend')

from app.adapters import get_adapter_for_file, GeMAdapter, GenericPdfAdapter
from mention_extractor import extract_mentions, load_db_sets
load_db_sets()

PDF1_PATH = r"C:\Users\devag\Downloads\Techical Specifications 1.pdf"
PDF2_PATH = r"C:\Users\devag\Downloads\_Uploads_job_45941.pdf"
PDF3_PATH = r"C:\Users\devag\.gemini\antigravity\scratch\standards\tests\fixtures\gem_bid_sample3.pdf"

print("=" * 90)
print("DOCUMENT ADAPTER ACCEPTANCE TEST SUITE (STEP 3)")
print("=" * 90)

# ── 1. TEST PDF-1 (Technical Specifications 1) ────────────────────────────────
print("\n" + "-" * 90)
print("TEST 1: Generic PDF Adapter on PDF-1 (Technical Specifications 1)")
print("-" * 90)
adapter1 = get_adapter_for_file(PDF1_PATH)
print(f"Selected Adapter: {adapter1.__class__.__name__}")
assert isinstance(adapter1, GenericPdfAdapter)

blocks1 = adapter1.extract_blocks(PDF1_PATH)
print(f"Extracted {len(blocks1)} blocks from PDF-1:")
for b in blocks1:
    mentions = [m for m in extract_mentions(b.text, b.tier) if m.disposition == 'KEEP']
    m_str = ', '.join(m.base_key for m in mentions) if mentions else '(none)'
    print(f"  p{b.page_no} b{b.block_idx:02d} [{b.tier:<14}] mentions={m_str:<25} text={b.text[:65]!r}")
    assert b.tier == "AUTHORITATIVE", f"Expected AUTHORITATIVE on PDF-1, got {b.tier}"
print("TEST 1 RESULT: ALL BLOCKS AUTHORITATIVE (PASS ✓)")


# ── 2. TEST PDF-2 (GeM Bid Job 45941) ─────────────────────────────────────────
print("\n" + "-" * 90)
print("TEST 2: GeM Adapter on PDF-2 (_Uploads_job_45941.pdf)")
print("-" * 90)
adapter2 = get_adapter_for_file(PDF2_PATH)
print(f"Selected Adapter: {adapter2.__class__.__name__}")
assert isinstance(adapter2, GeMAdapter)

blocks2 = adapter2.extract_blocks(PDF2_PATH)
print(f"Extracted {len(blocks2)} total blocks across all pages.")

# Print every block on Page 1
print("\n--- PDF-2 PAGE 1: EVERY BLOCK CLASSIFICATION ---")
p1_mentions = []
for b in blocks2:
    if b.page_no == 1:
        mentions = [m for m in extract_mentions(b.text, b.tier) if m.disposition == 'KEEP']
        m_str = ', '.join(f"{m.base_key} ({b.tier})" for m in mentions) if mentions else ''
        print(f"  p1 b{b.block_idx:02d} bbox=({b.bbox[0]:.0f},{b.bbox[1]:.0f}) [{b.tier:<14}] [{b.tier_reason[:30]:<30}] text={b.text[:65]!r}")
        if mentions:
            for m in mentions:
                p1_mentions.append((m.base_key.replace(' +NO_PART', ''), b.tier, m.raw_text))

# Print every block on Page 7 and Page 8
print("\n--- PDF-2 PAGE 7: EVERY BLOCK CLASSIFICATION ---")
for b in blocks2:
    if b.page_no == 7:
        print(f"  p7 b{b.block_idx:02d} bbox=({b.bbox[0]:.0f},{b.bbox[1]:.0f}) [{b.tier:<14}] [{b.tier_reason[:30]:<30}] text={b.text[:65]!r}")

print("\n--- PDF-2 PAGE 8: EVERY BLOCK CLASSIFICATION ---")
for b in blocks2:
    if b.page_no == 8:
        print(f"  p8 b{b.block_idx:02d} bbox=({b.bbox[0]:.0f},{b.bbox[1]:.0f}) [{b.tier:<14}] [{b.tier_reason[:30]:<30}] text={b.text[:65]!r}")

# Page 1 IS Mention Assertions
print("\n--- PAGE 1 IS MENTION TIER ASSERTIONS ---")
for bk, tier, raw in p1_mentions:
    print(f"  Mention found: raw={raw!r:<20} base_key={bk:<18} tier={tier}")

# Group tiers by base_key
p1_tiers = {}
for bk, tier, _ in p1_mentions:
    p1_tiers.setdefault(bk, []).append(tier)

# Mandatory assertions from prompt
assert 'CONTEXT_ONLY' in p1_tiers.get('IS694', []), f"IS 694 not CONTEXT_ONLY: {p1_tiers.get('IS694')}"
assert len([t for t in p1_tiers.get('IS694', []) if t == 'CONTEXT_ONLY']) >= 2, "Expected 2 IS 694 CONTEXT_ONLY mentions"
assert 'CONTEXT_ONLY' in p1_tiers.get('IS4989', []), f"IS 4989 not CONTEXT_ONLY: {p1_tiers.get('IS4989')}"
assert 'CONTEXT_ONLY' in p1_tiers.get('IS1554(PART1)', []), f"IS 1554 (Part 1) not CONTEXT_ONLY: {p1_tiers.get('IS1554(PART1)')}"
assert 'CORROBORATING' in p1_tiers.get('IS7098(PART1)', []), f"IS 7098 (Part 1) not CORROBORATING: {p1_tiers.get('IS7098(PART1)')}"

print("\nAssertions Check:")
print("  ASSERT IS 694 x2 has CONTEXT_ONLY:      PASS ✓")
print("  ASSERT IS 4989 has CONTEXT_ONLY:         PASS ✓")
print("  ASSERT IS 1554 (Part 1) has CONTEXT_ONLY: PASS ✓")
print("  ASSERT IS 7098 (Part 1) has CORROBORATING: PASS ✓")

# Real per-page tier summary from actual adapter output
print("\n--- PDF-2 ACTUAL PER-PAGE TIER SUMMARY (from GeMAdapter output) ---")
page_tiers_actual = {}
for b in blocks2:
    page_tiers_actual.setdefault(b.page_no, set()).add(b.tier)

for p in sorted(page_tiers_actual.keys()):
    tiers_list = sorted(page_tiers_actual[p])
    print(f"  Page {p}: {tiers_list}")


# ── 3. TEST SAMPLE 3 (Generalization on Third GeM Bid) ─────────────────────────
print("\n" + "-" * 90)
print("TEST 3: GeM Adapter on Third GeM Bid (gem_bid_sample3.pdf)")
print("-" * 90)
adapter3 = get_adapter_for_file(PDF3_PATH)
print(f"Selected Adapter: {adapter3.__class__.__name__}")
assert isinstance(adapter3, GeMAdapter)

blocks3 = adapter3.extract_blocks(PDF3_PATH)
sample3_mentions = []
for b in blocks3:
    mentions = [m for m in extract_mentions(b.text, b.tier) if m.disposition == 'KEEP']
    for m in mentions:
        sample3_mentions.append((m.base_key.replace(' +NO_PART', ''), b.tier, m.raw_text, b.page_no))
    m_str = ', '.join(f"{m.base_key} ({b.tier})" for m in mentions) if mentions else ''
    print(f"  p{b.page_no} b{b.block_idx:02d} [{b.tier:<14}] [{b.tier_reason[:25]:<25}] mentions={m_str:<30} text={b.text[:55]!r}")

s3_dict = {}
for bk, tier, raw, p in sample3_mentions:
    s3_dict[bk] = tier

print("\nSample 3 Mention Assertions:")
assert s3_dict.get('IS1239(PART1)') == 'CONTEXT_ONLY', f"IS 1239 expected CONTEXT_ONLY, got {s3_dict.get('IS1239(PART1)')}"
assert s3_dict.get('IS2062') == 'CONTEXT_ONLY', f"IS 2062 expected CONTEXT_ONLY, got {s3_dict.get('IS2062')}"
assert s3_dict.get('IS3589') == 'CORROBORATING', f"IS 3589 expected CORROBORATING, got {s3_dict.get('IS3589')}"
assert s3_dict.get('IS456') == 'AUTHORITATIVE', f"IS 456 expected AUTHORITATIVE, got {s3_dict.get('IS456')}"
assert s3_dict.get('IS808') == 'AUTHORITATIVE', f"IS 808 expected AUTHORITATIVE, got {s3_dict.get('IS808')}"
assert s3_dict.get('IS1239(PART2)') == 'CONTEXT_ONLY', f"IS 1239 (Part 2) expected CONTEXT_ONLY (GTC), got {s3_dict.get('IS1239(PART2)')}"

print("  ASSERT IS 1239 (Part 1) CONTEXT_ONLY (Searched Result): PASS ✓")
print("  ASSERT IS 2062 CONTEXT_ONLY (Searched Result):          PASS ✓")
print("  ASSERT IS 3589 CORROBORATING (Relevant Category):       PASS ✓")
print("  ASSERT IS 456 AUTHORITATIVE (Technical Spec):           PASS ✓")
print("  ASSERT IS 808 AUTHORITATIVE (Buyer ATC):                PASS ✓")
print("  ASSERT IS 1239 (Part 2) CONTEXT_ONLY (GTC):             PASS ✓")

print("\n" + "=" * 90)
print("ALL STEP 3 ADAPTER ACCEPTANCE TESTS PASSED WITH 100% SUCCESS ✓")
print("=" * 90)
