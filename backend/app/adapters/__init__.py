# -*- coding: utf-8 -*-
"""
backend/app/adapters/__init__.py
================================
Adapter registry and loader for tender audit parsing.
Supports GeM PDF, Generic PDF, Microsoft Word (.docx), and Microsoft Excel (.xlsx).
"""
from typing import List
from app.adapters.base import BaseAdapter, PageBlock
from app.adapters.generic_pdf import GenericPdfAdapter
from app.adapters.gem_adapter import GeMAdapter
from app.adapters.docx_adapter import DocxAdapter
from app.adapters.xlsx_adapter import XlsxAdapter

_ADAPTERS: List[BaseAdapter] = [
    GeMAdapter(),
    DocxAdapter(),
    XlsxAdapter(),
    GenericPdfAdapter(),
]

def get_adapter_for_file(file_path: str) -> BaseAdapter:
    """Select the first adapter capable of handling the file format/layout."""
    for adapter in _ADAPTERS:
        if adapter.can_handle(file_path):
            return adapter
    raise ValueError(f"No suitable document adapter found for {file_path}")

__all__ = [
    "BaseAdapter",
    "PageBlock",
    "GenericPdfAdapter",
    "GeMAdapter",
    "DocxAdapter",
    "XlsxAdapter",
    "get_adapter_for_file",
]
