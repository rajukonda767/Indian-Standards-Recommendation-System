"""
recommend.py
============
Pydantic data models for the Recommendation Engine API.
"""

from typing import Optional, List, Dict
from pydantic import BaseModel, Field

class RecommendRequest(BaseModel):
    query: str = Field(..., description="Natural language specification or procurement requirement (English, Hindi, etc.)")
    language: Optional[str] = Field("en", description="User interface language (en, hi, etc.)")
    selected_option: Optional[str] = Field(None, description="Disambiguation choice if officer selected an interactive option")

class AlliedStandard(BaseModel):
    ref_number: str
    ref_title: str
    edge_type: str
    category: str

class ComplianceSuite(BaseModel):
    test_methods: List[AlliedStandard] = []
    components: List[AlliedStandard] = []
    sampling_acceptance: List[AlliedStandard] = []
    allied_others: List[AlliedStandard] = []
    total_count: int = 0

class StandardCandidate(BaseModel):
    id: int
    standard_number: str
    title: str
    dept: str
    is_status: str = "Current"
    qco_ministry: Optional[str] = None
    active_licences: int = 0
    cosine_similarity: float
    keyword_boost: float = 0.0
    title_boost: float = 0.0
    qco_boost: float = 0.0
    licence_boost: float = 0.0
    final_score: float

class Disambiguation(BaseModel):
    is_ambiguous: bool = False
    confidence_gap: float = 0.0
    question: Optional[str] = None
    options: List[str] = []

class RecommendResponse(BaseModel):
    out_of_domain: bool = False
    boundary_message: Optional[str] = None
    query: str
    normalized_query: str
    primary_standard: Optional[StandardCandidate] = None
    compliance_suite: Optional[ComplianceSuite] = None
    alternative_candidates: List[StandardCandidate] = []
    disambiguation: Disambiguation
    grounded_justification: Optional[str] = None
    tender_clause: Optional[str] = None
    timings: Dict[str, float] = {}
