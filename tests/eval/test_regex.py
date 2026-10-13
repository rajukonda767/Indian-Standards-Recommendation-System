# -*- coding: utf-8 -*-
"""
tests/eval/test_regex.py
========================
Canonical IS & International Standards Regex Test Suite.
Imports directly from backend.app.parsers.mention_extractor.
"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'C:\Users\devag\.gemini\antigravity\scratch\standards\backend')

from app.parsers.mention_extractor import extract_mentions, load_db_sets

load_db_sets()

TESTS = [
    # Failing strings & edge cases from reviews
    ("IS 2202 : Part 1 : 1999",                  "G-05: colon Part+year"),
    ("IS 302 (Part 2/Sec 16):2026",               "G-06: Part/Sec paren+colon-year"),
    ("IS 694 1 core 1.5 sq mm",                   "G-07: quantity not absorbed"),
    ("IS 456 (2000)",                              "G-20: paren-year not part"),
    ("IS/IEC 60947-2",                             "G-18: IS/IEC hyphen-part"),
    ("IS/IEC/IEEE 60079 (Part 30/Sec 1)",          "G-19: triple family paren-Part"),
    ("THE RATE IS 1100 PER METER",                 "G-34: all-caps verb"),
    ("ANALYSIS 2",                                 "G-32: no IS at all"),
    ("THIS 2000 M",                                "G-33: THIS substring"),
    ("IS 694 - 2000 m",                            "G-10: space/dash-year + unit"),
    ("when 10 nos",                                "G-35: no IS"),
    # Year-drop bug cases (Fix 4)
    ("conforming to IS 694:2010 for cable",        "Fix4-a: colon-year lost"),
    ("IS 456:2000 and IS 800:2007",                "Fix4-b: two colon-years"),
    ("as per IS 1786:2008 grade Fe 500D",          "Fix4-c: colon-year + letters after"),
    # Other gold set cases
    ("IS : 7098 (Part 1)",                         "G-02: colon-sep standalone"),
    ("GRADEIS : 7098",                              "G-03: glued uppercase prefix"),
    ("IS 694:1990",                                 "G-27: outdated year"),
    ("ISI marked to IS 694",                        "G-21: ISI mark trigger"),
    ("IS : 7098 XLPE cable",                        "Fix6: no-Part, DB has only Parts"),
    ("IEC 60227",                                   "G-11: IEC family"),
    ("ASTM A615 Grade 60",                          "G-14: ASTM family"),
    # New requested fixtures (Item 1)
    ("IS 456-2000",                                "Fix1-1: hyphen 4-digit year"),
    ("IS 2202-1",                                  "Fix1-2: hyphen 1-digit part"),
    ("IS 1786-2008",                               "Fix1-3: hyphen 4-digit year"),
    ("IS 7098-1:1985",                             "Fix1-4: hyphen part + colon year"),
    ("BS 6004",                                    "Fix1-5: BS family"),
    ("ISO 9001",                                   "Fix1-6: ISO family"),
]

HDR = f"{'Label':<36} {'raw_text':<32} {'base_key':<28} {'yr':>5} {'part':<6} {'sec':<5} {'disp':<13}"
SEP = '-' * len(HDR)
print(f"\n{'='*len(HDR)}")
print("PATTERN A+B RESULTS ON ALL TEST STRINGS (WITH FIXES)")
print(f"{'='*len(HDR)}")
print(HDR)
print(SEP)

total_mentions = 0
kept_mentions = 0
dropped_mentions = 0

for text, label in TESTS:
    mentions = extract_mentions(text)

    if not mentions:
        print(f"  {label:<34} {'(NO MATCH)':<32} {'-':<28} {'-':>5} {'-':<6} {'-':<5} DROP")
        dropped_mentions += 1
    else:
        for m in mentions:
            total_mentions += 1
            yr_str   = str(m.year) if m.year else '-'
            part_str = m.part or '-'
            sec_str  = m.sec or '-'
            if m.disposition == 'KEEP':
                kept_mentions += 1
            else:
                dropped_mentions += 1
            print(f"  {label:<34} {repr(m.raw_text):<32} {m.base_key:<28} {yr_str:>5} {part_str:<6} {sec_str:<5} {m.disposition}")

print(SEP)
print(f"TOTAL TEST CASES: {len(TESTS)} | EXTRACTED MENTIONS: {total_mentions} | KEPT: {kept_mentions} | DROPPED/SUPPRESSED: {dropped_mentions}")
print("=" * len(HDR) + "\n")
