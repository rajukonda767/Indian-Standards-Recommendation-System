# -*- coding: utf-8 -*-
"""
backend/app/adapters/base.py
============================
Core data structures and interfaces for tender document adapters.
"""
from dataclasses import dataclass, field
from typing import Optional, List, Tuple
from abc import ABC, abstractmethod


@dataclass
class PageBlock:
    """Represents a discrete text block extracted from a tender document."""
    page_no: int               # 1-indexed page number
    block_idx: int             # block index on page
    bbox: Tuple[float, float, float, float]  # (x0, y0, x1, y1)
    text: str                  # normalized English text (Devanagari stripped or preserved)
    raw_text: str              # verbatim extracted text from document layer
    tier: str                  # 'AUTHORITATIVE' | 'CORROBORATING' | 'CONTEXT_ONLY'
    tier_reason: str           # explanation of tier assignment
    devanagari_ratio: float    # proportion of Devanagari characters
    section_label: Optional[str] = None  # parent section heading/label if any


class BaseAdapter(ABC):
    """Abstract base class for document adapters."""

    @abstractmethod
    def can_handle(self, file_path: str) -> bool:
        """Return True if this adapter can process the given document."""
        pass

    @abstractmethod
    def extract_blocks(self, file_path: str) -> List[PageBlock]:
        """Parse document and return classified PageBlocks with tier assignments."""
        pass
