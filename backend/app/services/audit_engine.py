"""
audit_engine.py
===============
Tender compliance auditing pipeline:
1. Groq Line-Item Extraction (extract item_id, description, cited_standard)
2. Recommendation Engine matching (determine statutory recommended standard)
3. Lineage & Contradiction Diff Analysis:
   - COMPLIANT: Valid and current edition
   - OUTDATED: Older edition or amalgamated standard (e.g. IS 694:1990 -> IS 694:2010; IS 8112 -> IS 269:2015)
   - MISSING: Product description un-cited, missing mandatory IS mark
   - CONTRADICTION: Specification text contradicts cited standard (e.g. PVC insulated citing IS 7098 XLPE)
4. Multi-dimensional statutory compliance scoring (Coverage, Currency, QCO, Overall)
"""

import re
import json
import time
import logging
from typing import List, Dict, Any, Tuple, Optional
from app.config import settings
from app.db import get_db_cursor
from app.models.audit import AuditLineItem, AuditReport
from app.services.embedding import embedding_service
from app.services.vector_search import search_candidates_pgvector, rerank_candidates
from app.parsers.groq_wrapper import get_groq_wrapper

logger = logging.getLogger(__name__)

# Known engineering contradiction rules
CONTRADICTION_RULES = [
    {
        "pattern": r"\bpvc\b|\bpolyvinyl chloride\b",
        "conflicting_standards": ["IS 7098"],
        "reason": "Specification specifies 'PVC insulated', but cited standard IS 7098 mandates Crosslinked Polyethylene (XLPE) insulation. Change insulation to XLPE or revise citation to IS 694 / IS 1554."
    },
    {
        "pattern": r"\bxlpe\b|\bcrosslinked polyethylene\b",
        "conflicting_standards": ["IS 694"],
        "reason": "Specification specifies 'XLPE insulated', but cited standard IS 694 covers only Polyvinyl Chloride (PVC) insulation. Revise citation to IS 7098."
    },
    {
        "pattern": r"\bopc\s*(43|53)?\b|\bordinary portland\b",
        "conflicting_standards": ["IS 1489"],
        "reason": "Specification specifies 'Ordinary Portland Cement (OPC)', but cited standard IS 1489 specifies Portland Pozzolana Cement (PPC). Revise citation to IS 269:2015."
    }
]

def extract_line_items_groq(tender_text: str) -> List[Dict[str, Any]]:
    """
    Extracts itemized procurement technical requirements from tender text using Groq.
    Returns list of dicts: [{"item_id": 1, "description": "...", "cited_standard": "IS ..." | null}]
    """
    system_prompt = (
        "You are an expert Indian Government procurement auditor (GeM / CPWD / Railways). "
        "Analyze the tender document / Bill of Quantities (BOQ) text and extract distinct technical items. "
        "For each item, identify: "
        "1. 'item_id': integer index (1, 2, ...) "
        "2. 'description': exact technical description of the product/material. "
        "3. 'cited_standard': any Indian Standard cited (e.g. 'IS 694:1990', 'IS 269', 'IS 7098 (Part 1)') or null if no standard is cited. "
        "Output strictly valid JSON with key 'items' containing the array. Do not output markdown codeblocks or conversational text."
    )

    # Limit text to first 8,000 characters if very long
    clipped_text = tender_text[:8000]

    try:
        wrapper = get_groq_wrapper()
        content = wrapper.create_chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"TENDER TEXT:\n{clipped_text}"}
            ],
            model=settings.GROQ_MODEL,
            temperature=0.0,
            max_tokens=800,
            prompt_version="line_items_v1"
        )
        content = content.strip()
        # Clean any surrounding markdown block if present
        if content.startswith("```"):
            content = re.sub(r"^```(json)?\n", "", content)
            content = re.sub(r"\n```$", "", content)
        
        parsed = json.loads(content)
        items = parsed.get("items", [])
        if not items and isinstance(parsed, list):
            items = parsed
        return items
    except Exception as e:
        logger.error(f"Groq line-item extraction failed: {e}. Falling back to regex line parser.")
        # Fallback regex parser for simple lists
        items = []
        lines = [ln.strip() for ln in tender_text.split("\n") if ln.strip()]
        idx = 1
        for line in lines:
            if len(line) < 15:
                continue
            # Look for IS pattern
            m = re.search(r"\bIS\s*\d+(\s*\([^\)]+\))?(\s*:\s*\d{4})?\b", line, re.IGNORECASE)
            cited = m.group(0) if m else None
            items.append({
                "item_id": idx,
                "description": line,
                "cited_standard": cited
            })
            idx += 1
            if idx > 10:
                break
        return items


def check_standard_lineage(cited_standard: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Checks if a cited standard is superseded, outdated, or amalgamated in Supabase.
    Returns: (is_superseded, newer_standard, remark)
    """
    if not cited_standard:
        return False, None, None

    cleaned = cited_standard.strip()
    # Normalize base number e.g. "IS 694:1990" -> base "IS694", year 1990
    m_yr = re.search(r":\s*(\d{4})", cleaned)
    cited_year = int(m_yr.group(1)) if m_yr else None
    base_num = re.sub(r":\s*\d{4}$", "", cleaned).strip().replace(" ", "").upper()

    with get_db_cursor() as cur:
        # 1. Check direct match in standards table
        cur.execute("""
            SELECT standard_number, year, is_status_label, withdraw_status, superseded_by_newer
            FROM standards
            WHERE base_number = %s;
        """, (base_num,))
        rows = cur.fetchall()

        if rows:
            for sn, cur_year, status_label, withdraw_st, superseded_by in rows:
                # If a specific year was cited and current year is greater
                if cited_year and cur_year and cited_year < cur_year:
                    return True, sn, f"Edition cited ({cited_year}) is superseded by current revision ({cur_year})."
                if withdraw_st or status_label == "Withdrawn":
                    newer = superseded_by or sn
                    return True, newer, f"Standard is marked as Withdrawn/Superseded by {newer}."

        # 2. Check standard_lineage table for amalgamations (e.g. IS 8112 -> IS 269)
        cur.execute("""
            SELECT standard_number, relationship
            FROM standard_lineage
            WHERE related_base_number = %s OR related_standard_raw ILIKE %s
            LIMIT 1;
        """, (base_num, f"%{cleaned}%"))
        lineage_row = cur.fetchone()
        if lineage_row:
            active_std, rel = lineage_row
            return True, active_std, f"Historical standard has been {rel} into current standard {active_std}."

    return False, None, None


def check_engineering_contradiction(description: str, cited_standard: str) -> Optional[str]:
    """Checks if description contains material parameters conflicting with the cited standard."""
    if not cited_standard:
        return None

    desc_lower = description.lower()
    for rule in CONTRADICTION_RULES:
        if re.search(rule["pattern"], desc_lower):
            for conf_std in rule["conflicting_standards"]:
                if conf_std.upper() in cited_standard.upper():
                    return rule["reason"]
    return None


def audit_tender_items(items: List[Dict[str, Any]]) -> AuditReport:
    """
    Core tender auditing engine.
    Audits every line item, runs diff analysis, and calculates statutory compliance scores.
    """
    t_start = time.time()
    embed_model = embedding_service()

    line_items: List[AuditLineItem] = []
    compliant_count = 0
    outdated_count = 0
    missing_count = 0
    conflict_count = 0
    total_qco_applicable = 0
    compliant_qco_count = 0

    for idx, item in enumerate(items, start=1):
        desc = item.get("description", "").strip()
        cited = item.get("cited_standard")
        if cited:
            cited = cited.strip()

        # 1. Run recommendation engine to find true statutory standard
        vec = embed_model.embed_query(desc)
        candidates = search_candidates_pgvector(vec, limit=8)
        ranked = rerank_candidates(desc, desc, candidates)
        top1 = ranked[0]

        rec_sn = top1["standard_number"]
        rec_title = top1["title"]
        qco_mandatory = bool(top1.get("qco_ministry")) or (top1.get("certification") == "Mandatory")
        conf_score = top1["final_score"]

        if qco_mandatory:
            total_qco_applicable += 1

        # 2. Check for Engineering Contradiction
        conflict_msg = check_engineering_contradiction(desc, cited)
        if conflict_msg:
            status = "CONTRADICTION"
            action = conflict_msg
            explanation = f"Specification conflict: Material described in tender contradicts the technical scope of cited standard {cited}."
            conflict_count += 1

        # 3. Check for Missing Citation
        elif not cited or cited.lower() in ("null", "none", "n/a", "-"):
            status = "MISSING"
            action = f"Mandate compliance with {rec_sn} ('{rec_title}') and require valid BIS Scheme-I licence."
            explanation = f"No Indian Standard cited for this item. Mandatory statutory standard identified is {rec_sn}."
            missing_count += 1

        # 4. Check for Outdated / Superseded Standard
        else:
            is_superseded, newer_std, lineage_remark = check_standard_lineage(cited)
            if is_superseded:
                status = "OUTDATED"
                target_std = newer_std or rec_sn
                action = f"Update citation from outdated {cited} to current active standard {target_std}."
                explanation = lineage_remark or f"Cited standard {cited} is superseded by current revision {target_std}."
                outdated_count += 1
            else:
                # 5. Check if cited standard matches recommended or base number matches
                cited_base = re.sub(r":\s*\d{4}$", "", cited).strip().replace(" ", "").upper()
                rec_base = top1["base_number"]

                if cited_base == rec_base or cited in rec_sn or rec_sn in cited:
                    status = "COMPLIANT"
                    action = "Specification is fully aligned with current Indian Standards. No modification required."
                    explanation = f"Cited standard {cited} is active and fully matches the product scope for {rec_sn}."
                    compliant_count += 1
                    if qco_mandatory:
                        compliant_qco_count += 1
                else:
                    # Mismatched standard recommendation
                    status = "OUTDATED"
                    action = f"Verify standard applicability: tender cites {cited}, but procurement engine recommends {rec_sn} based on scope."
                    explanation = f"Cited {cited} differs from primary recommended standard {rec_sn}."
                    outdated_count += 1

        line_items.append(AuditLineItem(
            item_id=idx,
            description=desc,
            cited_standard=cited,
            cited_status=status,
            recommended_standard=rec_sn,
            recommended_title=rec_title,
            action_required=action,
            qco_mandatory=qco_mandatory,
            confidence_score=round(conf_score, 4),
            explanation=explanation
        ))

    total = len(line_items)

    # 6. Calculate Statutory Compliance Metrics
    total_cited = total - missing_count

    # Coverage: proportion of items in tender that cite an Indian Standard
    coverage = round((total_cited / max(total, 1)) * 100, 1)

    # Currency: proportion of cited standards that are current (0% if none cited)
    currency = round((compliant_count / max(total_cited, 1)) * 100, 1) if total_cited > 0 else 0.0

    # QCO Compliance: mandatory items with valid active citations
    qco_compliance = round((compliant_qco_count / max(total_qco_applicable, 1)) * 100, 1) if total_qco_applicable > 0 else 100.0

    # Overall Score (Weighted)
    overall = round((0.40 * coverage) + (0.30 * currency) + (0.30 * qco_compliance), 1)

    # Summary remarks
    if total_cited == 0:
        remarks = "CRITICAL STATUTORY DEFICIENCY: No Indian Standards (BIS) are cited in this tender document. Un-cited procurement of mandatory items violates Quality Control Orders (QCO) and BIS Act 2016."
    elif overall >= 90:
        remarks = "Tender exhibits high statutory compliance. Minimal corrections required before RFP publication."
    elif overall >= 70:
        remarks = "Moderate compliance. Several outdated revisions or un-cited specifications must be corrected prior to issuance."
    else:
        remarks = "CRITICAL NON-COMPLIANCE: Tender contains obsolete standards, engineering contradictions, or un-cited mandatory QCO items. Revisions required under BIS Act 2016."

    t_total = time.time() - t_start

    return AuditReport(
        total_items=total,
        compliant_items=compliant_count,
        outdated_items=outdated_count,
        missing_items=missing_count,
        conflict_items=conflict_count,
        coverage_score=coverage,
        currency_score=currency,
        qco_compliance_score=qco_compliance,
        overall_score=overall,
        summary_remarks=remarks,
        line_items=line_items,
        timings={"total_audit_ms": round(t_total * 1000, 1)}
    )
