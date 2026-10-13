"""
bot_retrieval.py
================
Retrieval and grounding service for MiniBot AI Assistant (Phase 2).
Provides deterministic IS number extraction, canonical normalization,
grounded database facts assembly for audit, recommendation, and standards explorer screens.
"""

from __future__ import annotations

import re
import logging
from typing import Optional, List, Dict, Any, Tuple
import psycopg2

from app.db import get_db_cursor

logger = logging.getLogger("bis_backend.bot_retrieval")

# Words preceding lowercase 'is' that indicate English copula / question syntax, not standard code
COPULA_PRECEDING_WORDS = {
    "what", "how", "where", "when", "who", "which",
    "there", "that", "this", "it", "here", "why", "if"
}

# Regex to detect IS standard identifiers across messages and screens
# Matches:
#   IS 7098, IS7098, is 694:2010, IS 7098 (Part 1):2025, IS 1554-1,
#   IS 1554 (Part 1), IS/IEC 60502, IS 14255:1995, etc.
IS_MENTION_PATTERN = re.compile(
    r"""(?ix)
    \b
    (?P<fam>IS(?:\s*/\s*(?:IEC|ISO|IEEE|TR))?)
    [\s\.\:\/\-]*
    (?P<num>\d{2,6})
    (?:
        [\s\-]*(?:\(\s*)?(?:Part|Pt|Sec|Section)\.?[\s\-]*
        (?P<part>\d+(?:[\s\w\/\-]*)?)
        (?:\))?
        |
        -(?P<hyph_part>\d{1,2})\b
    )?
    (?:
        [\s\:]+(?P<year>(?:19|20)\d{2})\b
    )?
    """
)

# Year-only pattern to exclude false positive extractions
YEAR_PATTERN = re.compile(r'^(?:19|20)\d{2}$')


class NormalizedIS(str):
    """
    Normalized string representation of an Indian Standard identifier.
    Inherits from str so it can be passed anywhere a string is expected,
    while exposing base, part, year, and base_key attributes.
    """
    base: str
    part: Optional[str]
    year: Optional[int]
    base_key: str

    def __new__(
        cls,
        val: str,
        base: str,
        part: Optional[str] = None,
        year: Optional[int] = None,
        base_key: Optional[str] = None
    ) -> NormalizedIS:
        obj = super().__new__(cls, val)
        obj.base = base
        obj.part = part
        obj.year = year
        obj.base_key = base_key or base
        return obj


def extract_is_numbers(text: str) -> List[str]:
    """
    Extract pure Indian Standard numbers from arbitrary text.
    Handles:
      - 'IS 7098', 'IS7098', 'is 694:2010', 'IS 7098 (Part 1):2025'
      - 'IS 1554-1', 'IS 1554 (Part 1)', 'IS/IEC 60502', 'IS 14255:1995'
      - Hindi and Telugu sentences containing a Latin-script IS number
      - Multiple standards in one message and duplicate occurrences
      - Ignores years, copulas ('what is 2024'), clause numbers ('clause 5.2'),
        and unrelated numbers ('500 units', '100%').
    """
    if not text or not isinstance(text, str):
        return []

    results: List[str] = []
    seen: set[str] = set()

    for m in IS_MENTION_PATTERN.finditer(text):
        raw = m.group(0).strip()

        # Clean trailing punctuation from sentence boundaries (. , ; : ? !)
        raw = re.sub(r'[\.\,\;\:\?\!]+$', '', raw).strip()
        if not raw:
            continue

        # Copula check for lowercase 'is'
        start = m.start()
        prefix = text[:start].rstrip()
        prev_word = prefix.split()[-1].lower() if prefix.split() else ""
        prev_word_clean = re.sub(r'[^\w]', '', prev_word)

        if raw.lower().startswith("is") and not raw.startswith("IS"):
            if prev_word_clean in COPULA_PRECEDING_WORDS:
                continue

        # Exclude if the matched number is just a year (e.g. "is 2024" without part/standard cues)
        num_str = m.group("num")
        if not m.group("part") and not m.group("hyph_part") and not m.group("year"):
            if YEAR_PATTERN.match(num_str) and prev_word_clean in COPULA_PRECEDING_WORDS:
                continue

        # Deduplicate using stripped alphanumeric key
        dedup_key = re.sub(r'[^A-Z0-9]', '', raw.upper())
        if dedup_key not in seen:
            seen.add(dedup_key)
            results.append(raw)

    return results


def normalize_is(s: str) -> NormalizedIS:
    """
    Normalize an IS standard citation string into a canonical NormalizedIS object.
    Uppercase, strip spaces, dots, parentheses, slashes.
    Maintains base number, part, and year distinguishable.
    Examples:
      - 'IS 7098'               -> 'IS7098'
      - 'is 694:2010'           -> 'IS694:2010'
      - 'IS 7098 (Part 1):2025' -> 'IS7098:PART1:2025'
      - 'IS 1554-1'             -> 'IS1554:PART1'
      - 'IS 1554 (Part 1)'      -> 'IS1554:PART1'
      - 'IS/IEC 60502'          -> 'ISIEC60502'
      - 'IS 14255:1995'         -> 'IS14255:1995'
    """
    raw = s.strip()
    m = IS_MENTION_PATTERN.search(raw)
    if not m:
        cleaned = re.sub(r'[\s\.\(\)\/]', '', raw).upper()
        return NormalizedIS(cleaned, base=cleaned, part=None, year=None, base_key=cleaned)

    fam_raw = m.group("fam")
    num = m.group("num")
    part_raw = m.group("part") or m.group("hyph_part")
    year_raw = m.group("year")

    # Base identifier (spaces and slashes stripped)
    fam_clean = re.sub(r'[\s\.\(\)\/]', '', fam_raw).upper()
    base = f"{fam_clean}{num}"

    # DB base_key (preserves slash in joint family like IS/IEC)
    fam_db = re.sub(r'\s+', '', fam_raw.upper())
    db_base = f"{fam_db}{num}"

    part_clean = None
    if part_raw:
        p = re.sub(r'[\s\.\(\)]', '', part_raw).upper()
        if not p.startswith("PART"):
            p = f"PART{p}"
        part_clean = p

    year = int(year_raw) if year_raw else None

    # Construct canonical normalized string
    parts = [base]
    if part_clean:
        parts.append(part_clean)
    if year:
        parts.append(str(year))
    norm_val = ":".join(parts)

    # DB standard base_key pattern (e.g. IS7098(PART1) or IS/IEC60255(PART12))
    if part_clean:
        base_key = f"{db_base}({part_clean})"
    else:
        base_key = db_base

    return NormalizedIS(norm_val, base=base, part=part_clean, year=year, base_key=base_key)


def _lookup_standard_in_db(cur, norm: NormalizedIS) -> List[Dict[str, Any]]:
    """
    Query PostgreSQL database for standard records matching NormalizedIS.
    Attempts:
      1. Exact match with base_key and year (if year specified)
      2. Exact match with base_key (if part specified)
      3. Base number match (fallback returning all parts/versions)
    """
    cols = (
        "id, standard_number, base_number, year, dept, title, "
        "is_status_label, status_raw, qco_ministry, ministry, "
        "technical_committee, virtual_scope, supersedes_older, superseded_by_newer"
    )

    # 1. Exact match with year if year is present
    if norm.year:
        cur.execute(f"""
            SELECT {cols} FROM standards
            WHERE (base_key = %s OR base_number = %s) AND year = %s
            ORDER BY year DESC LIMIT 1;
        """, (norm.base_key, norm.base_key, norm.year))
        rows = cur.fetchall()
        if rows:
            return [_db_row_to_dict(cur, r) for r in rows]

    # 2. Match with base_key (specific part)
    if norm.part:
        cur.execute(f"""
            SELECT {cols} FROM standards
            WHERE base_key = %s OR base_number = %s
            ORDER BY year DESC;
        """, (norm.base_key, norm.base_key))
        rows = cur.fetchall()
        if rows:
            return [_db_row_to_dict(cur, r) for r in rows]

        # Normalized regex fallback in SQL: strip non-alphanumeric
        norm_sql = re.sub(r'[^A-Z0-9]', '', norm.base_key)
        cur.execute(f"""
            SELECT {cols} FROM standards
            WHERE REGEXP_REPLACE(UPPER(base_key), '[^A-Z0-9]', '', 'g') = %s
            ORDER BY year DESC;
        """, (norm_sql,))
        rows = cur.fetchall()
        if rows:
            return [_db_row_to_dict(cur, r) for r in rows]

    # 3. Fall back to base number: return all parts/versions
    base_prefix = f"{norm.base}%"
    cur.execute(f"""
        SELECT {cols} FROM standards
        WHERE base_number ILIKE %s OR base_key ILIKE %s
           OR REGEXP_REPLACE(UPPER(base_number), '[^A-Z0-9]', '', 'g') ILIKE %s
        ORDER BY standard_number ASC;
    """, (base_prefix, base_prefix, base_prefix))
    rows = cur.fetchall()
    if rows:
        return [_db_row_to_dict(cur, r) for r in rows]

    return []


def _lookup_successor_in_db(cur, raw_str: str, norm: NormalizedIS) -> Optional[Dict[str, Any]]:
    """
    Search if an older or superseded standard is referenced as superseded in the catalog.
    Checks supersedes_older in standards and standard_lineage table.
    """
    cols = (
        "id, standard_number, base_number, year, dept, title, "
        "is_status_label, status_raw, qco_ministry, ministry, "
        "technical_committee, virtual_scope, supersedes_older, superseded_by_newer"
    )

    # Search patterns
    num_match = re.search(r'\d+', norm.base)
    num_val = num_match.group(0) if num_match else norm.base

    # Check supersedes_older column
    pattern = f"%{num_val}%"
    cur.execute(f"""
        SELECT {cols} FROM standards
        WHERE supersedes_older ILIKE %s
        ORDER BY year DESC LIMIT 1;
    """, (pattern,))
    row = cur.fetchone()
    if row:
        return _db_row_to_dict(cur, row)

    # Check standard_lineage table
    cur.execute(f"""
        SELECT s.{cols.replace(', ', ', s.')}
        FROM standard_lineage l
        JOIN standards s ON l.standard_id = s.id
        WHERE l.related_standard_raw ILIKE %s
        ORDER BY s.year DESC LIMIT 1;
    """, (pattern,))
    row = cur.fetchone()
    if row:
        return _db_row_to_dict(cur, row)

    return None


def _db_row_to_dict(cur, row: tuple) -> Dict[str, Any]:
    cols = [d[0] for d in cur.description]
    return dict(zip(cols, row))


def build_facts(
    screen: str,
    screen_data: Dict[str, Any],
    message: str,
    db: Optional[Any] = None,
    history: Optional[List[Any]] = None
) -> Tuple[str, List[str], List[str]]:
    """
    Build grounded database facts text for MiniBot system prompt.
    Returns:
      (facts_text, found_is_list, not_found_is_list)

    Capabilities:
      - Extracts IS numbers from user message, history, and screen_data.
      - Loads real scorecard & per-item findings for 'audit' screen from DB.
      - Loads primary standard full DB record & aligned standards for 'recommend' screen.
      - Loads title, status, ministry, QCO details, successor for 'standards' screen.
      - For every IS number mentioned that is NOT found, outputs an explicit line:
        'NOT FOUND IN DATABASE: IS xxxx'.
      - Caps facts text at approximately 3000 characters with sensible priority truncation.
    """
    screen_clean = (screen or "home").lower().strip()
    screen_data = screen_data or {}
    message_text = message or ""

    # 1. Collect all IS numbers mentioned in user message, screen_data, and history
    extracted_from_msg = extract_is_numbers(message_text)
    all_is_mentions = list(extracted_from_msg)

    # Also inspect recent history if available
    if history:
        for h in reversed(history[-4:]):
            txt = getattr(h, "content", None) or (h.get("content") if isinstance(h, dict) else str(h))
            if txt:
                for sn in extract_is_numbers(txt):
                    if sn not in all_is_mentions:
                        all_is_mentions.append(sn)

    # Screen data standard references
    if screen_clean == "standards":
        s_num = screen_data.get("is_number") or screen_data.get("standard_number")
        if s_num and isinstance(s_num, str):
            for sn in extract_is_numbers(s_num) or [s_num]:
                if sn not in all_is_mentions:
                    all_is_mentions.append(sn)

    elif screen_clean == "recommend":
        p_is = screen_data.get("primary_is") or screen_data.get("standard_number") or screen_data.get("is_number")
        if p_is and isinstance(p_is, str):
            for sn in extract_is_numbers(p_is) or [p_is]:
                if sn not in all_is_mentions:
                    all_is_mentions.append(sn)
        q_val = screen_data.get("query")
        if q_val and isinstance(q_val, str):
            for sn in extract_is_numbers(q_val):
                if sn not in all_is_mentions:
                    all_is_mentions.append(sn)
        aligned = screen_data.get("aligned_is", [])
        if isinstance(aligned, list):
            for a in aligned[:5]:
                anum = a.get("is_number") or a.get("ref_number") if isinstance(a, dict) else str(a)
                if anum:
                    for sn in extract_is_numbers(anum):
                        if sn not in all_is_mentions:
                            all_is_mentions.append(sn)

    found_standards: List[str] = []
    not_found_standards: List[str] = []

    facts_sections: List[str] = []

    try:
        with get_db_cursor() as cur:
            # ── 2. Screen-specific factual retrieval ─────────────────────────

            # AUDIT SCREEN
            if screen_clean == "audit":
                job_id = screen_data.get("job_id")
                job_row = None

                if job_id:
                    # Check if valid UUID or integer index
                    job_id_str = str(job_id).strip()
                    try:
                        cur.execute("""
                            SELECT id, status, coverage, currency, qco_compliance,
                                   total_items, done_items, summary
                            FROM audit_jobs
                            WHERE id::text = %s;
                        """, (job_id_str,))
                        job_row = cur.fetchone()
                    except Exception:
                        cur.connection.rollback()
                        job_row = None

                    # If not found by direct ID, check if user passed integer job index
                    if not job_row and job_id_str.isdigit():
                        offset_idx = max(0, int(job_id_str) - 1)
                        cur.execute("""
                            SELECT id, status, coverage, currency, qco_compliance,
                                   total_items, done_items, summary
                            FROM audit_jobs
                            ORDER BY created_at DESC
                            LIMIT 1 OFFSET %s;
                        """, (offset_idx,))
                        job_row = cur.fetchone()

                if job_row:
                    j_dict = _db_row_to_dict(cur, job_row)
                    real_job_id = str(j_dict["id"])

                    facts_sections.append(
                        f"AUDIT JOB ID: {real_job_id}\n"
                        f"Job Status: {j_dict.get('status')}\n"
                        f"Specification Coverage Score: {j_dict.get('coverage')}%\n"
                        f"Standard Currency Score: {j_dict.get('currency')}%\n"
                        f"Mandatory QCO Compliance Score: {j_dict.get('qco_compliance')}%\n"
                        f"Total Audit Items: {j_dict.get('total_items', 0)}"
                    )
                    if j_dict.get("summary"):
                        facts_sections.append(f"Audit Summary: {j_dict['summary'][:300]}")

                    # Determine item focus
                    focus_seq = screen_data.get("item_index") or screen_data.get("seq_no")
                    if not focus_seq:
                        m_item = re.search(r'\bitem\s*(\d+)\b', message_text, re.I)
                        if m_item:
                            focus_seq = int(m_item.group(1))

                    if focus_seq:
                        cur.execute("""
                            SELECT seq_no, item_id, description, status, badge_color,
                                   findings, cited_standards, recommended_standards
                            FROM audit_items
                            WHERE job_id = %s AND (seq_no = %s OR item_id = %s)
                            LIMIT 1;
                        """, (real_job_id, int(focus_seq), str(focus_seq)))
                        item_row = cur.fetchone()
                        if item_row:
                            i_dict = _db_row_to_dict(cur, item_row)
                            raw_findings = i_dict.get('findings') or []
                            findings_lines = []
                            if isinstance(raw_findings, list):
                                for f in raw_findings:
                                    if isinstance(f, dict):
                                        code = f.get('code', 'Finding')
                                        msg = f.get('message', '')
                                        findings_lines.append(f"- {code}: {msg}")
                            elif isinstance(raw_findings, str):
                                findings_lines.append(raw_findings)
                            findings_fmt = "\n".join(findings_lines) if findings_lines else "No specific compliance gaps identified."

                            facts_sections.append(
                                f"AUDIT ITEM #{i_dict['seq_no']} (Item ID: {i_dict.get('item_id')}):\n"
                                f"Description: {i_dict.get('description', '')[:200]}\n"
                                f"Audit Status: {i_dict.get('status')} (Badge: {i_dict.get('badge_color')})\n"
                                f"Compliance Gaps / Failure Reasons:\n{findings_fmt}\n"
                                f"Cited Standards: {i_dict.get('cited_standards')}\n"
                                f"Recommended Standards: {i_dict.get('recommended_standards')}"
                            )
                            # Add item standards to mentions
                            if i_dict.get("cited_standards"):
                                for cs in extract_is_numbers(str(i_dict["cited_standards"])):
                                    if cs not in all_is_mentions:
                                        all_is_mentions.append(cs)
                            if i_dict.get("recommended_standards"):
                                for rs in extract_is_numbers(str(i_dict["recommended_standards"])):
                                    if rs not in all_is_mentions:
                                        all_is_mentions.append(rs)
                    else:
                        # Load first 5 items summary
                        cur.execute("""
                            SELECT seq_no, item_id, description, status, findings
                            FROM audit_items
                            WHERE job_id = %s
                            ORDER BY seq_no ASC LIMIT 5;
                        """, (real_job_id,))
                        item_rows = cur.fetchall()
                        if item_rows:
                            item_summaries = []
                            for ir in item_rows:
                                idct = _db_row_to_dict(cur, ir)
                                f_list = idct.get('findings') or []
                                f_codes = [f.get('code') for f in f_list if isinstance(f, dict)] if isinstance(f_list, list) else []
                                f_codes_str = ", ".join(f_codes) if f_codes else "None"
                                item_summaries.append(
                                    f"Item #{idct['seq_no']}: Status={idct['status']}, Gaps={f_codes_str}"
                                )
                            facts_sections.append("AUDIT ITEMS SUMMARY:\n" + "\n".join(item_summaries))

            # RECOMMEND SCREEN
            elif screen_clean == "recommend":
                query_val = screen_data.get("query")
                if query_val:
                    facts_sections.append(f"RECOMMENDATION QUERY: {query_val}")

                p_is = screen_data.get("primary_is") or screen_data.get("standard_number") or screen_data.get("is_number")
                if p_is:
                    facts_sections.append(f"PRIMARY RECOMMENDED STANDARD: {p_is}")

                aligned = screen_data.get("aligned_is", [])
                if isinstance(aligned, list) and aligned:
                    aligned_lines = []
                    for a in aligned[:5]:
                        if isinstance(a, dict):
                            is_code = a.get("is_number") or a.get("ref_number") or "Unknown"
                            title = a.get("title") or a.get("ref_title") or ""
                            aligned_lines.append(f"- {is_code}: {title}")
                        elif isinstance(a, str):
                            aligned_lines.append(f"- {a}")
                    if aligned_lines:
                        facts_sections.append("ALIGNED STANDARDS:\n" + "\n".join(aligned_lines))

            # ── 3. Standards database catalog lookup ─────────────────────────
            processed_keys: set[str] = set()

            for mention in all_is_mentions:
                norm = normalize_is(mention)
                if norm.base_key in processed_keys:
                    continue
                processed_keys.add(norm.base_key)

                records = _lookup_standard_in_db(cur, norm)

                if records:
                    found_standards.append(mention)
                    for rec in records:
                        std_lines = [
                            f"STANDARD: {rec['standard_number']}",
                            f"Title: {rec['title']}",
                            f"Status: {rec.get('is_status_label') or rec.get('status_raw') or 'Unknown'}"
                        ]

                        # Ministry / QCO details
                        qco_min = rec.get("qco_ministry")
                        gen_min = rec.get("ministry")
                        if qco_min:
                            std_lines.append(f"Mandatory QCO Governing Ministry: {qco_min}")
                        elif gen_min:
                            std_lines.append(f"Governing Ministry: {gen_min}")
                        else:
                            std_lines.append("QCO: No mandatory QCO order registered in catalog")

                        # Committee
                        if rec.get("technical_committee"):
                            std_lines.append(f"Technical Committee: {rec['technical_committee']}")

                        # Lineage & Successors
                        if rec.get("superseded_by_newer"):
                            std_lines.append(f"Superseded By Successor: {rec['superseded_by_newer']}")
                        if rec.get("supersedes_older"):
                            std_lines.append(f"Supersedes Older Edition: {rec['supersedes_older']}")

                        # Virtual scope (brief)
                        if rec.get("virtual_scope"):
                            scope_snip = rec["virtual_scope"][:250].strip()
                            std_lines.append(f"Scope: {scope_snip}")

                        facts_sections.append("\n".join(std_lines))

                else:
                    # Check if this standard was superseded by another standard in catalog
                    succ = _lookup_successor_in_db(cur, mention, norm)
                    if succ:
                        found_standards.append(mention)
                        facts_sections.append(
                            f"STANDARD: {mention}\n"
                            f"Status: Superseded / Withdrawn\n"
                            f"Successor Standard: {succ['standard_number']} (Title: {succ['title']})\n"
                            f"Successor Status: {succ.get('is_status_label') or succ.get('status_raw')}"
                        )
                    else:
                        # Record explicitly not found
                        not_found_standards.append(mention)
                        facts_sections.append(f"NOT FOUND IN DATABASE: {mention}")

    except Exception as e:
        logger.error(f"Database error during build_facts: {e}", exc_info=True)
        facts_sections.append(f"DATABASE LOOKUP STATUS: Partial lookup error ({str(e)})")

    # ── 4. Length Cap and Priority Truncation (approx 3000 chars) ────────────
    combined_facts = "\n\n".join(facts_sections)

    if len(combined_facts) > 3000:
        # Priority: Keep NOT FOUND notices and standard status intact; trim scope and extra items
        truncated_sections = []
        current_len = 0
        for sec in facts_sections:
            # If section contains Scope, truncate scope line
            if "Scope:" in sec:
                sec = re.sub(r'Scope:.*', 'Scope: (truncated)', sec, flags=re.DOTALL)
            if current_len + len(sec) < 2900:
                truncated_sections.append(sec)
                current_len += len(sec)
            else:
                truncated_sections.append("... [Additional database details truncated for length]")
                break
        combined_facts = "\n\n".join(truncated_sections)

    return combined_facts, found_standards, not_found_standards
