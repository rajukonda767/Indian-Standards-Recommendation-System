"""
test_recommend.py  -  Milestone 2.1: Recommendation Engine Verification
=========================================================================
SIH-26108 | BIS Standards AI Procurement Copilot
Architecture: Deterministic Rules Engine + Probabilistic AI

Layers:
  1. Query Parameter Extraction & Brand Stripping (Groq Qwen-27B)
  2. BAAI/bge-m3 on RTX 3050 CUDA (FP16) - 1024-dim normalized dense embeddings
  3. Supabase pgvector cosine top-10 retrieval
  4. Hybrid re-ranking (Cosine + Keyword/Synonym + Mandatory QCO Boost)
  5. Edge-case Gates (Domain Boundary Guard + Ambiguity Guard)
  6. Graph Traversal (standard_references + licence_varieties)
  7. Zero-hallucination Groq synthesis (facts-only, 1-2 sentence output)

Run from the project root:
    $env:PYTHONIOENCODING="utf-8"; python backend/test_recommend.py
"""

import os
import sys
import time
import re
import psycopg2
from dotenv import load_dotenv
import torch
from sentence_transformers import SentenceTransformer
from groq import Groq

# Force UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# -----------------------------------------------------------------------------
# 0. ENVIRONMENT SETUP
# -----------------------------------------------------------------------------
if os.path.exists("backend/.env"):
    load_dotenv("backend/.env")
elif os.path.exists(".env"):
    load_dotenv(".env")

DATABASE_URL = os.getenv("DATABASE_URL", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

if not DATABASE_URL:
    print("[ERROR] DATABASE_URL not set."); sys.exit(1)
if not GROQ_API_KEY:
    print("[ERROR] GROQ_API_KEY not set."); sys.exit(1)

if "sslmode" not in DATABASE_URL:
    DATABASE_URL += "?sslmode=require" if "?" not in DATABASE_URL else "&sslmode=require"

# -----------------------------------------------------------------------------
# 1. HARDWARE & MODEL SETUP
# -----------------------------------------------------------------------------
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

print("=" * 80)
print("SIH-26108 | MILESTONE 2.1 - RECOMMENDATION ENGINE VERIFICATION")
print("=" * 80)
print(f"\n[INIT] Hardware: {DEVICE.upper()}", end="")
if DEVICE == "cuda":
    print(f"  ->  {torch.cuda.get_device_name(0)}", end="")
print()

print("[INIT] Loading BAAI/bge-m3 (FP16 on CUDA) ...", end=" ", flush=True)
t0 = time.time()
MODEL = SentenceTransformer("BAAI/bge-m3", device=DEVICE)
if DEVICE == "cuda":
    MODEL.half()
print(f"done in {time.time()-t0:.2f}s")

GROQ_CLIENT = Groq(api_key=GROQ_API_KEY)
GROQ_MODEL = "qwen/qwen3.8-27b"

# -----------------------------------------------------------------------------
# 2. DATABASE CONNECTION
# -----------------------------------------------------------------------------
print("[INIT] Connecting to Supabase ...", end=" ", flush=True)
CONN = psycopg2.connect(
    DATABASE_URL,
    connect_timeout=15,
    keepalives=1,
    keepalives_idle=30,
    keepalives_interval=10,
    keepalives_count=5,
)
CONN.autocommit = True
print("connected.\n")

# -----------------------------------------------------------------------------
# 3. PROBABILISTIC AI: QUERY NORMALIZATION & BRAND STRIPPING (GROQ)
# -----------------------------------------------------------------------------
def normalize_query_groq(raw_query: str) -> tuple[str, float]:
    """
    Normalizes procurement query:
    - Strips proprietary trademarks (Havells, Polycab, Finolex, Tata Tiscon, etc.)
    - Translates non-English (Hindi/regional) to formal technical terms
    - Expands domain acronyms (PVC -> Polyvinyl Chloride, TMT -> Thermo-Mechanically Treated)
    """
    system_prompt = (
        "You are an Indian Standards (BIS) technical specification extractor for procurement. "
        "Given a user procurement query: "
        "1. Remove proprietary brand names (e.g. Havells, Polycab, Finolex, Tata, UltraTech). "
        "2. If query is in Hindi or Indian regional language, translate to English technical specifications. "
        "3. Expand core procurement specifications (e.g., house wiring -> PVC insulated copper wire for domestic building wiring). "
        "4. Output strictly a concise technical search phrase in English without quotation marks or conversational text."
    )
    t0 = time.time()
    try:
        resp = GROQ_CLIENT.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": raw_query}
            ],
            temperature=0.0,
            max_tokens=60
        )
        elapsed = time.time() - t0
        normalized = resp.choices[0].message.content.strip().strip('"')
        return normalized, elapsed
    except Exception as e:
        # Fallback to raw query if API error
        return raw_query, 0.0

# -----------------------------------------------------------------------------
# 4. KEYWORD, TITLE & LICENCE BOOST HELPERS
# -----------------------------------------------------------------------------
SYNONYM_GROUPS = [
    {"pvc", "polyvinyl chloride", "fr-pvc"},
    {"copper", "cu", "तांबा", "तांबे"},
    {"wire", "cables/cords", "cable", "conductor", "तार", "केबल"},
    {"fire resistant", "fr", "flame retardant", "heat resistant"},
    {"domestic", "residential", "house", "building", "घर", "वायरींग", "वायरिंग"},
    {"cement", "portland", "pozzolana", "calcined", "hydraulic", "सीमेंट"},
    {"foundation", "structural", "concrete", "mortar", "नींव"},
]

def keyword_boost(query_text: str, standard_row: dict) -> float:
    """
    Computes keyword matching score based on technical synonym overlap.
    """
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
    import math
    if not active_licences or active_licences <= 0:
        return 0.0
    return min(1.0, math.log10(1 + active_licences) / 3.5)


def mandatory_qco_boost(standard_row: dict) -> float:
    """
    Returns 1.0 if the standard is covered by a Quality Control Order (QCO)
    or has mandatory BIS certification. Returns 0.0 otherwise.
    """
    qco = (standard_row.get("qco_ministry") or "").strip()
    cert = (standard_row.get("certification") or "").strip().upper()
    if qco or "MANDATORY" in cert:
        return 1.0
    return 0.0


# -----------------------------------------------------------------------------
# 5. GRAPH TRAVERSAL HELPERS
# -----------------------------------------------------------------------------
def get_allied_standards(standard_id: int) -> list[dict]:
    """Fetch allied test methods & component standards from standard_references."""
    cur = CONN.cursor()
    cur.execute(
        """
        SELECT r.ref_standard_number, r.ref_title, r.edge_type
        FROM standard_references r
        WHERE r.primary_standard_id = %s
          AND r.edge_type IN ('TEST_METHOD', 'ALLIED', 'COMPONENT', 'REFERENCED_BY',
                              'test_method', 'allied', 'component', 'referenced_by')
        LIMIT 8;
        """,
        (standard_id,),
    )
    rows = cur.fetchall()
    cur.close()
    return [{"ref_number": r[0], "ref_title": r[1], "edge_type": r[2]} for r in rows]


def get_licence_info(standard_id: int) -> dict:
    """Fetch licence variety info from licence_varieties."""
    cur = CONN.cursor()
    cur.execute(
        """
        SELECT lv.total_isi_licences, lv.product_varieties
        FROM licence_varieties lv
        WHERE lv.standard_id = %s
        LIMIT 1;
        """,
        (standard_id,),
    )
    row = cur.fetchone()
    cur.close()
    if row:
        return {"total_isi_licences": row[0], "product_varieties": row[1]}
    return {}

# -----------------------------------------------------------------------------
# 6. GROQ ZERO-HALLUCINATION SYNTHESIS
# -----------------------------------------------------------------------------
def groq_synthesize(
    user_query: str,
    top_standard: dict,
    licence_info: dict,
    allied: list[dict],
) -> tuple[str, float]:
    """
    Calls Groq (qwen/qwen3.8-27b) with strictly retrieved DB facts.
    Returns 1-2 sentence grounded justification.
    """
    allied_text = "; ".join(
        f"{a['ref_number']} ({a['ref_title']})" for a in allied[:3]
    ) or "None listed"

    lic_count = licence_info.get("total_isi_licences", top_standard.get("active_licences", "Unknown"))
    varieties = licence_info.get("product_varieties", "General varieties")
    qco = top_standard.get("qco_ministry", "") or "Not under QCO"

    system_msg = (
        "You are a government procurement compliance assistant for India. "
        "You receive STRUCTURED DATABASE FACTS only. "
        "Your task: write exactly 1-2 sentences starting with 'Matched on' "
        "explaining why this Indian Standard applies to the user's procurement need. "
        "DO NOT mention any standards or facts NOT present in the provided context. "
        "Be concise, technical, and accurate."
    )

    user_msg = (
        f"User procurement query: \"{user_query}\"\n\n"
        f"RETRIEVED DATABASE FACTS:\n"
        f"  Standard Number : {top_standard['standard_number']}\n"
        f"  Title           : {top_standard['title']}\n"
        f"  Department      : {top_standard['dept']}\n"
        f"  Status          : {top_standard.get('is_status_label', 'Current')}\n"
        f"  Mandatory QCO   : {qco}\n"
        f"  Active Licences : {lic_count}\n"
        f"  Product Varieties: {varieties}\n"
        f"  Allied Test Methods: {allied_text}\n\n"
        "Write 1-2 sentences starting with 'Matched on':"
    )

    try:
        t0 = time.time()
        resp = GROQ_CLIENT.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=120,
            temperature=0.0,
        )
        elapsed = time.time() - t0
        text = resp.choices[0].message.content.strip()
        return text, elapsed
    except Exception as e:
        return f"[Groq synthesis error: {e}]", 0.0

# -----------------------------------------------------------------------------
# 7. CORE RECOMMENDATION PIPELINE
# -----------------------------------------------------------------------------
BOUNDARY_THRESHOLD  = 0.45   # Out of domain if max cosine < 0.45
AMBIGUITY_THRESHOLD = 0.05   # Ambiguous if Top1 - Top2 score < 0.05

def recommend(raw_query: str) -> dict:
    t_start = time.time()

    # Step 1: Normalize query via Groq (brand stripping, Hindi translation, spec expansion)
    normalized_query, t_norm = normalize_query_groq(raw_query)

    # Step 2: GPU Embed normalized query
    t0 = time.time()
    q_emb = MODEL.encode([normalized_query], normalize_embeddings=True)[0]
    t_embed = time.time() - t0
    q_vec_str = f"[{','.join(f'{x:.6f}' for x in q_emb)}]"

    # Step 3: pgvector Top-10 cosine search
    t0 = time.time()
    cur = CONN.cursor()
    cur.execute(
        """
        SELECT
            id,
            standard_number,
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
        LIMIT 10;
        """,
        (q_vec_str, q_vec_str),
    )
    rows = cur.fetchall()
    cur.close()
    t_vector = time.time() - t0

    if not rows:
        return {"status": "ERROR", "message": "No embeddings found in database."}

    cols = [
        "id", "standard_number", "title", "dept", "certification",
        "qco_ministry", "active_licences", "is_status_label",
        "group_name", "sub_group", "virtual_scope", "cosine_sim",
    ]
    candidates = [dict(zip(cols, r)) for r in rows]

    # Step 4: Domain Boundary Guard
    top_cosine = candidates[0]["cosine_sim"]
    if top_cosine < BOUNDARY_THRESHOLD:
        return {
            "status": "OUT_OF_DOMAIN",
            "top_cosine_sim": round(top_cosine, 4),
            "message": (
                f"Query does not match any BIS standard in the database "
                f"(max similarity: {top_cosine:.4f} < threshold: {BOUNDARY_THRESHOLD}). "
                "This procurement category is outside BIS repository scope."
            ),
            "timings": {
                "norm_ms": round(t_norm * 1000, 1),
                "embed_ms": round(t_embed * 1000, 1),
                "vector_ms": round(t_vector * 1000, 1),
                "total_ms": round((time.time() - t_start) * 1000, 1),
            },
        }

    # Step 5: Hybrid Re-ranking
    # Combine original and normalized query terms for scoring
    combined_query = f"{raw_query} {normalized_query}"
    for c in candidates:
        kw_b = keyword_boost(combined_query, c)
        tit_b = title_boost(combined_query, c["title"])
        qco_b = mandatory_qco_boost(c)
        lic_b = licence_boost(c.get("active_licences") or 0)

        # 60% Cosine + 15% Keyword + 10% Title Match + 10% Mandatory QCO + 5% Licence Adoption
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
    top1 = candidates[0]
    top2 = candidates[1]

    # Step 6: Ambiguity Guard
    delta = top1["final_score"] - top2["final_score"]
    ambiguous = False
    disambiguation_hint = None

    if delta < AMBIGUITY_THRESHOLD:
        missing_params = []
        q_lower = raw_query.lower()
        if not re.search(r"\d+(\.\d+)?\s*(sq\.?\s*mm|mm2|kv|v\b|amp|a\b|mpa)", q_lower):
            missing_params.append("technical specification (e.g. voltage, cross-section area, grade)")
        if not re.search(r"\b(building|structure|underground|overhead|panel|domestic|industrial)\b", q_lower):
            missing_params.append("application context (e.g. residential, industrial, structural)")

        if missing_params:
            ambiguous = True
            disambiguation_hint = (
                f"Close confidence margin between candidates (delta={delta:.4f} < {AMBIGUITY_THRESHOLD}). "
                f"Please specify: {'; '.join(missing_params)}. "
                f"Top candidates: [{top1['standard_number']}] vs [{top2['standard_number']}]."
            )

    # Step 7: Graph Traversal for Top-1
    t0 = time.time()
    allied = get_allied_standards(top1["id"])
    licence = get_licence_info(top1["id"])
    t_graph = time.time() - t0

    # Step 8: Groq Grounded Synthesis
    groq_explanation, t_groq = groq_synthesize(raw_query, top1, licence, allied)
    t_total = time.time() - t_start

    return {
        "status": "AMBIGUOUS" if ambiguous else "OK",
        "raw_query": raw_query,
        "normalized_query": normalized_query,
        "top_recommendation": {
            "standard_number": top1["standard_number"],
            "title": top1["title"],
            "dept": top1["dept"],
            "is_status": top1.get("is_status_label", "Current"),
            "qco_ministry": top1.get("qco_ministry") or "-",
            "active_licences": top1.get("active_licences", 0),
        },
        "scores": {
            "cosine_similarity": round(top1["cosine_sim"], 4),
            "keyword_boost": top1["keyword_boost"],
            "qco_boost": top1["qco_boost"],
            "final_score": top1["final_score"],
        },
        "disambiguation": {
            "is_ambiguous": ambiguous,
            "top1_top2_delta": round(delta, 4),
            "hint": disambiguation_hint,
        },
        "top2_preview": {
            "standard_number": top2["standard_number"],
            "title": top2["title"],
            "final_score": top2["final_score"],
        },
        "graph_context": {
            "allied_standards": allied,
            "licence_info": licence,
        },
        "groq_justification": groq_explanation,
        "timings": {
            "norm_ms": round(t_norm * 1000, 1),
            "embed_ms": round(t_embed * 1000, 1),
            "vector_ms": round(t_vector * 1000, 1),
            "graph_ms": round(t_graph * 1000, 1),
            "groq_ms": round(t_groq * 1000, 1),
            "total_ms": round(t_total * 1000, 1),
        },
    }

# -----------------------------------------------------------------------------
# 8. OUTPUT PRINTER
# -----------------------------------------------------------------------------
def print_result(case_num: int, label: str, result: dict):
    PASS = "[PASS]"
    WARN = "[WARN]"
    FAIL = "[FAIL]"
    SEP = "-" * 80

    print(f"\n{'=' * 80}")
    print(f"  TEST CASE {case_num}: {label}")
    print(f"{'=' * 80}")

    status = result.get("status", "ERROR")

    if status == "OUT_OF_DOMAIN":
        print(f"  Gate: Domain Boundary Guard Triggered  <- {PASS}")
        print(f"  Max Similarity : {result['top_cosine_sim']} (threshold: {BOUNDARY_THRESHOLD})")
        print(f"  Message        : {result['message']}")
    elif status == "ERROR":
        print(f"  Status: {FAIL}")
        print(f"  {result.get('message')}")
    else:
        print(f"  Raw Query       : \"{result['raw_query']}\"")
        print(f"  Normalized Query: \"{result['normalized_query']}\"")
        print(SEP)

        rec = result["top_recommendation"]
        sc = result["scores"]
        dis = result["disambiguation"]
        gx = result["graph_context"]
        tim = result["timings"]

        print(f"  Top Recommendation:")
        print(f"    Standard  : {rec['standard_number']}")
        print(f"    Title     : {rec['title']}")
        print(f"    Dept      : {rec['dept']}")
        print(f"    Status    : {rec['is_status']}")
        print(f"    QCO       : {rec['qco_ministry']}")
        print(f"    Licences  : {rec['active_licences']}")
        print(SEP)

        print(f"  Hybrid Scores:")
        print(f"    Cosine Similarity : {sc['cosine_similarity']}")
        print(f"    Keyword Boost     : {sc['keyword_boost']}")
        print(f"    QCO Boost         : {sc['qco_boost']}")
        print(f"    -- Final Score    : {sc['final_score']}")
        print(f"    Runner-Up         : {result['top2_preview']['standard_number']} (score: {result['top2_preview']['final_score']})")
        print(SEP)

        if dis["is_ambiguous"]:
            print(f"  Ambiguity Gate : {WARN} (delta={dis['top1_top2_delta']} < {AMBIGUITY_THRESHOLD})")
            print(f"    Hint: {dis['hint']}")
        else:
            print(f"  Ambiguity Gate : Clear (delta={dis['top1_top2_delta']})")
        print(SEP)

        allied = gx.get("allied_standards", [])
        lic = gx.get("licence_info", {})
        if allied:
            print(f"  Allied Test Methods / Component Standards ({len(allied)}):")
            for a in allied[:4]:
                print(f"    * {a['ref_number']} [{a['edge_type']}] {a['ref_title'][:60]}")
        else:
            print(f"  Allied Standards: None in graph for this standard.")

        if lic and lic.get("total_isi_licences"):
            print(f"  Licence Varieties:")
            print(f"    Total ISI Licences : {lic.get('total_isi_licences', '-')}")
            print(f"    Product Varieties  : {str(lic.get('product_varieties', '-'))[:80]}...")
        print(SEP)

        print(f"  Groq Justification ({GROQ_MODEL}):")
        print(f"    >> {result['groq_justification']}")
        print(SEP)

        print(f"  Timings:")
        print(f"    Norm (Groq) : {tim['norm_ms']} ms")
        print(f"    GPU Embed   : {tim['embed_ms']} ms")
        print(f"    pgvector    : {tim['vector_ms']} ms")
        print(f"    Graph DB    : {tim['graph_ms']} ms")
        print(f"    Groq Synth  : {tim['groq_ms']} ms")
        print(f"    TOTAL       : {tim['total_ms']} ms")

# -----------------------------------------------------------------------------
# 9. RUN AUTOMATED TEST SUITE
# -----------------------------------------------------------------------------
TEST_CASES = [
    {
        "num": 1,
        "label": "Electrical Wiring (English, specific)",
        "query": "1.5 sq mm fire resistant PVC copper wire for residential building",
        "expect_contains": "IS 694",
    },
    {
        "num": 2,
        "label": "Civil / Cement (English)",
        "query": "Portland Pozzolana cement for structural foundation",
        "expect_contains": ["IS 1489", "IS 269"],
    },
    {
        "num": 3,
        "label": "Multilingual Hindi - Home Wiring",
        "query": "घर की वायरिंग के लिए तांबे के तार",
        "expect_contains": "IS 694",
    },
    {
        "num": 4,
        "label": "Domain Boundary Guard - Medical X-Ray (out-of-scope)",
        "query": "Digital X-Ray apparatus for hospital diagnostics radiology",
        "expect_status": "OUT_OF_DOMAIN",
    },
]

if __name__ == "__main__":
    all_passed = True

    for tc in TEST_CASES:
        result = recommend(tc["query"])
        print_result(tc["num"], tc["label"], result)

        passed = True
        if "expect_status" in tc:
            if result.get("status") != tc["expect_status"]:
                print(f"\n  [FAIL] Expected status={tc['expect_status']}, got {result.get('status')}")
                passed = False
            else:
                print(f"\n  [PASS] Status correctly = {tc['expect_status']}")

        if "expect_contains" in tc:
            actual_sn = result.get("top_recommendation", {}).get("standard_number", "")
            expected = tc["expect_contains"]
            if isinstance(expected, list):
                hit = any(e in actual_sn for e in expected)
                label_str = " OR ".join(expected)
            else:
                hit = expected in actual_sn
                label_str = expected

            if not hit:
                print(f"\n  [FAIL] Expected top result to contain [{label_str}], got [{actual_sn}]")
                passed = False
            else:
                print(f"\n  [PASS] Top result = {actual_sn} (contains expected {label_str})")

        if not passed:
            all_passed = False

    print(f"\n{'=' * 80}")
    overall = "[PASS] ALL TESTS PASSED" if all_passed else "[WARN] SOME TESTS NEED REVIEW"
    print(f"  MILESTONE 2.1 RESULT: {overall}")
    print(f"  Recommendation engine is {'READY for FastAPI' if all_passed else 'NEEDS TUNING'}.")
    print("=" * 80)

    CONN.close()
