# -*- coding: utf-8 -*-
"""
backend/app/adapters/gem_adapter.py
===================================
Government e-Marketplace (GeM) Bid Document Adapter.
Handles two-column table pairing on Page 1 (GeMARPTS search results and categories),
section tracking across multi-page bids, GTC boundary detection, and Buyer-ATC tier preservation.
"""
import re
from typing import List, Optional, Tuple
import pymupdf

from app.adapters.base import BaseAdapter, PageBlock
from app.adapters.generic_pdf import calc_devanagari_ratio, strip_devanagari


class GeMAdapter(BaseAdapter):
    """Specialized adapter for GeM bid documents and schedules."""

    # GeMARPTS exact English label headings mapped to their procurement evidence tier
    GEMARPTS_LABELS = {
        "Searched Strings used in GeMARPTS": "CONTEXT_ONLY",
        "Searched Result generated in GeMARPTS": "CONTEXT_ONLY",
        "Relevant Categories selected for notification": "CORROBORATING",
    }

    # Markers that establish or end major bid document sections
    GTC_START_RE = re.compile(
        r'(?:This Bid is governed by the General Terms and Conditions'
        r'|यह\s+बिड\s+सामान्य\s+शर्तों\s+के\s+अंतर्गत\s+भी\s+शासित\s+है'
        r'|In\s+terms\s+of\s+GeM\s+GTC\s+clause)',
        re.IGNORECASE
    )

    GTC_END_RE = re.compile(
        r'(?:Technical\s+Specifications?|Buyer\s+Added|Schedule\s+of\s+Requirements'
        r'|Scope\s+of\s+Work|BOQ|Annexure|---\s*धन्यवाद\s*/\s*Thank\s+You\s*---)',
        re.IGNORECASE
    )

    BUYER_ATC_START_RE = re.compile(
        r'(?:Buyer\s+Added\s+Bid\s+Specific\s+Terms\s+and\s+Conditions'
        r'|Buyer\s+Added\s+Bid\s+Specific\s+ATC)',
        re.IGNORECASE
    )

    TECH_SPEC_START_RE = re.compile(
        r'(?:Technical\s+Specifications?|तकनीकी\s+विशिष्टियाँ|Schedule\s+of\s+Requirements)',
        re.IGNORECASE
    )

    GARBLE_RATIO_THRESHOLD = 0.35

    def can_handle(self, file_path: str) -> bool:
        if not file_path.lower().endswith('.pdf'):
            return False
        try:
            doc = pymupdf.open(file_path)
            if len(doc) == 0:
                return False
            p1_text = doc[0].get_text("text")
            return bool(re.search(r'GEM/\d{4}/|GeM\s+Bid|GeMARPTS|Bid\s+Number:\s*GEM', p1_text, re.IGNORECASE))
        except Exception:
            return False

    def extract_blocks(self, file_path: str) -> List[PageBlock]:
        doc = pymupdf.open(file_path)
        blocks_out: List[PageBlock] = []

        in_gtc = False
        in_buyer_atc = False
        current_section = "Bid Details"

        for pno in range(len(doc)):
            page = doc[pno]
            raw_blocks = page.get_text("blocks")

            if pno == 0:
                # Page 1: Apply two-column horizontal table pairing
                p1_blocks = self._parse_page_1_table(raw_blocks, pno + 1)
                blocks_out.extend(p1_blocks)
            else:
                # Pages 2+: State-machine section tracking
                for bidx, b in enumerate(raw_blocks):
                    x0, y0, x1, y1, btext = b[0], b[1], b[2], b[3], b[4]
                    btext_clean = btext.strip()
                    if not btext_clean:
                        continue

                    dev_ratio = calc_devanagari_ratio(btext_clean)
                    english_text = strip_devanagari(btext_clean)
                    english_compact = re.sub(r'\s+', ' ', english_text).strip()

                    # Check for section transitions
                    if self.TECH_SPEC_START_RE.search(english_compact) or self.TECH_SPEC_START_RE.search(btext_clean):
                        current_section = "Technical Specifications"
                        in_buyer_atc = False
                        in_gtc = False

                    elif self.BUYER_ATC_START_RE.search(english_compact):
                        in_buyer_atc = True
                        in_gtc = False
                        current_section = "Buyer Added ATC"

                    elif self.GTC_START_RE.search(english_compact) or self.GTC_START_RE.search(btext_clean):
                        in_gtc = True
                        in_buyer_atc = False
                        current_section = "General Terms and Conditions (GTC)"

                    elif in_gtc and self.GTC_END_RE.search(english_compact):
                        in_gtc = False
                        current_section = "Post-GTC Content"

                    # Tier assignment logic
                    if in_gtc:
                        tier = "CONTEXT_ONLY"
                        tier_reason = "gtc_boilerplate"
                    elif in_buyer_atc:
                        # Buyer-added ATC retains AUTHORITATIVE tier to audit buyer-stipulated technical clauses
                        tier = "AUTHORITATIVE"
                        tier_reason = "buyer_atc_authoritative"
                    else:
                        # Standard specification or bid requirement on pages 2-6
                        # All specification content on pages 2-6 is AUTHORITATIVE.
                        tier = "AUTHORITATIVE"
                        tier_reason = f"section_{current_section.lower().replace(' ', '_')}"

                    blocks_out.append(PageBlock(
                        page_no=pno + 1,
                        block_idx=bidx,
                        bbox=(x0, y0, x1, y1),
                        text=english_compact or btext_clean,
                        raw_text=btext_clean,
                        tier=tier,
                        tier_reason=tier_reason,
                        devanagari_ratio=dev_ratio,
                        section_label=current_section
                    ))

        return blocks_out

    def _parse_page_1_table(self, raw_blocks: list, page_no: int) -> List[PageBlock]:
        """
        Pairs left-column metadata labels (x < 250) with right-column content (x >= 250).
        Assigns CONTEXT_ONLY to 'Searched Result' and CORROBORATING to 'Relevant Categories'.
        """
        # Separate labels and values based on x-coordinate threshold (250 pt)
        label_blocks = []
        value_blocks = []

        for bidx, b in enumerate(raw_blocks):
            x0, y0, x1, y1, btext = b[0], b[1], b[2], b[3], b[4]
            bclean = btext.strip()
            if not bclean:
                continue
            eng = re.sub(r'\s+', ' ', strip_devanagari(bclean)).strip()
            item = {
                "bidx": bidx,
                "bbox": (x0, y0, x1, y1),
                "y0": y0,
                "y1": y1,
                "raw_text": bclean,
                "english": eng,
                "dev_ratio": calc_devanagari_ratio(bclean)
            }
            if x0 < 200:
                label_blocks.append(item)
            else:
                value_blocks.append(item)

        page_blocks_out: List[PageBlock] = []

        # Map labels to tiers
        for lb in label_blocks:
            l_eng = lb["english"]
            assigned_tier = "AUTHORITATIVE"
            matched_label = None

            for label_name, tier in self.GEMARPTS_LABELS.items():
                if label_name.lower() in l_eng.lower():
                    assigned_tier = tier
                    matched_label = label_name
                    break

            # Add the label block itself
            page_blocks_out.append(PageBlock(
                page_no=page_no,
                block_idx=lb["bidx"],
                bbox=lb["bbox"],
                text=lb["english"] or lb["raw_text"],
                raw_text=lb["raw_text"],
                tier=assigned_tier,
                tier_reason=f"table_label_{matched_label or 'general'}",
                devanagari_ratio=lb["dev_ratio"],
                section_label=matched_label
            ))

            # Find horizontally aligned value blocks
            # Overlap in y-range with 25pt tolerance for multi-line cells
            ly0, ly1 = lb["y0"], lb["y1"]
            paired_vals = [
                vb for vb in value_blocks
                if (max(ly0, vb["y0"]) < min(ly1, vb["y1"]) or abs(ly0 - vb["y0"]) < 25)
            ]

            for vb in paired_vals:
                page_blocks_out.append(PageBlock(
                    page_no=page_no,
                    block_idx=vb["bidx"],
                    bbox=vb["bbox"],
                    text=vb["english"] or vb["raw_text"],
                    raw_text=vb["raw_text"],
                    tier=assigned_tier,
                    tier_reason=f"paired_with_label_{matched_label or 'general'}",
                    devanagari_ratio=vb["dev_ratio"],
                    section_label=matched_label
                ))

        # Include any remaining unpaired blocks (headers, footers, etc.)
        paired_indices = {pb.block_idx for pb in page_blocks_out}
        for bidx, b in enumerate(raw_blocks):
            if bidx not in paired_indices:
                x0, y0, x1, y1, btext = b[0], b[1], b[2], b[3], b[4]
                bclean = btext.strip()
                if not bclean:
                    continue
                eng = re.sub(r'\s+', ' ', strip_devanagari(bclean)).strip()
                page_blocks_out.append(PageBlock(
                    page_no=page_no,
                    block_idx=bidx,
                    bbox=(x0, y0, x1, y1),
                    text=eng or bclean,
                    raw_text=bclean,
                    tier="AUTHORITATIVE",
                    tier_reason="unpaired_page1_block",
                    devanagari_ratio=calc_devanagari_ratio(bclean),
                    section_label=None
                ))

        # Sort blocks by page_no, y0, x0 for coherent order
        page_blocks_out.sort(key=lambda p: (p.page_no, p.bbox[1], p.bbox[0]))
        return page_blocks_out
