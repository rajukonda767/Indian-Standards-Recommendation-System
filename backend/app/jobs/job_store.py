"""
app/jobs/job_store.py
=====================
Synchronous (psycopg2) CRUD for audit_jobs and audit_items.
All functions are thread-safe (each acquires its own connection from the pool).
Called from async context via asyncio.run_in_executor where needed.
Includes automatic single retry on transient operational/network drops.
"""

from __future__ import annotations

import json
import time
import logging
import uuid
from typing import Any, Dict, List, Optional
import psycopg2

from app.db import get_db_cursor

logger = logging.getLogger(__name__)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _row_to_dict(cur, row) -> Dict[str, Any]:
    """Convert a psycopg2 row tuple to a dict using cursor description."""
    cols = [d[0] for d in cur.description]
    d: Dict[str, Any] = dict(zip(cols, row))
    # Serialise UUID and datetime to strings for JSON safety
    if 'id' in d and d['id'] is not None:
        d['id'] = str(d['id'])
    if 'job_id' in d and d['job_id'] is not None:
        d['job_id'] = str(d['job_id'])
    for ts_col in ('created_at', 'updated_at'):
        if ts_col in d and d[ts_col] is not None:
            d[ts_col] = d[ts_col].isoformat()
    return d


def with_db_retry(fn):
    """Decorator retrying once on transient DB connection drops."""
    def wrapper(*args, **kwargs):
        for attempt in range(2):
            try:
                return fn(*args, **kwargs)
            except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
                if attempt == 0:
                    logger.warning(f"Transient DB drop in {fn.__name__} ({e}), retrying...")
                    time.sleep(0.3)
                    continue
                raise
    return wrapper


_JOB_COLS = """
    id, status, filenames, doc_type, total_items, done_items,
    coverage, currency, qco_compliance,
    coverage_denominator, currency_denominator, qco_denominator,
    status_counts, summary, error_msg, created_at, updated_at
"""


# ─── Job CRUD ─────────────────────────────────────────────────────────────────

@with_db_retry
def create_job(filenames: List[str], doc_type: Optional[str] = None) -> Dict[str, Any]:
    """Insert a new audit_jobs row with status='pending'. Returns the created job."""
    job_id = str(uuid.uuid4())
    with get_db_cursor() as cur:
        cur.execute(f"""
            INSERT INTO audit_jobs (id, status, filenames, doc_type)
            VALUES (%s, 'pending', %s, %s)
            RETURNING {_JOB_COLS};
        """, (job_id, filenames, doc_type))
        row = cur.fetchone()
        return _row_to_dict(cur, row)


@with_db_retry
def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a single job by ID. Returns None if not found."""
    with get_db_cursor() as cur:
        cur.execute(f"SELECT {_JOB_COLS} FROM audit_jobs WHERE id = %s;", (job_id,))
        row = cur.fetchone()
        if row is None:
            return None
        return _row_to_dict(cur, row)


@with_db_retry
def list_jobs(limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
    """Return jobs ordered by created_at DESC."""
    with get_db_cursor() as cur:
        cur.execute(f"""
            SELECT {_JOB_COLS}
            FROM audit_jobs
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s;
        """, (limit, offset))
        rows = cur.fetchall()
        return [_row_to_dict(cur, r) for r in rows]


@with_db_retry
def update_job(job_id: str, **fields) -> None:
    """
    Update arbitrary fields on a job row.
    Allowed fields: status, total_items, done_items, coverage, currency,
    qco_compliance, coverage_denominator, currency_denominator, qco_denominator,
    status_counts, summary, error_msg.
    Always sets updated_at = NOW().
    """
    _ALLOWED = {
        'status', 'total_items', 'done_items',
        'coverage', 'currency', 'qco_compliance',
        'coverage_denominator', 'currency_denominator', 'qco_denominator',
        'status_counts', 'summary', 'error_msg',
    }
    unknown = set(fields) - _ALLOWED
    if unknown:
        raise ValueError(f"update_job: unknown fields {unknown}")
    if not fields:
        return

    set_parts = []
    params: List[Any] = []
    for key, val in fields.items():
        set_parts.append(f"{key} = %s")
        if key == 'status_counts' and isinstance(val, dict):
            params.append(json.dumps(val))
        else:
            params.append(val)
    set_parts.append("updated_at = NOW()")
    params.append(job_id)

    with get_db_cursor() as cur:
        cur.execute(
            f"UPDATE audit_jobs SET {', '.join(set_parts)} WHERE id = %s;",
            params,
        )


@with_db_retry
def increment_done(job_id: str) -> None:
    """Atomically increment done_items counter."""
    with get_db_cursor() as cur:
        cur.execute(
            "UPDATE audit_jobs SET done_items = done_items + 1, updated_at = NOW() WHERE id = %s;",
            (job_id,),
        )


# ─── Item CRUD ────────────────────────────────────────────────────────────────

@with_db_retry
def ensure_audit_tables_schema() -> None:
    """Ensures audit_items table has technical_spec and material_code columns."""
    try:
        with get_db_cursor() as cur:
            cur.execute("""
                ALTER TABLE audit_items ADD COLUMN IF NOT EXISTS technical_spec TEXT;
                ALTER TABLE audit_items ADD COLUMN IF NOT EXISTS material_code TEXT;
            """)
    except Exception as e:
        logger.warning(f"ensure_audit_tables_schema notice: {e}")


@with_db_retry
def upsert_item(job_id: str, item: Dict[str, Any]) -> None:
    """
    Insert or update a single audit_items row (keyed by job_id + seq_no).
    """
    # Attempt 1: with technical_spec and material_code columns
    try:
        with get_db_cursor() as cur:
            cur.execute("""
                INSERT INTO audit_items (
                    job_id, seq_no, item_id, description, quantity, unit,
                    status, badge_color, findings, cited_standards,
                    recommended_standards, source_tier, page_refs, processing_ms,
                    technical_spec, material_code
                ) VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s::jsonb, %s::jsonb,
                    %s::jsonb, %s, %s, %s,
                    %s, %s
                )
                ON CONFLICT (job_id, seq_no) DO UPDATE SET
                    status                = EXCLUDED.status,
                    badge_color           = EXCLUDED.badge_color,
                    findings              = EXCLUDED.findings,
                    cited_standards       = EXCLUDED.cited_standards,
                    recommended_standards = EXCLUDED.recommended_standards,
                    processing_ms         = EXCLUDED.processing_ms,
                    technical_spec        = EXCLUDED.technical_spec,
                    material_code         = EXCLUDED.material_code;
            """, (
                job_id,
                item['seq_no'],
                item.get('item_id'),
                item.get('description'),
                item.get('quantity'),
                item.get('unit'),
                item.get('status'),
                item.get('badge_color'),
                json.dumps(item.get('findings', [])),
                json.dumps(item.get('cited_standards', [])),
                json.dumps(item.get('recommended_standards', [])),
                item.get('source_tier'),
                item.get('page_refs', []),
                item.get('processing_ms'),
                item.get('technical_spec'),
                item.get('material_code'),
            ))
            return
    except psycopg2.Error as e:
        logger.info(f"Upsert fallback without dedicated columns: {e}")

    # Attempt 2: fallback without new columns if schema migration is pending
    with get_db_cursor() as cur:
        cur.execute("""
            INSERT INTO audit_items (
                job_id, seq_no, item_id, description, quantity, unit,
                status, badge_color, findings, cited_standards,
                recommended_standards, source_tier, page_refs, processing_ms
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s::jsonb, %s::jsonb,
                %s::jsonb, %s, %s, %s
            )
            ON CONFLICT (job_id, seq_no) DO UPDATE SET
                status                = EXCLUDED.status,
                badge_color           = EXCLUDED.badge_color,
                findings              = EXCLUDED.findings,
                cited_standards       = EXCLUDED.cited_standards,
                recommended_standards = EXCLUDED.recommended_standards,
                processing_ms         = EXCLUDED.processing_ms;
        """, (
            job_id,
            item['seq_no'],
            item.get('item_id'),
            item.get('description'),
            item.get('quantity'),
            item.get('unit'),
            item.get('status'),
            item.get('badge_color'),
            json.dumps(item.get('findings', [])),
            json.dumps(item.get('cited_standards', [])),
            json.dumps(item.get('recommended_standards', [])),
            item.get('source_tier'),
            item.get('page_refs', []),
            item.get('processing_ms'),
        ))


@with_db_retry
def get_job_items(job_id: str) -> List[Dict[str, Any]]:
    """Fetch all items for a job, ordered by seq_no, ensuring technical_spec and material_code are populated."""
    items = []
    with get_db_cursor() as cur:
        try:
            cur.execute("""
                SELECT seq_no, item_id, description, quantity, unit,
                       status, badge_color, findings, cited_standards,
                       recommended_standards, source_tier, page_refs, processing_ms,
                       technical_spec, material_code
                FROM audit_items
                WHERE job_id = %s
                ORDER BY seq_no;
            """, (job_id,))
            rows = cur.fetchall()
            items = [_row_to_dict(cur, r) for r in rows]
        except psycopg2.Error:
            cur.execute("""
                SELECT seq_no, item_id, description, quantity, unit,
                       status, badge_color, findings, cited_standards,
                       recommended_standards, source_tier, page_refs, processing_ms
                FROM audit_items
                WHERE job_id = %s
                ORDER BY seq_no;
            """, (job_id,))
            rows = cur.fetchall()
            items = [_row_to_dict(cur, r) for r in rows]

    # Post-process items to ensure technical_spec and material_code are never empty
    for it in items:
        # Fallback technical_spec from quotes in cited_standards or findings
        if not it.get("technical_spec"):
            cs_list = it.get("cited_standards") or []
            for cs in cs_list:
                q_text = (cs.get("quote") or {}).get("quote_text")
                if q_text and len(str(q_text).strip()) > 5:
                    it["technical_spec"] = str(q_text).strip()
                    break
            if not it.get("technical_spec"):
                f_list = it.get("findings") or []
                for f in f_list:
                    q_text = (f.get("evidence") or {}).get("quote")
                    if q_text and len(str(q_text).strip()) > 5:
                        it["technical_spec"] = str(q_text).strip()
                        break
        # Fallback material_code from item_id if item_id looks like a code (e.g. M8112355140)
        if not it.get("material_code"):
            i_id = str(it.get("item_id") or "")
            if len(i_id) >= 6 and not i_id.isdigit():
                it["material_code"] = i_id

    return items


# ─── Startup Cleanup ──────────────────────────────────────────────────────────

@with_db_retry
def mark_stale_jobs_failed() -> int:
    """
    Called once at application startup.
    Marks ALL jobs with status IN ('running', 'pending') as 'failed'.
    """
    with get_db_cursor() as cur:
        cur.execute("""
            UPDATE audit_jobs
            SET
                status    = 'failed',
                error_msg = 'Server restarted while job was in-flight',
                updated_at = NOW()
            WHERE status IN ('running', 'pending')
            RETURNING id, status;
        """)
        rows = cur.fetchall()

    count = len(rows)
    if count:
        ids = [str(r[0]) for r in rows]
        logger.warning(
            "Startup cleanup: %d stale audit job(s) marked failed: %s",
            count, ids,
        )
    else:
        logger.info("Startup cleanup: no stale audit jobs found.")
    return count
