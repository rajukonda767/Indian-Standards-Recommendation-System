"""
app/routers/audit_v2.py
=======================
Tender Compliance Audit v2 API Endpoints:
1. POST /api/audit/jobs: create job (files/text/items) -> background execution
2. POST /api/audit/upload: upload tender files with size & page/row limits -> launch job
3. GET  /api/audit/jobs/{job_id}: poll job (progress, progressive items completed so far)
4. GET  /api/audit/jobs/{job_id}/results: fetch complete audit report & scorecard
5. POST /api/audit/jobs/{job_id}/items/{item_id}/rerun: re-run a single line item
6. GET  /api/audit/jobs: list past audits with pagination
"""
import os
import shutil
import tempfile
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form

from app.jobs.job_store import get_job, get_job_items, list_jobs
from app.jobs.runner import launch_audit_job, rerun_single_item
from app.adapters import get_adapter_for_file

router = APIRouter(prefix="/audit", tags=["Tender Audit v2"])

# Explicit limit constants: strictly enforced without silent truncation
MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB max file size
MAX_PAGES_PER_DOC = 100                  # 100 pages max for PDF/DOCX
MAX_ROWS_PER_SPREADSHEET = 5000          # 5,000 rows max for XLSX

UPLOAD_DIR = os.path.join(tempfile.gettempdir(), "standard_audit_uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


class CreateJobRequest(BaseModel):
    file_paths: Optional[List[str]] = Field(None, description="Paths to tender PDF/DOCX/XLSX files on server")
    raw_items: Optional[List[Dict[str, Any]]] = Field(None, description="Pre-parsed or synthetic line items")
    doc_type: Optional[str] = Field("gem", description="Document type: gem | generic")


def validate_file_limits(file_path: str) -> None:
    """Validates file size and document structure against limits. Never truncates silently."""
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

    file_size = os.path.getsize(file_path)
    if file_size > MAX_FILE_SIZE_BYTES:
        size_mb = file_size / (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f"File '{os.path.basename(file_path)}' ({size_mb:.2f}MB) exceeds the maximum upload size limit of 25MB."
        )

    ext = os.path.splitext(file_path)[1].lower()
    if ext in (".xlsx", ".xlsm"):
        import openpyxl
        try:
            wb = openpyxl.load_workbook(file_path, read_only=True)
            sheet = wb.active
            if sheet and sheet.max_row and sheet.max_row > MAX_ROWS_PER_SPREADSHEET:
                row_count = sheet.max_row
                wb.close()
                raise HTTPException(
                    status_code=400,
                    detail=f"Spreadsheet '{os.path.basename(file_path)}' ({row_count} rows) exceeds the maximum limit of {MAX_ROWS_PER_SPREADSHEET} rows."
                )
            wb.close()
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to inspect spreadsheet: {e}")

    elif ext == ".pdf":
        import fitz
        try:
            doc = fitz.open(file_path)
            if doc.page_count > MAX_PAGES_PER_DOC:
                pg_cnt = doc.page_count
                doc.close()
                raise HTTPException(
                    status_code=400,
                    detail=f"PDF document '{os.path.basename(file_path)}' ({pg_cnt} pages) exceeds the maximum limit of {MAX_PAGES_PER_DOC} pages."
                )
            doc.close()
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to inspect PDF document: {e}")


@router.post("/jobs", status_code=201)
async def create_audit_job_endpoint(payload: CreateJobRequest):
    """
    Creates an asynchronous audit job and immediately returns job details with status='pending'.
    Processing proceeds in background worker thread with progressive persistence.
    """
    if not payload.file_paths and not payload.raw_items:
        raise HTTPException(
            status_code=400,
            detail="Either 'file_paths' or 'raw_items' must be provided to create an audit job."
        )

    if payload.file_paths:
        for fp in payload.file_paths:
            validate_file_limits(fp)

    job_id = launch_audit_job(
        file_paths=payload.file_paths,
        raw_items=payload.raw_items,
        doc_type=payload.doc_type
    )

    job = get_job(job_id)
    return job


@router.post("/upload", status_code=201)
async def upload_and_audit_files(
    files: List[UploadFile] = File(..., description="Tender files (PDF, DOCX, XLSX)"),
    doc_type: str = Form("gem", description="Document type: gem | generic")
):
    """
    Uploads tender files directly with strict size and page/row enforcement,
    saving them to staging and triggering an asynchronous audit job.
    """
    saved_paths = []
    try:
        for upload in files:
            # Check filename extension
            ext = os.path.splitext(upload.filename)[1].lower()
            if ext not in (".pdf", ".docx", ".xlsx", ".xlsm"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file format '{ext}' for file '{upload.filename}'. Allowed: .pdf, .docx, .xlsx."
                )

            target_path = os.path.join(UPLOAD_DIR, upload.filename)
            total_bytes = 0
            with open(target_path, "wb") as buffer:
                while True:
                    chunk = await upload.read(1024 * 1024)  # 1MB chunks
                    if not chunk:
                        break
                    total_bytes += len(chunk)
                    if total_bytes > MAX_FILE_SIZE_BYTES:
                        buffer.close()
                        os.remove(target_path)
                        raise HTTPException(
                            status_code=413,
                            detail=f"File '{upload.filename}' exceeds maximum upload size limit of 25MB."
                        )
                    buffer.write(chunk)

            validate_file_limits(target_path)
            saved_paths.append(target_path)

        job_id = launch_audit_job(file_paths=saved_paths, doc_type=doc_type)
        return get_job(job_id)

    except HTTPException:
        # Clean up files on error
        for p in saved_paths:
            if os.path.exists(p):
                try: os.remove(p)
                except Exception: pass
        raise
    except Exception as e:
        for p in saved_paths:
            if os.path.exists(p):
                try: os.remove(p)
                except Exception: pass
        raise HTTPException(status_code=500, detail=f"File upload error: {e}")


@router.get("/jobs")
async def list_audit_jobs(
    limit: int = Query(20, ge=1, le=100, description="Max jobs to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
):
    """
    List past audit jobs, newest first.
    Returns job summaries without full per-item findings.
    """
    return list_jobs(limit=limit, offset=offset)


@router.get("/jobs/{job_id}")
async def get_audit_job_poll(job_id: str):
    """
    Poll endpoint returning job progress.
    While status='running', 'items' list contains progressive items completed so far.
    """
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Audit job '{job_id}' not found.")
    job["items"] = get_job_items(job_id)
    return job


@router.get("/jobs/{job_id}/results")
async def get_audit_job_results(job_id: str):
    """
    Fetch final audit result and scorecard for a completed or in-progress job.
    """
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Audit job '{job_id}' not found.")

    items = get_job_items(job_id)

    scorecard = {
        "coverage": {
            "score": job.get("coverage"),
            "denominator": job.get("coverage_denominator"),
            "display": f"{job.get('coverage', 0.0):.1f}%" if job.get("coverage") is not None else "N/A"
        },
        "currency": {
            "score": job.get("currency"),
            "denominator": job.get("currency_denominator"),
            "display": f"{job.get('currency', 0.0):.1f}%" if job.get("currency") is not None else "N/A"
        },
        "qco_compliance": {
            "score": job.get("qco_compliance"),
            "denominator": job.get("qco_denominator"),
            "display": f"{job.get('qco_compliance', 0.0):.1f}%" if job.get("qco_compliance") is not None else "N/A"
        }
    }

    return {
        "job_id": job["id"],
        "status": job["status"],
        "total_items": job.get("total_items", 0),
        "done_items": job.get("done_items", 0),
        "scorecard": scorecard,
        "status_counts": job.get("status_counts", {}),
        "summary": job.get("summary", ""),
        "items": items,
        "created_at": job.get("created_at"),
        "updated_at": job.get("updated_at")
    }


@router.post("/jobs/{job_id}/items/{seq_no}/rerun")
async def rerun_item_endpoint(job_id: str, seq_no: int):
    """
    Re-runs audit for a single line item within an existing job.
    Updates the item and refreshes job-level scorecards.
    """
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Audit job '{job_id}' not found.")

    updated_item = rerun_single_item(job_id, seq_no)
    if not updated_item:
        raise HTTPException(status_code=404, detail=f"Item with seq_no '{seq_no}' not found in job '{job_id}'.")

    refreshed_job = get_job(job_id)
    return {
        "message": f"Item {seq_no} re-audited successfully.",
        "item": updated_item,
        "job_status": refreshed_job
    }
