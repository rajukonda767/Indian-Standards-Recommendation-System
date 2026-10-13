# -*- coding: utf-8 -*-
"""
tests/eval/run_phase1_audit.py
==============================
Re-runs items 1-4 with:
  1. Citation span stripped from raw_query (cited_standard_raw=None)
  2. audit_mode=True — skips all Groq calls (why-text, disambiguation, differentiators)
  3. Deduplication by base_key + plausibility threshold (final_score >= 0.50)
  4. Reports per-item latency breakdown

Point 2 fix: "conf" in previous output was actually elapsed_seconds printed as a float
that happened to look like a confidence score. The extract_spec() return value is
(ExtractedSpec, elapsed_seconds_float). The second element is NOT a confidence score.
It is labelled "conf" only because the run_phase1.py script printed it that way.
"""
import sys, os, re, time
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'C:\Users\devag\.gemini\antigravity\scratch\standards\backend')
os.chdir(r'C:\Users\devag\.gemini\antigravity\scratch\standards\backend')

from app.db import init_db_pool, get_db_cursor
from app.services.embedding import EmbeddingService
init_db_pool()
EmbeddingService.get_instance()

from services.extraction import extract_spec
from services.retrieval import retrieve_recommendations
import schemas

PLAUSIBILITY_THRESHOLD = 0.50   # min final_score to include in candidate list

# ── audit_mode retrieval: strip Groq calls, strip citation boost ───────────────
def retrieve_audit(item_description: str, mention_spans: list[str]):
    """
    Audit-mode retrieval:
    - Strips all regex-matched citation spans from query text before embedding.
    - Passes cited_standard_raw=None so no citation boost is applied.
    - Skips all Groq calls (why-text, disambiguation, differentiators).
    - Deduplicates candidates by base_key.
    - Applies plausibility threshold.
    Returns (candidates: list[dict], timings: dict)
    """
    # Strip citation spans from raw query
    query_stripped = item_description
    for span in mention_spans:
        # remove exact mention text (and variants with flexible whitespace)
        query_stripped = re.sub(re.escape(span.strip()), '', query_stripped)
    query_stripped = re.sub(r'\s+', ' ', query_stripped).strip()

    # Build a neutral ExtractedSpec (no cited standard)
    spec = schemas.ExtractedSpec(
        product_category=None,
        material=None,
        voltage_rating=None,
        dimensions=None,
        application=None,
        cited_standard_raw=None,   # ← no citation boost
        brand_names_removed=[],
    )

    # Extract semantic attributes from the stripped query (deterministic path)
    try:
        extracted_spec, _ = extract_spec(query_stripped)
        # Keep product_category and material; clear cited_standard_raw
        spec = schemas.ExtractedSpec(
            product_category=extracted_spec.product_category,
            material=extracted_spec.material,
            voltage_rating=extracted_spec.voltage_rating,
            dimensions=extracted_spec.dimensions,
            application=extracted_spec.application,
            cited_standard_raw=None,   # force no citation boost
            brand_names_removed=extracted_spec.brand_names_removed,
        )
    except Exception as e:
        print(f'  extract_spec failed: {e}')

    # Call retrieve_recommendations (will invoke Groq why-text per candidate)
    # We monkey-patch the Groq calls to be no-ops for audit mode
    import services.retrieval as ret_mod
    original_why = ret_mod.build_grounded_why
    original_disamb = ret_mod.generate_dynamic_disambiguation
    original_diff = ret_mod.generate_alternative_differentiators

    def _null_why(candidate, extracted, confidence_pct, raw_cosine_sim, raw_query=''):
        return f"[audit_mode] {candidate['standard_number']} — {candidate['title'][:80]}"

    def _null_disamb(top_candidates, extracted, raw_query):
        return ("Multiple matches", [], "Other")

    def _null_diff(primary, alternatives, raw_query):
        return {}

    ret_mod.build_grounded_why = _null_why
    ret_mod.generate_dynamic_disambiguation = _null_disamb
    ret_mod.generate_alternative_differentiators = _null_diff

    try:
        t0 = time.time()
        result, timings = retrieve_recommendations(query_stripped, spec)
        elapsed = time.time() - t0
        timings['audit_total_s'] = round(elapsed, 2)
    finally:
        ret_mod.build_grounded_why = original_why
        ret_mod.generate_dynamic_disambiguation = original_disamb
        ret_mod.generate_alternative_differentiators = original_diff

    # Collect all candidates (primary + candidates lists)
    cands = (getattr(result, 'primary', None) or []) + (getattr(result, 'candidates', None) or [])

    # Deduplicate by base_key
    seen_keys = set()
    deduped = []
    for c in cands:
        bn = getattr(c, 'base_number', None) or getattr(c, 'standard_number', '')
        # strip year from base_number: IS 694:2010 -> IS 694
        base = re.sub(r':\d{4}$', '', bn).strip()
        if base not in seen_keys:
            seen_keys.add(base)
            deduped.append(c)

    # Apply plausibility threshold
    plausible = [c for c in deduped if getattr(c, 'confidence', 0) >= PLAUSIBILITY_THRESHOLD * 100]
    # If all below threshold, keep top-3 regardless
    if not plausible:
        plausible = deduped[:3]

    return plausible, timings, query_stripped, spec


# ── Test items with citation spans pre-extracted ──────────────────────────────
ITEMS = [
    {
        "seq": 1,
        "description": "OPC 43 grade cement conforming to IS 269:2015",
        "citation_spans": ["IS 269:2015"],
        "cited_std": "IS269",  # for resolver
    },
    {
        "seq": 2,
        "description": "PVC insulated copper conductor wire IS 694",
        "citation_spans": ["IS 694"],
        "cited_std": "IS694",
    },
    {
        "seq": 3,
        "description": "Fe 500D TMT reinforcement bars for construction",
        "citation_spans": [],
        "cited_std": None,
    },
    {
        "seq": 4,
        "description": "PVC insulated power cable 1.1kV as per IS 7098 (Part 1)",
        "citation_spans": ["IS 7098 (Part 1)"],
        "cited_std": "IS7098(PART1)",
    },
]

print('\n' + '='*90)
print('PHASE 1 AUDIT_MODE RE-RUN (citation-stripped, no Groq, deduplicated)')
print(f'Plausibility threshold: final_score >= {PLAUSIBILITY_THRESHOLD:.0%}')
print('='*90)

# Fetch current latest editions for resolver
LATEST = {}
with get_db_cursor() as cur:
    for key in ['IS269', 'IS694', 'IS7098(PART1)', 'IS1786']:
        cur.execute(
            "SELECT standard_number, year FROM standards WHERE base_key=%s "
            "ORDER BY year DESC LIMIT 1", (key,)
        )
        r = cur.fetchone()
        if r:
            LATEST[key] = (r[0], r[1])

print(f'\nLatest editions from DB: {LATEST}')

all_findings = []

for item in ITEMS:
    seq = item['seq']
    desc = item['description']
    spans = item['citation_spans']
    cited = item['cited_std']

    print(f'\n--- Item {seq}: {desc} ---')
    if spans:
        print(f'  Citation spans stripped from query: {spans}')

    plausible, timings, stripped_q, spec = retrieve_audit(desc, spans)

    print(f'  Stripped query: {stripped_q!r}')
    print(f'  Extracted spec: {spec.model_dump(exclude_none=True)}')
    print(f'  Timing: embed={timings.get("embed_ms")}ms  vec={timings.get("vector_query_ms")}ms  '
          f'latest={timings.get("latest_edition_ms")}ms  allied={timings.get("allied_query_ms")}ms  '
          f'total={timings.get("audit_total_s")}s')

    print(f'  Top-5 plausible candidates (after dedup + threshold {PLAUSIBILITY_THRESHOLD:.0%}):')
    top5_bns = []
    for i, c in enumerate(plausible[:5], 1):
        sn = getattr(c, 'standard_number', '?')
        conf = getattr(c, 'confidence', 0)
        title = getattr(c, 'title', '')[:70]
        cert = getattr(c, 'certification', None)
        cert_str = ''
        if cert:
            cert_str = f'  cert={getattr(cert, "value", "?")} verified={getattr(cert, "verified", "?")}'
        print(f'    {i}. [{conf:.1f}%] {sn}  {title}{cert_str}')
        bn = re.sub(r':\d{4}$', '', getattr(c, 'base_number', sn) or sn)
        top5_bns.append(bn)

    # Resolver findings
    findings = []

    if not cited:
        findings.append('CITATION_MISSING')
    else:
        # Is cited standard among top-10 results?
        all_bns = [re.sub(r':\d{4}$', '', getattr(c, 'base_number', getattr(c, 'standard_number', '')) or '') for c in plausible]
        cited_base = re.sub(r'[\(\):\s]', '', cited.upper())  # rough
        cited_in_top = any(cited_base in bn.replace(' ', '').upper() or bn.replace(' ', '').upper() in cited_base for bn in all_bns[:10])

        if cited_in_top:
            findings.append('CITED_AMONG_CANDIDATES')
        else:
            findings.append('CITED_NOT_AMONG_CANDIDATES')

        # Check if top-1 independent is same family as cited
        if plausible:
            top1_sn = getattr(plausible[0], 'standard_number', '')
            top1_bn = re.sub(r'[\(\):\s]', '', top1_sn.upper())
            # PVC vs XLPE contradiction (item 4 specific)
            if 'IS7098' in cited.upper() and plausible:
                top1_title = getattr(plausible[0], 'title', '').lower()
                if 'xlpe' in top1_title or 'crosslinked' in top1_title:
                    # Item 4: cited IS 7098 (XLPE) but spec says PVC
                    # The independent top-1 should be IS 1554 or IS 694 for PVC
                    findings.append('TITLE_SPEC_INCONSISTENT')

        # Year checks
        if cited and cited in LATEST:
            # cited_std has no year info here (need the mention year)
            pass  # would check against item's cited year

    print(f'  Findings: {findings}')
    all_findings.append((seq, findings))

print('\n' + '='*90)
print('SUMMARY — Findings per item:')
for seq, findings in all_findings:
    print(f'  Item {seq}: {findings}')
print('='*90)
