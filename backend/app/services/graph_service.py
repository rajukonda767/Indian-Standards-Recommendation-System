"""
graph_service.py
================
Knowledge graph traversal for allied standards, test methods, licence varieties, and 2D visualization.
"""

import logging
from typing import Dict, Any, List
from app.db import get_db_cursor
from app.models.recommend import ComplianceSuite, AlliedStandard
from app.models.standard import KnowledgeGraphResponse, GraphNode, GraphLink

logger = logging.getLogger(__name__)

def get_normative_compliance_suite(standard_id: int) -> ComplianceSuite:
    """
    Fetches referenced standards for standard_id and categorizes them into:
    - Lab Test Methods
    - Components & Raw Materials
    - Sampling & Acceptance Standards
    - Allied / Referenced Standards
    """
    test_methods = []
    components = []
    sampling = []
    others = []

    with get_db_cursor() as cur:
        cur.execute("""
            SELECT ref_standard_number, ref_title, edge_type
            FROM standard_references
            WHERE primary_standard_id = %s
            ORDER BY edge_type ASC, ref_standard_number ASC;
        """, (standard_id,))
        rows = cur.fetchall()

    for ref_num, title, edge_type in rows:
        title_str = title or ""
        t_lower = title_str.lower()
        e_upper = (edge_type or "ALLIED").upper()

        std_item = AlliedStandard(
            ref_number=ref_num,
            ref_title=title_str,
            edge_type=e_upper,
            category="Allied"
        )

        if "sampling" in t_lower or "inspection" in t_lower or "acceptance" in t_lower or "SAMPLING" in e_upper:
            std_item.category = "Sampling & Acceptance"
            sampling.append(std_item)
        elif "test" in t_lower or "method" in t_lower or "analysis" in t_lower or "TEST_METHOD" in e_upper:
            std_item.category = "Mandatory Test Method"
            test_methods.append(std_item)
        elif "component" in e_upper or "conductor" in t_lower or "fitting" in t_lower or "insulation" in t_lower or "raw" in t_lower:
            std_item.category = "Component / Raw Material"
            components.append(std_item)
        else:
            std_item.category = "Allied Standard"
            others.append(std_item)

    return ComplianceSuite(
        test_methods=test_methods[:10],
        components=components[:10],
        sampling_acceptance=sampling[:10],
        allied_others=others[:10],
        total_count=len(rows)
    )


def get_licence_info(standard_id: int) -> Dict[str, Any]:
    """Fetches total active ISI licences and product varieties for standard_id."""
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT total_isi_licences, product_varieties
            FROM licence_varieties
            WHERE standard_id = %s
            LIMIT 1;
        """, (standard_id,))
        row = cur.fetchone()
    if row:
        return {"total_isi_licences": row[0] or 0, "product_varieties": row[1] or ""}
    return {"total_isi_licences": 0, "product_varieties": ""}


def get_knowledge_graph_data(standard_number: str) -> KnowledgeGraphResponse:
    """
    Constructs node-link JSON payload formatted for react-force-graph-2d.
    Includes:
    - Primary Standard (central root node)
    - Test Methods (linked with 'TESTS' link)
    - Component / Allied Standards (linked with 'REQUIRES' / 'REFERENCES' link)
    - Lineage Standards (linked with 'SUPERSEDES' or 'SUPERSEDED_BY' link)
    """
    with get_db_cursor() as cur:
        # Fetch primary standard details
        cur.execute("""
            SELECT id, standard_number, title, dept, is_status_label, active_licences
            FROM standards
            WHERE standard_number = %s;
        """, (standard_number,))
        primary = cur.fetchone()

        if not primary:
            return KnowledgeGraphResponse(standard_number=standard_number, nodes=[], links=[])

        primary_id, sn, title, dept, status_label, licences = primary

        nodes = [
            GraphNode(
                id=sn,
                label=sn,
                title=title,
                type="primary",
                dept=dept,
                val=28
            )
        ]
        links = []
        seen_nodes = {sn}

        # 1. Fetch Allied References
        cur.execute("""
            SELECT ref_standard_number, ref_title, edge_type
            FROM standard_references
            WHERE primary_standard_id = %s
            LIMIT 30;
        """, (primary_id,))
        refs = cur.fetchall()

        for ref_num, ref_title, edge_type in refs:
            if not ref_num:
                continue
            e_type = (edge_type or "ALLIED").upper()
            node_type = "test_method" if "TEST" in e_type or "test" in (ref_title or "").lower() else "allied"
            
            if ref_num not in seen_nodes:
                seen_nodes.add(ref_num)
                nodes.append(GraphNode(
                    id=ref_num,
                    label=ref_num,
                    title=ref_title or ref_num,
                    type=node_type,
                    dept=dept,
                    val=14 if node_type == "test_method" else 10
                ))

            links.append(GraphLink(
                source=sn,
                target=ref_num,
                label=e_type,
                edge_type=e_type
            ))

        # 2. Fetch Lineage Edges
        cur.execute("""
            SELECT relationship, related_standard_raw
            FROM standard_lineage
            WHERE standard_id = %s;
        """, (primary_id,))
        lineages = cur.fetchall()

        for rel, rel_std in lineages:
            if not rel_std or rel_std in seen_nodes:
                continue
            seen_nodes.add(rel_std)
            rel_type = "lineage"
            nodes.append(GraphNode(
                id=rel_std,
                label=rel_std,
                title=f"Historical Lineage ({rel})",
                type=rel_type,
                dept=dept,
                val=16
            ))
            links.append(GraphLink(
                source=sn,
                target=rel_std,
                label=rel.upper(),
                edge_type=rel.upper()
            ))

    return KnowledgeGraphResponse(
        standard_number=sn,
        nodes=nodes,
        links=links
    )
