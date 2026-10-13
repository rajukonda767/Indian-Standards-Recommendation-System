"""
recommend.py
============
FastAPI Router for the Recommendation Engine endpoint (/api/recommend).
"""

import time
import re
import logging
from fastapi import APIRouter, HTTPException, Depends
from app.config import settings
from app.models.recommend import (
    RecommendRequest,
    RecommendResponse,
    StandardCandidate,
    Disambiguation
)
from app.services.embedding import embedding_service
from app.services.vector_search import (
    search_candidates_pgvector,
    rerank_candidates
)
from app.services.graph_service import (
    get_normative_compliance_suite,
    get_licence_info
)
from app.services.groq_service import (
    normalize_query_groq,
    synthesize_justification_groq,
    generate_disambiguation_groq,
    generate_tender_clause
)

router = APIRouter(prefix="/recommend", tags=["Recommendation"])
logger = logging.getLogger(__name__)

@router.post("", response_model=RecommendResponse)
async def recommend_standard(request: RecommendRequest):
    t_start = time.time()
    raw_query = request.query.strip()
    if not raw_query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    # 0. If user provided a selected disambiguation option, enrich the query
    active_query = raw_query
    if request.selected_option:
        active_query = f"{raw_query} ({request.selected_option})"

    # 1. Groq Query Normalization (Brand stripping, Hindi/regional translation, spec expansion)
    normalized_query, t_norm = normalize_query_groq(active_query)

    # 2. Local GPU Embedding (BAAI/bge-m3 on RTX 3050 CUDA in FP16)
    t0 = time.time()
    model = embedding_service()
    query_vector = model.embed_query(normalized_query)
    t_embed = time.time() - t0

    # 3. Pgvector Top-15 Cosine Search on Supabase
    t0 = time.time()
    candidates_raw = search_candidates_pgvector(query_vector, limit=15)
    t_vector = time.time() - t0

    if not candidates_raw:
        raise HTTPException(status_code=500, detail="No standards found in database.")

    # 4. Domain Boundary Guard (Cosine < 0.45)
    top_cosine = candidates_raw[0]["cosine_sim"]
    if top_cosine < settings.BOUNDARY_THRESHOLD:
        return RecommendResponse(
            out_of_domain=True,
            boundary_message=(
                f"Your query '{raw_query}' (similarity {top_cosine:.4f}) does not match any Indian Standard "
                f"in the CED, ETD, or MTD repositories. This item appears outside the scope of indexed BIS standards."
            ),
            query=raw_query,
            normalized_query=normalized_query,
            disambiguation=Disambiguation(is_ambiguous=False),
            timings={
                "norm_ms": round(t_norm * 1000, 1),
                "embed_ms": round(t_embed * 1000, 1),
                "vector_ms": round(t_vector * 1000, 1),
                "total_ms": round((time.time() - t_start) * 1000, 1)
            }
        )

    # 5. Deterministic 5-Factor Hybrid Re-ranking
    ranked = rerank_candidates(raw_query, normalized_query, candidates_raw)
    top1 = ranked[0]
    top2 = ranked[1] if len(ranked) > 1 else None

    # 6. Interactive Ambiguity Guard (Delta < 0.05 on underspecified query)
    is_ambiguous = False
    question = None
    options = []
    delta = round(top1["final_score"] - top2["final_score"], 4) if top2 else 1.0

    if delta < settings.AMBIGUITY_THRESHOLD and not request.selected_option:
        # Check if critical parameters are absent
        q_lower = raw_query.lower()
        needs_param = not re.search(r"\d+(\.\d+)?\s*(sq\.?\s*mm|mm2|kv|v\b|amp|a\b|mpa)", q_lower)
        needs_context = not re.search(r"\b(building|structure|underground|overhead|panel|domestic|industrial)\b", q_lower)
        if needs_param or needs_context:
            is_ambiguous = True
            question, options = generate_disambiguation_groq(raw_query, top1, top2)

    # 7. Graph Traversal: Normative Compliance Suite & Licences
    t0 = time.time()
    compliance_suite = get_normative_compliance_suite(top1["id"])
    licence_info = get_licence_info(top1["id"])
    t_graph = time.time() - t0

    # 8. Zero-Hallucination Grounded Justification
    justification, t_groq_synth = synthesize_justification_groq(
        user_query=raw_query,
        top_standard=top1,
        licence_info=licence_info,
        allied_list=[{"ref_number": a.ref_number, "ref_title": a.ref_title} for a in compliance_suite.test_methods]
    )

    # 9. Ready-to-Paste Statutory Tender Technical Clause (BIS Act 2016)
    tender_clause = generate_tender_clause(top1, compliance_suite.test_methods)

    # 10. Format Candidates
    primary_candidate = StandardCandidate(
        id=top1["id"],
        standard_number=top1["standard_number"],
        title=top1["title"],
        dept=top1["dept"],
        is_status=top1.get("is_status_label") or "Current",
        qco_ministry=top1.get("qco_ministry"),
        active_licences=top1.get("active_licences", 0),
        cosine_similarity=round(top1["cosine_sim"], 4),
        keyword_boost=top1["keyword_boost"],
        title_boost=top1["title_boost"],
        qco_boost=top1["qco_boost"],
        licence_boost=top1["licence_boost"],
        final_score=top1["final_score"]
    )

    alternatives = []
    for alt in ranked[1:4]:
        alternatives.append(StandardCandidate(
            id=alt["id"],
            standard_number=alt["standard_number"],
            title=alt["title"],
            dept=alt["dept"],
            is_status=alt.get("is_status_label") or "Current",
            qco_ministry=alt.get("qco_ministry"),
            active_licences=alt.get("active_licences", 0),
            cosine_similarity=round(alt["cosine_sim"], 4),
            keyword_boost=alt["keyword_boost"],
            title_boost=alt["title_boost"],
            qco_boost=alt["qco_boost"],
            licence_boost=alt["licence_boost"],
            final_score=alt["final_score"]
        ))

    t_total = time.time() - t_start

    return RecommendResponse(
        out_of_domain=False,
        query=raw_query,
        normalized_query=normalized_query,
        primary_standard=primary_candidate,
        compliance_suite=compliance_suite,
        alternative_candidates=alternatives,
        disambiguation=Disambiguation(
            is_ambiguous=is_ambiguous,
            confidence_gap=delta,
            question=question,
            options=options
        ),
        grounded_justification=justification,
        tender_clause=tender_clause,
        timings={
            "norm_ms": round(t_norm * 1000, 1),
            "embed_ms": round(t_embed * 1000, 1),
            "vector_ms": round(t_vector * 1000, 1),
            "graph_ms": round(t_graph * 1000, 1),
            "groq_ms": round(t_groq_synth * 1000, 1),
            "total_ms": round(t_total * 1000, 1)
        }
    )
