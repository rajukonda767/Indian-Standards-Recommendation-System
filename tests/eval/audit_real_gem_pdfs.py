# -*- coding: utf-8 -*-
"""
tests/eval/audit_real_gem_pdfs.py
=================================
Runs the finding assembler + scorer on the two REAL GeM PDFs (PDF-1 and PDF-2)
with the fixed CERT_CUE_RE to evaluate QCO Compliance on real tender language.
"""
import sys, os, time
sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
sys.path.insert(0, r'C:\Users\devag\.gemini\antigravity\scratch\standards\backend')

from app.db import init_db_pool
from app.adapters import get_adapter_for_file
from app.parsers.mention_extractor import load_db_sets, extract_mentions
from app.parsers.item_builder import ItemBuilder
from app.parsers.verbatim_verifier import VerbatimQuoteVerifier
from app.parsers.standard_resolver import StandardResolver
from app.parsers.finding_assembler import FindingAssembler, FindingCode
from app.parsers.scorer import calculate_audit_scores

load_db_sets()
init_db_pool(10, 20)

PDF1_PATH = r"C:\Users\devag\Downloads\Techical Specifications 1.pdf"
PDF2_PATH = r"C:\Users\devag\Downloads\_Uploads_job_45941.pdf"

print("=" * 115)
print("AUDITING REAL GeM TENDER DOCUMENTS (PDF-1 and PDF-2) WITH UPDATED CERT_CUE_RE")
print("=" * 115)

a1 = get_adapter_for_file(PDF1_PATH)
b1 = a1.extract_blocks(PDF1_PATH)
res_pdf1 = ItemBuilder.build_items_from_blocks(b1, "PDF-1")

a2 = get_adapter_for_file(PDF2_PATH)
b2 = a2.extract_blocks(PDF2_PATH)
res_pdf2 = ItemBuilder.build_items_from_blocks(b2, "PDF-2")

joined_items = ItemBuilder.join_item_sets([res_pdf2.items, res_pdf1.items])
resolver = StandardResolver()

audited_items = []
print(f"\nExtracted and joined {len(joined_items)} real tender items across PDF-1 and PDF-2:\n")

for it in joined_items:
    spec_txt = it.technical_spec.value if it.technical_spec else ""
    desc_txt = it.description.value if it.description else ""
    combined_txt = f"{desc_txt} {spec_txt}".strip()
    
    mentions = extract_mentions(spec_txt, source_block_tier="AUTHORITATIVE")
    res_list = []
    for m in mentions:
        vq, _ = VerbatimQuoteVerifier.extract_and_verify_quote(m, spec_txt, "PDF-1", 1, 0)
        res_list.append(resolver.resolve_mention(m, combined_txt, vq))
    
    audited = FindingAssembler.assemble_item(it, res_list, "PDF-1", 1)
    audited_items.append(audited)
    
    cue_match = FindingAssembler.CERT_CUE_RE.search(combined_txt)
    matched_term = cue_match.group(0) if cue_match else None
    
    print(f"Item #{audited.seq_no} (ID: {audited.item_id}, Material Code: {audited.material_code}):")
    print(f"  • Description      : {repr(audited.description)}")
    print(f"  • Technical Spec   : {repr(audited.technical_spec)}")
    print(f"  • Matched CERT CUE : {repr(matched_term)}")
    print(f"  • is_qco_applicable: {audited.is_qco_applicable}")
    print(f"  • is_qco_compliant : {audited.is_qco_compliant}")
    print(f"  • Status           : {audited.status.upper()}")
    findings_summary = [
        f"{f.code.value if hasattr(f.code, 'value') else f.code} [{f.severity}]: {f.message[:70]}..."
        for f in audited.findings
    ]
    print(f"  • Findings ({len(audited.findings)}): {findings_summary}")
    print()

scorecard = calculate_audit_scores(audited_items)

print("=" * 115)
print("SCORECARD EVALUATION ON REAL GeM PDFs (PDF-1 & PDF-2)")
print("=" * 115)
print(f"1. Coverage Score       : {scorecard.coverage.display_value} ({scorecard.coverage.arithmetic_str})")
print(f"   Explanation          : {scorecard.coverage.explanation}")
print(f"2. Currency Score       : {scorecard.currency.display_value} ({scorecard.currency.arithmetic_str})")
print(f"   Explanation          : {scorecard.currency.explanation}")
print(f"3. QCO Compliance Score : {scorecard.qco_compliance.display_value} ({scorecard.qco_compliance.arithmetic_str})")
print(f"   Explanation          : {scorecard.qco_compliance.explanation}")
print("=" * 115)
