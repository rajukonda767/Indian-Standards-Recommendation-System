"""
retrieval.py
============
Vector retrieval, keyword re-ranking, out-of-domain cutoff,
dynamic ambiguity resolution, and allied standard graph traversal.
"""

import time
import logging
import re
from typing import List, Dict, Any, Tuple, Optional
from app.db import get_db_cursor
from app.services.embedding import embedding_service
from schemas import (
    ExtractedSpec, PrimaryCandidate, CertificationInfo,
    AlliedGroup, AlliedItem, RecommendResponse, DisambiguationOption
)
from services.contradiction import check_contradiction
from services.trade_synonyms import expand_trade_synonyms

import json
import os
from groq import Groq
from app.config import settings

logger = logging.getLogger(__name__)

# Groq client (reuses same key as extraction.py)
_groq_client: Optional[Groq] = None


def _get_groq() -> Groq:
    global _groq_client
    if _groq_client is None:
        _groq_client = Groq(api_key=settings.GROQ_API_KEY)
    return _groq_client


# Caches
_disambiguation_cache: Dict[str, Tuple[str, List[DisambiguationOption], str]] = {}
_why_cache: Dict[str, str] = {}
_differentiator_cache: Dict[str, Dict[str, str]] = {}

# Out-of-domain threshold (tuned to 0.50 after real empirical testing:
# separates out-of-domain queries like 'medical X-ray' at 0.49 from valid short queries like 'cable 150 sq mm' at 0.528)
BOUNDARY_THRESHOLD = 0.50

# Ambiguity score difference threshold
AMBIGUITY_THRESHOLD = 0.05


def detect_newer_edition(cur, standard_id: int, base_number: str, year: Optional[int]) -> Optional[str]:
    """
    Detects if a newer edition exists in the standards database.
    Checks:
    1. standard_lineage table (for 258 explicitly linked standards).
    2. base_number self-join fallback on standards table (covers all 5,585 standards).
    """
    # 1. Check standard_lineage table
    cur.execute("""
        SELECT related_standard_raw, relationship
        FROM standard_lineage
        WHERE (standard_id = %s OR standard_number = %s)
          AND relationship IN ('SUPERSEDED_BY', 'AMALGAMATED_INTO')
        LIMIT 1;
    """, (standard_id, base_number))
    row = cur.fetchone()
    if row and row[0]:
        return str(row[0])

    # 2. Self-join fallback on base_number in standards table
    if base_number and year:
        cur.execute("""
            SELECT standard_number, year
            FROM standards
            WHERE base_number = %s
              AND year > %s
              AND (is_status_label IN ('Current', 'Published') OR withdraw_status = FALSE)
            ORDER BY year DESC, id DESC
            LIMIT 1;
        """, (base_number, year))
        newer = cur.fetchone()
        if newer:
            return str(newer[0])

    return None


def fetch_allied_standards(cur, primary_standard_id: int) -> AlliedGroup:
    """
    Queries standard_references for primary_standard_id and maps
    rows by edge_type into the 6 exact named buckets from the Problem Statement.
    """
    cur.execute("""
        SELECT ref_standard_number, ref_title, edge_type, referenced_status, latest_edition_year
        FROM standard_references
        WHERE primary_standard_id = %s
        ORDER BY edge_type ASC, ref_standard_number ASC;
    """, (primary_standard_id,))
    rows = cur.fetchall()

    group = AlliedGroup()

    for ref_sn, title, edge_type, status, lat_yr in rows:
        sn_clean = (ref_sn or "").strip()
        title_clean = (title or "").strip()
        etype_clean = (edge_type or "REFERENCED_UNKNOWN").upper()

        item = AlliedItem(
            standard_number=sn_clean,
            title=title_clean,
            edge_type=etype_clean,
            category=etype_clean,
            status=status,
            latest_edition_year=lat_yr
        )

        if etype_clean == "TEST_METHOD":
            group.test_methods.append(item)
        elif etype_clean == "TERMINOLOGY":
            group.terminology.append(item)
        elif etype_clean == "SAFETY_STANDARD":
            group.safety_standards.append(item)
        elif etype_clean == "INSTALLATION_CODE":
            group.installation_standards.append(item)
        elif etype_clean == "COMPONENT_PRODUCT":
            group.related_product_standards.append(item)
        else:
            group.normative_references.append(item)

    return group


def generate_dynamic_disambiguation(
    top_candidates: List[Dict[str, Any]],
    extracted: ExtractedSpec,
    raw_query: str
) -> Tuple[str, List[DisambiguationOption], str]:
    """
    Groq-powered disambiguation engine.
    Returns (question, [DisambiguationOption], custom_option_text).
    Cached per (raw_query, frozenset of top standard_numbers).
    Fallback to template-based logic if Groq unavailable.
    """
    # Deduplicate candidates by base number, take top 3
    unique_candidates: List[Dict[str, Any]] = []
    seen_bases = set()
    for c in top_candidates:
        b = c.get("base_number") or c["standard_number"]
        if b not in seen_bases:
            seen_bases.add(b)
            unique_candidates.append(c)
        if len(unique_candidates) >= 3:
            break
    if len(unique_candidates) < 2:
        unique_candidates = top_candidates[:3]

    # Cache key
    cache_key = f"{raw_query.lower().strip()}|{','.join(c['standard_number'] for c in unique_candidates)}"
    if cache_key in _disambiguation_cache:
        return _disambiguation_cache[cache_key]

    def _strip_is_references(text: str) -> str:
        if not text:
            return ""
        import re
        # Remove (IS 694/1554) or (IS: 7098) or (IS ...)
        cleaned = re.sub(r"\s*\(\s*IS\b[^)]*\)", "", text, flags=re.IGNORECASE)
        # Remove standalone IS 694 or IS : 7098
        cleaned = re.sub(r"\bIS\s*[:\d][\w\s/().:-]*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s{2,}", " ", cleaned)
        cleaned = re.sub(r"\s+([?,.;])", r"\1", cleaned)
        return cleaned.strip()

    subject = extracted.product_category or extracted.material or raw_query.strip()

    # Build candidate summary for Groq
    candidates_json = [
        {
            "standard_number": c["standard_number"],
            "title": c["title"],
            "group_name": c.get("group_name") or "",
            "dept": c.get("dept") or "",
        }
        for c in unique_candidates
    ]

    system_prompt = (
        "You are an expert in Indian Bureau of Standards (BIS) procurement specifications. "
        "Given an ambiguous procurement query and a list of matching IS standards, output JSON "
        "to help a government procurement officer choose the right standard.\n\n"
        "Rules:\n"
        "1. The 'question' must be a concise, officer-friendly question (max 20 words) identifying WHAT specification or application they need to clarify.\n"
        "   CRITICAL: Do NOT mention any standard numbers, 'IS', or codes in the 'question' or in option 'label's (e.g. say 'Is the cable PVC insulated or XLPE insulated?', NEVER 'IS 694/1554 or IS 7098').\n"
        "2. Provide EXACTLY 3 distinct options corresponding to the top candidate specifications. Each option 'label' must be a short human-readable description of WHAT the specification covers "
        "(NOT the raw IS title string, and NEVER include 'IS' or standard numbers in the label). Examples: 'PVC insulated unsheathed/sheathed cables up to 1100V', "
        "'PVC insulated heavy duty cables up to 1100V', 'XLPE insulated cables up to 1100V'.\n"
        "3. 'rewritten_query' must be a complete, unambiguous procurement query ready to resubmit (include material, application, grade, dimensions if applicable).\n"
        "4. 'custom_option_text' is the label for the free-text 'something else' option (do not mention standard numbers or 'IS').\n"
        "Output ONLY valid JSON, no markdown, no explanation with exactly 3 options:\n"
        '{"question": "...", "options": [{"label": "...", "standard_number": "...", "rewritten_query": "..."}, {"label": "...", "standard_number": "...", "rewritten_query": "..."}, {"label": "...", "standard_number": "...", "rewritten_query": "..."}], "custom_option_text": "..."}'
    )

    user_msg = (
        f"Procurement query: \"{raw_query}\"\n"
        f"Extracted subject: \"{subject}\"\n"
        f"Candidate standards:\n{json.dumps(candidates_json, indent=2)}"
    )

    try:
        client = _get_groq()
        resp = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.2,
            max_tokens=512,
        )
        raw = resp.choices[0].message.content or ""
        # Strip markdown code fences if present
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw[raw.find("{"):raw.rfind("}") + 1]
        data = json.loads(raw)
        question: str = _strip_is_references(data.get("question", f"Which type of {subject} do you need?"))
        custom_option_text: str = _strip_is_references(data.get("custom_option_text", f"Something else — specify custom grade or application for {subject}"))
        options: List[DisambiguationOption] = []
        for opt in data.get("options", []):
            clean_label = _strip_is_references(opt.get("label", ""))
            if not clean_label:
                clean_label = opt.get("label", "Standard specification")
            options.append(DisambiguationOption(
                label=clean_label,
                standard_number=opt.get("standard_number", ""),
                rewritten_query=opt.get("rewritten_query", raw_query),
            ))

        # Guarantee at least 3 options if candidates are available
        if len(options) < 3 and len(unique_candidates) >= 3:
            used_sns = {opt.standard_number for opt in options}
            for c in unique_candidates:
                if c["standard_number"] not in used_sns:
                    clean_t = _strip_is_references(c["title"])
                    title_trimmed = clean_t[:65] + "..." if len(clean_t) > 68 else clean_t
                    options.append(DisambiguationOption(
                        label=title_trimmed,
                        standard_number=c["standard_number"],
                        rewritten_query=f"{raw_query} conforming to {c['standard_number']}",
                    ))
                    used_sns.add(c["standard_number"])
                if len(options) >= 3:
                    break

        logger.info(f"Groq disambiguation generated {len(options)} options for query '{raw_query}' (IS references stripped)")

    except Exception as e:
        logger.warning(f"Groq disambiguation failed ({e}), using template fallback")
        question = f"Multiple specifications match '{subject}'. Please select the specific application or type required:"
        custom_option_text = f"Something else — specify custom grade, dimensions, or application for {subject}"
        options = []
        for c in unique_candidates:
            clean_t = _strip_is_references(c["title"])
            title_trimmed = clean_t[:72] + "..." if len(clean_t) > 75 else clean_t
            options.append(DisambiguationOption(
                label=title_trimmed,
                standard_number=c["standard_number"],
                rewritten_query=f"{raw_query} conforming to {c['standard_number']}",
            ))

    result = (question, options, custom_option_text)
    _disambiguation_cache[cache_key] = result
    return result


def build_grounded_why(
    candidate: Dict[str, Any],
    extracted: ExtractedSpec,
    confidence_pct: float,
    raw_cosine_sim: float,
    raw_query: str = "",
    lang: str = "en"
) -> str:
    """
    Groq-powered officer-friendly why-text (1-2 sentences).
    Cached per (standard_number, raw_query, lang).
    Supports Telugu ('te'), Hindi ('hi'), and English ('en').
    Falls back to factual template if Groq unavailable.
    """
    sn = candidate["standard_number"]
    title = candidate["title"]
    status = candidate.get("is_status_label") or "Current"
    dept = candidate.get("dept") or "Technical Sector"
    licences = candidate.get("active_licences") or 0
    qco = candidate.get("qco_ministry")

    target_lang = (lang or "en").lower().strip()
    cache_key = f"{sn}|{raw_query.lower().strip()}|{target_lang}"
    if cache_key in _why_cache:
        return _why_cache[cache_key]

    # Build context for Groq
    context_parts = [
        f"Standard: {sn}",
        f"Title: {title}",
        f"Status: {status}",
        f"Department: {dept}",
    ]
    if licences > 0:
        context_parts.append(f"Active ISI licences: {licences}")
    if qco:
        context_parts.append(f"Mandatory QCO by: {qco}")
    if extracted.material:
        context_parts.append(f"Specified material: {extracted.material}")
    if extracted.application:
        context_parts.append(f"Application: {extracted.application}")

    if target_lang == "te":
        system_prompt = (
            "You are a BIS standards expert helping an Indian government procurement officer. "
            "Write 1-2 clear, natural sentences ONLY in Telugu (తెలుగు) explaining WHY this Indian Standard is the right recommendation "
            "for the procurement query. Keep all Indian Standard numbers (e.g. IS 7098 (Part 1):2025) and technical abbreviations in Latin script. "
            "Focus on: what the standard covers, why it matches the material/application, "
            "and any mandatory certification (ISI Mark / QCO) if applicable. "
            "Keep it under 60 words."
        )
    elif target_lang == "hi":
        system_prompt = (
            "You are a BIS standards expert helping an Indian government procurement officer. "
            "Write 1-2 clear, natural sentences ONLY in Hindi (हिन्दी) explaining WHY this Indian Standard is the right recommendation "
            "for the procurement query. Keep all Indian Standard numbers (e.g. IS 7098 (Part 1):2025) and technical abbreviations in Latin script. "
            "Focus on: what the standard covers, why it matches the material/application, "
            "and any mandatory certification (ISI Mark / QCO) if applicable. "
            "Keep it under 60 words."
        )
    else:
        system_prompt = (
            "You are a BIS standards expert helping a government procurement officer. "
            "Write 1-2 clear, plain-English sentences explaining WHY this Indian Standard is the right recommendation "
            "for the procurement query. Do NOT mention internal scores, cosine similarity, or vector search. "
            "Focus on: what the standard covers, why it matches the material/application, "
            "and any mandatory certification (ISI Mark / QCO) if applicable. "
            "Keep it under 60 words. Write in third person about the standard."
        )
    lang_suffix = ""
    if target_lang == "te":
        lang_suffix = "\n\n(Write strictly in Telugu / కేవలం తెలుగులోనే రాయండి):"
    elif target_lang == "hi":
        lang_suffix = "\n\n(Write strictly in Hindi / केवल हिन्दी में लिखें):"

    user_msg = (
        f"Procurement query: \"{raw_query}\"\n"
        f"Standard context:\n" + "\n".join(context_parts) +
        lang_suffix
    )

    try:
        client = _get_groq()
        resp = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.1,
            max_tokens=120,
        )
        why_text = (resp.choices[0].message.content or "").strip()
        # Remove leading think tags if model emits them
        if why_text.startswith("<think>"):
            why_text = why_text[why_text.find("</think>") + 8:].strip()
        if not why_text:
            raise ValueError("empty response")
    except Exception as e:
        logger.warning(f"Groq why-text failed for {sn} ({e}), using factual template")
        raw_pct = round(min(max(raw_cosine_sim, 0.0), 1.0) * 100, 1)
        boost_pct = round(max(confidence_pct - raw_pct, 0.0), 1)
        boost_note = f" (includes +{boost_pct:.1f}% keyword relevance boost)" if boost_pct > 0 else ""

        if target_lang == "te":
            parts = [
                f"{sn} ప్రమాణం '{title}' కోసం స్పెసిఫికేషన్‌లను నిర్దేశిస్తుంది మరియు ఇది BIS లో {status} గా ఉంది."
            ]
            if licences > 0:
                parts.append(f"దీనికి BIS పథకం కింద {licences} తయారీదారు లైసెన్సులు ఉన్నాయి.")
            if qco:
                parts.append(f"ఇది {qco} జారీ చేసిన తప్పనిసరి క్వాలిటీ కంట్రోల్ ఆర్డర్ (QCO) పరిధిలోకి వస్తుంది.")
            why_text = " ".join(parts)
        elif target_lang == "hi":
            parts = [
                f"{sn} मानक '{title}' के लिए विनिर्देश निर्धारित करता है और यह BIS में {status} है।"
            ]
            if licences > 0:
                parts.append(f"इसके तहत BIS स्कीम के अंतर्गत {licences} निर्माता लाइसेंस हैं।")
            if qco:
                parts.append(f"यह {qco} द्वारा जारी अनिवार्य गुणवत्ता नियंत्रण आदेश (QCO) के अंतर्गत आता है।")
            why_text = " ".join(parts)
        else:
            parts = [
                f"Retrieved from {dept} repository. Relevance score: {confidence_pct:.1f}%"
                f" (base vector similarity {raw_pct:.1f}%{boost_note}).",
                f"{sn} officially specifies '{title}' and is currently {status} in the BIS registry."
            ]
            if licences > 0:
                parts.append(f"Supported by {licences} active manufacturer ISI licences under BIS Scheme-I.")
            if qco:
                parts.append(f"Subject to mandatory Quality Control Order (QCO) issued by {qco}.")
            why_text = " ".join(parts)

    _why_cache[cache_key] = why_text
    return why_text


def generate_alternative_differentiators(
    primary: Dict[str, Any],
    alternatives: List[Dict[str, Any]],
    raw_query: str
) -> Dict[str, str]:
    """
    Groq-powered grounded differentiator generator.
    Produces an officer-friendly, data-driven condition for each alternative standard
    explaining when to choose that specification over the primary recommended standard.
    Returns: {standard_number: "If your specification requires..."}
    """
    if not alternatives:
        return {}

    cache_key = f"{primary['standard_number']}|{','.join(a['standard_number'] for a in alternatives)}"
    if cache_key in _differentiator_cache:
        return _differentiator_cache[cache_key]

    alts_payload = [
        {"standard_number": a["standard_number"], "title": a["title"]}
        for a in alternatives
    ]

    system_prompt = (
        "You are an expert technical procurement engineer. "
        "Given the primary recommended standard and a list of alternative candidate standards for a procurement requirement, "
        "write a concise, plain officer-friendly condition (8 to 14 words) for EACH alternative. "
        "Explain WHAT specific engineering condition, application, formulation, or material differs from the primary standard.\n\n"
        "Rules:\n"
        "1. Start each condition with 'If you require...' or 'If your specification calls for...' or 'If the application is for...'\n"
        "2. Ground strictly in the standard's official title and technical scope.\n"
        "3. Do NOT mention 'Indian Standard' or 'Indian Standards' or the IS code number in the condition sentence. Focus purely on technical specification, application, or engineering requirements.\n"
        "4. Output ONLY a valid JSON object mapping standard_number to the condition string:\n"
        '{"IS 13592:2013": "If you require UPVC pipes specifically for indoor soil, waste, and rainwater systems:", ...}'
    )
    user_msg = (
        f"Procurement query: \"{raw_query}\"\n"
        f"Primary recommended standard: {primary['standard_number']} — {primary['title']}\n"
        f"Alternative standards:\n{json.dumps(alts_payload, indent=2)}"
    )

    result_map: Dict[str, str] = {}
    try:
        client = _get_groq()
        resp = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.1,
            max_tokens=256,
        )
        raw = (resp.choices[0].message.content or "").strip()
        if raw.startswith("```"):
            raw = raw[raw.find("{"):raw.rfind("}") + 1]
        data = json.loads(raw)
        for a in alternatives:
            sn = a["standard_number"]
            if sn in data and isinstance(data[sn], str) and data[sn].strip():
                val = data[sn].strip()
                if not val.endswith(":"):
                    val = val + ":"
                result_map[sn] = val
    except Exception as e:
        logger.warning(f"Groq alternative differentiator failed ({e}), using grounded template")

    # High-quality factual fallbacks based on standard titles
    for a in alternatives:
        sn = a["standard_number"]
        if sn not in result_map:
            t_low = a["title"].lower()
            if "sewerage" in t_low or "underground" in t_low:
                result_map[sn] = "If you require pipes for underground drainage and sewerage systems:"
            elif "soil" in t_low or "waste" in t_low:
                result_map[sn] = "If you need piping for soil, waste, and rainwater discharge inside/outside buildings:"
            elif "corrugated" in t_low:
                result_map[sn] = "If your project requires single-wall corrugated pipes for drainage:"
            elif "borewell" in t_low or "tubewell" in t_low or "casing" in t_low:
                result_map[sn] = "If you are procuring PVC screen and casing pipes for borewells or tubewells:"
            elif "potable" in t_low or "water supply" in t_low or "water supplies" in t_low:
                result_map[sn] = "If pipes are intended for potable drinking water supply distribution:"
            elif "xlpe" in t_low or "crosslinked" in t_low:
                result_map[sn] = "If specifications require crosslinked polyethylene (XLPE) insulated cables:"
            elif "3.3 kv" in t_low or "11 kv" in t_low or "heavy duty" in t_low:
                result_map[sn] = "If your electrical installation operates at medium/high voltage (3.3 kV to 11 kV):"
            elif "53 grade" in t_low or "53" in a["title"]:
                result_map[sn] = "If design specifications mandate 53-grade high-strength Portland cement:"
            elif "pozzolana" in t_low or "ppc" in t_low:
                result_map[sn] = "If you are procuring Portland Pozzolana Cement (PPC) for durable concrete:"
            elif "slag" in t_low or "psc" in t_low:
                result_map[sn] = "If requirements call for Portland Slag Cement (PSC):"
            elif "tmt" in t_low or "deformed" in t_low or "fe 500" in t_low:
                result_map[sn] = "If procuring high-strength deformed TMT steel reinforcement bars:"
            elif "structural" in t_low or "section" in t_low:
                result_map[sn] = f"If procuring {a['title'].split('-')[0].strip()} for structural steelwork:"
            else:
                result_map[sn] = f"If technical requirements call for {a['title'].split('-')[0].strip()}:"

    _differentiator_cache[cache_key] = result_map
    return result_map


def retrieve_recommendations(
    raw_query: str,
    extracted: ExtractedSpec,
    audit_mode: bool = False,
    language: str = "en"
) -> Tuple[RecommendResponse, Dict[str, float]]:
    """
    Full Phase 1 recommendation execution pipeline.
    Returns: (RecommendResponse, timing_dict)
    """
    t_start = time.time()
    timings: Dict[str, float] = {}

    # 1. Expand colloquial Indian trade terms (e.g. GI pipe -> IS 1239, steel angle -> IS 808/IS 2062)
    # Applied as a standalone pre-processing step before vector embedding.
    embed_input = expand_trade_synonyms(raw_query)

    # 2. Local GPU Embedding (BAAI/bge-m3, 1024-dim, FP16)
    t0_embed = time.time()
    model = embedding_service()
    query_vector = model.embed_query(embed_input)
    timings["embed_ms"] = round((time.time() - t0_embed) * 1000, 1)

    # 3. pgvector Cosine Search Top 30
    t0_sql = time.time()
    sql_roundtrips = 0
    with get_db_cursor() as cur:
        vector_str = f"[{','.join(f'{x:.6f}' for x in query_vector)}]"
        sql_roundtrips += 1
        t_vec_start = time.time()
        cur.execute("""
            SELECT 
                s.id, s.standard_number, s.base_number, s.year, s.dept, s.title,
                s.is_status_label, s.withdraw_status, s.certification, s.certification_verified,
                s.qco_ministry, s.source_url, s.group_name, s.sub_group,
                s.active_licences,
                (1 - (s.scope_embedding <=> %s::vector)) AS raw_cosine_sim
            FROM standards s
            WHERE s.scope_embedding IS NOT NULL
            ORDER BY s.scope_embedding <=> %s::vector ASC
            LIMIT 30;
        """, (vector_str, vector_str))
        cols = [desc[0] for desc in cur.description]
        candidates_raw = [dict(zip(cols, row)) for row in cur.fetchall()]
        t_vec_ms = round((time.time() - t_vec_start) * 1000, 1)
        timings["vector_query_ms"] = t_vec_ms
        logger.info(f"Top-30 pgvector cosine query finished in {t_vec_ms}ms")

        # If user explicitly cited a standard (e.g. "IS 7098"), directly fetch and prioritize it.
        # Use PostgreSQL regex ~ with word-boundary to prevent IS 269 matching IS 2690/IS 16269.
        if extracted.cited_standard_raw:
            digits = re.findall(r"\d+", extracted.cited_standard_raw)
            if digits:
                sql_roundtrips += 1
                # Regex: IS<space><digits> followed by space, colon, '(', or end-of-string
                regex_pattern = f"IS\\s*{digits[0]}(\\s|:|\\(|$)"
                cur.execute("""
                    SELECT 
                        s.id, s.standard_number, s.base_number, s.year, s.dept, s.title,
                        s.is_status_label, s.withdraw_status, s.certification, s.certification_verified,
                        s.qco_ministry, s.source_url, s.group_name, s.sub_group,
                        s.active_licences,
                        0.96::float AS raw_cosine_sim
                    FROM standards s
                    WHERE s.standard_number ~ %s
                    ORDER BY s.year DESC
                    LIMIT 3;
                """, (regex_pattern,))
                cited_rows = [dict(zip(cols, row)) for row in cur.fetchall()]
                for cr in reversed(cited_rows):
                    candidates_raw = [c for c in candidates_raw if c["id"] != cr["id"]]
                    candidates_raw.insert(0, cr)

                # Check cross-standard supersession in standard_lineage (e.g. IS 3935 superseded by IS 11384)
                cur.execute("""
                    SELECT 
                        s2.id, s2.standard_number, s2.base_number, s2.year, s2.dept, s2.title,
                        s2.is_status_label, s2.withdraw_status, s2.certification, s2.certification_verified,
                        s2.qco_ministry, s2.source_url, s2.group_name, s2.sub_group,
                        s2.active_licences,
                        0.97::float AS raw_cosine_sim
                    FROM standard_lineage l
                    JOIN standards s2 ON l.standard_id = s2.id
                    WHERE REPLACE(l.related_standard_raw, ' ', '') LIKE %s AND l.relationship = 'SUPERSEDES'
                    ORDER BY s2.year DESC
                    LIMIT 1;
                """, (f"%IS{digits[0]}%",))
                superseding_rows = [dict(zip(cols, row)) for row in cur.fetchall()]
                for sr in reversed(superseding_rows):
                    candidates_raw = [c for c in candidates_raw if c["id"] != sr["id"]]
                    candidates_raw.insert(0, sr)

        # 4. Out-of-domain cutoff (1.3)
        if not candidates_raw or float(candidates_raw[0]["raw_cosine_sim"]) < BOUNDARY_THRESHOLD:
            top_sim = float(candidates_raw[0]["raw_cosine_sim"]) if candidates_raw else 0.0
            timings["vector_ms"] = round((time.time() - t0_sql) * 1000, 1)
            timings["sql_roundtrips"] = sql_roundtrips
            timings["total_ms"] = round((time.time() - t_start) * 1000, 1)
            return RecommendResponse(
                status="out_of_scope",
                message="No standard in our current dataset (5,585 standards across CED, ETD, MTD) matches this description confidently. This item may be outside our indexed sectors.",
                extracted_spec=extracted,
                timings=timings
            ), timings

        # 5. Keyword Boost & Score Calculation
        q_low = raw_query.lower()
        mat_lower = (extracted.material or "").lower()
        cat_lower = (extracted.product_category or "").lower()

        for c in candidates_raw:
            c["raw_cosine_sim"] = float(c["raw_cosine_sim"])
            text_corpus = f"{c['title']} {c['group_name'] or ''} {c['sub_group'] or ''}".lower()
            boost = 0.0

            # Base category & material boost
            if mat_lower and mat_lower in text_corpus:
                boost += 0.05
            if cat_lower and cat_lower in text_corpus:
                boost += 0.04

            # Technical discriminator boosting from raw procurement terms:
            # 1. Insulation / Material precision
            if "pvc" in q_low and ("pvc" in text_corpus or "polyvinyl" in text_corpus):
                boost += 0.08
            if "xlpe" in q_low and ("xlpe" in text_corpus or "crosslinked" in text_corpus):
                boost += 0.08
            # 2. Voltage rating precision & mismatch penalty
            if ("1100" in q_low or "1.1" in q_low or "lv" in q_low) and ("1 100" in text_corpus or "1100" in text_corpus):
                boost += 0.06
            if ("1100" in q_low or "1.1" in q_low or "lv" in q_low) and ("high voltage" in text_corpus or "hv" in text_corpus):
                boost -= 0.15  # Voltage band penalty (e.g. IS 5819 HV standard for LV query)
            elif ("hv" in q_low or "high voltage" in q_low or "11kv" in q_low or "33kv" in q_low) and ("1 100" in text_corpus or "1100" in text_corpus):
                boost -= 0.15
            # 3. Steel bar / rebar / TMT precision
            if "tmt" in q_low and ("deformed" in text_corpus or "reinforcement" in text_corpus):
                boost += 0.08
            # 4. Angle / Structural section precision
            if "angle" in q_low and "angle" in text_corpus:
                boost += 0.08
            if ("angle" in q_low or "beam" in q_low or "channel" in q_low) and ("structural steel" in text_corpus or "hot rolled" in text_corpus):
                boost += 0.06
            # 5. GI / Steel pipe & tube precision
            if ("pipe" in q_low or "tube" in q_low) and ("tubes" in text_corpus or "pipe" in text_corpus or "tubulars" in text_corpus):
                boost += 0.08
            if "gi" in q_low and ("zinc" in text_corpus or "galvanized" in text_corpus or "wrought" in text_corpus or "tubular" in text_corpus):
                boost += 0.06
            # 6. Cement formulation precision
            if "opc" in q_low or "43 grade" in q_low or "53 grade" in q_low:
                if "ordinary portland cement" in text_corpus and "microfine" not in text_corpus:
                    boost += 0.06
            elif "ppc" in q_low and "pozzolana" in text_corpus:
                boost += 0.08
            elif "slag" in q_low and "slag" in text_corpus:
                boost += 0.08

            c["keyword_boost"] = boost
            c["final_score"] = c["raw_cosine_sim"] + boost

        # Sort by final score
        candidates_raw.sort(key=lambda x: x["final_score"], reverse=True)

        # Rank + Margin filter calibrated on gold set:
        # Candidate is kept if: rank == 0 OR (margin from top-1 <= 0.15 AND score >= top_score * 0.80)
        if candidates_raw:
            top_score = candidates_raw[0]["final_score"]
            top_candidates = [
                c for i, c in enumerate(candidates_raw[:5])
                if i == 0 or (top_score - c["final_score"] <= 0.15 and c["final_score"] >= top_score * 0.80)
            ]
        else:
            top_candidates = []

        # Fast Batch self-join + lineage check for latest editions (Single consolidated SQL query)
        top_ids = [c["id"] for c in top_candidates]
        sql_roundtrips += 1
        t_sub_start = time.time()
        cur.execute("""
            WITH latest_editions AS (
                SELECT base_number, standard_number, year
                FROM (
                    SELECT base_number, standard_number, year,
                           ROW_NUMBER() OVER (PARTITION BY base_number ORDER BY year DESC, id DESC) as rn
                    FROM standards
                    WHERE is_status_label IN ('Current', 'Published') OR withdraw_status = FALSE
                ) sub
                WHERE rn = 1
            ),
            newer_self_join AS (
                SELECT s.id AS standard_id, le.standard_number AS newer_standard
                FROM standards s
                JOIN latest_editions le ON s.base_number = le.base_number
                WHERE s.id = ANY(%s) AND s.year < le.year
            ),
            newer_lineage AS (
                SELECT s.id AS standard_id, s2.standard_number AS newer_standard
                FROM standard_lineage l
                JOIN standards s2 ON l.standard_id = s2.id
                JOIN standards s ON s.id = ANY(%s) AND REPLACE(l.related_standard_raw, ' ', '') LIKE '%%' || s.base_number || '%%'
                WHERE l.relationship = 'SUPERSEDES' AND s.base_number NOT IN ('IS', 'IS/') AND s.id != s2.id
            )
            SELECT standard_id, newer_standard FROM newer_self_join
            UNION ALL
            SELECT standard_id, newer_standard FROM newer_lineage;
        """, (top_ids, top_ids))
        newer_map = dict(cur.fetchall())
        t_sub_ms = round((time.time() - t_sub_start) * 1000, 1)
        timings["latest_edition_ms"] = t_sub_ms
        logger.info(f"Batched latest edition & lineage check finished in {t_sub_ms}ms for {len(top_ids)} candidates")

        for c in top_candidates:
            c["superseded_by"] = newer_map.get(c["id"])

        # 6. Ambiguity Detection (Tuned to resolve fully-specified queries confidently)
        top1 = top_candidates[0]
        top2 = top_candidates[1] if len(top_candidates) > 1 else None
        delta = (top1["final_score"] - top2["final_score"]) if top2 else 1.0

        q_clean = raw_query.lower()

        # Check if specification has all critical engineering discriminators
        is_fully_specified = False
        if ("cable" in q_clean or "wire" in q_clean):
            # Cable is fully-specified if it has voltage rating AND (dimensions OR application OR material)
            if extracted.voltage_rating and (extracted.dimensions or extracted.application or "pvc" in q_clean or "xlpe" in q_clean):
                is_fully_specified = True
        elif "cement" in q_clean:
            # Cement is fully-specified if explicit grade/type is specified (OPC, PPC, PSC, 43, 53, etc.)
            if any(k in q_clean for k in ["opc", "ppc", "psc", "slag", "43", "53", "rapid", "white", "portland"]):
                is_fully_specified = True
        elif any(k in q_clean for k in ["steel", "rebar", "bar", "tmt"]):
            # Steel reinforcement is fully-specified if it has grade/type (TMT, 500, deformed) AND dimensions
            if extracted.dimensions and any(k in q_clean for k in ["tmt", "500", "415", "550", "deformed"]):
                is_fully_specified = True

        # Ambiguity rule:
        # A query is ambiguous if:
        # 1. Delta between top candidates is narrow (< AMBIGUITY_THRESHOLD)
        # 2. User has NOT cited a specific standard (not extracted.cited_standard_raw)
        # 3. Query is NOT already fully-specified with critical engineering parameters!
        is_ambiguous = bool(delta < AMBIGUITY_THRESHOLD and not extracted.cited_standard_raw and not is_fully_specified)

        # 7. Build Primary Candidates with Rule 2 Certification Gating & Contradiction Check
        alt_diff_map: Dict[str, str] = {}
        if len(top_candidates) > 1 and not audit_mode:
            alt_diff_map = generate_alternative_differentiators(top_candidates[0], top_candidates[1:], raw_query)

        primary_list: List[PrimaryCandidate] = []
        for c in top_candidates:
            # Rule 1.5 Contradiction Check (Material & Voltage)
            conflict_warning = check_contradiction(
                extracted_material=extracted.material,
                candidate_title=c["title"],
                candidate_number=c["standard_number"],
                extracted_voltage=extracted.voltage_rating
            )

            # Rule 2 Certification Gating
            is_verified = bool(c.get("certification_verified"))
            if is_verified:
                cert_info = CertificationInfo(
                    verified=True,
                    value=c.get("certification") or "Mandatory",
                    qco_ministry=c.get("qco_ministry"),
                    source_url=c.get("source_url")
                )
            else:
                cert_info = CertificationInfo(
                    verified=False,
                    value="Certification status not verified — check BIS portal",
                    qco_ministry=None,
                    source_url=c.get("source_url")
                )

            # Confidence percentage scaled — strictly capped at 100.0%, matches why-text score exactly
            confidence_pct = round(min(max(c["final_score"], 0.10), 1.00) * 100, 1)

            if audit_mode:
                why_text = f"[Audit] {c['standard_number']} specifies '{c['title']}'."
            else:
                why_text = build_grounded_why(c, extracted, confidence_pct, c["raw_cosine_sim"], raw_query, lang=language)

            candidate_obj = PrimaryCandidate(
                standard_id=c["id"],
                standard_number=c["standard_number"],
                title=c["title"],
                confidence=confidence_pct,
                is_status_label=c.get("is_status_label") or "Current",
                superseded_by=c.get("superseded_by"),
                why=why_text,
                conflict_warning=conflict_warning,
                certification=cert_info,
                differentiator=alt_diff_map.get(c["standard_number"])
            )
            primary_list.append(candidate_obj)

        # 8. Allied Standards Grouping for Top Primary Standard
        sql_roundtrips += 1
        t_allied_start = time.time()
        allied_group = fetch_allied_standards(cur, top1["id"])
        t_allied_ms = round((time.time() - t_allied_start) * 1000, 1)
        timings["allied_query_ms"] = t_allied_ms
        logger.info(f"Allied standards query finished in {t_allied_ms}ms for standard id {top1['id']}")

        timings["vector_ms"] = round((time.time() - t0_sql) * 1000, 1)
        timings["sql_total_ms"] = timings["vector_ms"]
        timings["sql_roundtrips"] = sql_roundtrips
        logger.info(f"All {sql_roundtrips} SQL queries completed in {timings['vector_ms']}ms total (vector={timings.get('vector_query_ms')}ms, latest={timings.get('latest_edition_ms')}ms, allied={t_allied_ms}ms)")

        # 9. Handle Ambiguous State Output
        if is_ambiguous:
            if audit_mode:
                q_ambig = f"Multiple specifications match this description."
                opts_ambig = []
                custom_opt_text = None
            else:
                q_ambig, opts_ambig, custom_opt_text = generate_dynamic_disambiguation(candidates_raw[:4], extracted, raw_query)
            timings["total_ms"] = round((time.time() - t_start) * 1000, 1)
            return RecommendResponse(
                status="ambiguous",
                primary=[],
                candidates=primary_list,
                allied=allied_group,
                disambiguation_question=q_ambig,
                disambiguation_options=opts_ambig,
                custom_option_text=custom_opt_text,
                extracted_spec=extracted,
                timings=timings
            ), timings

        timings["total_ms"] = round((time.time() - t_start) * 1000, 1)
        return RecommendResponse(
            status="ok",
            primary=primary_list,
            allied=allied_group,
            disambiguation_question=None,
            disambiguation_options=None,
            extracted_spec=extracted,
            timings=timings
        ), timings
