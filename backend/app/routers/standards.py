"""
standards.py
============
FastAPI Router for Standards Explorer & 2D Knowledge Graph visualization.
"""

from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from app.db import get_db_cursor
from app.models.standard import (
    StandardSummary,
    StandardDetail,
    LineageRecord,
    KnowledgeGraphResponse
)
from app.services.graph_service import get_knowledge_graph_data

router = APIRouter(prefix="/standards", tags=["Standards Explorer"])


@router.get("/filters")
async def get_filter_options():
    """Return distinct filter options (committees, statuses) for the UI.
    Only returns committees with proper {DEPT} {NN} - {Name} format (strips bare-name duplicates).
    """
    import re
    with get_db_cursor() as cur:
        cur.execute(
            "SELECT DISTINCT technical_committee FROM standards "
            "WHERE technical_committee IS NOT NULL ORDER BY technical_committee"
        )
        all_committees = [r[0] for r in cur.fetchall()]

    # Only keep entries that match "{DEPT} {NN} - {Name}" format
    # This strips bare-name duplicates like "Power Cables", "Ferro Alloys" etc.
    prefix_pattern = re.compile(r'^(CED|ETD|MTD)\s+\d+\s*-\s*.+')
    committees = [c for c in all_committees if prefix_pattern.match(c)]

    return {
        "committees": committees,
        "statuses": ["Current", "Reaffirmed", "Under Review", "Published", "Withdrawn"]
    }


@router.get("", response_model=List[StandardSummary])
async def list_standards(
    dept: Optional[str] = Query(None, description="Department filter (CED, ETD, MTD)"),
    committee: Optional[str] = Query(None, description="Technical committee filter"),
    status: Optional[str] = Query(None, description="Status filter (Current, Reaffirmed, Under Review, Published, Withdrawn)"),
    qco_only: bool = Query(False, description="Filter for standards with mandatory QCO"),
    search: Optional[str] = Query(None, description="Keyword search in standard number or title"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    """Browse and filter indexed BIS standards with pagination."""
    conditions = ["1=1"]
    params = []

    if dept:
        conditions.append("dept = %s")
        params.append(dept.upper())
    if committee:
        conditions.append("technical_committee = %s")
        params.append(committee)
    if status:
        st_clean = status.strip().lower()
        if st_clean == "reaffirmed":
            conditions.append("reaffirmation_year IS NOT NULL")
        elif st_clean == "withdrawn":
            conditions.append("(is_status_label ILIKE '%withdraw%' OR status_raw ILIKE '%withdraw%')")
        elif st_clean == "under review":
            conditions.append("is_status_label = 'Under Review'")
        elif st_clean == "published":
            conditions.append("is_status_label = 'Published'")
        elif st_clean == "current":
            conditions.append("(is_status_label = 'Current' OR status_raw = 'Current')")
        else:
            conditions.append("is_status_label = %s")
            params.append(status)
    if qco_only:
        conditions.append("qco_ministry IS NOT NULL")
    if search:
        conditions.append("(standard_number ILIKE %s OR title ILIKE %s)")
        search_param = f"%{search.strip()}%"
        params.extend([search_param, search_param])

    where_clause = " AND ".join(conditions)
    params.extend([limit, offset])

    with get_db_cursor() as cur:
        cur.execute(f"""
            SELECT id, standard_number, base_number, year, dept, title,
                   is_status_label, qco_ministry, active_licences, references_count,
                   reaffirmation_year
            FROM standards
            WHERE {where_clause}
            ORDER BY active_licences DESC, standard_number ASC
            LIMIT %s OFFSET %s;
        """, tuple(params))
        rows = cur.fetchall()

    return [
        StandardSummary(
            id=r[0],
            standard_number=r[1],
            base_number=r[2],
            year=r[3],
            dept=r[4],
            title=r[5],
            is_status_label=r[6],
            qco_ministry=r[7],
            active_licences=r[8] or 0,
            references_count=r[9] or 0,
            reaffirmation_year=r[10]
        )
        for r in rows
    ]


@router.get("/{standard_number}", response_model=StandardDetail)
async def get_standard_detail(standard_number: str):
    """Fetch complete metadata, licence varieties, and lineage for a single standard."""
    sn_clean = standard_number.strip()
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT s.id, s.standard_number, s.base_number, s.year, s.dept, s.title,
                   s.is_status_label, s.qco_ministry, s.active_licences, s.references_count,
                   s.status_raw, s.published_on, s.reaffirmation_year, s.revisions_count,
                   s.technical_committee, s.ics_code, s.type_of_standard, s.certification,
                   s.group_name, s.sub_group, s.sub_sub_group, s.virtual_scope,
                   s.source_url,
                   lv.total_isi_licences, lv.product_varieties
            FROM standards s
            LEFT JOIN licence_varieties lv ON s.id = lv.standard_id
            WHERE s.standard_number = %s;
        """, (sn_clean,))
        row = cur.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail=f"Standard '{sn_clean}' not found.")

        # Fetch lineage
        cur.execute("""
            SELECT relationship, related_standard_raw, related_base_number, related_year
            FROM standard_lineage
            WHERE standard_id = %s;
        """, (row[0],))
        lineage_rows = cur.fetchall()

    lineage_records = [
        LineageRecord(
            relationship=lr[0],
            related_standard_raw=lr[1],
            related_base_number=lr[2],
            related_year=lr[3]
        )
        for lr in lineage_rows
    ]

    return StandardDetail(
        id=row[0],
        standard_number=row[1],
        base_number=row[2],
        year=row[3],
        dept=row[4],
        title=row[5],
        is_status_label=row[6],
        qco_ministry=row[7],
        active_licences=row[8] or 0,
        references_count=row[9] or 0,
        status_raw=row[10],
        published_on=str(row[11]) if row[11] else None,
        reaffirmation_year=row[12],
        revisions_count=row[13],
        technical_committee=row[14],
        ics_code=row[15],
        type_of_standard=row[16],
        certification=row[17],
        group_name=row[18],
        sub_group=row[19],
        sub_sub_group=row[20],
        virtual_scope=row[21],
        source_url=row[22] or None,
        total_isi_licences=row[23],
        product_varieties=row[24],
        lineage=lineage_records
    )


@router.get("/{standard_number}/graph", response_model=KnowledgeGraphResponse)
async def get_standard_graph(standard_number: str):
    """Returns nodes and links for 2D Knowledge Graph visualization."""
    data = get_knowledge_graph_data(standard_number.strip())
    if not data.nodes:
        raise HTTPException(status_code=404, detail=f"No graph data found for '{standard_number}'.")
    return data
