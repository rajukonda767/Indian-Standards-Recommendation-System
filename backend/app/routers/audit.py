"""
audit.py
========
FastAPI Router for the Tender Compliance Audit Engine (/api/audit).
Supports both raw text/BOQ input and multipart PDF uploads.
"""

import logging
from fastapi import APIRouter, HTTPException, UploadFile, File
from app.models.audit import TextAuditRequest, AuditReport
from app.services.pdf_service import extract_text_from_pdf
from app.services.audit_engine import extract_line_items_groq, audit_tender_items

router = APIRouter(prefix="/audit", tags=["Tender Compliance Audit"])
logger = logging.getLogger(__name__)

@router.post("/text", response_model=AuditReport)
async def audit_tender_text(request: TextAuditRequest):
    """
    Audits pasted tender document specifications or Bill of Quantities (BOQ).
    Extracts itemized specifications using Groq and evaluates statutory compliance.
    """
    text = request.tender_text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Tender text cannot be empty.")

    logger.info(f"Auditing tender text ({len(text)} characters)...")
    items = extract_line_items_groq(text)
    if not items:
        raise HTTPException(status_code=422, detail="No discrete technical line items could be extracted from text.")

    report = audit_tender_items(items)
    return report


@router.post("/pdf", response_model=AuditReport)
async def audit_tender_pdf(file: UploadFile = File(...)):
    """
    Upload a tender PDF specification document.
    Extracts text via PyMuPDF, parses line items via Groq, and generates full statutory audit report.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Uploaded file must be a valid PDF document.")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded PDF file is empty.")

    logger.info(f"Processing uploaded PDF: {file.filename} ({len(content)} bytes)...")
    text = extract_text_from_pdf(content)

    if not text.strip():
        raise HTTPException(status_code=422, detail="Could not extract readable text from PDF. It may be scanned or empty.")

    items = extract_line_items_groq(text)
    if not items:
        raise HTTPException(status_code=422, detail="No technical procurement items found in PDF content.")

    report = audit_tender_items(items)
    return report
