# -*- coding: utf-8 -*-
"""
tests/eval/test_bounded_extractor.py
====================================
Acceptance Test Suite for Bounded Line-Range LLM Extractor (Step 4b):
1. Sample 1: GeM BoQ pasted text with electrical cables, IS standards, quantities, and UoM.
2. Sample 2: CPWD / Railway civil engineering specification with TMT bars, cement, and concrete.
3. Sample 3: Industrial procurement batch with 10-digit material codes (8110264037) & technical specs.
4. Failure-Injection Test: Hallucinated text not present in source is caught, dropped, and logged.
5. Verbatim Substring Assertion: Asserts 100% of extracted item fields are verbatim substrings.
"""
import sys, os, time, json
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'C:\Users\devag\.gemini\antigravity\scratch\standards\backend')

from app.parsers.bounded_extractor import BoundedExtractor, BoundedExtractionResult
from app.parsers.groq_wrapper import get_groq_wrapper
from app.parsers.redactor import Redactor

print("=" * 110)
print("TEST SUITE: STEP 4b BOUNDED LINE-RANGE LLM EXTRACTOR (PASTED TEXT)")
print("=" * 110)


# ══════════════════════════════════════════════════════════════════════════════
# SAMPLE 1: REALISTIC GeM SCHEDULE LINE ITEM BOQ
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "#" * 110)
print("SAMPLE 1: GeM ELECTRICAL CABLES & BOQ SCHEDULE (LIVE LLM RUN)")
print("#" * 110)

SAMPLE1_TEXT = """Schedule of Quantities and Technical Specifications:
Item 1: XLPE Insulated Armoured Power Cable 3.5 Core x 185 Sq.mm aluminium conductor
Conforming strictly to IS 7098 (Part 1):1988 with up-to-date amendments.
Quantity: 1200 MTR
Item 2: PVC Insulated Copper Control Cable 4 Core x 2.5 Sq.mm flexible conductor
Conforming strictly to IS 1554 (Part 1) and IS 694.
Quantity: 3500 MTR
Item 3: Multistrand Flexible Single Core Copper Wire 1.5 Sq.mm FRLS insulation
Conforming to IS 694:2010 with authentic ISI mark.
Quantity: 5000 MTR"""

res1 = BoundedExtractor.extract_items_bounded(SAMPLE1_TEXT, doc_name="GeM-Cables-BoQ")

print(f"Extracted Items Count: {len(res1.items)}")
print(f"Validation Failures  : {len(res1.validation_failures)}")
assert len(res1.items) == 3, f"Expected 3 items, got {len(res1.items)}"
assert len(res1.validation_failures) == 0, f"Unexpected validation failures: {res1.validation_failures}"

for idx, it in enumerate(res1.items, 1):
    print(f"\nItem {it.seq_no} (Display ID: {it.item_id}):")
    print(f"  Description   : {repr(it.description.value if it.description else None)}")
    print(f"  Technical Spec: {repr(it.technical_spec.value if it.technical_spec else None)}")
    print(f"  Quantity      : {it.quantity.value if it.quantity else None}")
    print(f"  Unit          : {it.unit.value if it.unit else None}")
    
    # HARD VERBATIM ASSERTIONS
    if it.description:
        assert it.description.value in SAMPLE1_TEXT, f"Description not verbatim: {it.description.value}"
    if it.technical_spec:
        assert it.technical_spec.value in SAMPLE1_TEXT, f"Technical spec not verbatim: {it.technical_spec.value}"
    if it.quantity:
        assert it.quantity.value in SAMPLE1_TEXT, f"Quantity not verbatim: {it.quantity.value}"
    if it.unit:
        assert it.unit.value in SAMPLE1_TEXT, f"Unit not verbatim: {it.unit.value}"

print("\nSample 1: All 3 items extracted with 100% hard verbatim verification! ✓")


# ══════════════════════════════════════════════════════════════════════════════
# SAMPLE 2: CPWD / RAILWAYS CIVIL & STRUCTURAL SPECIFICATION
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "#" * 110)
print("SAMPLE 2: CPWD CIVIL & STRUCTURAL PROCUREMENT (LIVE LLM RUN)")
print("#" * 110)

SAMPLE2_TEXT = """Bill of Quantities for Construction Package 04:
Item 1: High Yield Strength Deformed Thermo-Mechanically Treated TMT steel bars Fe 500D
Material must comply with IS 1786:2008 specifications for concrete reinforcement.
Estimated Quantity: 450 MT
Item 2: Ordinary Portland Cement Grade 53 in 50 kg HDPE bags
Manufactured and tested in strict compliance with IS 269:2015.
Estimated Quantity: 8000 Bags
Item 3: Structural Steel Hot Rolled Medium Weight Beams ISMB 300
Conforming to IS 808:1989 and IS 2062 Grade E250 quality A.
Estimated Quantity: 150 MT"""

res2 = BoundedExtractor.extract_items_bounded(SAMPLE2_TEXT, doc_name="CPWD-Civil-Package")

print(f"Extracted Items Count: {len(res2.items)}")
print(f"Validation Failures  : {len(res2.validation_failures)}")
assert len(res2.items) == 3, f"Expected 3 items, got {len(res2.items)}"
assert len(res2.validation_failures) == 0, f"Unexpected validation failures: {res2.validation_failures}"

for idx, it in enumerate(res2.items, 1):
    print(f"\nItem {it.seq_no} (Display ID: {it.item_id}):")
    print(f"  Description   : {repr(it.description.value if it.description else None)}")
    print(f"  Technical Spec: {repr(it.technical_spec.value if it.technical_spec else None)}")
    print(f"  Quantity      : {it.quantity.value if it.quantity else None}")
    print(f"  Unit          : {it.unit.value if it.unit else None}")

    # HARD VERBATIM ASSERTIONS
    if it.description:
        assert it.description.value in SAMPLE2_TEXT, f"Description not verbatim: {it.description.value}"
    if it.technical_spec:
        assert it.technical_spec.value in SAMPLE2_TEXT, f"Technical spec not verbatim: {it.technical_spec.value}"
    if it.quantity:
        assert it.quantity.value in SAMPLE2_TEXT, f"Quantity not verbatim: {it.quantity.value}"
    if it.unit:
        assert it.unit.value in SAMPLE2_TEXT, f"Unit not verbatim: {it.unit.value}"

print("\nSample 2: All 3 items extracted with 100% hard verbatim verification! ✓")


# ══════════════════════════════════════════════════════════════════════════════
# SAMPLE 3: INDUSTRIAL PROCUREMENT BATCH WITH 10-DIGIT MATERIAL CODES
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "#" * 110)
print("SAMPLE 3: INDUSTRIAL BATCH WITH 10-DIGIT CODES & REDACTOR FIREWALL (LIVE LLM RUN)")
print("#" * 110)

SAMPLE3_TEXT = """NTPC Procurement Tender No: NTPC/2026/BOQ/001
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
Quantity: 1800 MTR"""

res3 = BoundedExtractor.extract_items_bounded(SAMPLE3_TEXT, doc_name="NTPC-Industrial-Batch")

print(f"Extracted Items Count: {len(res3.items)}")
print(f"Validation Failures  : {len(res3.validation_failures)}")
assert len(res3.items) == 3, f"Expected 3 items, got {len(res3.items)}"
assert len(res3.validation_failures) == 0, f"Unexpected validation failures: {res3.validation_failures}"

for idx, it in enumerate(res3.items, 1):
    print(f"\nItem {it.seq_no} (Display ID: {it.item_id}):")
    print(f"  Material Code : {it.material_code.value if it.material_code else None}")
    print(f"  Description   : {repr(it.description.value if it.description else None)}")
    print(f"  Technical Spec: {repr(it.technical_spec.value if it.technical_spec else None)}")
    print(f"  Quantity      : {it.quantity.value if it.quantity else None}")
    print(f"  Unit          : {it.unit.value if it.unit else None}")

    # HARD VERBATIM ASSERTIONS
    if it.material_code:
        assert it.material_code.value in SAMPLE3_TEXT, f"Material code not verbatim: {it.material_code.value}"
    if it.description:
        assert it.description.value in SAMPLE3_TEXT, f"Description not verbatim: {it.description.value}"
    if it.technical_spec:
        assert it.technical_spec.value in SAMPLE3_TEXT, f"Technical spec not verbatim: {it.technical_spec.value}"
    if it.quantity:
        assert it.quantity.value in SAMPLE3_TEXT, f"Quantity not verbatim: {it.quantity.value}"
    if it.unit:
        assert it.unit.value in SAMPLE3_TEXT, f"Unit not verbatim: {it.unit.value}"

# Verify 10-digit material codes were accurately preserved
codes = [it.material_code.value for it in res3.items]
assert codes == ["8110264037", "9876543210", "7112345678"], f"Expected exact codes, got {codes}"
print("\nSample 3: All 3 items with bare 10-digit codes extracted with 100% hard verbatim verification! ✓")


# ══════════════════════════════════════════════════════════════════════════════
# PART 4: FAILURE-INJECTION TEST (HALLUCINATED TEXT NOT IN SOURCE)
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "#" * 110)
print("PART 4: FAILURE-INJECTION TEST (SYNTHESIZED / HALLUCINATED TEXT REJECTION)")
print("#" * 110)

# Simulate an LLM attempting to reference non-existent lines or an injector hallucinating text
SOURCE_FOR_INJECTION = """[L1] Item 1: Standard Copper Flexible Wire 1.0 sq mm
[L2] Conforming to IS 694.
[L3] Quantity: 500 Meters"""

# Inject an LLM response referencing line 99 (out of bounds)
mock_hallucinated_llm_response = json.dumps({
    "items": [
        {
            "item_index": 1,
            "desc_lines": [1],
            "spec_lines": [2],
            "code_line": 99,  # Line 99 does NOT exist in source!
            "qty_line": 3,
            "unit_line": 3
        }
    ]
})

res_fail = BoundedExtractor.extract_items_bounded(
    SOURCE_FOR_INJECTION,
    doc_name="Failure-Injection-Test",
    mock_llm_response=mock_hallucinated_llm_response
)

print(f"Extracted Items Count: {len(res_fail.items)}")
print(f"Validation Failures  : {len(res_fail.validation_failures)}")
assert len(res_fail.items) == 1
# Verify out-of-bounds line 99 resulted in None for material_code (cannot hallucinate code)
assert res_fail.items[0].material_code is None
print("Out-of-bounds line index safely handled with zero hallucinated code! ✓")

# Now inject a direct hallucinated field value through the validator
class HallucinatedExtractor(BoundedExtractor):
    @classmethod
    def _extract_quantity_unit_from_line(cls, line_text: str):
        # Inject hallucinated unit
        return "500", "HALLUCINATED_NON_EXISTENT_UNIT_XYZ"

res_fail2 = HallucinatedExtractor.extract_items_bounded(
    SOURCE_FOR_INJECTION,
    doc_name="Failure-Injection-Test-2",
    mock_llm_response=mock_hallucinated_llm_response
)

print(f"\nInjected Hallucinated Unit Test:")
print(f"Validation Failures Recorded: {len(res_fail2.validation_failures)}")
for f in res_fail2.validation_failures:
    print(f"  Field: {f['field']} | Rejected Value: {repr(f['rejected_value'])} | Reason: {f['reason']}")

assert len(res_fail2.validation_failures) >= 1
assert res_fail2.validation_failures[0]["rejected_value"] == "HALLUCINATED_NON_EXISTENT_UNIT_XYZ"
assert res_fail2.items[0].unit is None, "Hallucinated unit was not dropped!"
print("Hard Verbatim Validator successfully caught, dropped, and logged hallucinated text! ✓")


print("\n" + "=" * 110)
print("ALL BOUNDED EXTRACTOR ACCEPTANCE TESTS PASSED WITH 100% SUCCESS ✓")
print("=" * 110 + "\n")
