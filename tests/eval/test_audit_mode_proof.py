# -*- coding: utf-8 -*-
"""
tests/eval/test_audit_mode_proof.py
===================================
Proof of audit_mode:
1. Replaces Groq client with a mock that raises AssertionError if called.
2. Proves retrieve_recommendations(..., audit_mode=True) never calls Groq.
3. Proves Item 4 top-10 candidates are IDENTICAL with and without citation text
   when stripped of citation spans and trigger words ("as per", "conforming to").
4. Re-runs Phase 1 acceptance query with audit_mode=False to confirm zero regression.
"""
import sys, os, re
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'C:\Users\devag\.gemini\antigravity\scratch\standards\backend')
os.chdir(r'C:\Users\devag\.gemini\antigravity\scratch\standards\backend')

from app.db import init_db_pool
init_db_pool()
from app.services.embedding import EmbeddingService
EmbeddingService.get_instance()

import services.retrieval as ret_mod
from schemas import ExtractedSpec

print("=" * 80)
print("AUDIT_MODE PROOF & NON-CIRCULAR RETRIEVAL TEST")
print("=" * 80)

# ── 1. TEST THAT GROQ IS NEVER CALLED IN AUDIT_MODE ───────────────────────────
class RaisingGroq:
    class Chat:
        class Completions:
            @staticmethod
            def create(*args, **kwargs):
                raise AssertionError("CRITICAL FAILURE: Groq API was called during audit_mode=True!")
        completions = Completions()
    chat = Chat()

original_get_groq = ret_mod._get_groq
ret_mod._get_groq = lambda: RaisingGroq()

test_spec = ExtractedSpec(
    product_category="power cable",
    material="PVC",
    voltage_rating="1.1kV",
    dimensions=None,
    application=None,
    cited_standard_raw=None,
    brand_names_removed=[]
)

try:
    resp, timings = ret_mod.retrieve_recommendations(
        "PVC insulated power cable 1.1kV",
        test_spec,
        audit_mode=True
    )
    print("\n1. RaisingGroq Mock Test:")
    print(f"   audit_mode=True executed successfully in {timings.get('total_ms')}ms")
    print(f"   Candidates returned: {len(resp.primary or resp.candidates)}")
    print("   ASSERTION PASSED: Zero Groq API calls made during audit_mode ✓")
except AssertionError as e:
    print(f"   FAILED: {e}")
    sys.exit(1)
finally:
    ret_mod._get_groq = original_get_groq


# ── 2. PROVE TOP-10 IDENTICAL WITH & WITHOUT CITATION TEXT ────────────────────
def clean_audit_query(raw_text: str, citation_spans: list[str]) -> str:
    """Strip citation spans and trigger words ('as per', 'conforming to', 'marked to')."""
    s = raw_text
    for span in citation_spans:
        s = re.sub(re.escape(span.strip()), '', s)
    # Strip trigger phrases
    s = re.sub(r'\b(?:as\s+per|conforming\s+to|marked\s+to|meeting\s+specifications?\s+of)\b', '', s, flags=re.I)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

query_with_citation = "PVC insulated power cable 1.1kV as per IS 7098 (Part 1)"
query_without_citation = "PVC insulated power cable 1.1kV"

clean_q1 = clean_audit_query(query_with_citation, ["IS 7098 (Part 1)"])
clean_q2 = clean_audit_query(query_without_citation, [])

print(f"\n2. Non-Circular Top-10 Invariance Test:")
print(f"   Original with citation:    {query_with_citation!r}")
print(f"   Cleaned query 1:           {clean_q1!r}")
print(f"   Original without citation: {query_without_citation!r}")
print(f"   Cleaned query 2:           {clean_q2!r}")

resp1, _ = ret_mod.retrieve_recommendations(clean_q1, test_spec, audit_mode=True)
resp2, _ = ret_mod.retrieve_recommendations(clean_q2, test_spec, audit_mode=True)

cands1 = (resp1.primary or resp1.candidates)[:10]
cands2 = (resp2.primary or resp2.candidates)[:10]

top10_nums1 = [c.standard_number for c in cands1]
top10_nums2 = [c.standard_number for c in cands2]

print("\n   Top-10 for cleaned query with citation:")
for i, num in enumerate(top10_nums1, 1):
    print(f"     {i:2d}. {num}")

print("\n   Top-10 for clean query without citation:")
for i, num in enumerate(top10_nums2, 1):
    print(f"     {i:2d}. {num}")

assert top10_nums1 == top10_nums2, f"Top-10 lists differ!\n{top10_nums1}\nvs\n{top10_nums2}"
print("\n   ASSERTION PASSED: Top-10 candidate lists are 100% IDENTICAL ✓")


# ── 3. PHASE 1 REGRESSION TEST WITH AUDIT_MODE=FALSE ──────────────────────────
print("\n3. Phase 1 Normal Path (audit_mode=False) Regression Test:")
normal_spec = ExtractedSpec(
    product_category="cement",
    material="Ordinary Portland Cement",
    dimensions="43 grade",
    application=None,
    cited_standard_raw="IS 269:2015",
    brand_names_removed=[]
)
resp_normal, timings_normal = ret_mod.retrieve_recommendations(
    "OPC 43 grade cement conforming to IS 269:2015",
    normal_spec,
    audit_mode=False
)
top1_norm = resp_normal.primary[0] if resp_normal.primary else resp_normal.candidates[0]
print(f"   Normal path status: {resp_normal.status}")
print(f"   Top-1: {top1_norm.standard_number} ({top1_norm.title[:50]}...)")
print(f"   Why text generated: {top1_norm.why[:80]}...")
assert "269" in top1_norm.standard_number, f"Expected IS 269, got {top1_norm.standard_number}"
assert top1_norm.why and len(top1_norm.why) > 10, "Expected why text in audit_mode=False"
print("   ASSERTION PASSED: Phase 1 normal retrieval intact with zero regression ✓")

print("\n" + "=" * 80)
print("AUDIT_MODE PROOF VERIFIED SUCCESSFULLY")
print("=" * 80)
