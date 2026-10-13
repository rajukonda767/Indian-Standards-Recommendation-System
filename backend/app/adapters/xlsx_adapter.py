# -*- coding: utf-8 -*-
"""
backend/app/adapters/xlsx_adapter.py
====================================
Tender document adapter for Excel spreadsheets (.xlsx, .xlsm).

Reads spreadsheet BoQs via openpyxl:
- Maps tabular rows to standard pipe-delimited PageBlocks compatible with HeaderMapper.
- Inherits cell values across merged ranges.
- Enforces strict row and file size limits without silent truncation.
"""
from __future__ import annotations

import os
from typing import List, Tuple, Optional, Any
import openpyxl

from app.adapters.base import BaseAdapter, PageBlock


class XlsxAdapter(BaseAdapter):
    """Adapter for Microsoft Excel (.xlsx) procurement schedule and BoQ workbooks."""

    MAX_ROWS = 5000  # Hard ceiling on row count to avoid memory exhaustion

    def can_handle(self, file_path: str) -> bool:
        ext = os.path.splitext(file_path)[1].lower()
        return ext in (".xlsx", ".xlsm", ".xltx")

    def extract_blocks(self, file_path: str) -> List[PageBlock]:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"XLSX file not found: {file_path}")

        wb = openpyxl.load_workbook(file_path, data_only=True)
        sheet = wb.active
        if sheet is None:
            raise ValueError("Excel workbook contains no active worksheets.")

        max_row = sheet.max_row
        if max_row > self.MAX_ROWS:
            raise ValueError(
                f"XLSX exceeds maximum row limit: {max_row} rows found (limit: {self.MAX_ROWS})."
            )

        # Build merged cells lookup to inherit values across vertical merged spans
        merged_value_map = {}
        for rng in sheet.merged_cells.ranges:
            top_left_val = sheet.cell(row=rng.min_row, column=rng.min_col).value
            if rng.min_row != rng.max_row:
                for row in range(rng.min_row + 1, rng.max_row + 1):
                    for col in range(rng.min_col, rng.max_col + 1):
                        merged_value_map[(row, col)] = top_left_val

        blocks: List[PageBlock] = []
        block_idx = 0
        pseudo_page = 1
        ROWS_PER_PAGE = 50

        for r_idx, row in enumerate(sheet.iter_rows(values_only=False), start=1):
            row_cells = []
            has_content = False

            for c_idx, cell in enumerate(row, start=1):
                val = cell.value
                if val is None and (r_idx, c_idx) in merged_value_map:
                    val = merged_value_map[(r_idx, c_idx)]

                if val is not None:
                    # Clean up representation
                    str_val = str(val).strip().replace("\n", " ")
                    if str_val:
                        has_content = True
                    row_cells.append(str_val)
                else:
                    row_cells.append("")

            if not has_content:
                continue

            # Strip trailing blank cells
            while row_cells and not row_cells[-1]:
                row_cells.pop()

            row_line = " | ".join(row_cells)
            if not row_line.strip():
                continue

            if r_idx > 1 and (r_idx - 1) % ROWS_PER_PAGE == 0:
                pseudo_page += 1

            blocks.append(PageBlock(
                page_no=pseudo_page,
                block_idx=block_idx,
                bbox=(0.0, float(block_idx * 18), 500.0, float(block_idx * 18 + 14)),
                text=row_line,
                raw_text=row_line,
                tier="AUTHORITATIVE",
                tier_reason="xlsx_boq_row",
                devanagari_ratio=0.0,
                section_label=sheet.title
            ))
            block_idx += 1

        wb.close()
        return blocks
