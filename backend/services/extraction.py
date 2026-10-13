"""
extraction.py
=============
Groq-powered technical specification extraction engine.
Translates regional terms, strips commercial brand names into generic parameters,
and enforces zero-hallucination structured JSON extraction.
"""

import os
import re
import json
import time
import logging
from typing import Tuple, List, Optional, Dict
from groq import Groq
from app.config import settings
from schemas import ExtractedSpec

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a technical specification extraction engine for Indian Standards (BIS) government procurement.
Your task is to parse unstructured, noisy procurement queries or tender line items and extract structured engineering parameters into strict JSON.

Output JSON Schema:
{
  "product_category": string or null,
  "material": string or null,
  "voltage_rating": string or null,
  "dimensions": string or null,
  "application": string or null,
  "cited_standard_raw": string or null,
  "brand_names_removed": [string, ...]
}

STRICT NON-NEGOTIABLE RULES:
1. Strip commercial brand names (e.g. Havells, Polycab, Finolex, KEI, Anchor, Tata Tiscon, UltraTech, ACC, Jindal, Schneider) and record them in brand_names_removed.
2. Translate Hindi or regional words to English technical terminology (e.g. "बिजली का तार" -> power cable, "सीमेंट" -> cement, "सरिया" / "लोहा" -> reinforcement steel rebar).
3. If the user mentions any cited standard (e.g. "IS 694", "IS 1786:2008"), extract it verbatim in cited_standard_raw.
4. NEVER invent, extrapolate, or hallucinate a value. If a parameter is not explicitly mentioned or clearly implied by engineering definition, use null.
5. Return ONLY a single raw valid JSON object. No explanation, no markdown fence, no preamble."""

# Common Indian brand names regex for pre-extraction & verification
KNOWN_BRANDS = [
    r"\bhavells\b", r"\bpolycab\b", r"\bfinolex\b", r"\brr\s*kabel\b", r"\bkei\b",
    r"\banchor\b", r"\btata\s*tiscon\b", r"\bultratech\b", r"\bambridge\b", r"\bjindal\b",
    r"\bkamdhenu\b", r"\bambuja\b", r"\bacc\b", r"\bdalmia\b", r"\bshree\s*cement\b",
    r"\bphilips\b", r"\bschneider\b", r"\bl&t\b", r"\blarsen\s*(&|and)\s*toubro\b",
    r"\bfinolex\s*pipes\b", r"\bastral\b", r"\bashirvad\b", r"\bsupreme\b"
]


from app.parsers.groq_wrapper import get_groq_wrapper

_extraction_cache: Dict[str, ExtractedSpec] = {}

def get_groq_client():
    return get_groq_wrapper().client


def extract_spec(text: str) -> Tuple[ExtractedSpec, float]:
    """
    Extracts structured technical specification from raw text using Groq LLM.
    Returns: (ExtractedSpec, latency_seconds)
    """
    t_start = time.time()
    clean_text = text.strip()
    if not clean_text:
        return ExtractedSpec(), 0.0

    cache_key = clean_text.lower()
    if cache_key in _extraction_cache:
        cached_spec = _extraction_cache[cache_key]
        return cached_spec, round(time.time() - t_start, 4)

    # 1. Regex check for cited standard e.g. "IS 694:2010"
    is_pattern = re.search(r"\bIS\s*\d+(?:\s*\([^\)]+\))?(?:\s*:\s*\d{4})?\b", clean_text, re.IGNORECASE)
    regex_cited = is_pattern.group(0).strip() if is_pattern else None

    # 2. Identify known brand names locally
    detected_brands = []
    for pb in KNOWN_BRANDS:
        m = re.search(pb, clean_text, re.IGNORECASE)
        if m:
            detected_brands.append(m.group(0).strip())

    try:
        wrapper = get_groq_wrapper()
        t_call_start = time.time()
        raw_output = wrapper.create_chat_completion(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": clean_text}
            ],
            model=settings.GROQ_MODEL,
            temperature=0.0,
            max_tokens=200,
            prompt_version="ext_v1"
        )
        groq_dur_ms = round((time.time() - t_call_start) * 1000, 1)
        raw_output = raw_output.strip()
        logger.info(f"Groq API call succeeded in {groq_dur_ms}ms")

        # Parse JSON
        json_match = re.search(r"\{.*\}", raw_output, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(0))
        else:
            data = {}

        # Merge local brand detection with LLM brand detection
        all_brands = list(set((data.get("brand_names_removed") or []) + detected_brands))

        spec = ExtractedSpec(
            product_category=data.get("product_category"),
            material=data.get("material"),
            voltage_rating=data.get("voltage_rating"),
            dimensions=data.get("dimensions"),
            application=data.get("application"),
            cited_standard_raw=data.get("cited_standard_raw") or regex_cited,
            brand_names_removed=all_brands
        )
        _extraction_cache[cache_key] = spec
    except Exception as e:
        logger.warning(f"Groq extraction failed, using deterministic regex fallback: {e}")
        # Deterministic fallback
        spec = ExtractedSpec(
            product_category=None,
            material="PVC" if re.search(r"\bpvc\b", clean_text, re.I) else ("XLPE" if re.search(r"\bxlpe\b", clean_text, re.I) else None),
            voltage_rating=re.search(r"\b(\d+\s*(?:kv|v))\b", clean_text, re.I).group(1) if re.search(r"\b(\d+\s*(?:kv|v))\b", clean_text, re.I) else None,
            dimensions=None,
            application=None,
            cited_standard_raw=regex_cited,
            brand_names_removed=detected_brands
        )
        _extraction_cache[cache_key] = spec

    latency = time.time() - t_start
    return spec, latency
