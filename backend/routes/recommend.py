"""
recommend.py
============
FastAPI Route Handlers for Phase 1: Recommendation Engine (/api/recommend & /api/extract).
"""

import time
import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from schemas import (
    ExtractRequest, ExtractedSpec, RecommendRequest, RecommendResponse
)
from services.extraction import extract_spec
from services.retrieval import retrieve_recommendations, detect_newer_edition
from app.db import get_db_cursor

router = APIRouter(tags=["Recommendation Engine"])
logger = logging.getLogger(__name__)


@router.post("/extract", response_model=ExtractedSpec)
async def extract_specification(request: ExtractRequest):
    """
    1.1 Extraction Endpoint:
    Takes raw procurement text or tender line item, extracts structured parameters
    using Groq with strict JSON output, strips brands, and translates regional terms.
    """
    raw_text = request.text.strip()
    if not raw_text:
        raise HTTPException(status_code=400, detail="Text cannot be empty.")

    spec, latency = extract_spec(raw_text)
    return spec


@router.post("/recommend", response_model=RecommendResponse)
async def recommend_standards(request: RecommendRequest):
    """
    1.2 - 1.6 Recommendation Endpoint:
    Accepts raw query or pre-extracted spec, performs pgvector cosine search,
    evaluates boundary cutoff, detects dynamic ambiguity, checks material contradictions,
    enforces Rule 2 certification gating, and returns 6 grouped allied reference buckets.
    """
    t_start = time.time()
    
    # 1. Determine extracted spec
    if request.extracted:
        extracted = request.extracted
        raw_query = request.query or extracted.product_category or "procurement item"
        t_extract_ms = 0.0
    elif request.query and request.query.strip():
        raw_query = request.query.strip()
        # If user passed a selected disambiguation option, enrich query
        if request.selected_option:
            raw_query = f"{raw_query} ({request.selected_option})"
        extracted, t_extract = extract_spec(raw_query)
        t_extract_ms = round(t_extract * 1000, 1)
    else:
        raise HTTPException(status_code=400, detail="Either 'query' or 'extracted' spec must be provided.")

    # 2. Retrieve recommendations
    response, timings = retrieve_recommendations(raw_query, extracted, language=request.language or "en")
    timings["extract_ms"] = t_extract_ms
    timings["total_ms"] = round((time.time() - t_start) * 1000, 1)
    response.timings = timings

    return response


@router.get("/test/lineage-fallback")
async def test_lineage_fallback():
    """
    Demonstrates Item 4: base_number self-join fallback for 'latest edition' detection
    on Extended-tier standards that have NO standard_lineage row.
    """
    with get_db_cursor() as cur:
        # Test on IS 432 (Part 1):1982 (Old standard in CED, has newer IS 432 (Part 1):2026, but NO lineage row)
        test_standard_number = "IS 432 (Part 1):1982"
        cur.execute("SELECT id, standard_number, base_number, year FROM standards WHERE standard_number = %s;", (test_standard_number,))
        old_std = cur.fetchone()
        
        if not old_std:
            return {"error": f"Standard {test_standard_number} not found."}
            
        old_id, old_sn, base_no, old_yr = old_std
        
        # Check standard_lineage
        cur.execute("SELECT count(*) FROM standard_lineage WHERE standard_id = %s OR standard_number = %s;", (old_id, old_sn))
        lineage_count = cur.fetchone()[0]
        
        # Run self-join fallback
        detected_newer = detect_newer_edition(cur, old_id, base_no, old_yr)
        
        return {
            "tested_standard": old_sn,
            "year": old_yr,
            "base_number": base_no,
            "lineage_table_rows_found": lineage_count,
            "lineage_table_covered": False if lineage_count == 0 else True,
            "self_join_detected_newer_edition": detected_newer,
            "status": "newer edition exists" if detected_newer else "no newer edition found"
        }
