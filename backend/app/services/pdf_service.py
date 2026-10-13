"""
pdf_service.py
==============
Tender PDF text extraction using PyMuPDF (fitz) with header/footer cleanup.
"""

import io
import re
import logging
import pymupdf as fitz

logger = logging.getLogger(__name__)

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    Extracts structured text from PDF file bytes.
    Cleans up redundant whitespace and header/footer noise.
    """
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        pages_text = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text")

            # Basic clean-up of page numbering / repetitive footer lines
            cleaned_lines = []
            for line in text.split("\n"):
                line_str = line.strip()
                # Skip standalone page numbers e.g. "Page 1 of 5", "- 2 -"
                if re.match(r"^(page\s+\d+(\s+of\s+\d+)?|\d+|\-\s*\d+\s*\-)$", line_str, re.IGNORECASE):
                    continue
                if line_str:
                    cleaned_lines.append(line_str)

            pages_text.append("\n".join(cleaned_lines))

        doc.close()
        full_text = "\n\n".join(pages_text)
        logger.info(f"Extracted {len(full_text)} characters across {len(pages_text)} pages.")
        return full_text
    except Exception as e:
        logger.error(f"PDF extraction error: {e}")
        raise ValueError(f"Failed to extract text from PDF: {str(e)}")
