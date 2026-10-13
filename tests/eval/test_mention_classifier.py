# -*- coding: utf-8 -*-
"""
tests/eval/test_mention_classifier.py
=====================================
Comprehensive Acceptance Test Suite for Mention Role Classifier:
1. Real GeM PDFs Mentions: Runs live classifier on PDF-1 and PDF-2 mentions.
2. GeMARPTS CONTEXT_ONLY Isolation & Adversarial Hard Prior Test:
   Confirms IS 4989, IS 694, IS 1554 from PDF-2 p1 b18 get noise or vague_reference,
   never required_spec, even when deliberately tempted by an adversarial prompt.
3. needs_review Fallback Test: Demonstrates fallback triggered by mocked malformed response.
4. Token Cost Telemetry: Verifies output tokens per batch are far below the 1,000 OTPM cap.
5. Three Bounded-Extractor Samples: Runs live classifier on all mentions from Step 4b samples.
"""
import sys, os, time, json
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'C:\Users\devag\.gemini\antigravity\scratch\standards\backend')

from app.adapters import get_adapter_for_file
from app.parsers.mention_extractor import extract_mentions, load_db_sets
from app.parsers.mention_classifier import (
    MentionRoleClassifier,
    MentionRole,
    MentionToClassify,
    ClassifiedMention,
    get_mention_classifier
)
from app.parsers.groq_wrapper import get_groq_wrapper

load_db_sets()

PDF1_PATH = r"C:\Users\devag\Downloads\Techical Specifications 1.pdf"
PDF2_PATH = r"C:\Users\devag\Downloads\_Uploads_job_45941.pdf"

print("=" * 110)
print("STAGE: MENTION ROLE CLASSIFIER ACCEPTANCE SUITE")
print("=" * 110)

classifier = MentionRoleClassifier()


# ══════════════════════════════════════════════════════════════════════════════
# ACCEPTANCE ITEM 1: REAL GeM PDFs MENTIONS CLASSIFICATION
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "#" * 110)
print("PART 1: REAL GeM BID PDFs MENTIONS CLASSIFICATION (PDF-1 & PDF-2)")
print("#" * 110)

def extract_pdf_mentions(pdf_path: str, doc_name: str) -> list[MentionToClassify]:
    adapter = get_adapter_for_file(pdf_path)
    blocks = adapter.extract_blocks(pdf_path)
    items: list[MentionToClassify] = []
    for b in blocks:
        found = extract_mentions(b.text, source_block_tier=b.tier)
        for mn in found:
            sec_info = f" | Section: {b.section_label}" if b.section_label else ""
            items.append(MentionToClassify(
                mention=mn,
                tier=b.tier,
                context=f"Doc: {doc_name} p{b.page_no} b{b.block_idx:02d} [{b.tier}]{sec_info} - {b.text}"
            ))
    return items

pdf1_mentions = extract_pdf_mentions(PDF1_PATH, "PDF-1")
pdf2_mentions = extract_pdf_mentions(PDF2_PATH, "PDF-2")

print(f"\n1. Classifying PDF-1 Mentions ({len(pdf1_mentions)} total)...")
res_pdf1 = classifier.classify_batch(pdf1_mentions, batch_size=8, prompt_version="pdf1_roles_v1")
for idx, cm in enumerate(res_pdf1, 1):
    print(f"   [{idx}] {cm.mention.raw_text:<25} base={cm.mention.base_key:<16} tier={cm.tier:<14} -> ROLE: {cm.role.value:<18} (cached={cm.cached})")
    assert cm.role in (MentionRole.REQUIRED_SPEC, MentionRole.CERTIFICATION_MARK), f"Unexpected role for PDF-1 spec: {cm.role}"

print(f"\n2. Classifying PDF-2 Mentions ({len(pdf2_mentions)} total)...")
res_pdf2 = classifier.classify_batch(pdf2_mentions, batch_size=8, prompt_version="pdf2_roles_v1")
for idx, cm in enumerate(res_pdf2, 1):
    print(f"   [{idx}] {cm.mention.raw_text:<25} base={cm.mention.base_key:<16} tier={cm.tier:<14} -> ROLE: {cm.role.value:<18} (cached={cm.cached})")

# Assertions on PDF-2 roles:
# CONTEXT_ONLY mentions in p1 b18 must be noise or vague_reference, NEVER required_spec
p1_b18_mentions = [cm for cm in res_pdf2 if cm.tier == "CONTEXT_ONLY"]
assert len(p1_b18_mentions) == 4
for cm in p1_b18_mentions:
    assert cm.role in (MentionRole.NOISE, MentionRole.VAGUE_REFERENCE), f"CONTEXT_ONLY mention got invalid role: {cm.role}"
    assert cm.role != MentionRole.REQUIRED_SPEC, f"CONTEXT_ONLY mention must NEVER be required_spec! Got {cm.role}"

# Relevant category mention in p1 b20 (CORROBORATING)
corroborating_mentions = [cm for cm in res_pdf2 if cm.tier == "CORROBORATING"]
assert len(corroborating_mentions) == 1
assert corroborating_mentions[0].role in (MentionRole.CATEGORY_LABEL, MentionRole.VAGUE_REFERENCE), f"Expected category label, got {corroborating_mentions[0].role}"

print("\nPDF-1 and PDF-2 mentions classified and verified successfully! ✓")


# ══════════════════════════════════════════════════════════════════════════════
# ACCEPTANCE ITEM 2: GeMARPTS CONTEXT_ONLY ADVERSARIAL HARD-PRIOR TEST
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "#" * 110)
print("PART 2: GeMARPTS CONTEXT_ONLY ISOLATION & ADVERSARIAL HARD-PRIOR OVERRIDE TEST")
print("#" * 110)

print("Target Mentions in GeMARPTS Searched Result Block (p1 b18):")
print("  - IS 694")
print("  - IS 4989")
print("  - IS 1554 (Part 1)")
print("  - IS 694")

# Adversarial Test: Force mock LLM to return 'required_spec' for these CONTEXT_ONLY mentions
print("\nInjecting ADVERSARIAL LLM response that claims all these mentions are 'required_spec'...")
adversarial_classifier = MentionRoleClassifier()
adversarial_res = adversarial_classifier.classify_batch(
    p1_b18_mentions,
    force_adversarial_role=MentionRole.REQUIRED_SPEC
)

print("\nAdversarial Test Evaluation Results:")
for cm in adversarial_res:
    print(f"   Mention: {cm.mention.raw_text:<20} | Source Tier: {cm.tier:<14} | Result Role: {cm.role.value:<12} | Override: {cm.override_reason}")
    assert cm.role != MentionRole.REQUIRED_SPEC, "CRITICAL ERROR: CONTEXT_ONLY mention was assigned required_spec!"
    assert cm.role in (MentionRole.NOISE, MentionRole.VAGUE_REFERENCE), f"Expected noise or vague_reference, got {cm.role}"
    assert cm.override_reason == "TIER_HARD_PRIOR_CONTEXT_ONLY_CANNOT_BE_REQUIRED_SPEC"

print("\nHard prior verified: CONTEXT_ONLY mentions CAN NEVER receive required_spec under any prompt! ✓")


# ══════════════════════════════════════════════════════════════════════════════
# ACCEPTANCE ITEM 3: DETERMINISTIC 'needs_review' FALLBACK ON MALFORMED / TIMEOUT
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "#" * 110)
print("PART 3: DETERMINISTIC 'needs_review' FALLBACK ON CLASSIFIER FAILURE")
print("#" * 110)

test_fail_items = [
    MentionToClassify(mention=pdf1_mentions[0].mention, tier="AUTHORITATIVE", context="Testing malformed failure fallback")
]

# Simulate malformed non-JSON output from LLM (e.g. gateway error or corrupted output)
malformed_output = "<html>502 Bad Gateway: The upstream server failed to respond.</html>"

fallback_classifier = MentionRoleClassifier()
fallback_res = fallback_classifier.classify_batch(test_fail_items, mock_response=malformed_output)

print(f"Mocked Malformed LLM Response: {repr(malformed_output)}")
print(f"Fallback Result Role: {fallback_res[0].role.value}")
print(f"Override Reason     : {fallback_res[0].override_reason}")

assert fallback_res[0].role == MentionRole.NEEDS_REVIEW, f"Expected needs_review, got {fallback_res[0].role}"
assert fallback_res[0].role != MentionRole.REQUIRED_SPEC, "Failure must NEVER fallback to required_spec!"
print("Fallback verified: Classifier failure safely defaults to 'needs_review', never 'required_spec'! ✓")


# ══════════════════════════════════════════════════════════════════════════════
# ACCEPTANCE ITEM 4: TOKEN COST & OTPM CAP COMPLIANCE
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "#" * 110)
print("PART 4: TOKEN COST PER BATCH & 1,000 OTPM CAP COMPLIANCE")
print("#" * 110)

# Check last live batch stats from classifier
stats = classifier.last_batch_stats
print(f"Live Batch Telemetry:")
print(f"  Batch Size                : {stats.get('batch_size')} mentions")
print(f"  Output Tokens Reserved    : {stats.get('output_tokens_reserved')} tokens")
print(f"  Elapsed Time              : {stats.get('elapsed_seconds')} s")
print(f"  Key Slot Serving Call     : {stats.get('serving_slot')}")
print(f"  OTPM Cap Utilization      : ~{stats.get('output_tokens_reserved', 0) / 1000 * 100:.1f}% of 1,000 OTPM limit")

assert stats.get('output_tokens_reserved', 0) <= 250, "Output tokens exceed expected budget!"
print("Token cost confirmed: Bounded batch output consumes <25% of 1,000 OTPM cap! ✓")


# ══════════════════════════════════════════════════════════════════════════════
# ACCEPTANCE ITEM 5: THREE BOUNDED-EXTRACTOR PASTED-TEXT SAMPLES
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "#" * 110)
print("PART 5: THREE BOUNDED-EXTRACTOR PASTED-TEXT SAMPLES' MENTIONS")
print("#" * 110)

SAMPLES = [
    ("Sample 1 (GeM Cables BoQ)", """Schedule of Quantities and Technical Specifications:
Item 1: XLPE Insulated Armoured Power Cable 3.5 Core x 185 Sq.mm aluminium conductor
Conforming strictly to IS 7098 (Part 1):1988 with up-to-date amendments.
Quantity: 1200 MTR
Item 2: PVC Insulated Copper Control Cable 4 Core x 2.5 Sq.mm flexible conductor
Conforming strictly to IS 1554 (Part 1) and IS 694.
Quantity: 3500 MTR
Item 3: Multistrand Flexible Single Core Copper Wire 1.5 Sq.mm FRLS insulation
Conforming to IS 694:2010 with authentic ISI mark.
Quantity: 5000 MTR"""),

    ("Sample 2 (CPWD Civil & Structural)", """Bill of Quantities for Construction Package 04:
Item 1: High Yield Strength Deformed Thermo-Mechanically Treated TMT steel bars Fe 500D
Material must comply with IS 1786:2008 specifications for concrete reinforcement.
Estimated Quantity: 450 MT
Item 2: Ordinary Portland Cement Grade 53 in 50 kg HDPE bags
Manufactured and tested in strict compliance with IS 269:2015.
Estimated Quantity: 8000 Bags
Item 3: Structural Steel Hot Rolled Medium Weight Beams ISMB 300
Conforming to IS 808:1989 and IS 2062 Grade E250 quality A.
Estimated Quantity: 150 MT"""),

    ("Sample 3 (NTPC Industrial Procurement)", """NTPC Procurement Tender No: NTPC/2026/BOQ/001
Notice: For inquiries contact grievance officer at hod.tender@ntpc.co.in or call +91 98765 43210.
Schedule Items:
Line 1: Material Code: 8110264037 - CBLE: PVC FRLS 1.1KV Copper Conductor 1CX1.5 SQMM
Technical Specification: Heavy duty PVC insulated cables per IS 694:2010.
Quantity: 6500 MTR
Line 2: Material Code: 9876543210 - CBLE: PVC 1.1KV Copper Conductor 1CX2.5 SQMM
Technical Specification: Single core PVC cable conforming to IS 694.
Quantity: 4200 MTR
Line 3: Material Code: 7112345678 - CBLE: PVC 1.1KV Armoured FRLS Copper 3CX2.5 SQMM
Technical Specification: Multi core armoured cable conforming to IS 1554 (Part 1).
Quantity: 1800 MTR""")
]

for s_label, s_text in SAMPLES:
    print(f"\n--- {s_label} ---")
    raw_mentions = extract_mentions(s_text, source_block_tier="AUTHORITATIVE")
    to_classify = [
        MentionToClassify(
            mention=m,
            tier="AUTHORITATIVE",
            context=f"{m.context_before} [{m.raw_text}] {m.context_after}"
        )
        for m in raw_mentions
    ]
    classified = classifier.classify_batch(to_classify, batch_size=8, prompt_version=f"{s_label}_v1")
    print(f"Extracted & Classified {len(classified)} mentions:")
    for c in classified:
        print(f"   {c.mention.raw_text:<25} base={c.mention.base_key:<18} -> ROLE: {c.role.value:<18} (cached={c.cached})")
        assert c.role in (MentionRole.REQUIRED_SPEC, MentionRole.CERTIFICATION_MARK), f"Unexpected role for sample mention: {c.role}"

print("\nAll pasted-text samples' mentions classified and verified as required specifications! ✓")

print("\n" + "=" * 110)
print("ALL MENTION ROLE CLASSIFIER ACCEPTANCE TESTS COMPLETED WITH 100% SUCCESS ✓")
print("=" * 110 + "\n")
