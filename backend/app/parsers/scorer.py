# -*- coding: utf-8 -*-
"""
backend/app/parsers/scorer.py
=============================
Audit Scoring Engine for Tender Standards Compliance.

Computes the three core procurement audit sub-scores:
1. Coverage: Proportion of line items specifying an identified Indian or international standard.
2. Currency: Proportion of dated standard citations that are the current, un-superseded edition.
   - Fully supports N/A when denominator is 0 (e.g. when citations omit publication year: CITATION_NO_YEAR).
3. QCO Compliance: Proportion of items falling under statutory Quality Control Orders (QCO)
   that properly stipulate mandatory BIS Certification / ISI Mark requirements.
   - Fully supports N/A when no items fall under mandatory QCOs.

Strictly follows deterministic arithmetic with explicit X of Y denominators and audit diagnostics.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from app.parsers.finding_assembler import AuditedItem, FindingCode


@dataclass
class SubScore:
    """Represents an individual audit dimension sub-score with exact arithmetic."""
    name: str
    numerator: int
    denominator: int
    percentage: Optional[float]  # None if denominator == 0 (N/A)
    is_na: bool
    display_value: str          # e.g. "100.0%", "0.0%", "N/A"
    arithmetic_str: str         # e.g. "3 of 3 items (100.0%)", "0 of 0 dated items (N/A)"
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "numerator": self.numerator,
            "denominator": self.denominator,
            "percentage": self.percentage,
            "is_na": self.is_na,
            "display_value": self.display_value,
            "arithmetic_str": self.arithmetic_str,
            "explanation": self.explanation,
        }


@dataclass
class AuditScoreCard:
    """Overall scorecard consolidating Coverage, Currency, and QCO Compliance."""
    total_items: int
    coverage: SubScore
    currency: SubScore
    qco_compliance: SubScore
    status_counts: Dict[str, int] = field(default_factory=dict)
    finding_counts: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_items": self.total_items,
            "coverage": self.coverage.to_dict(),
            "currency": self.currency.to_dict(),
            "qco_compliance": self.qco_compliance.to_dict(),
            "status_counts": self.status_counts,
            "finding_counts": self.finding_counts,
        }


def calculate_audit_scores(items: List[AuditedItem]) -> AuditScoreCard:
    """
    Computes Coverage, Currency, and QCO Compliance scores strictly from per-item findings.
    
    Rules:
    - Coverage:
        Denominator = Total auditable items.
        Numerator = Items with has_identified_standard == True.
    - Currency:
        Denominator = Items with dated standard citations (has_current_edition is not None).
        Numerator = Items where has_current_edition == True.
        If Denominator == 0 (e.g. all citations are undated CITATION_NO_YEAR): N/A.
    - QCO Compliance:
        Denominator = Items where is_qco_applicable == True.
        Numerator = Items where is_qco_compliant == True (no CERT_NOT_MENTIONED finding).
        If Denominator == 0 (no items under mandatory QCO): N/A.
    """
    total_items = len(items)

    status_counts: Dict[str, int] = {}
    finding_counts: Dict[str, int] = {}

    for it in items:
        status_counts[it.status] = status_counts.get(it.status, 0) + 1
        for f in it.findings:
            c_val = f.code.value if hasattr(f.code, "value") else str(f.code)
            finding_counts[c_val] = finding_counts.get(c_val, 0) + 1

    # ── 1. Coverage Calculation ────────────────────────────────────────────────
    cov_num = sum(1 for it in items if it.has_identified_standard)
    cov_den = total_items

    if cov_den > 0:
        cov_pct = round((cov_num / cov_den) * 100.0, 1)
        cov_disp = f"{cov_pct:.1f}%"
        cov_arith = f"{cov_num} of {cov_den} items ({cov_disp})"
        cov_expl = f"{cov_num} of {cov_den} procurement items cite an identified standard."
        cov_na = False
    else:
        cov_pct = None
        cov_disp = "N/A"
        cov_arith = "0 of 0 items (N/A)"
        cov_expl = "No procurement items available to audit."
        cov_na = True

    coverage_score = SubScore(
        name="Coverage",
        numerator=cov_num,
        denominator=cov_den,
        percentage=cov_pct,
        is_na=cov_na,
        display_value=cov_disp,
        arithmetic_str=cov_arith,
        explanation=cov_expl,
    )

    # ── 2. Currency Calculation ────────────────────────────────────────────────
    # Evaluates all items citing an identified standard (taking both dated and undated into consideration)
    cited_items = [it for it in items if it.has_identified_standard]
    cur_den = len(cited_items)
    cur_num = sum(1 for it in cited_items if it.has_current_edition is True)

    if cur_den > 0:
        cur_pct = round((cur_num / cur_den) * 100.0, 1)
        cur_disp = f"{cur_pct:.1f}%"
        cur_arith = f"{cur_num} of {cur_den} cited items ({cur_disp})"
        cur_expl = f"{cur_num} of {cur_den} items cite an active and current standard in the BIS registry."
        cur_na = False
    else:
        cur_pct = None
        cur_disp = "N/A"
        cur_arith = "0 of 0 items (N/A)"
        cur_expl = "No cited standards found to evaluate currency."
        cur_na = True

    currency_score = SubScore(
        name="Currency",
        numerator=cur_num,
        denominator=cur_den,
        percentage=cur_pct,
        is_na=cur_na,
        display_value=cur_disp,
        arithmetic_str=cur_arith,
        explanation=cur_expl,
    )

    # ── 3. QCO Compliance Calculation ──────────────────────────────────────────
    qco_items = [it for it in items if it.is_qco_applicable]
    qco_den = len(qco_items)
    qco_num = sum(1 for it in qco_items if it.is_qco_compliant)

    if qco_den > 0:
        qco_pct = round((qco_num / qco_den) * 100.0, 1)
        qco_disp = f"{qco_pct:.1f}%"
        qco_arith = f"{qco_num} of {qco_den} QCO items ({qco_disp})"
        qco_expl = (
            f"{qco_num} of {qco_den} items subject to statutory Quality Control Orders "
            f"properly stipulate mandatory BIS Certification / ISI Mark requirements."
        )
        qco_na = False
    else:
        qco_pct = None
        qco_disp = "N/A"
        qco_arith = "0 of 0 QCO items (N/A)"
        qco_expl = "N/A: None of the procurement items fall under mandatory statutory Quality Control Orders."
        qco_na = True

    qco_score = SubScore(
        name="QCO Compliance",
        numerator=qco_num,
        denominator=qco_den,
        percentage=qco_pct,
        is_na=qco_na,
        display_value=qco_disp,
        arithmetic_str=qco_arith,
        explanation=qco_expl,
    )

    return AuditScoreCard(
        total_items=total_items,
        coverage=coverage_score,
        currency=currency_score,
        qco_compliance=qco_score,
        status_counts=status_counts,
        finding_counts=finding_counts,
    )
