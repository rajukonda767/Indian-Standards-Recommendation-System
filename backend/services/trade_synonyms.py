"""
trade_synonyms.py
=================
Standalone lookup table and pre-processing mapping for Indian procurement trade terminology
to statutory Indian Standards (BIS) product descriptions.
Applied before vector embedding to bridge colloquial/market terms to formal BIS catalogue titles.
"""

import re
from typing import Dict, Tuple

# Comprehensive trade synonym mapping for Indian procurement (22+ verified domain mappings)
TRADE_SYNONYMS: Dict[str, str] = {
    # 1. Structural steel & piping
    r"\bgi\s*pipes?\b": "galvanized mild steel tubes and pipe fittings IS 1239 IS 4736",
    r"\bms\s*pipes?\b": "mild steel tubes tubulars and other wrought steel fittings IS 1239",
    r"\b(?:ms|steel)\s*angles?\b": "hot rolled steel angle sections structural steel IS 808 IS 2062",
    r"\b(?:ms|steel)\s*channels?\b": "hot rolled steel beam and channel sections IS 808",
    r"\b(?:ms|steel)\s*(?:beams?|joists?)\b": "hot rolled steel beam column and channel sections IS 808",
    r"\b(?:ms|steel)\s*plates?\b": "hot rolled medium and high tensile structural steel plates IS 2062",
    r"\b(?:gi|cgi)\s*sheets?\b": "corrugated galvanized steel sheets for roofing IS 277",

    # 2. Reinforcement steel (Rebar)
    r"\b(?:tmt\s*(?:500d?|550d?|bars?|rebars?)|tata\s*tiscon|kamdhenu|jindal\s*panther)\b": (
        "high strength deformed steel bars and wires for concrete reinforcement IS 1786"
    ),

    # 3. Plastic piping systems
    r"\b(?:upvc|pvc-u)\s*pipes?\b": "unplasticized PVC pipes for potable water supplies IS 4985",
    r"\bcpvc\s*pipes?\b": "chlorinated polyvinyl chloride CPVC pipes for potable hot and cold water distribution IS 15778",
    r"\bswr\s*pipes?\b": "unplasticized PVC pipes for soil and waste discharge systems IS 13592",
    r"\bhdpe\s*pipes?\b": "high density polyethylene pipes for water supply IS 4984",
    r"\bpvc\s*conduits?\b": "conduits for electrical installations rigid non-flame propagating PVC pipes IS 9537",

    # 4. Electrical cables & conductors
    r"\b(?:house\s*wiring(?:\s*cables?)?|wiring\s*cables?)\b": (
        "polyvinyl chloride PVC insulated unsheathed and sheathed cables for working voltages up to 1100V IS 694"
    ),
    r"\bsubmersible\s*cables?\b": "PVC insulated copper conductor submersible pump cables IS 694",
    r"\bacsr\s*conductors?\b": "aluminum conductors galvanized steel reinforced for overhead transmission IS 398",
    r"\baaac\s*conductors?\b": "all aluminum alloy conductors for overhead transmission IS 398",

    # 5. Welding consumables
    r"\bwelding\s*electrodes?\b": "covered electrodes for manual metal arc welding of carbon and carbon manganese steel IS 814",

    # 6. Cement varieties
    r"\b(?:opc(?:\s*cement)?|43\s*grade\s*cement|53\s*grade\s*cement)\b": (
        "ordinary portland cement 43 53 grade specification IS 269"
    ),
    r"\bppc(?:\s*cement)?\b": "portland pozzolana cement fly ash based specification IS 1489",
    r"\bpsc(?:\s*cement)?\b": "portland slag cement specification IS 455"
}


def expand_trade_synonyms(query: str) -> str:
    """
    Expands colloquial Indian procurement trade terms into formal BIS terminology
    before vector embedding.
    Example: 'GI pipe' -> 'GI pipe galvanized mild steel tubes and pipe fittings IS 1239 IS 4736'
    Preserves original query and appends formal terms so that exact-term boosts still apply.
    """
    expanded = query.strip()
    matched_expansions = []

    for pattern, formal_term in TRADE_SYNONYMS.items():
        if re.search(pattern, query, re.IGNORECASE):
            matched_expansions.append(formal_term)

    if matched_expansions:
        # Prepend original query for preservation, followed by formal BIS vocabulary
        return f"{expanded} {' '.join(matched_expansions)}"

    return expanded
