# -*- coding: utf-8 -*-
"""
backend/app/parsers/verbatim_verifier.py
========================================
Deterministic Verbatim-Quote Verifier for Tender Standards Auditing.

Guarantees provenance integrity:
1. Extracts the exact substring around each mention as its verbatim "quote".
2. Normalizes whitespace and Unicode (NFKC) without semantic alterations.
3. Confirms that the quote exists verbatim in the source PageBlock text.
4. Any mention whose quote cannot be verified is DROPPED and logged with an
   explicit diagnostic reason, never silently kept.
5. Zero LLM involvement — purely deterministic, audit-traceable code.
"""
from __future__ import annotations
import re
import unicodedata
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, Any

from app.parsers.mention_extractor import Mention

logger = logging.getLogger("verbatim_verifier")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter("[%(levelname)s] [VerbatimVerifier] %(message)s")
    ch.setFormatter(formatter)
    logger.addHandler(ch)


@dataclass
class VerifiedQuote:
    """Verbatim quote record with byte/char offsets in source PageBlock."""
    raw_mention_text: str
    quote_text: str
    start_offset: int
    end_offset: int
    doc_name: str
    page_no: int
    block_idx: int
    verified: bool = True
    failure_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_mention_text": self.raw_mention_text,
            "quote_text": self.quote_text,
            "start_offset": self.start_offset,
            "end_offset": self.end_offset,
            "doc_name": self.doc_name,
            "page_no": self.page_no,
            "block_idx": self.block_idx,
            "verified": self.verified,
            "failure_reason": self.failure_reason
        }


class VerbatimQuoteVerifier:
    """
    Pure-code deterministic verifier for standard mentions and surrounding quotes.
    """

    @staticmethod
    def normalize(text: str) -> str:
        """Applies Unicode NFKC normalization and collapses excessive whitespace."""
        if not text:
            return ""
        norm = unicodedata.normalize("NFKC", text)
        return re.sub(r'[\r\n\t]+', ' ', norm).strip()

    @classmethod
    def extract_and_verify_quote(
        cls,
        mention: Mention,
        source_block_text: str,
        doc_name: str = "doc",
        page_no: int = 1,
        block_idx: int = 0,
        quote_padding: int = 35,
        corrupted_override_quote: Optional[str] = None
    ) -> Tuple[Optional[VerifiedQuote], Optional[str]]:
        """
        Extracts the surrounding quote around mention and verifies it exists verbatim
        in source_block_text.
        
        Returns:
            (VerifiedQuote, None) if verified successfully.
            (None, failure_reason) if verification fails (mention dropped).
        """
        if not source_block_text:
            reason = "EMPTY_SOURCE_BLOCK_TEXT"
            logger.warning(
                f"[DROPPED_UNVERIFIED_QUOTE] Mention '{mention.raw_text}' dropped: {reason} "
                f"(doc={doc_name} p{page_no} b{block_idx})."
            )
            return None, reason

        norm_source = cls.normalize(source_block_text)
        norm_mention = cls.normalize(mention.raw_text)

        # Deliberate corruption testing hook
        if corrupted_override_quote is not None:
            candidate_quote = corrupted_override_quote
            start_pos = -1
            end_pos = -1
        else:
            # Locate mention within normalized source
            # First try exact span if available
            # First try exact start and end if available
            start_pos = -1
            if hasattr(mention, 'start') and hasattr(mention, 'end') and mention.start is not None and mention.end is not None:
                s, e = mention.start, mention.end
                if s < len(source_block_text) and e <= len(source_block_text):
                    candidate_slice = source_block_text[s:e]
                    if cls.normalize(candidate_slice) == norm_mention:
                        start_pos = s
                        end_pos = e

            # Fallback: substring search in source text
            if start_pos == -1:
                # Case-insensitive or normalized search
                match = re.search(re.escape(norm_mention), norm_source, re.IGNORECASE)
                if match:
                    start_pos = match.start()
                    end_pos = match.end()

            if start_pos == -1:
                reason = f"MENTION_TEXT_NOT_FOUND_IN_SOURCE: '{norm_mention}' not in source block"
                logger.warning(
                    f"[DROPPED_UNVERIFIED_QUOTE] Mention '{mention.raw_text}' dropped: {reason} "
                    f"(doc={doc_name} p{page_no} b{block_idx})."
                )
                return None, reason

            # Extract surrounding quote window
            # When source block is a single specification clause or table cell (<= 2000 chars),
            # preserve the FULL verbatim text so technical specification clauses are never chopped or truncated!
            if len(norm_source) <= 2000:
                q_start = 0
                q_end = len(norm_source)
                candidate_quote = norm_source
            else:
                q_start = max(0, start_pos - 250)
                q_end = min(len(norm_source), end_pos + 250)
                candidate_quote = norm_source[q_start:q_end]

        # ── VERBATIM CONFIRMATION IN SOURCE ──
        norm_candidate = cls.normalize(candidate_quote)
        if norm_candidate not in norm_source:
            reason = f"QUOTE_NOT_SUBSTRING_OF_SOURCE: '{norm_candidate[:40]}...' not found in source block"
            logger.warning(
                f"[DROPPED_UNVERIFIED_QUOTE] Mention '{mention.raw_text}' dropped: {reason} "
                f"(doc={doc_name} p{page_no} b{block_idx})."
            )
            return None, reason

        # Confirm the mention text itself is present inside the extracted quote
        if norm_mention.lower() not in norm_candidate.lower():
            reason = f"MENTION_NOT_IN_EXTRACTED_QUOTE: '{norm_mention}' not in '{norm_candidate}'"
            logger.warning(
                f"[DROPPED_UNVERIFIED_QUOTE] Mention '{mention.raw_text}' dropped: {reason} "
                f"(doc={doc_name} p{page_no} b{block_idx})."
            )
            return None, reason

        verified_record = VerifiedQuote(
            raw_mention_text=mention.raw_text,
            quote_text=candidate_quote,
            start_offset=start_pos,
            end_offset=end_pos,
            doc_name=doc_name,
            page_no=page_no,
            block_idx=block_idx,
            verified=True,
            failure_reason=None
        )
        return verified_record, None
