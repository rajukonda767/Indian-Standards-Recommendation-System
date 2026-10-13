# -*- coding: utf-8 -*-
"""
tests/eval/mention_extractor.py
"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'C:\Users\devag\.gemini\antigravity\scratch\standards\backend')

from app.parsers.mention_extractor import (
    extract_mentions,
    Mention,
    load_db_sets,
    _DB_EXACT,
    _DB_FAM_NUM,
    IS_FAMILY_RE,
    NON_IS_RE,
)

if __name__ == "__main__":
    load_db_sets()
    TEST_STRINGS = [
        "IS 456-2000",
        "IS 2202-1",
        "IS/IEC 60947-2",
        "IS 1786-2008",
        "IS 7098-1:1985",
        "IS 302 (Part 2/Sec 16):2026"
    ]
    print("\n" + "=" * 100)
    print(f"{'Input':<30} | {'Raw Matched':<18} | {'Base Key':<20} | {'Yr':<6} | {'Part':<6} | {'Disp':<6}")
    print("=" * 100)
    for s in TEST_STRINGS:
        mentions = extract_mentions(s)
        if not mentions:
            print(f"{s:<30} | {'(NONE)':<18} | {'-':<20} | {'-':<6} | {'-':<6} | {'DROP':<6}")
        for m in mentions:
            yr_str = str(m.year) if m.year else '-'
            pt_str = str(m.part) if m.part else '-'
            print(f"{s:<30} | {m.raw_text:<18} | {m.base_key:<20} | {yr_str:<6} | {pt_str:<6} | {m.disposition:<6}")
    print("=" * 100)
