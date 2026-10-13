# -*- coding: utf-8 -*-
"""
backend/app/parsers/item_builder.py
===================================
Deterministic Item Builder and Bid-Level Clause Extractor for Tender Documents.
Extracts discrete procurement line items from document adapter PageBlocks and tabular rows.
Dynamically maps columns by reading header rows instead of assuming fixed row patterns.
Enforces strict firewalls: no CONTEXT_ONLY text can ever enter an item specification field.
Captures tender-wide clauses (e.g. Buyer ATC) into an authoritative bid-level clause bucket,
scanned by mention_extractor so standards like IS 808 and IS 456 are never lost.
Supports multi-document joining by material code (exact) or normalized description (fuzzy),
explicitly flagging uncertain joins (never merging silently), preserving all descriptions
across documents with source provenance, and tracking cross-document discrepancies.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Tuple, Any, Set, Union

from app.adapters.base import PageBlock
from app.parsers.mention_extractor import extract_mentions, Mention


@dataclass
class SourceRef:
    doc_name: str
    page_no: int
    block_idx: int
    tier: str  # "AUTHORITATIVE", "CORROBORATING", "CONTEXT_ONLY"


@dataclass
class ItemField:
    value: str
    source: SourceRef


@dataclass
class AuditItem:
    seq_no: int = 0
    item_id: str = ""
    material_code: Optional[ItemField] = None
    description: Optional[ItemField] = None
    technical_spec: Optional[ItemField] = None
    quantity: Optional[ItemField] = None
    unit: Optional[ItemField] = None
    tier: str = "AUTHORITATIVE"
    all_sources: List[SourceRef] = field(default_factory=list)
    all_descriptions: List[ItemField] = field(default_factory=list)
    cross_doc_mismatches: List[Dict[str, Any]] = field(default_factory=list)
    join_status: Optional[str] = None
    is_uncertain_join: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "seq_no": self.seq_no,
            "item_id": self.item_id,
            "material_code": self.material_code.value if self.material_code else None,
            "description": self.description.value if self.description else None,
            "technical_spec": self.technical_spec.value if self.technical_spec else None,
            "quantity": self.quantity.value if self.quantity else None,
            "unit": self.unit.value if self.unit else None,
            "tier": self.tier,
            "join_status": self.join_status,
            "is_uncertain_join": self.is_uncertain_join,
            "all_descriptions": [
                {
                    "value": d.value,
                    "source": {
                        "doc": d.source.doc_name,
                        "page": d.source.page_no,
                        "block": d.source.block_idx,
                        "tier": d.source.tier,
                    }
                }
                for d in self.all_descriptions
            ],
            "cross_doc_mismatches": self.cross_doc_mismatches,
            "sources": [
                {
                    "doc": s.doc_name,
                    "page": s.page_no,
                    "block": s.block_idx,
                    "tier": s.tier,
                }
                for s in self.all_sources
            ],
        }


@dataclass
class UnsegmentedBlock:
    doc_name: str
    page_no: int
    block_idx: int
    tier: str
    text: str
    reason: str


@dataclass
class BidClause:
    clause_id: str
    heading: str
    text: str
    source: SourceRef
    mentions: List[Mention] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "clause_id": self.clause_id,
            "heading": self.heading,
            "text": self.text,
            "source": {
                "doc": self.source.doc_name,
                "page": self.source.page_no,
                "block": self.source.block_idx,
                "tier": self.source.tier,
            },
            "mentions": [
                {
                    "raw_text": m.raw_text,
                    "base_key": m.base_key,
                    "year": m.year,
                    "part": m.part,
                    "disposition": m.disposition,
                }
                for m in self.mentions
            ],
        }


class ExtractionResult(tuple):
    """
    Container for item extraction results.
    Inherits from tuple (items, unsegmented) to maintain 100% backward compatibility
    with existing code unpacking `items, unseg = build_items_from_blocks(...)`,
    while exposing `.bid_level_clauses`, `.items`, and `.unsegmented`.
    """
    def __new__(cls, items: List[AuditItem], unsegmented: List[UnsegmentedBlock], bid_level_clauses: Optional[List[BidClause]] = None):
        return super().__new__(cls, (items, unsegmented))

    def __init__(self, items: List[AuditItem], unsegmented: List[UnsegmentedBlock], bid_level_clauses: Optional[List[BidClause]] = None):
        self.items = items
        self.unsegmented = unsegmented
        self.bid_level_clauses = bid_level_clauses or []


class ColumnRole(str, Enum):
    SL_NO = "SL_NO"
    MATERIAL_CODE = "MATERIAL_CODE"
    DESCRIPTION = "DESCRIPTION"
    TECHNICAL_SPEC = "TECHNICAL_SPEC"
    QUANTITY = "QUANTITY"
    UNIT = "UNIT"
    UNKNOWN = "UNKNOWN"


class HeaderMapper:
    """Dynamically maps tabular column headers to standard column roles with strict commercial exclusions."""

    PRICE_WORDS = {"price", "rate", "cost", "amount", "value", "val", "currency", "tax", "gst", "duty", "fee"}
    CODE_EXCLUSIONS = {"cost", "project", "hsn", "postal", "zip", "vendor", "account", "gl", "tax", "sac"}

    ROLE_ALIASES: Dict[ColumnRole, List[str]] = {
        ColumnRole.SL_NO: [
            "sl.no", "sl no", "slno", "s.no", "s. no.", "s. no", "s.no.", "s no", "sno",
            "sl. no", "sl. no.", "sl no.",
            "item no", "item #", "item no.", "sr.no", "sr no", "serial no", "p.सं.",
            "s.n.", "s.n", "line", "item", "schedule item no", "schedule item no.", "schedule no"
        ],
        ColumnRole.MATERIAL_CODE: [
            "material code", "item code", "part no", "part code", "part #", "mat code",
            "material #", "product code", "sap code", "catalog no", "cat no"
        ],
        ColumnRole.DESCRIPTION: [
            "description of goods", "item description / specification", "short description",
            "item description", "description", "details", "material description",
            "product description", "item details", "nomenclature", "product name", "item name", "desc"
        ],
        ColumnRole.TECHNICAL_SPEC: [
            "technical specification", "tech spec", "technical specifications",
            "specification", "specifications", "spec", "specs", "detailed spec",
            "requirements", "parameters", "scope"
        ],
        ColumnRole.QUANTITY: [
            "estimated quantity", "quantity & unit", "quantity", "qty", "qty.", "total quantity",
            "ord qty", "ordered qty", "bid quantity", "मात्रा", "boq qty", "count"
        ],
        ColumnRole.UNIT: [
            "unit of measurement", "measuring unit", "unit of measure", "uom", "u.o.m", "u/m"
        ],
    }

    @classmethod
    def match_role(cls, cell_text: str) -> ColumnRole:
        t = cell_text.strip().lower()
        if not t:
            return ColumnRole.UNKNOWN

        words = set(re.findall(r'[a-z]+', t))

        # Rule 1: Commercial / Price exclusion (e.g. "Unit Price", "Unit Rate")
        if words & cls.PRICE_WORDS:
            return ColumnRole.UNKNOWN

        # Rule 2: HSN / SAC / Cost code exclusion (e.g. "HSN Code", "HSN/SAC", "Cost Code")
        if "hsn" in words or "sac" in words or (words & cls.CODE_EXCLUSIONS and "code" in words):
            return ColumnRole.UNKNOWN

        # Rule 3: Exact match against registered aliases
        for role, aliases in cls.ROLE_ALIASES.items():
            if t in aliases:
                return role

        # Rule 4: Standalone "unit" or "units" (e.g. "unit", "units", "unit (nos)", "unit (mtr)")
        if re.search(r'\bunits?\b', t) and not (words & cls.PRICE_WORDS):
            return ColumnRole.UNIT

        # Rule 5: Substring matching sorted by alias length descending
        all_pairs = []
        for role, aliases in cls.ROLE_ALIASES.items():
            for alias in aliases:
                all_pairs.append((len(alias), alias, role))
        all_pairs.sort(key=lambda x: -x[0])

        for _, alias, role in all_pairs:
            if re.search(r'\b' + re.escape(alias) + r'\b', t):
                return role

        return ColumnRole.UNKNOWN

    @classmethod
    def detect_column_mapping_from_cells(cls, header_cells: List[str]) -> Dict[int, ColumnRole]:
        mapping: Dict[int, ColumnRole] = {}
        for idx, cell in enumerate(header_cells):
            role = cls.match_role(cell)
            mapping[idx] = role
        return mapping

    @classmethod
    def detect_column_mapping_from_line(cls, line: str) -> Optional[List[Tuple[ColumnRole, int]]]:
        """
        Detects column header roles and their left-to-right character positions
        in a single continuous line of text.
        Returns sorted list of (role, position).
        """
        t = line.lower().strip()
        # Headers are concise single rows, not multi-sentence prose paragraphs
        if not t or len(t) > 200 or len(t.split()) > 25:
            return None
        words = set(re.findall(r'[a-z]+', t))
        found: List[Tuple[int, ColumnRole, str]] = []

        # Check explicit aliases
        for role, aliases in cls.ROLE_ALIASES.items():
            best_pos = -1
            best_alias = ""
            for alias in aliases:
                p = t.find(alias)
                if p != -1 and (best_pos == -1 or p < best_pos):
                    # Verify not part of price phrase
                    sub_context = t[max(0, p - 5): min(len(t), p + len(alias) + 10)]
                    if not (set(re.findall(r'[a-z]+', sub_context)) & cls.PRICE_WORDS):
                        best_pos = p
                        best_alias = alias
            if best_pos != -1:
                found.append((best_pos, role, best_alias))

        # Check standalone unit
        m_unit = re.search(r'\bunits?\b', t)
        if m_unit:
            p = m_unit.start()
            sub_context = t[max(0, p - 5): min(len(t), p + 15)]
            if not (set(re.findall(r'[a-z]+', sub_context)) & cls.PRICE_WORDS):
                if not any(r == ColumnRole.UNIT for _, r, _ in found):
                    found.append((p, ColumnRole.UNIT, m_unit.group(0)))

        if len(found) >= 3:
            found.sort(key=lambda x: x[0])
            return [(r, p) for p, r, _ in found]
        return None


def normalize_description(text: str) -> Set[str]:
    """Tokenizes and normalizes item description for deterministic fuzzy matching."""
    t = text.lower()
    t = re.sub(r'(\d+)\s*(?:sq\.?\s*mm|sqmm)', r'\1sqmm', t)
    t = re.sub(r'(\d+)\s*(?:core|c)\b', r'\1c', t)
    tokens = re.findall(r'[a-z0-9]+', t)
    stopwords = {"and", "the", "to", "for", "as", "per", "grade", "with", "all", "three", "colours", "cble", "cable"}
    return {w for w in tokens if w not in stopwords and len(w) > 0}


def calc_description_similarity(desc1: str, desc2: str) -> float:
    """Calculates Jaccard similarity between two normalized item descriptions."""
    s1 = normalize_description(desc1)
    s2 = normalize_description(desc2)
    if not s1 or not s2:
        return 0.0
    intersection = len(s1 & s2)
    union = len(s1 | s2)
    return intersection / union if union > 0 else 0.0


class ItemBuilder:
    """Deterministic Line Item Builder and Bid-Level Clause Extractor."""

    TABULAR_ROW_START_RE = re.compile(
        r'^(?P<sl>\d{1,4})\s+(?P<code>[A-Z0-9]{8,15})\s+(?P<desc>.+)',
        re.IGNORECASE
    )

    QTY_UNIT_RE = re.compile(
        r'^(?P<qty>\d+(?:\.\d+)?)\s*(?P<unit>[A-Za-z]+)?$'
    )

    SCHEDULE_ITEM_RE = re.compile(
        r'^(?:(?P<code>[A-Z0-9]{8,15})[:\s]+)?'
        r'(?P<desc>[A-Za-z0-9][^\(\n]+?)'
        r'\s*\(\s*(?P<qty>\d+(?:\.\d+)?)\s*(?P<unit>[A-Za-z]+)\s*\)$',
        re.IGNORECASE
    )

    BUYER_ATC_HEADER_RE = re.compile(
        r'(?:Buyer\s+Added\s+Bid\s+Specific\s+Terms\s+and\s+Conditions'
        r'|Buyer\s+Added\s+Bid\s+Specific\s+ATC)',
        re.IGNORECASE
    )

    CLAUSE_START_RE = re.compile(
        r'^(?:Clause\s+\d+|OPTION\s+CLAUSE|\d+\.\s+Generic|\d+\.\s+Buyer\s+Added|[1-9]\d?\.\s+)',
        re.IGNORECASE
    )

    HEADER_KEYWORDS = [
        "technical specification", "schedule of quantities", "bill of quantities",
        "consignee", "delivery schedule", "general terms", "buyer added", "total quantity",
        "gemarpts", "relevant categories", "experience and turnover", "bid details",
        "emd detail", "epbg detail", "payment timelines", "evaluation method"
    ]

    @classmethod
    def build_items_from_blocks(
        cls,
        blocks: List[PageBlock],
        doc_name: str = "document"
    ) -> ExtractionResult:
        """
        Deterministically extracts AuditItem line items and BidClause authoritative clauses
        from PageBlock stream.
        Separates unsegmented blocks with transparent diagnostic reasons.
        Strictly guarantees: NO CONTEXT_ONLY text is ever included in an item or clause.
        """
        items: List[AuditItem] = []
        unsegmented: List[UnsegmentedBlock] = []
        bid_level_clauses: List[BidClause] = []

        # Check for tabular header line with dynamic column order
        detected_col_order: Optional[List[ColumnRole]] = None
        for b in blocks:
            if b.tier != "CONTEXT_ONLY":
                if '|' in b.text:
                    cells = [c.strip() for c in b.text.split('|')]
                    cell_map = HeaderMapper.detect_column_mapping_from_cells(cells)
                    distinct_roles = {r for r in cell_map.values() if r != ColumnRole.UNKNOWN}
                    if len(distinct_roles) >= 3:
                        detected_col_order = [cell_map[i] for i in sorted(cell_map.keys())]
                        break
                mapping = HeaderMapper.detect_column_mapping_from_line(b.text.strip())
                if mapping:
                    distinct_line_roles = {r for r, _ in mapping}
                    if len(distinct_line_roles) >= 3:
                        detected_col_order = [role for role, _ in mapping]
                        break

        has_tabular_rows = any(cls.TABULAR_ROW_START_RE.match(b.text.strip()) for b in blocks)
        has_pipe_rows = any('|' in b.text for b in blocks if b.tier != "CONTEXT_ONLY")
        is_reordered_table = bool(detected_col_order and (
            has_pipe_rows or not has_tabular_rows or
            (detected_col_order[0] != ColumnRole.SL_NO and detected_col_order[0] != ColumnRole.MATERIAL_CODE)
        ))

        in_atc_section = False
        current_atc_heading = ""

        if is_reordered_table and detected_col_order:
            # ── PATH A0: Reordered Tabular BOQ (e.g. Quantity | Unit | Material Code | ...) ──
            header_seen = False
            for b in blocks:
                b_text = b.text.strip()
                if not b_text:
                    continue

                if b.tier == "CONTEXT_ONLY":
                    unsegmented.append(UnsegmentedBlock(
                        doc_name=doc_name, page_no=b.page_no, block_idx=b.block_idx,
                        tier=b.tier, text=b_text, reason="context_only_tier_firewalled"
                    ))
                    continue

                # Filter page numbers
                if re.match(r'^\d+\s*/\s*\d+$', b_text):
                    unsegmented.append(UnsegmentedBlock(
                        doc_name=doc_name, page_no=b.page_no, block_idx=b.block_idx,
                        tier=b.tier, text=b_text, reason="short_label_or_page_number"
                    ))
                    continue

                # Check if this block is the header itself
                is_header = False
                if '|' in b_text:
                    cells = [c.strip() for c in b_text.split('|')]
                    cell_map = HeaderMapper.detect_column_mapping_from_cells(cells)
                    distinct_roles = {r for r in cell_map.values() if r != ColumnRole.UNKNOWN}
                    if len(distinct_roles) >= 3:
                        is_header = True
                if not is_header:
                    m_hdr = HeaderMapper.detect_column_mapping_from_line(b_text)
                    if m_hdr and len({r for r, _ in m_hdr}) >= 3:
                        is_header = True

                if is_header:
                    header_seen = True
                    unsegmented.append(UnsegmentedBlock(
                        doc_name=doc_name, page_no=b.page_no, block_idx=b.block_idx,
                        tier=b.tier, text=b_text, reason="document_header_or_metadata"
                    ))
                    continue

                if not header_seen:
                    reason = cls._classify_unsegmented_reason(b_text, b.tier)
                    unsegmented.append(UnsegmentedBlock(
                        doc_name=doc_name, page_no=b.page_no, block_idx=b.block_idx,
                        tier=b.tier, text=b_text, reason=reason
                    ))
                    continue

                # Parse tabular data line (either pipe-separated or multi-token)
                tokens = [p.strip() for p in b_text.split('|')] if '|' in b_text else b_text.split()
                if len(tokens) >= len(detected_col_order) - 1:
                    # Guard against repeated header lines
                    if '|' in b_text:
                        check_cells = [c.strip() for c in b_text.split('|')]
                        check_map = HeaderMapper.detect_column_mapping_from_cells(check_cells)
                        if len({r for r in check_map.values() if r != ColumnRole.UNKNOWN}) >= 3:
                            unsegmented.append(UnsegmentedBlock(
                                doc_name=doc_name, page_no=b.page_no, block_idx=b.block_idx,
                                tier=b.tier, text=b_text, reason="document_header_or_metadata"
                            ))
                            continue

                    row_cells = tokens[:len(detected_col_order)]
                    sl_v, code_v, desc_v, spec_v, qty_v, unit_v = None, None, None, None, None, None
                    for c_idx, role in enumerate(detected_col_order):
                        if c_idx < len(tokens):
                            val = tokens[c_idx].strip()
                            if role == ColumnRole.SL_NO: sl_v = val
                            elif role == ColumnRole.MATERIAL_CODE: code_v = val
                            elif role == ColumnRole.DESCRIPTION: desc_v = val
                            elif role == ColumnRole.TECHNICAL_SPEC: spec_v = val
                            elif role == ColumnRole.QUANTITY: qty_v = val
                            elif role == ColumnRole.UNIT: unit_v = val

                    src = SourceRef(doc_name, b.page_no, b.block_idx, b.tier)
                    all_descs = []
                    if desc_v:
                        all_descs.append(ItemField(desc_v, src))
                    if spec_v:
                        all_descs.append(ItemField(spec_v, src))

                    seq_val = len(items) + 1
                    try:
                        seq_val = int(sl_v) if sl_v and sl_v.isdigit() else (len(items) + 1)
                    except Exception:
                        seq_val = len(items) + 1

                    item = AuditItem(
                        seq_no=seq_val,
                        item_id=sl_v or str(len(items) + 1),
                        material_code=ItemField(code_v, src) if code_v else None,
                        description=ItemField(desc_v or spec_v, src) if (desc_v or spec_v) else None,
                        technical_spec=ItemField(spec_v, src) if spec_v else None,
                        quantity=ItemField(qty_v, src) if qty_v else None,
                        unit=ItemField(unit_v, src) if unit_v else None,
                        tier=b.tier,
                        all_sources=[src],
                        all_descriptions=all_descs if all_descs else ([ItemField(desc_v, src)] if desc_v else [])
                    )
                    items.append(item)
                else:
                    reason = cls._classify_unsegmented_reason(b_text, b.tier)
                    unsegmented.append(UnsegmentedBlock(
                        doc_name=doc_name, page_no=b.page_no, block_idx=b.block_idx,
                        tier=b.tier, text=b_text, reason=reason
                    ))

        elif has_tabular_rows:
            # ── PATH A: Tabular BOQ / Spec Row Segmentation ──────────────────
            cur_row_blocks: List[PageBlock] = []
            cur_sl: Optional[str] = None
            cur_code: Optional[str] = None
            cur_desc_start: Optional[str] = None

            for b in blocks:
                b_text = b.text.strip()
                if not b_text:
                    continue

                # Context-only blocks are strictly firewalled
                if b.tier == "CONTEXT_ONLY":
                    unsegmented.append(UnsegmentedBlock(
                        doc_name=doc_name, page_no=b.page_no, block_idx=b.block_idx,
                        tier=b.tier, text=b_text, reason="context_only_tier_firewalled"
                    ))
                    continue

                m_start = cls.TABULAR_ROW_START_RE.match(b_text)
                if m_start:
                    if cur_row_blocks:
                        item = cls._assemble_tabular_item(
                            cur_sl, cur_code, cur_desc_start, cur_row_blocks, doc_name
                        )
                        if item:
                            items.append(item)
                    cur_sl = m_start.group("sl")
                    cur_code = m_start.group("code")
                    cur_desc_start = m_start.group("desc")
                    cur_row_blocks = [b]
                elif cur_row_blocks:
                    cur_row_blocks.append(b)
                    qm = cls.QTY_UNIT_RE.match(b_text)
                    if qm:
                        item = cls._assemble_tabular_item(
                            cur_sl, cur_code, cur_desc_start, cur_row_blocks, doc_name
                        )
                        if item:
                            items.append(item)
                        cur_row_blocks = []
                        cur_sl = None
                        cur_code = None
                        cur_desc_start = None
                else:
                    reason = cls._classify_unsegmented_reason(b_text, b.tier)
                    unsegmented.append(UnsegmentedBlock(
                        doc_name=doc_name, page_no=b.page_no, block_idx=b.block_idx,
                        tier=b.tier, text=b_text, reason=reason
                    ))

            if cur_row_blocks:
                item = cls._assemble_tabular_item(
                    cur_sl, cur_code, cur_desc_start, cur_row_blocks, doc_name
                )
                if item:
                    items.append(item)

        else:
            # ── PATH B: Schedule / Portal Item Matching & Bid-Level Clauses ──
            for b in blocks:
                b_text = b.text.strip()
                if not b_text:
                    continue

                # Context-only blocks are strictly firewalled
                if b.tier == "CONTEXT_ONLY":
                    unsegmented.append(UnsegmentedBlock(
                        doc_name=doc_name, page_no=b.page_no, block_idx=b.block_idx,
                        tier=b.tier, text=b_text, reason="context_only_tier_firewalled"
                    ))
                    continue

                # Filter page numbers and short metadata labels before clause classification
                if re.match(r'^\d+\s*/\s*\d+$', b_text) or len(b_text) < 10:
                    unsegmented.append(UnsegmentedBlock(
                        doc_name=doc_name, page_no=b.page_no, block_idx=b.block_idx,
                        tier=b.tier, text=b_text, reason="short_label_or_page_number"
                    ))
                    continue

                # Check if block transitions into Buyer ATC Section
                if cls.BUYER_ATC_HEADER_RE.search(b_text):
                    in_atc_section = True
                    current_atc_heading = b_text
                    unsegmented.append(UnsegmentedBlock(
                        doc_name=doc_name, page_no=b.page_no, block_idx=b.block_idx,
                        tier=b.tier, text=b_text, reason="buyer_atc_section_header"
                    ))
                    continue

                # Check if block is a Technical Specification item (e.g. "Specification: RCC structures...")
                m_spec = re.match(r'^(?:Specification|Tech(?:nical)?\s*Spec(?:ification)?)\s*:\s*(?P<content>.+)', b_text, re.I)
                if m_spec and b.tier == "AUTHORITATIVE":
                    content = m_spec.group("content").strip()
                    m_desc = re.match(r'^([^,;:\n]+?(?:\s+(?:must|shall|conforming|to|is|in\s+accordance)\b|[.,;]|$))', content, re.I)
                    short_desc = m_desc.group(1).strip(" .,;:") if m_desc else content[:40]
                    short_desc = re.sub(r'\s+(?:must|shall|conforming|to|is|in\s+accordance)$', '', short_desc, flags=re.I).strip()

                    src = SourceRef(doc_name, b.page_no, b.block_idx, b.tier)
                    item = AuditItem(
                        item_id=str(len(items) + 1),
                        material_code=None,
                        description=ItemField(short_desc or content[:30], src),
                        technical_spec=ItemField(b_text, src),
                        quantity=None,
                        unit=None,
                        tier=b.tier,
                        all_sources=[src],
                        all_descriptions=[ItemField(short_desc or content[:30], src)]
                    )
                    items.append(item)
                    continue

                # Check if block is an Authoritative Bid-Level Clause (e.g. Buyer ATC)
                is_clause = False
                if b.tier == "AUTHORITATIVE":
                    if in_atc_section or (b.section_label and "Buyer" in b.section_label):
                        is_clause = True
                    elif cls.CLAUSE_START_RE.match(b_text):
                        is_clause = True

                if is_clause:
                    mentions = extract_mentions(b_text, source_block_tier="AUTHORITATIVE")
                    src = SourceRef(doc_name, b.page_no, b.block_idx, b.tier)
                    clause_id = f"ATC-{len(bid_level_clauses) + 1}"
                    bid_level_clauses.append(BidClause(
                        clause_id=clause_id,
                        heading=current_atc_heading or "Buyer Added ATC",
                        text=b_text,
                        source=src,
                        mentions=mentions
                    ))
                    continue

                # Schedule line item pattern (e.g. GeM portal line item)
                m_sched = cls.SCHEDULE_ITEM_RE.match(b_text)
                if m_sched and len(m_sched.group("desc").strip()) >= 5:
                    code = m_sched.group("code")
                    desc = m_sched.group("desc").strip()
                    qty = m_sched.group("qty")
                    unit = m_sched.group("unit")

                    src = SourceRef(doc_name, b.page_no, b.block_idx, b.tier)
                    item = AuditItem(
                        item_id=str(len(items) + 1),
                        material_code=ItemField(code, src) if code else None,
                        description=ItemField(desc, src),
                        technical_spec=None,
                        quantity=ItemField(qty, src) if qty else None,
                        unit=ItemField(unit, src) if unit else None,
                        tier=b.tier,
                        all_sources=[src],
                        all_descriptions=[ItemField(desc, src)]
                    )
                    items.append(item)
                else:
                    reason = cls._classify_unsegmented_reason(b_text, b.tier)
                    unsegmented.append(UnsegmentedBlock(
                        doc_name=doc_name, page_no=b.page_no, block_idx=b.block_idx,
                        tier=b.tier, text=b_text, reason=reason
                    ))

        for idx, item in enumerate(items, 1):
            item.seq_no = idx
        return ExtractionResult(items, unsegmented, bid_level_clauses)

    @classmethod
    def build_items_from_table_rows(
        cls,
        rows: List[List[str]],
        doc_name: str = "table_doc",
        inherit_blank_cells: bool = True
    ) -> Tuple[List[AuditItem], List[UnsegmentedBlock]]:
        """
        Dynamically extracts AuditItems from structured table rows.
        Reads column headers to map column roles regardless of column order,
        handles merged cells (blank cells inheriting values from previous row),
        description-only rows, and absent material codes.
        """
        items: List[AuditItem] = []
        unsegmented: List[UnsegmentedBlock] = []

        if not rows:
            return items, unsegmented

        first_row = [str(c).strip() for c in rows[0]]
        col_map = HeaderMapper.detect_column_mapping_from_cells(first_row)

        recognized_roles = {r for r in col_map.values() if r != ColumnRole.UNKNOWN}
        has_header = len(recognized_roles) >= 2
        data_rows = rows[1:] if has_header else rows

        if not has_header:
            col_map = {}

        prev_sl: Optional[str] = None
        prev_code: Optional[str] = None
        prev_desc: Optional[str] = None

        for row_idx, raw_cells in enumerate(data_rows, start=1 if has_header else 0):
            cells = [str(c).strip() for c in raw_cells]
            if not any(cells):
                continue

            sl_val: Optional[str] = None
            code_val: Optional[str] = None
            desc_val: Optional[str] = None
            spec_val: Optional[str] = None
            qty_val: Optional[str] = None
            unit_val: Optional[str] = None

            if has_header:
                for c_idx, cell_text in enumerate(cells):
                    role = col_map.get(c_idx, ColumnRole.UNKNOWN)
                    if not cell_text:
                        continue
                    if role == ColumnRole.SL_NO:
                        sl_val = cell_text
                    elif role == ColumnRole.MATERIAL_CODE:
                        code_val = cell_text
                    elif role == ColumnRole.DESCRIPTION:
                        desc_val = cell_text
                    elif role == ColumnRole.TECHNICAL_SPEC:
                        spec_val = cell_text
                    elif role == ColumnRole.QUANTITY:
                        qm = cls.QTY_UNIT_RE.match(cell_text)
                        if qm:
                            qty_val = qm.group("qty")
                            if qm.group("unit") and not unit_val:
                                unit_val = qm.group("unit")
                        else:
                            qty_val = cell_text
                    elif role == ColumnRole.UNIT:
                        unit_val = cell_text

                # Merged-cell support: Inherit values from preceding row if blank
                if inherit_blank_cells:
                    if not sl_val and prev_sl and (desc_val or spec_val or qty_val):
                        sl_val = prev_sl
                    if not code_val and prev_code and (desc_val or spec_val or qty_val):
                        code_val = prev_code
                    if not desc_val and prev_desc and (spec_val or qty_val):
                        desc_val = prev_desc

                    if sl_val: prev_sl = sl_val
                    if code_val: prev_code = code_val
                    if desc_val: prev_desc = desc_val

            else:
                joined_row_text = " ".join(cells).strip()
                m_q = re.search(r'\(\s*(?:Qty|Quantity)?[:\s]*(\d+(?:\.\d+)?)\s*([A-Za-z]+)?\s*\)', joined_row_text, re.I)
                if m_q:
                    qty_val = m_q.group(1)
                    unit_val = m_q.group(2)
                    desc_val = re.sub(r'\(\s*(?:Qty|Quantity)?[:\s]*\d+.*?\)', '', joined_row_text).strip()
                else:
                    desc_val = joined_row_text

            if desc_val or code_val:
                src = SourceRef(doc_name, page_no=1, block_idx=row_idx, tier="AUTHORITATIVE")
                item = AuditItem(
                    item_id=sl_val or str(len(items) + 1),
                    material_code=ItemField(code_val, src) if code_val else None,
                    description=ItemField(desc_val, src) if desc_val else None,
                    technical_spec=ItemField(spec_val, src) if spec_val else None,
                    quantity=ItemField(qty_val, src) if qty_val else None,
                    unit=ItemField(unit_val, src) if unit_val else None,
                    tier="AUTHORITATIVE",
                    all_sources=[src],
                    all_descriptions=[ItemField(desc_val, src)] if desc_val else []
                )
                items.append(item)
            else:
                unsegmented.append(UnsegmentedBlock(
                    doc_name=doc_name, page_no=1, block_idx=row_idx,
                    tier="AUTHORITATIVE", text=" ".join(cells), reason="unstructured_row"
                ))

        for idx, item in enumerate(items, 1):
            item.seq_no = idx
        return items, unsegmented

    @classmethod
    def _assemble_tabular_item(
        cls,
        sl: Optional[str],
        code: Optional[str],
        desc_start: Optional[str],
        row_blocks: List[PageBlock],
        doc_name: str
    ) -> Optional[AuditItem]:
        """Assembles a tabular BOQ item from its constituent PageBlocks."""
        if not row_blocks:
            return None

        first_block = row_blocks[0]
        sources = [SourceRef(doc_name, b.page_no, b.block_idx, b.tier) for b in row_blocks]

        qty_field: Optional[ItemField] = None
        unit_field: Optional[ItemField] = None
        content_blocks = list(row_blocks)

        last_block = row_blocks[-1]
        qm = cls.QTY_UNIT_RE.match(last_block.text.strip())
        if qm:
            src_last = SourceRef(doc_name, last_block.page_no, last_block.block_idx, last_block.tier)
            qty_field = ItemField(qm.group("qty"), src_last)
            unit_field = ItemField(qm.group("unit") or "", src_last)
            content_blocks = row_blocks[:-1]

        short_desc_parts = [desc_start] if desc_start else []
        spec_parts = []

        is_spec_mode = False
        spec_source: Optional[SourceRef] = None

        for b in content_blocks[1:]:
            b_text = b.text.strip()
            if any(k in b_text.upper() for k in ["POWER CABLE", "CONTROL CABLE", "SPECIFICATION", "VOLTAGE GRADE", "CONDUCTOR"]):
                is_spec_mode = True
                if not spec_source:
                    spec_source = SourceRef(doc_name, b.page_no, b.block_idx, b.tier)
            elif re.match(r'^(?:STR:|AR\s+FRLS|CU-STR)', b_text, re.I):
                is_spec_mode = False

            if is_spec_mode:
                spec_parts.append(b_text)
            else:
                short_desc_parts.append(b_text)

        short_desc_str = " ".join(short_desc_parts).strip()
        spec_str = " ".join(spec_parts).strip()

        src_first = SourceRef(doc_name, first_block.page_no, first_block.block_idx, first_block.tier)
        desc_field = ItemField(short_desc_str, src_first) if short_desc_str else None

        return AuditItem(
            item_id=sl or "1",
            material_code=ItemField(code, src_first) if code else None,
            description=desc_field,
            technical_spec=ItemField(spec_str, spec_source or src_first) if spec_str else None,
            quantity=qty_field,
            unit=unit_field,
            tier=first_block.tier,
            all_sources=sources,
            all_descriptions=[desc_field] if desc_field else []
        )

    @classmethod
    def _classify_unsegmented_reason(cls, text: str, tier: str) -> str:
        """Determines diagnostic reason for an unsegmented block."""
        if tier == "CONTEXT_ONLY":
            return "context_only_tier"
        t_low = text.lower()
        if any(h in t_low for h in cls.HEADER_KEYWORDS):
            return "document_header_or_metadata"
        if len(text) < 15:
            return "short_label_or_page_number"
        if "option clause" in t_low or "vendor code" in t_low or "terms and conditions" in t_low:
            return "buyer_atc_clause"
        return "unstructured_non_item_text"

    @classmethod
    def join_item_sets(
        cls,
        doc_items_list: List[List[AuditItem]],
        desc_similarity_threshold: float = 0.70
    ) -> List[AuditItem]:
        """
        Merges items across multiple tender documents.
        1. Primary join: Exact match on material_code.
        2. Fallback join: Normalized description similarity with explicit uncertainty tracking.
        3. Preserves all descriptions with provenance in `all_descriptions`.
        4. Detects and records cross-document discrepancies in `cross_doc_mismatches`.
        Strictly guarantees: NO CONTEXT_ONLY field is ever accepted.
        """
        if not doc_items_list:
            return []
        if len(doc_items_list) == 1:
            return doc_items_list[0]

        primary_items: List[AuditItem] = [
            AuditItem(
                item_id=it.item_id,
                material_code=it.material_code,
                description=it.description,
                technical_spec=it.technical_spec,
                quantity=it.quantity,
                unit=it.unit,
                tier=it.tier,
                all_sources=list(it.all_sources),
                all_descriptions=list(it.all_descriptions) if it.all_descriptions else ([it.description] if it.description else []),
                cross_doc_mismatches=[],
                join_status="PRIMARY_DOCUMENT_ITEM",
                is_uncertain_join=False
            )
            for it in doc_items_list[0]
        ]

        for item_set in doc_items_list[1:]:
            for incoming in item_set:
                inc_code = incoming.material_code.value.strip().upper() if incoming.material_code else None
                inc_desc = incoming.description.value.strip() if incoming.description else ""

                matched_primary: Optional[AuditItem] = None
                join_reason = ""
                is_uncertain = False

                # ── PASS 1: Exact Material Code Match ──
                if inc_code:
                    for p in primary_items:
                        p_code = p.material_code.value.strip().upper() if p.material_code else None
                        if p_code and p_code == inc_code:
                            matched_primary = p
                            join_reason = f"EXACT_MATERIAL_CODE_MATCH ({inc_code})"
                            is_uncertain = False
                            break

                # ── PASS 2: Normalized Description Similarity (Fallback) ──
                if not matched_primary and inc_desc:
                    candidates: List[Tuple[float, AuditItem]] = []
                    for p in primary_items:
                        p_desc = p.description.value.strip() if p.description else ""
                        if p_desc:
                            sim = calc_description_similarity(inc_desc, p_desc)
                            if sim >= desc_similarity_threshold:
                                candidates.append((sim, p))

                    if len(candidates) == 1:
                        best_sim, best_p = candidates[0]
                        matched_primary = best_p
                        join_reason = f"UNCERTAIN_DESCRIPTION_MATCH (score={best_sim:.2f}, matched='{best_p.description.value}')"
                        is_uncertain = True
                    elif len(candidates) > 1:
                        incoming.join_status = f"AMBIGUOUS_CANDIDATES ({len(candidates)} matches >= {desc_similarity_threshold})"
                        incoming.is_uncertain_join = False
                        primary_items.append(incoming)
                        continue

                # ── MERGE OR APPEND ──
                if matched_primary:
                    assert incoming.tier != "CONTEXT_ONLY", "Context-only leak in incoming item!"

                    # Technical spec enrichment
                    if incoming.technical_spec and not matched_primary.technical_spec:
                        assert incoming.technical_spec.source.tier != "CONTEXT_ONLY", "Context-only leak in spec!"
                        matched_primary.technical_spec = incoming.technical_spec

                    # Preserve all descriptions with source provenance
                    if incoming.description:
                        matched_primary.all_descriptions.append(incoming.description)

                        # Detect and record cross-document mismatch
                        if matched_primary.description:
                            p_val = matched_primary.description.value.strip()
                            i_val = incoming.description.value.strip()
                            if p_val != i_val:
                                sim = calc_description_similarity(p_val, i_val)
                                matched_primary.cross_doc_mismatches.append({
                                    "field": "description",
                                    "doc1": matched_primary.description.source.doc_name,
                                    "value1": p_val,
                                    "doc2": incoming.description.source.doc_name,
                                    "value2": i_val,
                                    "mismatch_type": "FIELD_VALUE_DISCREPANCY",
                                    "similarity_score": round(sim, 3)
                                })

                        # Enrich primary description (prefer longer or authoritative CBLE: prefix)
                        should_replace_desc = (
                            not matched_primary.description
                            or len(incoming.description.value) > len(matched_primary.description.value)
                            or (matched_primary.description.value.startswith("BLE:") and incoming.description.value.startswith("CBLE:"))
                        )
                        if should_replace_desc:
                            assert incoming.description.source.tier != "CONTEXT_ONLY", "Context-only leak in desc!"
                            matched_primary.description = incoming.description

                    # Quantity enrichment
                    if incoming.quantity and not matched_primary.quantity:
                        matched_primary.quantity = incoming.quantity
                        matched_primary.unit = incoming.unit

                    # Append sources
                    for s in incoming.all_sources:
                        if s not in matched_primary.all_sources:
                            matched_primary.all_sources.append(s)

                    matched_primary.join_status = join_reason
                    matched_primary.is_uncertain_join = is_uncertain

                else:
                    incoming.join_status = "UNMATCHED_NO_CODE" if not inc_code else "UNMATCHED_CODE_NOT_FOUND"
                    incoming.is_uncertain_join = False
                    primary_items.append(incoming)

        for idx, item in enumerate(primary_items, 1):
            item.seq_no = idx

        return primary_items
