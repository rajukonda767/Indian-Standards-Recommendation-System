"""
groq_service.py
===============
Groq Cloud API integration (Qwen/Llama) for:
1. Technical query normalization & brand name pollution stripping
2. Zero-hallucination grounded justification synthesis
3. Interactive procurement disambiguation questions & options
4. Ready-to-paste statutory Tender Technical Clauses (BIS Act 2016)
"""

import logging
import time
from typing import Tuple, List, Dict, Any, Optional
from groq import Groq
from app.config import settings

from app.parsers.groq_wrapper import get_groq_wrapper

logger = logging.getLogger(__name__)

def get_groq_client():
    return get_groq_wrapper().client


def normalize_query_groq(raw_query: str) -> Tuple[str, float]:
    """
    Normalizes procurement query:
    - Strips proprietary trademarks (Havells, Polycab, Finolex, Tata Tiscon, UltraTech, etc.)
    - Translates non-English (Hindi/regional) to formal technical procurement terms
    - Expands domain abbreviations (e.g., PVC -> Polyvinyl Chloride, TMT -> Thermo-Mechanically Treated)
    """
    system_prompt = (
        "You are an Indian Standards (BIS) technical specification extractor for public procurement. "
        "Given a user procurement query: "
        "1. Remove all proprietary brand names (e.g. Havells, Polycab, Finolex, Tata, UltraTech, ACC). "
        "2. If query is in Hindi or Indian regional language, translate to English technical specifications. "
        "3. DO NOT invent unstated technical parameters (e.g. if user says '150 sq mm cable', do NOT assume 'PVC' or 'copper' or 'domestic'; if user says 'cement', do NOT assume 'OPC 43' or 'PPC'). "
        "4. Output strictly a concise technical search phrase in English without quotes or conversational prefix."
    )

    t0 = time.time()
    try:
        wrapper = get_groq_wrapper()
        normalized = wrapper.create_chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": raw_query}
            ],
            model=settings.GROQ_MODEL,
            temperature=0.0,
            max_tokens=60,
            prompt_version="norm_v1"
        )
        elapsed = time.time() - t0
        return normalized.strip().strip('"'), elapsed
    except Exception as e:
        logger.error(f"Groq query normalization failed: {e}")
        return raw_query, 0.0


def synthesize_justification_groq(
    user_query: str,
    top_standard: Dict[str, Any],
    licence_info: Dict[str, Any],
    allied_list: List[Dict[str, Any]]
) -> Tuple[str, float]:
    """
    Synthesizes a 1-2 sentence grounded justification strictly from retrieved facts.
    """
    allied_text = "; ".join(
        f"{a['ref_number']} ({a['ref_title']})" for a in allied_list[:3]
    ) or "None listed"

    lic_count = licence_info.get("total_isi_licences", top_standard.get("active_licences", "Unknown"))
    varieties = licence_info.get("product_varieties", "Standard specifications")
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

    t0 = time.time()
    try:
        wrapper = get_groq_wrapper()
        content = wrapper.create_chat_completion(
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg}
            ],
            model=settings.GROQ_MODEL,
            max_tokens=120,
            temperature=0.0,
            prompt_version="just_v1"
        )
        elapsed = time.time() - t0
        return content.strip(), elapsed
    except Exception as e:
        logger.error(f"Groq justification synthesis failed: {e}")
        return f"Matched on technical scope for {top_standard['standard_number']}.", 0.0


def generate_disambiguation_groq(
    user_query: str,
    top1: Dict[str, Any],
    top2: Dict[str, Any]
) -> Tuple[str, List[str]]:
    """
    Generates a clarifying question and selectable options when top candidates have close scores.
    """
    system_prompt = (
        "You are a senior technical procurement officer in India. "
        "The user query is ambiguous between two candidate Indian Standards. "
        "Formulate a single concise clarifying question and 2-3 distinct technical options. "
        "Format output strictly as: "
        "QUESTION: <question text> "
        "OPTION: <option 1 text> "
        "OPTION: <option 2 text> "
        "OPTION: <option 3 text>"
    )

    user_msg = (
        f"User Query: \"{user_query}\"\n"
        f"Candidate 1: {top1['standard_number']} - {top1['title']}\n"
        f"Candidate 2: {top2['standard_number']} - {top2['title']}\n"
    )

    try:
        wrapper = get_groq_wrapper()
        content = wrapper.create_chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg}
            ],
            model=settings.GROQ_MODEL,
            temperature=0.0,
            max_tokens=150,
            prompt_version="disam_v1"
        )
        lines = [line.strip() for line in (content or "").split("\n") if line.strip()]
        
        question = "Please clarify your specific technical requirements:"
        options = []
        for line in lines:
            if line.upper().startswith("QUESTION:"):
                question = line[len("QUESTION:"):].strip()
            elif line.upper().startswith("OPTION:"):
                options.append(line[len("OPTION:"):].strip())

        if not options:
            options = [
                f"{top1['standard_number']} ({top1['title'][:40]}...)",
                f"{top2['standard_number']} ({top2['title'][:40]}...)"
            ]
        return question, options
    except Exception as e:
        logger.error(f"Groq disambiguation generation failed: {e}")
        return (
            f"Please clarify if you require {top1['standard_number']} or {top2['standard_number']}.",
            [top1['standard_number'], top2['standard_number']]
        )


def generate_tender_clause(
    top_standard: Dict[str, Any],
    test_methods: List[Any]
) -> str:
    """
    Generates a legally enforceable, ready-to-paste technical clause
    for GeM (Government e-Marketplace), CPWD, or Public Sector tenders
    under Section 16 & 17 of the Bureau of Indian Standards Act, 2016.
    """
    sn = top_standard["standard_number"]
    title = top_standard["title"]
    qco = top_standard.get("qco_ministry")
    qco_clause = (
        f"The supplied goods must strictly comply with the mandatory Quality Control Order (QCO) "
        f"issued by {qco} and bear the authentic Standard Mark (ISI mark) under BIS (Conformity Assessment) Regulations, 2018."
        if qco else
        "The supplied goods shall conform to statutory quality parameters and bear the Standard Mark (ISI Mark) under Scheme-I of BIS."
    )

    tests_cited = ""
    if test_methods:
        test_nums = [t.ref_number for t in test_methods[:3]]
        tests_cited = f" Factory acceptance testing and pre-dispatch inspection shall conform to mandatory test procedures prescribed under {', '.join(test_nums)}."

    clause = (
        f"TECHNICAL SPECIFICATION & STATUTORY COMPLIANCE CLAUSE:\n"
        f"\"The material supplied under this contract shall strictly conform in all respects to {sn} "
        f"('{title}'), including all up-to-date amendments and revisions issued by the Bureau of Indian Standards. "
        f"{qco_clause}{tests_cited} "
        f"The bidder shall furnish a valid BIS Licence Certificate (CM/L number) along with NABL-accredited test reports "
        f"attesting conformity prior to shipment. Any supply deviating from {sn} shall be liable for summarily rejection "
        f"under Section 16 & 17 of the Bureau of Indian Standards Act, 2016.\""
    )
    return clause
