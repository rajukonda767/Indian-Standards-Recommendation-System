# -*- coding: utf-8 -*-
"""
tests/eval/run_pdf1_rows_recommender.py
Runs the independent recommender on the real row texts of PDF-1.
"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'C:\Users\devag\.gemini\antigravity\scratch\standards\backend')
os.chdir(r'C:\Users\devag\.gemini\antigravity\scratch\standards\backend')

from app.db import init_db_pool
init_db_pool()
from app.services.embedding import EmbeddingService
EmbeddingService.get_instance()

import services.retrieval as ret_mod
from schemas import ExtractedSpec

rows = [
    (10, "CBLE:PVC FRLS 1.1KV:CU-STR:1CX1.5SQMM POWER CABLE :SPECIFICATION/VOLTAGE GRADE-IS : 7098 XLPE CU STRANDED:CABLE SECTION-1 C X 1.5 SQ.MM ALL THREE COLOURS RED,YELLOW,BLUE", "1.1kV", "1CX1.5SQMM"),
    (20, "CBLE:PVC 1.1KV:CU-STR:1CX2.5SQMM POWER CABLE (PART-1):SPECIFICATION/VOLTAGE GRADE-IS : 7098 XLPE INSULATED UNARMOURED, 1.1 KV GRADE:CONDUCTOR-COPPER - STRANDED:CABLE SECTION-1C X 2.5 SQ.MM", "1.1kV", "1CX2.5SQMM"),
    (30, "CBLE:PVC 1.1KV AR FRLS:CU-STR:3CX2.5SQMM CONTROL CABLE -CONDUCTOR SIZE UP TO 2.5 SQ MM):SPECIFICATION/VOLTAGE GRADE-IS : 7098 XLPE INSULATED FRLS, 1100 V GRADE:CONDUCTOR-COPPER - STRANDED:CABLE SECTION-3 C X 2.5 SQ.MM", "1.1kV", "3CX2.5SQMM"),
]

print("=" * 80)
print("INDEPENDENT RECOMMENDER ON REAL PDF-1 BOQ ROWS")
print("=" * 80)

for seq, text, volt, dim in rows:
    # Clean query (strip citation and trigger words)
    clean_q = text.replace("IS : 7098", "").replace("GRADE-", "").strip()
    spec = ExtractedSpec(
        product_category="power cable",
        material="PVC",
        voltage_rating=volt,
        dimensions=dim,
        application=None,
        cited_standard_raw=None,
        brand_names_removed=[]
    )
    resp, timings = ret_mod.retrieve_recommendations(clean_q, spec, audit_mode=True)
    cands = resp.primary or resp.candidates
    t_ms = timings.get('total_ms', 0)
    print(f"\n--- ROW {seq} ({t_ms}ms) ---")
    print(f"Short Desc: {text[:40]}")
    for i, c in enumerate(cands[:4], 1):
        conflict = f" [CONFLICT: {c.conflict_warning}]" if c.conflict_warning else ""
        print(f"  {i}. [{c.confidence}%] {c.standard_number} - {c.title[:65]}{conflict}")
