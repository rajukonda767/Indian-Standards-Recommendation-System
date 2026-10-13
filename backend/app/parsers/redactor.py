# -*- coding: utf-8 -*-
"""
backend/app/parsers/redactor.py
===============================
Deterministic PII and Contact Information Redactor for Tender Documents.
Removes emails, phone numbers, and contact strings before text is sent to any LLM.
Maintains bidirectional character offset mapping between original and redacted text.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import List, Tuple, Optional


@dataclass
class RedactedSpan:
    orig_start: int
    orig_end: int
    redacted_start: int
    redacted_end: int
    entity_type: str
    original_text: str
    replacement: str


@dataclass
class RedactionResult:
    original_text: str
    redacted_text: str
    spans: List[RedactedSpan] = field(default_factory=list)

    def to_original_offset(self, redacted_idx: int) -> int:
        """Map character offset in redacted_text back to original_text."""
        if not self.spans:
            return redacted_idx
        shift = 0
        for span in self.spans:
            if redacted_idx < span.redacted_start:
                return redacted_idx + shift
            elif span.redacted_start <= redacted_idx < span.redacted_end:
                # Inside the replacement token -> map to start of original span
                return span.orig_start
            else:
                # After the replacement token
                shift = span.orig_end - span.redacted_end
        return redacted_idx + shift

    def to_redacted_offset(self, orig_idx: int) -> int:
        """Map character offset in original_text to redacted_text."""
        if not self.spans:
            return orig_idx
        shift = 0
        for span in self.spans:
            if orig_idx < span.orig_start:
                return orig_idx - shift
            elif span.orig_start <= orig_idx < span.orig_end:
                return span.redacted_start
            else:
                shift = (span.orig_end - span.orig_start) - len(span.replacement)
        return orig_idx - shift


class Redactor:
    """Removes emails and phone numbers while keeping character offsets mappable."""

    # RFC 5322 compatible email pattern
    EMAIL_PATTERN = re.compile(
        r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b'
    )

    # Indian mobile and STD landline telephone patterns (supports +91, spaces, hyphens)
    PHONE_PATTERN = re.compile(
        r'(?<![A-Za-z0-9])'  # not preceded by alphanumeric (avoid part/material codes)
        r'(?:'
        r'(?:\+91[\s\-]?)?[6-9]\d{4}[\s\-]?\d{5}'         # e.g. +91 98765 43210 or 98765 43210
        r'|'
        r'(?:\+91[\s\-]?)?[6-9]\d{9}'                     # e.g. +91 9876543210 or 9876543210
        r'|'
        r'0\d{2,4}[\s\-]?\d{3,4}[\s\-]?\d{4}'             # e.g. 040-2345 6789 or 011-23456789
        r'|'
        r'(?:Tel|Phone|Mobile|Fax|Cell|Contact)[\s.:\-]+(?:\+91[\s\-]?)?\d{8,12}'
        r')'
        r'(?![A-Za-z0-9])'  # not followed by alphanumeric
    )

    # Prefix indicating a material/part/SAP code, not a personal phone number
    MATERIAL_CODE_PREFIX_RE = re.compile(
        r'(?:Material\s*Code|Mat\s*Code|Item\s*Code|Part\s*(?:No|Code|#)|Code|SAP\s*Code|Ref\s*(?:No)?|Sl\.?\s*No|BOQ\s*Item|Item\s*\d+|Item|\[L\d+\]|\b\d+\s*\||\|)\s*[:#\-\s|]*$',
        re.IGNORECASE
    )

    @classmethod
    def redact(
        cls,
        text: str,
        is_material_code: bool = False,
        field_type: Optional[str] = None
    ) -> RedactionResult:
        if not text:
            return RedactionResult(original_text="", redacted_text="", spans=[])

        # If explicitly marked as material code or field_type is material_code, never redact as phone
        is_code_field = is_material_code or field_type in ("material_code", "item_code", "part_no", "code")

        raw_matches: List[Tuple[int, int, str, str]] = []

        # Find emails
        for m in cls.EMAIL_PATTERN.finditer(text):
            raw_matches.append((m.start(), m.end(), "EMAIL", m.group(0)))

        # Find phone numbers (skip if this is a material code field)
        if not is_code_field:
            for m in cls.PHONE_PATTERN.finditer(text):
                prefix_text = text[:m.start()]
                suffix_text = text[m.end():]
                clean_suffix = suffix_text.lstrip()
                # Check if preceded or followed by material code markers or tabular pipe separators
                if (
                    cls.MATERIAL_CODE_PREFIX_RE.search(prefix_text)
                    or clean_suffix.startswith((':', '-', '|', 'cble', 'cable', 'kv', 'mtr', 'nos'))
                    or ('|' in prefix_text and '|' in suffix_text)
                ):
                    continue  # Protected material code
                raw_matches.append((m.start(), m.end(), "PHONE", m.group(0)))

        # Sort by start offset
        raw_matches.sort(key=lambda x: x[0])

        # Deduplicate overlapping spans
        deduped: List[Tuple[int, int, str, str]] = []
        last_end = -1
        for start, end, etype, matched in raw_matches:
            if start >= last_end:
                deduped.append((start, end, etype, matched))
                last_end = end

        # Construct redacted string and span tracking
        output_parts: List[str] = []
        spans: List[RedactedSpan] = []
        cur_orig_pos = 0
        cur_red_pos = 0

        for start, end, etype, orig_match in deduped:
            # Unchanged text before match
            prefix = text[cur_orig_pos:start]
            output_parts.append(prefix)
            cur_red_pos += len(prefix)

            # Replacement token
            token = f"[{etype}_REDACTED]"
            output_parts.append(token)
            red_start = cur_red_pos
            red_end = cur_red_pos + len(token)
            cur_red_pos = red_end

            spans.append(RedactedSpan(
                orig_start=start,
                orig_end=end,
                redacted_start=red_start,
                redacted_end=red_end,
                entity_type=etype,
                original_text=orig_match,
                replacement=token
            ))
            cur_orig_pos = end

        # Trailing text
        tail = text[cur_orig_pos:]
        output_parts.append(tail)

        return RedactionResult(
            original_text=text,
            redacted_text="".join(output_parts),
            spans=spans
        )
