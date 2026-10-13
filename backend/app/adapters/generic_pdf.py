# -*- coding: utf-8 -*-
"""
backend/app/adapters/generic_pdf.py
===================================
Generic PDF document adapter using PyMuPDF.
Handles standard tender PDFs, bilingual Hindi/English documents, and garbled text.
"""
import re
from typing import List
import pymupdf

from app.adapters.base import BaseAdapter, PageBlock


def calc_devanagari_ratio(text: str) -> float:
    """Calculate the ratio of Devanagari script characters in text."""
    if not text:
        return 0.0
    dev_chars = sum(1 for c in text if 0x0900 <= ord(c) <= 0x097F)
    return dev_chars / len(text)


def strip_devanagari(text: str) -> str:
    """Strip Devanagari Unicode characters, leaving Latin, numerals, and punctuation."""
    return ''.join(c for c in text if not (0x0900 <= ord(c) <= 0x097F))


class GenericPdfAdapter(BaseAdapter):
    """Adapter for generic tender PDFs without platform-specific metadata templates."""

    GARBLE_RATIO_THRESHOLD = 0.35

    def can_handle(self, file_path: str) -> bool:
        return file_path.lower().endswith('.pdf')

    def extract_blocks(self, file_path: str) -> List[PageBlock]:
        doc = pymupdf.open(file_path)
        blocks_out: List[PageBlock] = []

        for pno in range(len(doc)):
            page = doc[pno]
            raw_blocks = page.get_text("blocks", sort=True)

            for bidx, b in enumerate(raw_blocks):
                x0, y0, x1, y1, btext = b[0], b[1], b[2], b[3], b[4]
                btext_clean = btext.strip()
                if not btext_clean:
                    continue

                dev_ratio = calc_devanagari_ratio(btext_clean)
                english_text = strip_devanagari(btext_clean)
                english_compact = re.sub(r'\s+', ' ', english_text).strip()

                # Garble rule: if Devanagari dominates the block
                if dev_ratio > self.GARBLE_RATIO_THRESHOLD:
                    # If meaningful English remains (e.g. contains letters or standard names), keep English text
                    has_substantive_english = bool(re.search(r'[A-Za-z]{3,}|\bIS\b|\d{3,}', english_compact))
                    if has_substantive_english:
                        tier = "AUTHORITATIVE"
                        tier_reason = f"bilingual (dev {dev_ratio:.0%}, retained English)"
                        final_text = english_compact
                    else:
                        tier = "CONTEXT_ONLY"
                        tier_reason = f"garbled_non_latin (dev {dev_ratio:.0%}, no English)"
                        final_text = english_compact or btext_clean
                else:
                    tier = "AUTHORITATIVE"
                    tier_reason = "default_authoritative"
                    final_text = english_compact or btext_clean

                blocks_out.append(PageBlock(
                    page_no=pno + 1,
                    block_idx=bidx,
                    bbox=(x0, y0, x1, y1),
                    text=final_text,
                    raw_text=btext_clean,
                    tier=tier,
                    tier_reason=tier_reason,
                    devanagari_ratio=dev_ratio,
                    section_label=None
                ))

        return blocks_out
