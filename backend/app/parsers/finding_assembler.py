# -*- coding: utf-8 -*-
"""
backend/app/parsers/finding_assembler.py
========================================
Production-Grade Finding Assembler for Tender Standards Auditing.

Assembles per-item findings into the formal 16-code catalogue:
- CITATION_MISSING, CITATION_NO_YEAR, CITATION_NO_PART, PART_MISMATCH_VOLTAGE
- OUTDATED_EDITION, SUPERSEDED, WITHDRAWN, WRONG_STANDARD, NON_BIS_STANDARD
- VAGUE_REFERENCE, CERT_NOT_MENTIONED, ALLIED_MISSING, TITLE_SPEC_INCONSISTENT
- BRAND_RESTRICTIVE, CANNOT_VERIFY, OUT_OF_COVERAGE

Severity Taxonomy:
- 'error'   : Critical contradictions, superseded editions, missing mandatory specs
- 'warning' : Undated citations, unverified certifications, vague references, missing parts
- 'info'    : Informative notes (e.g. international equivalent resolved)

Field Consistency Comparator:
- Evaluates insulation-to-insulation and sheath-to-sheath independently.
- Recognizes that under IS 7098 ("Crosslinked Polyethylene Insulated Thermoplastic Sheathed Cables"),
  PVC/FRLS is the standard thermoplastic outer sheath material for XLPE-insulated cables,
  avoiding false-positive contradictions from commercial title shorthand.
"""
from __future__ import annotations
import re
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple

from app.db import get_db_cursor
from app.adapters.base import PageBlock
from app.parsers.item_builder import AuditItem
from app.parsers.standard_resolver import ResolvedStandard, Finding, StandardResolver
from app.parsers.verbatim_verifier import VerifiedQuote

logger = logging.getLogger("finding_assembler")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter("[%(levelname)s] [FindingAssembler] %(message)s")
    ch.setFormatter(formatter)
    logger.addHandler(ch)


class FindingCode(str, Enum):
    CITATION_MISSING          = "CITATION_MISSING"
    CITATION_NO_YEAR          = "CITATION_NO_YEAR"
    CITATION_NO_PART          = "CITATION_NO_PART"
    PART_MISMATCH_VOLTAGE     = "PART_MISMATCH_VOLTAGE"
    OUTDATED_EDITION          = "OUTDATED_EDITION"
    SUPERSEDED                = "SUPERSEDED"
    WITHDRAWN                 = "WITHDRAWN"
    WRONG_STANDARD            = "WRONG_STANDARD"
    NON_BIS_STANDARD          = "NON_BIS_STANDARD"
    VAGUE_REFERENCE           = "VAGUE_REFERENCE"
    CERT_NOT_MENTIONED        = "CERT_NOT_MENTIONED"
    ALLIED_MISSING            = "ALLIED_MISSING"
    TITLE_SPEC_INCONSISTENT   = "TITLE_SPEC_INCONSISTENT"
    BRAND_RESTRICTIVE         = "BRAND_RESTRICTIVE"
    CANNOT_VERIFY             = "CANNOT_VERIFY"
    OUT_OF_COVERAGE           = "OUT_OF_COVERAGE"


@dataclass
class ItemFinding:
    """Audit finding with full provenance, reconciled severity ('error'|'warning'|'info'), and verbatim evidence."""
    code: FindingCode
    severity: str  # 'error' | 'warning' | 'info'
    message: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code.value,
            "severity": self.severity,
            "message": self.message,
            "evidence": self.evidence,
            "details": self.details
        }


@dataclass
class AuditedItem:
    """Fully audited procurement line item ready for card rendering and scoring."""
    seq_no: int
    item_id: str
    material_code: Optional[str]
    description: str
    technical_spec: str
    resolved_standards: List[ResolvedStandard] = field(default_factory=list)
    findings: List[ItemFinding] = field(default_factory=list)
    status: str = "compliant"  # compliant | incomplete | outdated | superseded | conflict | missing | cannot_verify
    is_qco_applicable: bool = False
    is_qco_compliant: bool = True
    has_identified_standard: bool = False
    has_current_edition: Optional[bool] = None  # True (current) | False (outdated/superseded) | None (excluded, e.g. no year)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "seq_no": self.seq_no,
            "item_id": self.item_id,
            "material_code": self.material_code,
            "description": self.description,
            "technical_spec": self.technical_spec,
            "resolved_standards": [s.to_dict() for s in self.resolved_standards],
            "findings": [f.to_dict() for f in self.findings],
            "status": self.status,
            "is_qco_applicable": self.is_qco_applicable,
            "is_qco_compliant": self.is_qco_compliant,
            "has_identified_standard": self.has_identified_standard,
            "has_current_edition": self.has_current_edition
        }


class FindingAssembler:
    """
    Assembles per-item findings from resolver output, checking cross-field consistency,
    QCO statutory certification rules, and brand restrictions.
    """

    # Certification cues: supports 'ISI mark', 'ISI marked', 'BIS certified', 'BIS certification', 'BIS license/licence'
    CERT_CUE_RE = re.compile(
        r'\b(?:ISI\s*mark(?:ed|ing)?|BIS\s*cert(?:ified|ification)?|BIS\s*licen[sc]e?|standard\s*mark(?:ed)?|valid\s*CML|third\s*party\s*cert(?:ified|ification)?)\b',
        re.IGNORECASE
    )

    # Brand restrictiveness pattern
    BRAND_RESTRICTIVE_RE = re.compile(
        r'\b(?:make|brand)\s*[:\-]?\s*([A-Za-z0-9&]+)(?:\s+only|\s*,\s*no\s+other)?\b',
        re.IGNORECASE
    )

    # Explicit insulation patterns
    INSULATION_PVC_RE = re.compile(r'\b(?:pvc\s+insulat(?:ed|ion)?|insulation\s*:\s*pvc)\b', re.IGNORECASE)
    INSULATION_XLPE_RE = re.compile(r'\b(?:xlpe\s+insulat(?:ed|ion)?|insulation\s*:\s*xlpe)\b', re.IGNORECASE)

    # Explicit sheath patterns
    SHEATH_PVC_RE = re.compile(r'\b(?:pvc\s+sheath(?:ed|ing)?|sheath(?:ed|ing)?\s*:\s*pvc|frls|outer\s+sheath)\b', re.IGNORECASE)

    @classmethod
    def assemble_item(
        cls,
        item: AuditItem,
        resolved_standards: List[ResolvedStandard],
        doc_name: str = "TenderDoc",
        page_no: int = 1
    ) -> AuditedItem:
        """
        Assembles and synthesizes findings for a single AuditItem.
        """
        desc_val = item.description.value if item.description else ""
        spec_val = item.technical_spec.value if item.technical_spec else ""
        combined_text = f"{desc_val} {spec_val}".strip()

        item_findings: List[ItemFinding] = []
        is_qco_applicable = False
        is_qco_compliant = True
        has_identified_standard = False
        has_current_edition: Optional[bool] = None

        # ── 1. Check CITATION_MISSING ──
        if not resolved_standards:
            has_identified_standard = False
            item_findings.append(ItemFinding(
                code=FindingCode.CITATION_MISSING,
                severity="error",
                message=f"No standard or specification cited for item '{item.item_id}'.",
                evidence={"item_id": item.item_id, "description": desc_val, "page_no": page_no, "doc_name": doc_name}
            ))

        # ── 2. Process Resolved Standards ──
        for res in resolved_standards:
            # Evidence dictionary from verified quote or field source
            evidence_dict = {}
            if res.quote:
                evidence_dict = {
                    "quote": res.quote.quote_text,
                    "page_no": res.quote.page_no,
                    "doc_name": res.quote.doc_name,
                    "block_idx": res.quote.block_idx
                }
            else:
                evidence_dict = {
                    "quote": res.raw_citation,
                    "page_no": page_no,
                    "doc_name": doc_name,
                    "block_idx": 0
                }

            # Map findings from resolver
            for f in res.findings:
                if f.code == "SUPERSEDED":
                    item_findings.append(ItemFinding(
                        code=FindingCode.SUPERSEDED,
                        severity="error",  # Reconciled from 'critical' -> 'error'
                        message=f.message,
                        evidence=evidence_dict,
                        details=f.details
                    ))
                    has_current_edition = False

                elif f.code == "OUTDATED_EDITION":
                    item_findings.append(ItemFinding(
                        code=FindingCode.OUTDATED_EDITION,
                        severity="warning",
                        message=f.message,
                        evidence=evidence_dict,
                        details=f.details
                    ))
                    has_current_edition = False

                elif f.code == "CITATION_NO_YEAR":
                    item_findings.append(ItemFinding(
                        code=FindingCode.CITATION_NO_YEAR,
                        severity="warning",
                        message=f.message,
                        evidence=evidence_dict,
                        details=f.details
                    ))
                    # Year not specified in tender: cannot be certified as current edition
                    has_current_edition = False

                elif f.code == "CITATION_NO_PART":
                    item_findings.append(ItemFinding(
                        code=FindingCode.CITATION_NO_PART,
                        severity="warning",
                        message=f.message,
                        evidence=evidence_dict,
                        details=f.details
                    ))

                elif f.code == "NO_INDIAN_EQUIVALENT_FOUND":
                    item_findings.append(ItemFinding(
                        code=FindingCode.CANNOT_VERIFY,
                        severity="warning",
                        message=f.message,
                        evidence=evidence_dict,
                        details=f.details
                    ))

                elif f.code == "INTERNATIONAL_EQUIVALENT_RESOLVED":
                    item_findings.append(ItemFinding(
                        code=FindingCode.NON_BIS_STANDARD,
                        severity="info",
                        message=f.message,
                        evidence=evidence_dict,
                        details=f.details
                    ))

            # Mark identified standard coverage
            if res.status != "cannot_verify" and res.status != "missing":
                has_identified_standard = True
                if res.cited_year is not None and has_current_edition is None:
                    # Valid year cited and not marked superseded/outdated
                    if res.status not in ("superseded", "outdated") and not any(
                        getattr(f, 'code', str(f)) in ("SUPERSEDED", "OUTDATED_EDITION") for f in res.findings
                    ):
                        has_current_edition = True
                    else:
                        has_current_edition = False
                elif res.cited_year is None:
                    # Undated citation: tender omitted publication year, so it is NOT verified current
                    has_current_edition = False

            # ── 3. Check Statutory QCO Mandate in DB ──
            qco_min, cert_type, cert_verified = cls._lookup_qco(res.resolved_base_key or res.base_key)
            if cert_type == "Mandatory" or qco_min:
                is_qco_applicable = True
                # Verify if tender stipulates mandatory ISI mark / BIS license
                if not cls.CERT_CUE_RE.search(combined_text):
                    is_qco_compliant = False
                    if cert_verified is True:
                        msg = (
                            f"Item '{item.item_id}' falls under mandatory Quality Control Order (QCO) "
                            f"issued by {qco_min or 'Central Government'} for {res.resolved_standard_number or res.base_key}, "
                            f"but mandatory BIS Certification / ISI Mark requirement is not stipulated in the tender specification."
                        )
                    else:
                        msg = (
                            f"Potential Quality Control Order (QCO) noted for {res.resolved_standard_number or res.base_key}, "
                            f"but certification status not verified, check BIS portal. "
                            f"Tender does not stipulate mandatory BIS Certification / ISI Mark requirement."
                        )
                    item_findings.append(ItemFinding(
                        code=FindingCode.CERT_NOT_MENTIONED,
                        severity="warning",
                        message=msg,
                        evidence=evidence_dict,
                        details={
                            "qco_ministry": qco_min,
                            "standard": res.resolved_standard_number,
                            "certification_verified": cert_verified
                        }
                    ))
            elif not cert_verified and res.resolved_base_key and not cls.CERT_CUE_RE.search(combined_text):
                item_findings.append(ItemFinding(
                    code=FindingCode.CERT_NOT_MENTIONED,
                    severity="warning",
                    message=(
                        f"Certification status not verified, check BIS portal for {res.resolved_standard_number or res.base_key}. "
                        f"Tender does not specify mandatory BIS Certification / ISI Mark requirement."
                    ),
                    evidence=evidence_dict,
                    details={
                        "standard": res.resolved_standard_number,
                        "certification_verified": False,
                        "qco_ministry": None
                    }
                ))

        # ── 4. Cross-Field Consistency Check (TITLE_SPEC_INCONSISTENT) ──
        # Check explicit insulation-to-insulation and sheath-to-sheath comparisons.
        # Under IS 7098 ("Crosslinked Polyethylene Insulated Thermoplastic Sheathed Cables"):
        #   - Conductor Insulation: XLPE
        #   - Sheath / Jacketing: Thermoplastic (PVC / PVC FRLS)
        # Therefore, "PVC FRLS" or bare "PVC" in cable title refers to the sheath material,
        # which is fully compatible with IS 7098 (XLPE insulation + PVC sheath).
        desc_insul_pvc = bool(cls.INSULATION_PVC_RE.search(desc_val))
        spec_insul_xlpe = bool(cls.INSULATION_XLPE_RE.search(spec_val)) or (
            "7098" in spec_val and not cls.INSULATION_PVC_RE.search(spec_val)
        )

        desc_insul_xlpe = bool(cls.INSULATION_XLPE_RE.search(desc_val))
        spec_insul_pvc = bool(cls.INSULATION_PVC_RE.search(spec_val))

        # Only fire if there is an explicit insulation-to-insulation contradiction
        if desc_insul_pvc and spec_insul_xlpe:
            item_findings.append(ItemFinding(
                code=FindingCode.TITLE_SPEC_INCONSISTENT,
                severity="error",
                message=(
                    f"Item description specifies 'PVC' insulation ('{desc_val}'), but technical specification "
                    f"mandates 'IS 7098' Crosslinked Polyethylene (XLPE) insulation. "
                    f"Contradictory insulation specifications create critical contractual ambiguity."
                ),
                evidence={
                    "description_quote": desc_val,
                    "spec_quote": spec_val[:80],
                    "doc_name": doc_name,
                    "page_no": page_no
                },
                details={"desc_insulation": "PVC", "spec_insulation": "XLPE", "standard": "IS 7098"}
            ))
        elif desc_insul_xlpe and spec_insul_pvc:
            item_findings.append(ItemFinding(
                code=FindingCode.TITLE_SPEC_INCONSISTENT,
                severity="error",
                message=(
                    f"Item description specifies 'XLPE' insulation ('{desc_val}'), but technical specification "
                    f"mandates 'PVC' insulation ('{spec_val[:80]}')."
                ),
                evidence={
                    "description_quote": desc_val,
                    "spec_quote": spec_val[:80],
                    "doc_name": doc_name,
                    "page_no": page_no
                },
                details={"desc_insulation": "XLPE", "spec_insulation": "PVC"}
            ))

        # ── 5. Brand Restrictiveness Check (BRAND_RESTRICTIVE) ──
        m_brand = cls.BRAND_RESTRICTIVE_RE.search(combined_text)
        if m_brand and not re.search(r'\bor\s+equivalent\b', combined_text, re.I):
            item_findings.append(ItemFinding(
                code=FindingCode.BRAND_RESTRICTIVE,
                severity="warning",
                message=f"Tender specifies proprietary make/brand '{m_brand.group(1)}' without allowing 'or equivalent' alternatives.",
                evidence={"match": m_brand.group(0), "page_no": page_no, "doc_name": doc_name}
            ))

        # ── 6. Synthesize Overall Item Status ──
        status = "compliant"
        finding_codes = {f.code for f in item_findings}

        if FindingCode.SUPERSEDED in finding_codes:
            status = "superseded"
        elif FindingCode.TITLE_SPEC_INCONSISTENT in finding_codes:
            status = "conflict"
        elif FindingCode.OUTDATED_EDITION in finding_codes:
            status = "outdated"
        elif FindingCode.CITATION_MISSING in finding_codes:
            status = "missing"
        elif FindingCode.CANNOT_VERIFY in finding_codes:
            status = "cannot_verify"
        elif (
            FindingCode.CITATION_NO_YEAR in finding_codes
            or FindingCode.CITATION_NO_PART in finding_codes
            or FindingCode.CERT_NOT_MENTIONED in finding_codes
        ):
            status = "incomplete"

        return AuditedItem(
            seq_no=item.seq_no,
            item_id=item.item_id,
            material_code=item.material_code.value if item.material_code else None,
            description=desc_val,
            technical_spec=spec_val,
            resolved_standards=resolved_standards,
            findings=item_findings,
            status=status,
            is_qco_applicable=is_qco_applicable,
            is_qco_compliant=is_qco_compliant,
            has_identified_standard=has_identified_standard,
            has_current_edition=has_current_edition
        )

    _QCO_CACHE: Dict[str, Tuple[Optional[str], Optional[str], bool]] = {}

    @classmethod
    def _lookup_qco(cls, base_key: str) -> Tuple[Optional[str], Optional[str], bool]:
        """Queries PostgreSQL standards table for QCO ministry, certification, and verification flag."""
        if not base_key:
            return None, None, False
        if base_key in cls._QCO_CACHE:
            return cls._QCO_CACHE[base_key]
        try:
            with get_db_cursor() as cur:
                cur.execute("""
                    SELECT s.qco_ministry, s.certification, COALESCE(s.certification_verified, FALSE)
                    FROM standards s
                    JOIN standard_keys k ON k.standard_id = s.id
                    WHERE k.base_key = %s
                    LIMIT 1;
                """, (base_key,))
                row = cur.fetchone()
                if row:
                    res = (row[0], row[1], bool(row[2]))
                    cls._QCO_CACHE[base_key] = res
                    return res
                # Fallback to direct standards table
                cur.execute("""
                    SELECT qco_ministry, certification, COALESCE(certification_verified, FALSE)
                    FROM standards 
                    WHERE base_number = %s OR base_key = %s 
                    LIMIT 1;
                """, (base_key, base_key))
                row = cur.fetchone()
                if row:
                    res = (row[0], row[1], bool(row[2]))
                    cls._QCO_CACHE[base_key] = res
                    return res
        except Exception as e:
            logger.warning(f"QCO lookup error for {base_key}: {e}")
        res = (None, None, False)
        cls._QCO_CACHE[base_key] = res
        return res
