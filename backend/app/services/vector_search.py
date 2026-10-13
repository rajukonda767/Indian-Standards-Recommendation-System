"""
vector_search.py
================
Pgvector cosine similarity retrieval and 5-factor deterministic hybrid scoring re-ranker.
"""

import math
import logging
from typing import List, Dict, Any
from app.db import get_db_cursor
from app.config import settings

logger = logging.getLogger(__name__)

SYNONYM_GROUPS = [
    {"pvc", "polyvinyl chloride", "fr-pvc"},
    {"copper", "cu", "तांबा", "तांबे"},
    {"wire", "cables/cords", "cable", "conductor", "तार", "केबल"},
    {"fire resistant", "fr", "flame retardant", "heat resistant"},
    {"domestic", "residential", "house", "building", "घर", "वायरींग", "वायरिंग"},
    {"cement", "portland", "pozzolana", "calcined", "hydraulic", "सीमेंट"},
    {"foundation", "structural", "concrete", "mortar", "नींव"},
]

def keyword_boost(query_text: str, standard_row: Dict[str, Any]) -> float:
    """Computes keyword matching score based on technical synonym overlap."""
    combined_standard = " ".join([
        standard_row.get("title", ""),
        standard_row.get("virtual_scope", "") or "",
        standard_row.get("group_name", "") or "",
        standard_row.get("sub_group", "") or "",
    ]).lower()

    q_lower = query_text.lower()
    matches = 0
    total_query_groups = 0

    for group in SYNONYM_GROUPS:
        if any(term in q_lower for term in group):
            total_query_groups += 1
            if any(term in combined_standard for term in group):
                matches += 1

    if total_query_groups == 0:
        return 0.0
    return min(matches / total_query_groups, 1.0)


def title_boost(query_text: str, title: str) -> float:
    """Awards bonus if the core product/material matches the primary standard title."""
    q_lower = query_text.lower()
    t_lower = title.lower()
    score = 0.0
    if ("pvc" in q_lower or "polyvinyl chloride" in q_lower) and ("polyvinyl chloride" in t_lower or "pvc" in t_lower):
        score += 0.5
    if ("cement" in q_lower or "सीमेंट" in q_lower) and "cement" in t_lower:
        score += 0.5
    if ("wire" in q_lower or "cable" in q_lower or "तार" in q_lower) and any(w in t_lower for w in ["cable", "wire", "cord"]):
        score += 0.5
    return min(1.0, score)


def licence_boost(active_licences: int) -> float:
    """Log-scaled market adoption signal (active Scheme-I licences)."""
    if not active_licences or active_licences <= 0:
        return 0.0
    return min(1.0, math.log10(1 + active_licences) / 3.5)


def mandatory_qco_boost(standard_row: Dict[str, Any]) -> float:
    """Returns 1.0 if standard has a mandatory Quality Control Order or mandatory certification."""
    qco = (standard_row.get("qco_ministry") or "").strip()
    cert = (standard_row.get("certification") or "").strip().upper()
    if qco or "MANDATORY" in cert:
        return 1.0
    return 0.0


def search_candidates_pgvector(query_vector: List[float], limit: int = 15) -> List[Dict[str, Any]]:
    """Runs pgvector cosine distance search on Supabase."""
    vec_str = f"[{','.join(f'{x:.6f}' for x in query_vector)}]"
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT
                id,
                standard_number,
                base_number,
                title,
                dept,
                certification,
                qco_ministry,
                active_licences,
                is_status_label,
                group_name,
                sub_group,
                virtual_scope,
                1 - (scope_embedding <=> %s::vector) AS cosine_sim
            FROM standards
            WHERE scope_embedding IS NOT NULL
            ORDER BY scope_embedding <=> %s::vector ASC
            LIMIT %s;
        """, (vec_str, vec_str, limit))
        rows = cur.fetchall()

    cols = [
        "id", "standard_number", "base_number", "title", "dept", "certification",
        "qco_ministry", "active_licences", "is_status_label",
        "group_name", "sub_group", "virtual_scope", "cosine_sim"
    ]
    return [dict(zip(cols, r)) for r in rows]


def rerank_candidates(
    raw_query: str,
    normalized_query: str,
    candidates: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Applies the validated 5-Factor Hybrid Scoring Formula:
    60% CosineSim + 15% KeywordBoost + 10% TitleMatch + 10% MandatoryQCO + 5% LicenceAdoption
    """
    combined_query = f"{raw_query} {normalized_query}"
    for c in candidates:
        kw_b = keyword_boost(combined_query, c)
        tit_b = title_boost(combined_query, c["title"])
        qco_b = mandatory_qco_boost(c)
        lic_b = licence_boost(c.get("active_licences") or 0)

        final_score = (
            0.60 * c["cosine_sim"]
            + 0.15 * kw_b
            + 0.10 * tit_b
            + 0.10 * qco_b
            + 0.05 * lic_b
        )
        c["keyword_boost"] = round(kw_b, 4)
        c["title_boost"] = round(tit_b, 4)
        c["qco_boost"] = qco_b
        c["licence_boost"] = round(lic_b, 4)
        c["final_score"] = round(final_score, 4)

    candidates.sort(key=lambda x: x["final_score"], reverse=True)
    return candidates
