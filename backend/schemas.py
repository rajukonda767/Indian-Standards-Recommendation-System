"""
schemas.py
==========
Pydantic data contracts for SIH-26108 BIS Standards Recommendation & Tender Audit Engine.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# ── Phase 1.1 Extraction Schemas ─────────────────────────────────────────────

class ExtractedSpec(BaseModel):
    product_category: Optional[str] = Field(None, description="Generic engineering product category")
    material: Optional[str] = Field(None, description="Primary material (e.g. PVC, XLPE, Steel, HDPE)")
    voltage_rating: Optional[str] = Field(None, description="Electrical voltage rating (e.g. 1100V, 11kV)")
    dimensions: Optional[str] = Field(None, description="Cross-section, diameter, or physical dimensions")
    application: Optional[str] = Field(None, description="Intended usage or installation environment")
    cited_standard_raw: Optional[str] = Field(None, description="Verbatim cited IS standard if present")
    brand_names_removed: List[str] = Field(default_factory=list, description="Commercial brand/trade names stripped")


class ExtractRequest(BaseModel):
    text: str = Field(..., description="Raw requirement or tender line item text")


# ── Phase 1.2 - 1.6 Recommendation Schemas ───────────────────────────────────

class RecommendRequest(BaseModel):
    query: Optional[str] = Field(None, description="Raw natural language procurement query")
    extracted: Optional[ExtractedSpec] = Field(None, description="Pre-extracted structured specification")
    selected_option: Optional[str] = Field(None, description="Disambiguation choice if officer selected an option")
    language: Optional[str] = Field("en", description="Target UI language (en, hi, te)")


class CertificationInfo(BaseModel):
    verified: bool
    value: Optional[str] = None
    qco_ministry: Optional[str] = None
    source_url: Optional[str] = None


class PrimaryCandidate(BaseModel):
    standard_id: int
    standard_number: str
    title: str
    confidence: float = Field(..., ge=0.0, le=100.0, description="Confidence percentage 0-100")
    is_status_label: str
    superseded_by: Optional[str] = None
    why: str = Field(..., description="Grounded explanation built strictly from retrieved DB fields")
    conflict_warning: Optional[str] = None
    certification: CertificationInfo
    differentiator: Optional[str] = Field(None, description="Officer-friendly condition explaining when to choose this alternative over primary")


class AlliedItem(BaseModel):
    standard_number: str
    title: str
    edge_type: str
    category: str
    status: Optional[str] = None
    latest_edition_year: Optional[int] = None


class AlliedGroup(BaseModel):
    normative_references: List[AlliedItem] = Field(default_factory=list)
    test_methods: List[AlliedItem] = Field(default_factory=list)
    terminology: List[AlliedItem] = Field(default_factory=list)
    safety_standards: List[AlliedItem] = Field(default_factory=list)
    installation_standards: List[AlliedItem] = Field(default_factory=list)
    related_product_standards: List[AlliedItem] = Field(default_factory=list)


class DisambiguationOption(BaseModel):
    """One selectable card in the disambiguation modal."""
    label: str = Field(..., description="Human-readable spec description, e.g. 'PVC pipe fittings for drainage'")
    standard_number: str = Field(..., description="IS number, e.g. 'IS 4985:2000'")
    rewritten_query: str = Field(..., description="Ready-to-submit reformulated query for this standard")


class RecommendResponse(BaseModel):
    status: str = Field(..., description="'ok' | 'ambiguous' | 'out_of_scope'")
    primary: List[PrimaryCandidate] = Field(default_factory=list)
    allied: AlliedGroup = Field(default_factory=AlliedGroup)
    disambiguation_question: Optional[str] = None
    disambiguation_options: Optional[List[DisambiguationOption]] = None
    custom_option_text: Optional[str] = None
    candidates: Optional[List[PrimaryCandidate]] = None
    message: Optional[str] = None
    extracted_spec: Optional[ExtractedSpec] = None
    timings: Dict[str, float] = Field(default_factory=dict)
