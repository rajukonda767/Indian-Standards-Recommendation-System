# -*- coding: utf-8 -*-
import sys, os, re
sys.stdout.reconfigure(encoding='utf-8')
import pymupdf

pdf1 = r"C:\Users\devag\Downloads\Techical Specifications 1.pdf"
pdf2 = r"C:\Users\devag\Downloads\_Uploads_job_45941.pdf"

def analyze_pdf(pdf_path, name):
    print(f"\n==================================================")
    print(f"ANALYSIS OF {name} ({pdf_path})")
    print(f"==================================================")
    doc = pymupdf.open(pdf_path)
    print(f"Total pages: {len(doc)}")
    
    for pno, page in enumerate(doc):
        text = page.get_text("text")
        devanagari_chars = len([c for c in text if 0x0900 <= ord(c) <= 0x097F])
        total_chars = max(len(text), 1)
        ratio = devanagari_chars / total_chars
        print(f"Page {pno+1}: {total_chars} chars, Devanagari: {devanagari_chars} ({ratio:.2%})")
        
        # Check blocks
        blocks = page.get_text("blocks")
        for b in blocks:
            b_text = b[4]
            if "7098" in b_text or "GeM" in b_text or "General Terms" in b_text or "GTC" in b_text:
                print(f"  [Block bbox ({b[0]:.1f}, {b[1]:.1f}, {b[2]:.1f}, {b[3]:.1f})]:")
                for line in b_text.strip().split("\n")[:4]:
                    print(f"    {line}")
                dev_b = len([c for c in b_text if 0x0900 <= ord(c) <= 0x097F])
                print(f"    -> Devanagari ratio: {dev_b}/{len(b_text)} ({dev_b/max(len(b_text),1):.2%})")

analyze_pdf(pdf1, "PDF 1 (Technical Specifications 1.pdf)")
analyze_pdf(pdf2, "PDF 2 (_Uploads_job_45941.pdf)")
