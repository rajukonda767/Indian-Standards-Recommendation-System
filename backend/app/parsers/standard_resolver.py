# -*- coding: utf-8 -*-
"""
backend/app/parsers/standard_resolver.py
========================================
Production-Grade Deterministic Standard Resolver for Tender Auditing.

Capabilities:
1. DB matching against `standards` and `standard_keys`.
2. Exact edition & lineage tracking: identifies older cited years and retrieves the
   exact successor standard from `standard_lineage` / `standards`, emitting exactly
   ONE finding code (SUPERSEDED or OUTDATED_EDITION, never both for the same citation).
3. Part selection by voltage/rating where item attributes support it (e.g. 1.1 kV cable -> Part 1);
   otherwise leaves Part unresolved and emits CITATION_NO_PART.
4. International (IEC/ISO/BS/EN/ASTM/DIN/IEEE/UL) -> Indian equivalent mapping table with
   a deterministic CANNOT_VERIFY outcome when no equivalent is found (never guessing).
5. Fuzzy "did you mean" suggestion field only, never auto-applied.
"""
from __future__ import annotations
import re
import difflib
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple

from app.db import get_db_cursor
from app.parsers.mention_extractor import Mention, _DB_EXACT, load_db_sets
from app.parsers.verbatim_verifier import VerifiedQuote

logger = logging.getLogger("standard_resolver")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter("[%(levelname)s] [StandardResolver] %(message)s")
    ch.setFormatter(formatter)
    logger.addHandler(ch)


@dataclass
class Finding:
    """Audit finding code, severity, and diagnostic explanation."""
    code: str  # SUPERSEDED | OUTDATED_EDITION | CITATION_NO_PART | NO_INDIAN_EQUIVALENT_FOUND | UNKNOWN_STANDARD | COMPLIANT
    severity: str  # critical | warning | info
    message: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "details": self.details
        }


@dataclass
class ResolvedStandard:
    """Fully resolved standard entity with lineage, part resolution, and audit findings."""
    raw_citation: str
    base_key: str
    cited_year: Optional[int] = None
    cited_part: Optional[str] = None
    resolved_standard_number: Optional[str] = None
    resolved_base_key: Optional[str] = None
    resolved_year: Optional[int] = None
    resolved_part: Optional[str] = None
    status: str = "compliant"  # compliant | superseded | outdated | cannot_verify | missing
    findings: List[Finding] = field(default_factory=list)
    successor_standard_number: Optional[str] = None
    successor_year: Optional[int] = None
    is_international: bool = False
    international_family: Optional[str] = None
    equivalent_standard_number: Optional[str] = None
    suggestion: Optional[str] = None
    part_resolution_source: Optional[str] = None
    base_standard_valid: bool = False
    quote: Optional[VerifiedQuote] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_citation": self.raw_citation,
            "base_key": self.base_key,
            "cited_year": self.cited_year,
            "cited_part": self.cited_part,
            "resolved_standard_number": self.resolved_standard_number,
            "resolved_base_key": self.resolved_base_key,
            "resolved_year": self.resolved_year,
            "resolved_part": self.resolved_part,
            "status": self.status,
            "findings": [f.to_dict() for f in self.findings],
            "successor_standard_number": self.successor_standard_number,
            "successor_year": self.successor_year,
            "is_international": self.is_international,
            "international_family": self.international_family,
            "equivalent_standard_number": self.equivalent_standard_number,
            "suggestion": self.suggestion,
            "part_resolution_source": self.part_resolution_source,
            "base_standard_valid": self.base_standard_valid,
            "quote": self.quote.to_dict() if self.quote else None
        }


class StandardResolver:
    """
    Deterministic Resolver executing DB resolution, voltage-based part selection,
    lineage tracking, international mapping, and fuzzy suggestions.
    """

    # ── Deterministic International Equivalent Mapping Table ──────────────────
    INTERNATIONAL_EQUIVALENTS: Dict[str, Dict[str, Any]] = {
        # IEC Cables & Electrical
        "IEC60227": {
            "family": "IEC",
            "equivalent_base_key": "IS694",
            "standard_number": "IS 694:2010",
            "title": "Polyvinyl Chloride Insulated Cables for Working Voltages Up to and Including 1100 V",
            "relationship": "EQUIVALENT"
        },
        "IEC60502": {
            "family": "IEC",
            "equivalent_base_key": "IS7098(PART1)",
            "standard_number": "IS 7098 (Part 1):2025",
            "title": "Crosslinked Polyethylene Insulated Thermoplastic Sheathed Cables",
            "relationship": "EQUIVALENT"
        },
        "IEC60502(PART1)": {
            "family": "IEC",
            "equivalent_base_key": "IS7098(PART1)",
            "standard_number": "IS 7098 (Part 1):2025",
            "title": "Crosslinked Polyethylene Insulated Cables Part 1 For Working Voltages up to and Including 1.1 kV",
            "relationship": "EQUIVALENT"
        },
        "IEC60947(PART2)": {
            "family": "IEC",
            "equivalent_base_key": "IS/IEC60947(PART2)",
            "standard_number": "IS/IEC 60947 (Part 2):2016",
            "title": "Low-Voltage Switchgear and Controlgear Part 2 Circuit-Breakers",
            "relationship": "IDENTICAL_ADOPTION"
        },
        "IEC60079": {
            "family": "IEC",
            "equivalent_base_key": "IS/IEC60079",
            "standard_number": "IS/IEC 60079",
            "title": "Explosive Atmospheres",
            "relationship": "IDENTICAL_ADOPTION"
        },
        # ISO Quality & Environmental
        "ISO9001": {
            "family": "ISO",
            "equivalent_base_key": "IS/ISO9001",
            "standard_number": "IS/ISO 9001:2015",
            "title": "Quality Management Systems - Requirements",
            "relationship": "IDENTICAL_ADOPTION"
        },
        "ISO14001": {
            "family": "ISO",
            "equivalent_base_key": "IS/ISO14001",
            "standard_number": "IS/ISO 14001:2015",
            "title": "Environmental Management Systems - Requirements with Guidance for Use",
            "relationship": "IDENTICAL_ADOPTION"
        },
        "ISO45001": {
            "family": "ISO",
            "equivalent_base_key": "IS/ISO45001",
            "standard_number": "IS/ISO 45001:2018",
            "title": "Occupational Health and Safety Management Systems - Requirements",
            "relationship": "IDENTICAL_ADOPTION"
        },
        # British Standards (BS)
        "BS6004": {
            "family": "BS",
            "equivalent_base_key": "IS694",
            "standard_number": "IS 694:2010",
            "title": "Electric Cables - PVC Insulated and PVC Sheathed Cables",
            "relationship": "EQUIVALENT"
        },
        "BS5308": {
            "family": "BS",
            "equivalent_base_key": "IS1554(PART1)",
            "standard_number": "IS 1554 (Part 1):1988",
            "title": "Instrumentation Cables",
            "relationship": "EQUIVALENT"
        },
        # ASTM (American Society for Testing and Materials)
        "ASTMA615": {
            "family": "ASTM",
            "equivalent_base_key": "IS1786",
            "standard_number": "IS 1786:2008",
            "title": "High Strength Deformed Steel Bars and Wires for Concrete Reinforcement",
            "relationship": "EQUIVALENT"
        },
        "ASTMC150": {
            "family": "ASTM",
            "equivalent_base_key": "IS269",
            "standard_number": "IS 269:2015",
            "title": "Ordinary Portland Cement",
            "relationship": "EQUIVALENT"
        },
        # EN (European Norm)
        "EN10025": {
            "family": "EN",
            "equivalent_base_key": "IS2062",
            "standard_number": "IS 2062:2011",
            "title": "Hot Rolled Medium and High Tensile Structural Steel",
            "relationship": "EQUIVALENT"
        },
        # DIN (German Institute for Standardization)
        "DIN488": {
            "family": "DIN",
            "equivalent_base_key": "IS1786",
            "standard_number": "IS 1786:2008",
            "title": "Reinforcing Steels - Reinforcing Steel Bars",
            "relationship": "EQUIVALENT"
        },
        # IEEE
        "IEEE80": {
            "family": "IEEE",
            "equivalent_base_key": "IS3043",
            "standard_number": "IS 3043:2018",
            "title": "IEEE Guide for Safety in AC Substation Grounding / Code of Practice for Earthing",
            "relationship": "EQUIVALENT"
        },
        # UL (Underwriters Laboratories)
        "UL94": {
            "family": "UL",
            "equivalent_base_key": "IS11731(PART1)",
            "standard_number": "IS 11731 (Part 1):1986",
            "title": "Flammability of Plastic Materials for Parts in Devices and Appliances",
            "relationship": "EQUIVALENT"
        }
    }

    # International prefixes
    INTL_FAMILIES = ("IEC", "ISO", "BS", "EN", "ASTM", "DIN", "IEEE", "UL")

    # Voltage regex for Part selection
    VOLTAGE_1_1KV_RE = re.compile(
        r'(?:1\.1\s*k\s*v|1100\s*v|650\s*/\s*1100\s*v|\blt\b|low\s+voltage|low\s+tension)',
        re.IGNORECASE
    )
    VOLTAGE_HT_RE = re.compile(
        r'(?:3\.3\s*k\s*v|6\.6\s*k\s*v|11\s*k\s*v|22\s*k\s*v|33\s*k\s*v|\bht\b|high\s+tension|medium\s+voltage)',
        re.IGNORECASE
    )
    VOLTAGE_EHT_RE = re.compile(
        r'(?:66\s*k\s*v|132\s*k\s*v|220\s*k\s*v|\beht\b|extra\s+high\s+tension)',
        re.IGNORECASE
    )

    def __init__(self):
        load_db_sets()

    @classmethod
    def resolve_part_by_attributes(
        cls,
        base_family: str,
        item_text: str
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Deterministically infers Part based on voltage/rating in item text.
        Returns: (resolved_part, resolved_base_key, resolution_source)
        """
        fam = base_family.upper().strip()
        fam_clean = re.sub(r'\s*\+NO_PART$', '', fam)

        if fam_clean == "IS7098":
            if cls.VOLTAGE_1_1KV_RE.search(item_text):
                return "1", "IS7098(PART1)", "item_voltage_rating (1.1 kV / 1100 V)"
            elif cls.VOLTAGE_HT_RE.search(item_text):
                return "2", "IS7098(PART2)", "item_voltage_rating (HT / 3.3-33 kV)"
            elif cls.VOLTAGE_EHT_RE.search(item_text):
                return "3", "IS7098(PART3)", "item_voltage_rating (EHT / 66-220 kV)"
            return None, None, None

        elif fam_clean == "IS1554":
            if cls.VOLTAGE_1_1KV_RE.search(item_text):
                return "1", "IS1554(PART1)", "item_voltage_rating (1.1 kV / 1100 V)"
            elif cls.VOLTAGE_HT_RE.search(item_text):
                return "2", "IS1554(PART2)", "item_voltage_rating (HT / 3.3-11 kV)"
            return None, None, None

        elif fam_clean == "IS1239":
            if re.search(r'\b(?:fitting|elbow|tee|socket|union|reducer|bend)\b', item_text, re.I):
                return "2", "IS1239(PART2)", "item_product_type (pipe fittings)"
            elif re.search(r'\b(?:tube|pipe|piping|casing)\b', item_text, re.I):
                return "1", "IS1239(PART1)", "item_product_type (steel tubes)"
            return None, None, None

        return None, None, None

    def resolve_mention(
        self,
        mention: Mention,
        item_context: str = "",
        verified_quote: Optional[VerifiedQuote] = None
    ) -> ResolvedStandard:
        """
        Resolves a single standard mention against standards registry and lineage.
        """
        raw_key = mention.base_key
        norm_key = re.sub(r'\s*\+NO_PART$', '', raw_key).upper()
        cited_year = mention.year
        cited_part = mention.part

        # ── 1. Check International Families & Mapping Table ────────────────────
        is_intl = False
        intl_fam = None
        for fam in self.INTL_FAMILIES:
            if norm_key.startswith(fam) and not norm_key.startswith("IS/" + fam):
                is_intl = True
                intl_fam = fam
                break

        if is_intl:
            if norm_key in self.INTERNATIONAL_EQUIVALENTS:
                eq_info = self.INTERNATIONAL_EQUIVALENTS[norm_key]
                eq_base = eq_info["equivalent_base_key"]
                eq_std = eq_info["standard_number"]
                
                # Fetch DB details for the equivalent Indian standard
                res_indian = self._resolve_indian_key(
                    base_key=eq_base,
                    cited_year=None,
                    cited_part=None,
                    raw_citation=mention.raw_text,
                    item_context=item_context
                )
                res_indian.is_international = True
                res_indian.international_family = intl_fam
                res_indian.equivalent_standard_number = eq_std
                res_indian.quote = verified_quote
                res_indian.findings.append(Finding(
                    code="INTERNATIONAL_EQUIVALENT_RESOLVED",
                    severity="info",
                    message=f"Foreign standard '{mention.raw_text}' ({intl_fam}) resolved to Indian standard equivalent '{eq_std}' ({eq_info['title']}).",
                    details={"foreign_standard": mention.raw_text, "indian_equivalent": eq_std}
                ))
                return res_indian
            else:
                # Undefined / unmapped international standard -> strictly CANNOT_VERIFY
                return ResolvedStandard(
                    raw_citation=mention.raw_text,
                    base_key=norm_key,
                    cited_year=cited_year,
                    cited_part=cited_part,
                    status="cannot_verify",
                    is_international=True,
                    international_family=intl_fam,
                    quote=verified_quote,
                    findings=[
                        Finding(
                            code="NO_INDIAN_EQUIVALENT_FOUND",
                            severity="warning",
                            message=f"No recognized Indian standard (BIS) equivalent found for foreign standard '{mention.raw_text}' ({intl_fam}).",
                            details={"family": intl_fam, "raw_citation": mention.raw_text}
                        )
                    ]
                )

        # ── 2. Part Resolution by Item Voltage / Rating Attributes ─────────────
        resolved_part = cited_part
        resolved_key = norm_key
        resolution_source = None

        if "(PART" not in norm_key and not cited_part:
            inf_part, inf_key, inf_source = self.resolve_part_by_attributes(norm_key, item_context)
            if inf_part and inf_key:
                resolved_part = inf_part
                resolved_key = inf_key
                resolution_source = inf_source

        # ── 3. DB Lookup & Lineage Resolution for Indian Standard ──────────────
        res = self._resolve_indian_key(
            base_key=resolved_key,
            cited_year=cited_year,
            cited_part=resolved_part,
            raw_citation=mention.raw_text,
            item_context=item_context
        )
        res.part_resolution_source = resolution_source
        res.quote = verified_quote

        # If it's a multi-part family and Part could not be resolved -> CITATION_NO_PART
        if norm_key in ("IS7098", "IS1554", "IS1239") and not resolved_part and "(PART" not in resolved_key:
            res.findings.append(Finding(
                code="CITATION_NO_PART",
                severity="warning",
                message=f"Standard '{mention.raw_text}' is a multi-part standard with discrete parts by voltage/product type, but no Part was specified and item attributes are insufficient to disambiguate.",
                details={"base_family": norm_key}
            ))

        return res

    _STD_CACHE: Dict[str, Any] = {}
    _LIN_CACHE: Dict[Tuple[str, Optional[int]], Any] = {}

    def _resolve_indian_key(
        self,
        base_key: str,
        cited_year: Optional[int],
        cited_part: Optional[str],
        raw_citation: str,
        item_context: str
    ) -> ResolvedStandard:
        """Queries PostgreSQL standards and standard_keys tables to resolve status and lineage."""
        if base_key in self._STD_CACHE:
            rows = self._STD_CACHE[base_key]
        else:
            with get_db_cursor() as cur:
                # Query standard_keys
                cur.execute("""
                    SELECT s.id, s.standard_number, s.base_number, s.base_key, s.year, 
                           s.is_status_label, s.supersedes_older, s.superseded_by_newer, s.title
                    FROM standards s
                    JOIN standard_keys k ON k.standard_id = s.id
                    WHERE k.base_key = %s
                    ORDER BY s.year DESC;
                """, (base_key,))
                rows = cur.fetchall()

                if not rows:
                    # Try fallback matching without part if bare base_number matches
                    cur.execute("""
                        SELECT id, standard_number, base_number, base_key, year, 
                               is_status_label, supersedes_older, superseded_by_newer, title
                        FROM standards
                        WHERE base_number = %s OR base_key = %s
                        ORDER BY year DESC;
                    """, (base_key, base_key))
                    rows = cur.fetchall()

            self._STD_CACHE[base_key] = rows

        if not rows:
            # Fuzzy suggestion lookup (Did you mean)
            close_matches = difflib.get_close_matches(base_key, list(_DB_EXACT), n=1, cutoff=0.70)
            suggestion_str = f"Did you mean '{close_matches[0]}'?" if close_matches else None
            return ResolvedStandard(
                raw_citation=raw_citation,
                base_key=base_key,
                cited_year=cited_year,
                cited_part=cited_part,
                status="missing",
                suggestion=suggestion_str,
                findings=[
                    Finding(
                        code="UNKNOWN_STANDARD",
                        severity="warning",
                        message=f"Standard '{raw_citation}' (key={base_key}) not found in standards registry. {suggestion_str or ''}".strip(),
                        details={"suggestion": close_matches[0] if close_matches else None}
                    )
                ]
            )

        # Latest active edition row
        latest_row = rows[0]
        latest_id = latest_row[0]
        latest_std_num = latest_row[1]
        latest_year = latest_row[4]
        latest_status = latest_row[5]
        latest_supersedes = latest_row[6]
        latest_superseded_by = latest_row[7]

        findings: List[Finding] = []
        status = "compliant"
        successor_std = None
        successor_yr = None

        # Check year discrepancy
        if cited_year is not None:
            if latest_year is not None and cited_year < latest_year:
                lin_key = (base_key, cited_year)
                if lin_key in self._LIN_CACHE:
                    lin_row = self._LIN_CACHE[lin_key]
                else:
                    with get_db_cursor() as cur:
                        cur.execute("""
                            SELECT s.standard_number, s.year, l.relationship, l.related_standard_raw
                            FROM standard_lineage l
                            JOIN standards s ON s.id = l.standard_id
                            WHERE (l.related_base_number = %s OR l.related_standard_raw ILIKE %s)
                              AND (l.related_year = %s OR l.related_year IS NULL)
                            ORDER BY s.year DESC LIMIT 1;
                        """, (base_key.replace("(", "").replace(")", ""), f"%{base_key}%", cited_year))
                        lin_row = cur.fetchone()
                    self._LIN_CACHE[lin_key] = lin_row

                if lin_row or (latest_supersedes and str(cited_year) in latest_supersedes):
                    # Formally superseded by newer edition/standard
                    successor_std = lin_row[0] if lin_row else latest_std_num
                    successor_yr = lin_row[1] if lin_row else latest_year
                    status = "superseded"
                    # EXACTLY ONE finding code emitted: SUPERSEDED (not both OUTDATED_EDITION and SUPERSEDED)
                    findings.append(Finding(
                        code="SUPERSEDED",
                        severity="error",
                        message=f"Cited edition '{raw_citation}' ({cited_year}) has been superseded by '{successor_std}' ({successor_yr}).",
                        details={"cited_year": cited_year, "successor_standard": successor_std, "successor_year": successor_yr}
                    ))
                else:
                    # Outdated edition of same standard without formal lineage supersession
                    status = "outdated"
                    findings.append(Finding(
                        code="OUTDATED_EDITION",
                        severity="warning",
                        message=f"Cited edition '{raw_citation}' ({cited_year}) is outdated. Latest published edition is '{latest_std_num}' ({latest_year}).",
                        details={"cited_year": cited_year, "latest_year": latest_year}
                    ))
        else:
            # ── CITED WITHOUT YEAR: CITATION_NO_YEAR ──
            # Do NOT resolve to bare "compliant". Emit CITATION_NO_YEAR finding.
            # Separately state that the base standard is otherwise valid and active in the BIS registry.
            status = "incomplete"
            base_std_name = latest_std_num.split(":")[0] if ":" in latest_std_num else latest_std_num
            findings.append(Finding(
                code="CITATION_NO_YEAR",
                severity="warning",
                message=(
                    f"Standard cited without publication/revision year. Base standard '{base_std_name}' is valid "
                    f"and active in BIS registry (latest active edition is '{latest_std_num}' / {latest_year}), "
                    f"but tender does not specify the applicable edition year."
                ),
                details={
                    "base_standard_valid": True,
                    "base_standard_name": base_std_name,
                    "latest_active_edition": latest_std_num,
                    "latest_active_year": latest_year,
                    "is_status_label": latest_status
                }
            ))

        return ResolvedStandard(
            raw_citation=raw_citation,
            base_key=base_key,
            cited_year=cited_year,
            cited_part=cited_part,
            resolved_standard_number=latest_std_num,
            resolved_base_key=base_key,
            resolved_year=latest_year,
            resolved_part=cited_part,
            status=status,
            findings=findings,
            successor_standard_number=successor_std,
            successor_year=successor_yr,
            base_standard_valid=True
        )
