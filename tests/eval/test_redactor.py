# -*- coding: utf-8 -*-
"""
tests/eval/test_redactor.py
===========================
Acceptance test for PII and contact information redactor.
Tests against real emails and phone numbers from GeM Bid PDF-2 (_Uploads_job_45941.pdf).
"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'C:\Users\devag\.gemini\antigravity\scratch\standards\backend')

import pymupdf
from app.parsers.redactor import Redactor

PDF2_PATH = r"C:\Users\devag\Downloads\_Uploads_job_45941.pdf"

print("=" * 80)
print("REDACTOR ACCEPTANCE TEST — REAL PDF-2 BID VERIFICATION")
print("=" * 80)

doc = pymupdf.open(PDF2_PATH)
p1_text = doc[0].get_text()

res = Redactor.redact(p1_text)

print(f"Total Redacted Spans Found on Page 1: {len(res.spans)}")
print("-" * 80)
for idx, s in enumerate(res.spans, 1):
    print(f"[{idx}] {s.entity_type:<6} original='{s.original_text}' -> '{s.replacement}' (orig [{s.orig_start}:{s.orig_end}] -> red [{s.redacted_start}:{s.redacted_end}])")

print("-" * 80)
print("OFFSET MAPPING ACCURACY CHECK:")
for s in res.spans:
    mapped_orig = res.to_original_offset(s.redacted_start)
    assert mapped_orig == s.orig_start, f"Offset mismatch: mapped {mapped_orig} != expected {s.orig_start}"
    mapped_red = res.to_redacted_offset(s.orig_start)
    assert mapped_red == s.redacted_start, f"Redacted offset mismatch: mapped {mapped_red} != expected {s.redacted_start}"
print("All offset mappings verified bidirectional and exact! ✓")

print("-" * 80)
print("BEFORE / AFTER SNIPPET (Page 1 Email Blocks):")
for s in res.spans:
    if s.entity_type == "EMAIL":
        before_context = p1_text[max(0, s.orig_start - 35): min(len(p1_text), s.orig_end + 35)].replace('\n', ' ')
        red_start = s.redacted_start
        red_end = s.redacted_end
        after_context = res.redacted_text[max(0, red_start - 35): min(len(res.redacted_text), red_end + 35)].replace('\n', ' ')
        print(f"BEFORE: ... {before_context} ...")
        print(f"AFTER:  ... {after_context} ...")
        print()

# Ensure no emails remain in redacted text
import re
remaining_emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', res.redacted_text)
assert len(remaining_emails) == 0, f"Leak detected! Remaining emails: {remaining_emails}"
print("VERIFICATION RESULT: ZERO EMAILS REMAINING IN REDACTED TEXT (PASS ✓)")
