# -*- coding: utf-8 -*-
"""
backend/app/parsers/bounded_extractor.py
========================================
Bounded Line-Range LLM Extractor for Unstructured / Pasted Tender Text.

Architectural Design (Step 4b):
1. Line Numbering: Numbers source lines [L1], [L2], ...
2. Strict Redactor Firewall: Sanitizes text with `Redactor.redact` before LLM dispatch.
3. Bounded LLM Prompt: LLM returns ONLY JSON line indices/ranges, strictly under the 1,000 OTPM cap.
4. Python-Side Text Slicing: Code slices lines directly from raw source text using returned line ranges.
5. Hard Verbatim Validation: Every extracted field must be an exact verbatim substring of the source text.
   Any field failing `val in raw_source` is immediately dropped and logged as a validation failure.
"""
from __future__ import annotations
import re
import json
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple

from app.config import settings
from app.parsers.redactor import Redactor
from app.parsers.groq_wrapper import get_groq_wrapper
from app.parsers.item_builder import AuditItem, ItemField, SourceRef

logger = logging.getLogger("bounded_extractor")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter("[%(levelname)s] [BoundedExtractor] %(message)s")
    ch.setFormatter(formatter)
    logger.addHandler(ch)


@dataclass
class BoundedExtractionResult:
    items: List[AuditItem]
    validation_failures: List[Dict[str, Any]] = field(default_factory=list)
    raw_source: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0


class BoundedExtractor:
    """
    Extracts line items from pasted text by prompting the LLM for line indices only,
    slicing the text in Python, and strictly validating verbatim substrings.
    """

    SYSTEM_PROMPT = (
        "You are a precision line-number indexer for procurement tender text.\n"
        "Given numbered lines [L1], [L2], etc., identify procurement line items.\n"
        "Return ONLY a JSON object indicating line numbers where each field appears.\n"
        "DO NOT output or rephrase text. Output integers only for line references.\n\n"
        "Schema:\n"
        "{\n"
        "  \"items\": [\n"
        "    {\n"
        "      \"item_index\": 1,\n"
        "      \"desc_lines\": [1, 2],\n"
        "      \"code_line\": 1,\n"
        "      \"spec_lines\": [2],\n"
        "      \"qty_line\": 3,\n"
        "      \"unit_line\": 3\n"
        "    }\n"
        "  ]\n"
        "}\n"
        "Note: Use null if a field is not present. Return valid JSON only."
    )

    @classmethod
    def format_numbered_lines(cls, text: str) -> Tuple[List[str], str]:
        """
        Splits text into non-empty lines and returns (lines_list, numbered_text).
        Lines are indexed 1-based: [L1], [L2], ...
        """
        raw_lines = [l.strip() for l in text.splitlines() if l.strip()]
        numbered_lines = [f"[L{idx}] {line}" for idx, line in enumerate(raw_lines, 1)]
        return raw_lines, "\n".join(numbered_lines)

    @classmethod
    def _extract_quantity_unit_from_line(cls, line_text: str) -> Tuple[Optional[str], Optional[str]]:
        """Extracts quantity and unit substring from a line."""
        # e.g. "3000 MTR", "500 Numbers", "100.5 Sq.Mtr", "Qty: 200 Nos"
        m = re.search(r'(?:Qty|Quantity)?[:\s]*(\d+(?:\.\d+)?)\s*([A-Za-z/]+)?', line_text, re.I)
        if m:
            qty = m.group(1)
            unit = m.group(2) if m.group(2) else None
            return qty, unit
        return None, None

    @classmethod
    def _extract_material_code_from_line(cls, line_text: str) -> Optional[str]:
        """Extracts material or catalog code substring from a line."""
        # 1. Standalone 10-digit code starting with 6-9 or M-prefixed code
        m1 = re.search(r'\b(?:M)?([6-9]\d{9})\b', line_text)
        if m1:
            return m1.group(0)
        # 2. Alphanumeric part / code: e.g. "CBLE-1001", "CBL-900", "ITEM-042"
        m2 = re.search(r'\b([A-Z]{2,}[-_/][A-Z0-9]+)\b', line_text)
        if m2:
            return m2.group(1)
        # 3. Explicit prefix e.g. "Code: 12345"
        m3 = re.search(r'(?:Material|Item|Part)?\s*Code\s*[:#\-\s]+\s*([A-Za-z0-9\-_/]+)', line_text, re.I)
        if m3:
            return m3.group(1)
        return None

    @classmethod
    def extract_items_bounded(
        cls,
        raw_text: str,
        doc_name: str = "pasted_tender",
        mock_llm_response: Optional[str] = None
    ) -> BoundedExtractionResult:
        """
        Executes bounded line-range extraction:
        1. Number source lines [L1]..[Ln]
        2. Validate & redact PII
        3. LLM returns JSON with line numbers only
        4. Python slices verbatim text
        5. Hard verbatim check: val in raw_text
        """
        raw_lines, numbered_text = cls.format_numbered_lines(raw_text)
        if not raw_lines:
            return BoundedExtractionResult(items=[], raw_source=raw_text)

        # 1. Redact any PII before prompt construction
        redacted_numbered_text = Redactor.redact(numbered_text).redacted_text

        # 2. LLM Call (or mock for testing)
        if mock_llm_response:
            llm_output = mock_llm_response
        else:
            wrapper = get_groq_wrapper()
            messages = [
                {"role": "system", "content": cls.SYSTEM_PROMPT},
                {"role": "user", "content": f"NUMBERED SOURCE LINES:\n{redacted_numbered_text}"}
            ]
            llm_output = wrapper.create_chat_completion(
                messages=messages,
                model=settings.GROQ_MODEL,
                temperature=0.0,
                max_tokens=300,
                prompt_version="bounded_v1"
            )

        # 3. Parse JSON from LLM
        clean_json_str = llm_output.strip()
        if clean_json_str.startswith("```"):
            clean_json_str = re.sub(r"^```(json)?\n", "", clean_json_str)
            clean_json_str = re.sub(r"\n```$", "", clean_json_str)

        try:
            parsed = json.loads(clean_json_str)
            raw_item_records = parsed.get("items", []) if isinstance(parsed, dict) else parsed
        except Exception as e:
            logger.error(f"Failed to parse LLM JSON: {e}. Raw output: {repr(llm_output)}")
            raw_item_records = []

        # 4. Python Slicing & Hard Verbatim Validation
        items: List[AuditItem] = []
        validation_failures: List[Dict[str, Any]] = []

        total_lines = len(raw_lines)

        for rec_idx, rec in enumerate(raw_item_records, 1):
            # Parse line indices
            desc_lines = rec.get("desc_lines") or []
            if isinstance(desc_lines, int):
                desc_lines = [desc_lines]
            spec_lines = rec.get("spec_lines") or []
            if isinstance(spec_lines, int):
                spec_lines = [spec_lines]
            code_line = rec.get("code_line")
            qty_line = rec.get("qty_line")
            unit_line = rec.get("unit_line")

            # Slice description
            desc_parts = [raw_lines[idx - 1] for idx in desc_lines if 1 <= idx <= total_lines]
            sliced_desc = " ".join(desc_parts).strip() if desc_parts else None

            # Slice technical spec
            spec_parts = [raw_lines[idx - 1] for idx in spec_lines if 1 <= idx <= total_lines]
            sliced_spec = " ".join(spec_parts).strip() if spec_parts else None

            # Material code
            sliced_code = None
            if code_line and 1 <= code_line <= total_lines:
                sliced_code = cls._extract_material_code_from_line(raw_lines[code_line - 1])

            # Quantity and unit
            sliced_qty = None
            sliced_unit = None
            if qty_line and 1 <= qty_line <= total_lines:
                q_val, u_val = cls._extract_quantity_unit_from_line(raw_lines[qty_line - 1])
                sliced_qty = q_val
                sliced_unit = u_val
            if unit_line and 1 <= unit_line <= total_lines and not sliced_unit:
                _, u_val2 = cls._extract_quantity_unit_from_line(raw_lines[unit_line - 1])
                sliced_unit = u_val2

            # ── HARD VERBATIM SUBSTRING VALIDATION ──
            # Every field value MUST be a verbatim substring in raw_text!
            fields_to_validate = [
                ("material_code", sliced_code, code_line or 1),
                ("description", sliced_desc, desc_lines[0] if desc_lines else 1),
                ("technical_spec", sliced_spec, spec_lines[0] if spec_lines else 1),
                ("quantity", sliced_qty, qty_line or 1),
                ("unit", sliced_unit, unit_line or 1),
            ]

            valid_fields: Dict[str, Optional[ItemField]] = {
                "material_code": None,
                "description": None,
                "technical_spec": None,
                "quantity": None,
                "unit": None,
            }

            for f_name, f_val, line_ref in fields_to_validate:
                if not f_val:
                    continue

                # Multi-line descriptions may have whitespace differences from joined lines
                # Check each constituent line or normalized substring
                is_verbatim = False
                if f_val in raw_text:
                    is_verbatim = True
                elif f_name in ("description", "technical_spec"):
                    # Check if all constituent words/lines are verbatim in raw_text
                    constituent_parts = [p.strip() for p in f_val.split("\n") if p.strip()]
                    if all(p in raw_text for p in constituent_parts):
                        is_verbatim = True

                if is_verbatim:
                    src = SourceRef(doc_name, page_no=1, block_idx=line_ref, tier="AUTHORITATIVE")
                    valid_fields[f_name] = ItemField(value=f_val, source=src)
                else:
                    # HARD REJECTION: Drop the field and record validation failure
                    logger.error(
                        f"VERBATIM VALIDATION FAILED: field='{f_name}' value={repr(f_val)} "
                        f"is NOT a verbatim substring of source! Field dropped."
                    )
                    validation_failures.append({
                        "item_index": rec_idx,
                        "field": f_name,
                        "rejected_value": f_val,
                        "reason": "NOT_VERBATIM_SUBSTRING_OF_SOURCE"
                    })

            # Only construct item if at least description or material code is valid
            if valid_fields["description"] or valid_fields["material_code"]:
                src_primary = (
                    valid_fields["description"].source
                    if valid_fields["description"]
                    else SourceRef(doc_name, page_no=1, block_idx=1, tier="AUTHORITATIVE")
                )
                audit_item = AuditItem(
                    seq_no=len(items) + 1,
                    item_id=str(len(items) + 1),
                    material_code=valid_fields["material_code"],
                    description=valid_fields["description"],
                    technical_spec=valid_fields["technical_spec"],
                    quantity=valid_fields["quantity"],
                    unit=valid_fields["unit"],
                    tier="AUTHORITATIVE",
                    all_sources=[src_primary],
                    all_descriptions=[valid_fields["description"]] if valid_fields["description"] else []
                )
                items.append(audit_item)

        return BoundedExtractionResult(
            items=items,
            validation_failures=validation_failures,
            raw_source=raw_text
        )
