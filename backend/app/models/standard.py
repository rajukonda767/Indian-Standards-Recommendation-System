"""
standard.py
===========
Pydantic data models for standards exploration and 2D knowledge graph visualization.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel

class LineageRecord(BaseModel):
    relationship: str
    related_standard_raw: str
    related_base_number: Optional[str] = None
    related_year: Optional[int] = None

class StandardSummary(BaseModel):
    id: int
    standard_number: str
    base_number: str
    year: Optional[int]
    dept: Optional[str]
    title: str
    is_status_label: Optional[str]
    qco_ministry: Optional[str]
    active_licences: int = 0
    references_count: int = 0
    reaffirmation_year: Optional[int] = None

class StandardDetail(StandardSummary):
    status_raw: Optional[str] = None
    published_on: Optional[str] = None
    reaffirmation_year: Optional[int] = None
    revisions_count: Optional[int] = None
    technical_committee: Optional[str] = None
    ics_code: Optional[str] = None
    type_of_standard: Optional[str] = None
    certification: Optional[str] = None
    group_name: Optional[str] = None
    sub_group: Optional[str] = None
    sub_sub_group: Optional[str] = None
    virtual_scope: Optional[str] = None
    source_url: Optional[str] = None
    total_isi_licences: Optional[int] = None
    product_varieties: Optional[str] = None
    lineage: List[LineageRecord] = []

class GraphNode(BaseModel):
    id: str
    label: str
    title: str
    type: str  # "primary", "test_method", "component", "sampling", "lineage"
    dept: Optional[str] = None
    val: int = 10  # node size

class GraphLink(BaseModel):
    source: str
    target: str
    label: str
    edge_type: str

class KnowledgeGraphResponse(BaseModel):
    standard_number: str
    nodes: List[GraphNode]
    links: List[GraphLink]
