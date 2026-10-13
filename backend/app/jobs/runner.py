# -*- coding: utf-8 -*-
"""
backend/app/jobs/runner.py
==========================
Production-Grade Background Audit Job Runner.

Manages the complete lifecycle of tender compliance audits:
1. Job Creation: Inserts 'pending' audit job into Supabase `audit_jobs`.
2. Asynchronous Execution: Dispatches background execution without blocking API threads.
3. Progressive Item Updates: As each line item is extracted, resolved, and assembled,
   it is immediately persisted to `audit_items` and `done_items` is incremented.
4. Scorecard Synthesis: On completion, computes Coverage, Currency, and QCO Compliance
   denominators and updates `audit_jobs` status to 'done'.
5. Single Item Rerun: Supports isolated re-auditing of an individual item and scorecard update.
"""
from __future__ import annotations

import time
import uuid
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
from typing import List, Dict, Any, Optional

from app.jobs.job_store import (
    create_job,
    get_job,
    update_job,
    increment_done,
    upsert_item,
    get_job_items,
    ensure_audit_tables_schema,
)
from app.adapters import get_adapter_for_file
from app.parsers.mention_extractor import extract_mentions, load_db_sets
from app.parsers.item_builder import ItemBuilder, AuditItem, ItemField, SourceRef
from app.parsers.verbatim_verifier import VerbatimQuoteVerifier
from app.parsers.standard_resolver import StandardResolver, ResolvedStandard
from app.parsers.finding_assembler import FindingAssembler, AuditedItem, FindingCode, ItemFinding
from app.parsers.scorer import calculate_audit_scores, AuditScoreCard

logger = logging.getLogger("audit_runner")
logger.setLevel(logging.INFO)

# Global thread pool for CPU/IO background audit runs
_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="audit_worker")

STATUS_BADGE_MAP = {
    "compliant": "green",
    "incomplete": "yellow",
    "outdated": "orange",
    "superseded": "red",
    "conflict": "red",
    "missing": "gray",
    "cannot_verify": "purple",
}


def _get_badge_color(status: str) -> str:
    return STATUS_BADGE_MAP.get(status.lower(), "gray")


def run_audit_sync(
    job_id: str,
    file_paths: Optional[List[str]] = None,
    raw_items: Optional[List[Dict[str, Any]]] = None,
    doc_type: Optional[str] = "gem"
) -> Dict[str, Any]:
    """
    Synchronous worker executing the audit pipeline step-by-step with progressive persistence.
    """
    logger.info(f"Starting audit job {job_id}...")
    ensure_audit_tables_schema()
    load_db_sets()
    update_job(job_id, status="running")

    try:
        items_to_audit: List[AuditItem] = []


        # ── 1. Document Extraction & Item Building ──
        if file_paths:
            if len(file_paths) == 1:
                fp = file_paths[0]
                table_items: List[AuditItem] = []
                if fp.lower().endswith('.pdf'):
                    try:
                        import pymupdf
                        p_doc = pymupdf.open(fp)
                        for pno in range(len(p_doc)):
                            p_tab_finder = p_doc[pno].find_tables()
                            for p_tab in p_tab_finder.tables:
                                p_rows = p_tab.extract()
                                t_items, _ = ItemBuilder.build_items_from_table_rows(p_rows, doc_name=f"Doc{pno+1}")
                                table_items.extend(t_items)
                    except Exception as e:
                        logger.warning(f"Table extraction failed, falling back to blocks: {e}")

                if table_items:
                    items_to_audit = table_items
                else:
                    adapter = get_adapter_for_file(fp)
                    blocks = adapter.extract_blocks(fp)
                    ext_res = ItemBuilder.build_items_from_blocks(blocks, doc_name="Doc1")
                    items_to_audit = ext_res.items
            else:
                # Multi-document join (e.g. Schedule + Technical Spec)
                item_sets = []
                for idx, fp in enumerate(file_paths, 1):
                    t_items_multi: List[AuditItem] = []
                    if fp.lower().endswith('.pdf'):
                        try:
                            import pymupdf
                            p_doc = pymupdf.open(fp)
                            for pno in range(len(p_doc)):
                                p_tab_finder = p_doc[pno].find_tables()
                                for p_tab in p_tab_finder.tables:
                                    p_rows = p_tab.extract()
                                    t_items_page, _ = ItemBuilder.build_items_from_table_rows(p_rows, doc_name=f"PDF-{idx}")
                                    t_items_multi.extend(t_items_page)
                        except Exception as e:
                            logger.warning(f"Table extraction failed for {fp}: {e}")

                    if t_items_multi:
                        item_sets.append(t_items_multi)
                    else:
                        adapter = get_adapter_for_file(fp)
                        blocks = adapter.extract_blocks(fp)
                        ext_res = ItemBuilder.build_items_from_blocks(blocks, doc_name=f"PDF-{idx}")
                        item_sets.append(ext_res.items)
                items_to_audit = ItemBuilder.join_item_sets(item_sets)
        elif raw_items:
            # Direct synthetic or pre-parsed items
            for idx, ri in enumerate(raw_items, 1):
                item_id = str(ri.get("item_id", idx))
                seq_no = ri.get("seq_no", idx)
                desc = ri.get("description", "")
                spec = ri.get("technical_spec", "")
                qty = str(ri.get("quantity", ""))
                unit = str(ri.get("unit", ""))
                mat_code = ri.get("material_code")

                it = AuditItem(
                    item_id=item_id,
                    seq_no=seq_no,
                    description=ItemField(value=desc, source=SourceRef(doc_name="Input", page_no=1, block_idx=0, tier="AUTHORITATIVE")),
                    technical_spec=ItemField(value=spec, source=SourceRef(doc_name="Input", page_no=1, block_idx=0, tier="AUTHORITATIVE")),
                    quantity=ItemField(value=qty, source=SourceRef(doc_name="Input", page_no=1, block_idx=0, tier="AUTHORITATIVE")) if qty else None,
                    unit=ItemField(value=unit, source=SourceRef(doc_name="Input", page_no=1, block_idx=0, tier="AUTHORITATIVE")) if unit else None,
                    material_code=ItemField(value=mat_code, source=SourceRef(doc_name="Input", page_no=1, block_idx=0, tier="AUTHORITATIVE")) if mat_code else None,
                )
                items_to_audit.append(it)
        else:
            raise ValueError("No files or items provided for audit.")

        total_items = len(items_to_audit)
        update_job(job_id, total_items=total_items, done_items=0)
        logger.info(f"Job {job_id}: Processing {total_items} line items...")

        resolver = StandardResolver()
        audited_item_objs: List[AuditedItem] = []

        # ── 2. Progressive Item Audit Loop (Parallel Worker Pool) ──
        def _process_item(item: AuditItem) -> AuditedItem:
            t_item_start = time.perf_counter()
            try:
                spec_val = item.technical_spec.value if item.technical_spec else ""
                desc_val = item.description.value if item.description else ""
                item_combined_txt = f"{desc_val} {spec_val}".strip()

                # Extract standard mentions
                mentions = extract_mentions(spec_val, source_block_tier="AUTHORITATIVE")
                if not mentions and desc_val:
                    # Secondary lookup in description
                    mentions = extract_mentions(desc_val, source_block_tier="AUTHORITATIVE")

                resolved_stds: List[ResolvedStandard] = []
                for m in mentions:
                    v_quote, _ = VerbatimQuoteVerifier.extract_and_verify_quote(
                        mention=m,
                        source_block_text=spec_val or desc_val,
                        doc_name=item.technical_spec.source.doc_name if item.technical_spec else "TenderDoc",
                        page_no=item.technical_spec.source.page_no if item.technical_spec else 1,
                        block_idx=item.technical_spec.source.block_idx if item.technical_spec else 0,
                    )
                    resolved = resolver.resolve_mention(
                        mention=m,
                        item_context=item_combined_txt,
                        verified_quote=v_quote
                    )
                    resolved_stds.append(resolved)

                # Assemble findings for item
                audited = FindingAssembler.assemble_item(
                    item=item,
                    resolved_standards=resolved_stds,
                    doc_name=item.technical_spec.source.doc_name if item.technical_spec else "TenderDoc",
                    page_no=item.technical_spec.source.page_no if item.technical_spec else 1
                )

                proc_ms = round((time.perf_counter() - t_item_start) * 1000.0, 2)

                # Build recommendations
                rec_stds = []
                for rs in resolved_stds:
                    if rs.successor_standard_number:
                        rec_stds.append({
                            "cited": rs.raw_citation,
                            "recommended": rs.successor_standard_number,
                            "year": rs.successor_year,
                            "reason": f"Supersedes cited edition ({rs.cited_year})"
                        })
                    elif rs.status == "outdated":
                        rec_stds.append({
                            "cited": rs.raw_citation,
                            "recommended": rs.resolved_standard_number,
                            "year": rs.resolved_year,
                            "reason": f"Latest active published edition ({rs.resolved_year})"
                        })

                badge_color = _get_badge_color(audited.status)

                # Format for database persistence
                db_item_dict = {
                    "seq_no": audited.seq_no,
                    "item_id": audited.item_id,
                    "description": audited.description,
                    "technical_spec": audited.technical_spec,
                    "material_code": audited.material_code,
                    "quantity": item.quantity.value if item.quantity else None,
                    "unit": item.unit.value if item.unit else None,
                    "status": audited.status,
                    "badge_color": badge_color,
                    "findings": [f.to_dict() for f in audited.findings],
                    "cited_standards": [s.to_dict() for s in audited.resolved_standards],
                    "recommended_standards": rec_stds,
                    "source_tier": "AUTHORITATIVE",
                    "page_refs": [item.technical_spec.source.page_no] if item.technical_spec else [1],
                    "processing_ms": proc_ms,
                }

                # Progressive persistence
                upsert_item(job_id, db_item_dict)
                increment_done(job_id)
                return audited

            except Exception as exc:
                proc_ms = round((time.perf_counter() - t_item_start) * 1000.0, 2)
                logger.exception(f"Job {job_id}: Item {item.item_id} (seq {item.seq_no}) encountered exception: {exc}")
                err_finding = ItemFinding(
                    code=FindingCode.CANNOT_VERIFY,
                    severity="error",
                    message=f"Item audit error: {type(exc).__name__}: {str(exc)}",
                    evidence={
                        "doc_name": item.technical_spec.source.doc_name if item.technical_spec else "TenderDoc",
                        "page_no": item.technical_spec.source.page_no if item.technical_spec else 1
                    },
                    details={"error": str(exc), "error_type": type(exc).__name__}
                )
                fallback_audited = AuditedItem(
                    item_id=item.item_id,
                    seq_no=item.seq_no,
                    description=item.description.value if item.description else "",
                    technical_spec=item.technical_spec.value if item.technical_spec else "",
                    material_code=item.material_code.value if item.material_code else None,
                    findings=[err_finding],
                    resolved_standards=[],
                    status="cannot_verify",
                    has_identified_standard=False,
                    has_current_edition=None,
                    is_qco_applicable=False,
                    is_qco_compliant=True
                )
                db_item_dict = {
                    "seq_no": item.seq_no,
                    "item_id": item.item_id,
                    "description": item.description.value if item.description else "",
                    "quantity": item.quantity.value if item.quantity else None,
                    "unit": item.unit.value if item.unit else None,
                    "status": "cannot_verify",
                    "badge_color": "purple",
                    "findings": [err_finding.to_dict()],
                    "cited_standards": [],
                    "recommended_standards": [],
                    "source_tier": "AUTHORITATIVE",
                    "page_refs": [item.technical_spec.source.page_no] if item.technical_spec else [1],
                    "processing_ms": proc_ms,
                }
                try:
                    upsert_item(job_id, db_item_dict)
                except Exception as db_err:
                    logger.error(f"Job {job_id}: Failed to upsert fallback for {item.item_id}: {db_err}")
                try:
                    increment_done(job_id)
                except Exception as db_err:
                    logger.error(f"Job {job_id}: Failed to increment done for {item.item_id}: {db_err}")
                return fallback_audited

        # Parallelize across worker threads sized to key count / pool capacity (6 workers)
        num_workers = min(6, total_items) if total_items > 0 else 1
        JOB_TIMEOUT_SEC = 180.0
        ITEM_TIMEOUT_SEC = 45.0
        t_job_audit_start = time.perf_counter()

        with ThreadPoolExecutor(max_workers=num_workers, thread_name_prefix="item_auditor") as executor:
            future_to_item = {executor.submit(_process_item, it): it for it in items_to_audit}
            completed_ids = set()

            try:
                for fut in as_completed(future_to_item, timeout=JOB_TIMEOUT_SEC):
                    it = future_to_item[fut]
                    try:
                        audited_res = fut.result()
                        audited_item_objs.append(audited_res)
                        completed_ids.add(it.item_id)
                    except Exception as worker_err:
                        logger.exception(f"Job {job_id}: Worker future returned unhandled error for {it.item_id}: {worker_err}")
            except TimeoutError:
                logger.warning(f"Job {job_id}: Overall timeout ({JOB_TIMEOUT_SEC}s) reached before all items collected.")

            # Fill any remaining items skipped by overall job timeout
            for it in items_to_audit:
                if it.item_id not in completed_ids:
                    logger.warning(f"Job {job_id}: Marking uncompleted item {it.item_id} as cannot_verify: timeout.")
                    t_finding = ItemFinding(
                        code=FindingCode.CANNOT_VERIFY,
                        severity="error",
                        message=f"Item audit timed out after {ITEM_TIMEOUT_SEC:.1f}s",
                        evidence={
                            "doc_name": it.technical_spec.source.doc_name if it.technical_spec else "TenderDoc",
                            "page_no": it.technical_spec.source.page_no if it.technical_spec else 1
                        },
                        details={"timeout_type": "item_or_job_timeout"}
                    )
                    t_audited = AuditedItem(
                        item_id=it.item_id,
                        seq_no=it.seq_no,
                        description=it.description.value if it.description else "",
                        technical_spec=it.technical_spec.value if it.technical_spec else "",
                        material_code=it.material_code.value if it.material_code else None,
                        findings=[t_finding],
                        resolved_standards=[],
                        status="cannot_verify",
                        has_identified_standard=False,
                        has_current_edition=None,
                        is_qco_applicable=False,
                        is_qco_compliant=True
                    )
                    db_item_dict = {
                        "seq_no": it.seq_no,
                        "item_id": it.item_id,
                        "description": it.description.value if it.description else "",
                        "quantity": it.quantity.value if it.quantity else None,
                        "unit": it.unit.value if it.unit else None,
                        "status": "cannot_verify",
                        "badge_color": "purple",
                        "findings": [t_finding.to_dict()],
                        "cited_standards": [],
                        "recommended_standards": [],
                        "source_tier": "AUTHORITATIVE",
                        "page_refs": [it.technical_spec.source.page_no] if it.technical_spec else [1],
                        "processing_ms": round(ITEM_TIMEOUT_SEC * 1000.0, 2),
                    }
                    try:
                        upsert_item(job_id, db_item_dict)
                        increment_done(job_id)
                    except Exception:
                        pass
                    audited_item_objs.append(t_audited)
                    completed_ids.add(it.item_id)
                    t_finding = ItemFinding(
                        code=FindingCode.CANNOT_VERIFY,
                        severity="error",
                        message="Audit item cancelled: job reached 3-minute overall timeout",
                        evidence={
                            "doc_name": it.technical_spec.source.doc_name if it.technical_spec else "TenderDoc",
                            "page_no": it.technical_spec.source.page_no if it.technical_spec else 1
                        },
                        details={"timeout_type": "job_timeout"}
                    )
                    t_audited = AuditedItem(
                        item_id=it.item_id,
                        seq_no=it.seq_no,
                        description=it.description.value if it.description else "",
                        technical_spec=it.technical_spec.value if it.technical_spec else "",
                        material_code=it.material_code.value if it.material_code else None,
                        findings=[t_finding],
                        resolved_standards=[],
                        status="cannot_verify",
                        has_identified_standard=False,
                        has_current_edition=None,
                        is_qco_applicable=False,
                        is_qco_compliant=True
                    )
                    db_item_dict = {
                        "seq_no": it.seq_no,
                        "item_id": it.item_id,
                        "description": it.description.value if it.description else "",
                        "quantity": it.quantity.value if it.quantity else None,
                        "unit": it.unit.value if it.unit else None,
                        "status": "cannot_verify",
                        "badge_color": "purple",
                        "findings": [t_finding.to_dict()],
                        "cited_standards": [],
                        "recommended_standards": [],
                        "source_tier": "AUTHORITATIVE",
                        "page_refs": [it.technical_spec.source.page_no] if it.technical_spec else [1],
                        "processing_ms": 0.0,
                    }
                    try:
                        upsert_item(job_id, db_item_dict)
                        increment_done(job_id)
                    except Exception:
                        pass
                    audited_item_objs.append(t_audited)

        # ── 3. Calculate Overall Audit Scores ──
        scorecard = calculate_audit_scores(audited_item_objs)

        cov_val = scorecard.coverage.percentage
        cur_val = scorecard.currency.percentage
        qco_val = scorecard.qco_compliance.percentage

        summary_msg = (
            f"Audit Completed: Coverage {scorecard.coverage.display_value} ({scorecard.coverage.arithmetic_str}), "
            f"Currency {scorecard.currency.display_value} ({scorecard.currency.arithmetic_str}), "
            f"QCO Compliance {scorecard.qco_compliance.display_value} ({scorecard.qco_compliance.arithmetic_str})."
        )

        update_job(
            job_id,
            status="done",
            total_items=total_items,
            done_items=total_items,
            coverage=cov_val,
            currency=cur_val,
            qco_compliance=qco_val,
            coverage_denominator=scorecard.coverage.denominator,
            currency_denominator=scorecard.currency.denominator,
            qco_denominator=scorecard.qco_compliance.denominator,
            status_counts=scorecard.status_counts,
            summary=summary_msg,
        )

        logger.info(f"Audit job {job_id} successfully completed. Summary: {summary_msg}")
        return get_job(job_id) or {}

    except Exception as e:
        logger.exception(f"Audit job {job_id} encountered critical failure: {e}")
        update_job(job_id, status="error", error_msg=str(e))
        return get_job(job_id) or {}


def launch_audit_job(
    file_paths: Optional[List[str]] = None,
    raw_items: Optional[List[Dict[str, Any]]] = None,
    doc_type: Optional[str] = "gem"
) -> str:
    """
    Creates job row and launches the background audit worker thread.
    Returns: job_id (str)
    """
    job_record = create_job(filenames=file_paths or ["raw_items"], doc_type=doc_type)
    job_id = job_record["id"]

    # Submit to ThreadPoolExecutor for background non-blocking execution
    _EXECUTOR.submit(run_audit_sync, job_id, file_paths, raw_items, doc_type)
    return job_id


def rerun_single_item(job_id: str, seq_no: int) -> Optional[Dict[str, Any]]:
    """
    Re-audits a single item in an existing job and refreshes job scores.
    """
    items = get_job_items(job_id)
    target = next((it for it in items if it["seq_no"] == seq_no), None)
    if not target:
        return None

    load_db_sets()
    resolver = StandardResolver()

    # Reconstruct item
    desc_val = target.get("description", "")
    spec_val = target.get("technical_spec", "")
    if not spec_val:
        # Look in cited standards for technical context
        for cs in target.get("cited_standards", []):
            if "raw_citation" in cs:
                spec_val += f" {cs['raw_citation']}"

    item_obj = AuditItem(
        item_id=target.get("item_id", str(seq_no)),
        seq_no=seq_no,
        description=ItemField(value=desc_val, source=SourceRef("Doc", 1, 0, "AUTHORITATIVE")),
        technical_spec=ItemField(value=spec_val or desc_val, source=SourceRef("Doc", 1, 0, "AUTHORITATIVE")),
    )

    t0 = time.perf_counter()
    mentions = extract_mentions(spec_val or desc_val, source_block_tier="AUTHORITATIVE")
    resolved_stds = []
    for m in mentions:
        vq, _ = VerbatimQuoteVerifier.extract_and_verify_quote(m, spec_val or desc_val, "Doc", 1, 0)
        resolved = resolver.resolve_mention(m, f"{desc_val} {spec_val}", vq)
        resolved_stds.append(resolved)

    audited = FindingAssembler.assemble_item(item_obj, resolved_stds, "Doc", 1)
    proc_ms = round((time.perf_counter() - t0) * 1000.0, 2)

    db_item = {
        "seq_no": audited.seq_no,
        "item_id": audited.item_id,
        "description": audited.description,
        "technical_spec": audited.technical_spec or target.get("technical_spec"),
        "material_code": audited.material_code or target.get("material_code"),
        "quantity": target.get("quantity"),
        "unit": target.get("unit"),
        "status": audited.status,
        "badge_color": _get_badge_color(audited.status),
        "findings": [f.to_dict() for f in audited.findings],
        "cited_standards": [s.to_dict() for s in audited.resolved_standards],
        "recommended_standards": target.get("recommended_standards", []),
        "source_tier": "AUTHORITATIVE",
        "page_refs": target.get("page_refs", [1]),
        "processing_ms": proc_ms,
    }

    upsert_item(job_id, db_item)

    # Re-calculate job-level scores
    all_items = get_job_items(job_id)
    # Convert to AuditedItem objects for calculate_audit_scores
    audited_objs = []
    for it in all_items:
        codes = [f.get("code") for f in it.get("findings", [])]
        has_id_std = bool(it.get("cited_standards"))
        has_cur_ed = None
        if has_id_std:
            if "SUPERSEDED" in codes or "OUTDATED_EDITION" in codes or "CITATION_NO_YEAR" in codes:
                has_cur_ed = False
            else:
                has_cur_ed = True

        qco_app = False
        for cs in it.get("cited_standards", []):
            base_k = cs.get("resolved_base_key") or cs.get("base_key")
            if base_k:
                q_min, c_type, _ = FindingAssembler._lookup_qco(base_k)
                if c_type == "Mandatory" or q_min:
                    qco_app = True
                    break
        if "CERT_NOT_MENTIONED" in codes:
            qco_app = True
            qco_comp = False
        else:
            qco_comp = True if qco_app else True

        audited_objs.append(AuditedItem(
            seq_no=it["seq_no"],
            item_id=it["item_id"],
            material_code=None,
            description=it.get("description", ""),
            technical_spec="",
            findings=[],
            status=it.get("status", "compliant"),
            is_qco_applicable=qco_app,
            is_qco_compliant=qco_comp,
            has_identified_standard=has_id_std,
            has_current_edition=has_cur_ed
        ))

    scorecard = calculate_audit_scores(audited_objs)
    update_job(
        job_id,
        coverage=scorecard.coverage.percentage,
        currency=scorecard.currency.percentage,
        qco_compliance=scorecard.qco_compliance.percentage,
        coverage_denominator=scorecard.coverage.denominator,
        currency_denominator=scorecard.currency.denominator,
        qco_denominator=scorecard.qco_compliance.denominator,
        status_counts=scorecard.status_counts,
    )

    return db_item
