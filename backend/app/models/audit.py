"""
audit.py
========
Pydantic data models for the Tender Compliance Audit Engine.
"""

from typing import Optional, List, Dict
from pydantic import BaseModel, Field

class TextAuditRequest(BaseModel):
    tender_text: str = Field(..., description="Raw text of the tender specification or Bill of Quantities (BOQ)")

class AuditLineItem(BaseModel):
    item_id: int
    description: str
    cited_standard: Optional[str] = None
    cited_status: str = Field(..., description="COMPLIANT, OUTDATED, MISSING, or CONTRADICTION")
    recommended_standard: str
    recommended_title: str
    action_required: str
    qco_mandatory: bool = False
    confidence_score: float = 0.0
    explanation: str

class AuditReport(BaseModel):
    total_items: int = 0
    compliant_items: int = 0
    outdated_items: int = 0
    missing_items: int = 0
    conflict_items: int = 0
    coverage_score: float = 0.0      # % of items with standard identified
    currency_score: float = 0.0      # % of cited standards that are current
    qco_compliance_score: float = 0.0 # % of mandatory items properly compliant
    overall_score: float = 0.0       # Weighted composite audit score (0-100)
    summary_remarks: str = ""
    line_items: List[AuditLineItem] = []
    timings: Dict[str, float] = {}
