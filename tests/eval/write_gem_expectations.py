# -*- coding: utf-8 -*-
"""
tests/eval/write_gem_expectations.py
====================================
Generates verifiable GeM expectation JSON files.
Hash definition: SHA-256 calculated over canonical JSON (sort_keys=True, indent=2)
EXCLUDING the 'sha256' key itself, ensuring reproducible independent verification.
"""
import sys, os, json, hashlib
sys.stdout.reconfigure(encoding='utf-8')

OUT1_PATH = r"C:\Users\devag\.gemini\antigravity\scratch\standards\tests\eval\gold\gem_pdf1_expectations.json"
OUT2_PATH = r"C:\Users\devag\.gemini\antigravity\scratch\standards\tests\eval\gold\gem_pdf2_expectations.json"

# ── 1. PDF-1: Technical Specifications 1 (3-Row BoQ Table) ───────────────────
pdf1_data = {
    "pdf_label": "Technical Specifications 1",
    "pages": 1,
    "doc_type": "technical_spec_annexure",
    "note": "Table containing 3 cable BoQ rows (Sl.no 10, 20, 30). Handled by table-row segmentation (Step 4).",
    "expected_items": [
        {
            "item_seq": 10,
            "material_code": "M8110264037",
            "short_description": "CBLE:PVC FRLS 1.1KV:CU-STR:1CX1.5SQMM",
            "technical_specification": "POWER CABLE :SPECIFICATION/VOLTAGE GRADE-IS : 7098 XLPE CU STRANDED:CABLE SECTION-1 C X 1.5 SQ.MM ALL THREE COLOURS RED,YELLOW,BLUE",
            "quantity": 2000,
            "unit": "M",
            "cited_standard_raw": "IS : 7098",
            "expected_base_key": "IS7098",
            "tier": "AUTHORITATIVE",
            "internal_conflict": {
                "short_desc_span": "CBLE:PVC FRLS 1.1KV",
                "spec_span": "IS : 7098 XLPE CU STRANDED",
                "finding": "SPEC_INTERNAL_CONFLICT",
                "reason": "Short description specifies PVC insulation, but technical specification cites IS 7098 (XLPE insulation)."
            },
            "expected_findings": [
                "SPEC_INTERNAL_CONFLICT",
                "CITATION_NO_PART",
                "CITATION_NO_YEAR",
                "CERT_NOT_MENTIONED"
            ],
            "independent_recommendation": {
                "top_1_standard": "IS 1554 (Part 1):1988",
                "title": "Specification for PVC insulated (Heavy Duty) electric cables: Part 1 for working voltages up to and including 1100 V",
                "confidence": 75.9
            }
        },
        {
            "item_seq": 20,
            "material_code": "M8110224040",
            "short_description": "CBLE:PVC 1.1KV:CU-STR:1CX2.5SQMM",
            "technical_specification": "POWER CABLE (PART-1):SPECIFICATION/VOLTAGE GRADE-IS : 7098 XLPE INSULATED UNARMOURED, 1.1 KV GRADE:CONDUCTOR-COPPER - STRANDED:CABLE SECTION-1C X 2.5 SQ.MM",
            "quantity": 2500,
            "unit": "M",
            "cited_standard_raw": "IS : 7098",
            "part_prefix_in_text": "(PART-1)",
            "expected_base_key": "IS7098(PART1)",
            "tier": "AUTHORITATIVE",
            "internal_conflict": {
                "short_desc_span": "CBLE:PVC 1.1KV",
                "spec_span": "IS : 7098 XLPE INSULATED UNARMOURED",
                "finding": "SPEC_INTERNAL_CONFLICT",
                "reason": "Short description specifies PVC insulation, but technical specification cites IS 7098 (XLPE insulation)."
            },
            "expected_findings": [
                "SPEC_INTERNAL_CONFLICT",
                "CITATION_NO_YEAR",
                "CERT_NOT_MENTIONED"
            ],
            "independent_recommendation": {
                "top_1_standard": "IS 1554 (Part 1):1988",
                "title": "Specification for PVC insulated (Heavy Duty) electric cables: Part 1 for working voltages up to and including 1100 V",
                "confidence": 86.7
            }
        },
        {
            "item_seq": 30,
            "material_code": "M8112355140",
            "short_description": "CBLE:PVC 1.1KV AR FRLS:CU-STR:3CX2.5SQMM",
            "technical_specification": "CONTROL CABLE -CONDUCTOR SIZE UP TO 2.5 SQ MM):SPECIFICATION/VOLTAGE GRADE-IS : 7098 XLPE INSULATED FRLS, 1100 V GRADE:CONDUCTOR-COPPER - STRANDED:CABLE SECTION-3 C X 2.5 SQ.MM",
            "quantity": 2000,
            "unit": "M",
            "cited_standard_raw": "IS : 7098",
            "expected_base_key": "IS7098",
            "tier": "AUTHORITATIVE",
            "internal_conflict": {
                "short_desc_span": "CBLE:PVC 1.1KV AR FRLS",
                "spec_span": "IS : 7098 XLPE INSULATED FRLS",
                "finding": "SPEC_INTERNAL_CONFLICT",
                "reason": "Short description specifies PVC insulation, but technical specification cites IS 7098 (XLPE insulation)."
            },
            "expected_findings": [
                "SPEC_INTERNAL_CONFLICT",
                "CITATION_NO_PART",
                "CITATION_NO_YEAR",
                "CERT_NOT_MENTIONED"
            ],
            "independent_recommendation": {
                "top_1_standard": "IS 1554 (Part 1):1988",
                "title": "Specification for PVC insulated (Heavy Duty) electric cables: Part 1 for working voltages up to and including 1100 V",
                "confidence": 83.7
            }
        }
    ]
}

# ── 2. PDF-2: GeM Bid Job 45941 (Two-Column Layout) ───────────────────────────
pdf2_data = {
    "pdf_label": "GeM Bid Job 45941",
    "pages": 8,
    "doc_type": "gem_bid",
    "note": "Two-column GeM bid document. Page 1 has GeMARPTS search results and category notification. GTC on p7-8.",
    "page_1_block_expectations": [
        {
            "section_heading": "Searched Result generated in GeMARPTS",
            "tier": "CONTEXT_ONLY",
            "expected_mentions": [
                {"raw": "IS 694", "base_key": "IS694", "tier": "CONTEXT_ONLY"},
                {"raw": "IS 4989", "base_key": "IS4989", "tier": "CONTEXT_ONLY"},
                {"raw": "IS 1554 (Part 1)", "base_key": "IS1554(PART1)", "tier": "CONTEXT_ONLY"},
                {"raw": "IS 694", "base_key": "IS694", "tier": "CONTEXT_ONLY"}
            ]
        },
        {
            "section_heading": "Relevant Categories selected for notification",
            "tier": "CORROBORATING",
            "expected_mentions": [
                {"raw": "IS 7098 (Part 1)", "base_key": "IS7098(PART1)", "tier": "CORROBORATING"}
            ]
        }
    ],
    "per_page_tier_summary": {
        "p1": ["AUTHORITATIVE", "CONTEXT_ONLY", "CORROBORATING"],
        "p2": ["AUTHORITATIVE"],
        "p3": ["AUTHORITATIVE"],
        "p4": ["AUTHORITATIVE"],
        "p5": ["AUTHORITATIVE"],
        "p6": ["AUTHORITATIVE"],
        "p7": ["AUTHORITATIVE", "CONTEXT_ONLY"],
        "p8": ["CONTEXT_ONLY"]
    },
    "gtc_scope": {
        "start_page": 7,
        "start_block": 13,
        "start_marker": "This Bid is governed by the General Terms and Conditions",
        "end_page": 8,
        "end_marker": "---धन्यवाद/Thank You---",
        "tier": "CONTEXT_ONLY"
    },
    "buyer_atc_scope": {
        "start_page": 5,
        "start_marker": "Buyer Added Bid Specific Terms and Conditions",
        "end_page": 7,
        "end_block": 12,
        "tier": "AUTHORITATIVE",
        "rule": "Buyer-added ATC clauses retain AUTHORITATIVE tier to audit buyer-specified technical standards."
    }
}

def compute_hash_and_write(data: dict, out_path: str) -> str:
    # 1. Canonical JSON bytes EXCLUDING sha256 key
    clean_dict = {k: v for k, v in data.items() if k != "sha256"}
    canonical_bytes = json.dumps(clean_dict, sort_keys=True, indent=2, ensure_ascii=False).encode('utf-8')
    h = hashlib.sha256(canonical_bytes).hexdigest()
    # 2. Store sha256 attribute and write file
    data_with_hash = dict(data)
    data_with_hash["sha256"] = h
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data_with_hash, f, indent=2, ensure_ascii=False)
    return h

h1 = compute_hash_and_write(pdf1_data, OUT1_PATH)
h2 = compute_hash_and_write(pdf2_data, OUT2_PATH)

print("=" * 85)
print("REQUIREMENT 6: EXPECTATION FILES GENERATED (HASH DEFINED OVER NON-SHA256 FIELDS)")
print("=" * 85)
print(f"PDF-1 Expectations ({OUT1_PATH}):")
print(f"  SHA-256: {h1}")
print(f"  Verification command:\n    python -c \"import json, hashlib; d=json.load(open(r'{OUT1_PATH}', encoding='utf-8')); d.pop('sha256', None); print(hashlib.sha256(json.dumps(d, sort_keys=True, indent=2, ensure_ascii=False).encode('utf-8')).hexdigest())\"")

print(f"\nPDF-2 Expectations ({OUT2_PATH}):")
print(f"  SHA-256: {h2}")
print(f"  Verification command:\n    python -c \"import json, hashlib; d=json.load(open(r'{OUT2_PATH}', encoding='utf-8')); d.pop('sha256', None); print(hashlib.sha256(json.dumps(d, sort_keys=True, indent=2, ensure_ascii=False).encode('utf-8')).hexdigest())\"")
