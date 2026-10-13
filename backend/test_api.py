"""
test_api.py
===========
Automated test suite for FastAPI REST endpoints (Milestone 2.2).
Tests:
1. GET  /api/health
2. POST /api/recommend (Primary standard, compliance suite, tender clause)
3. POST /api/recommend (Interactive Disambiguation Guard on underspecified query)
4. POST /api/recommend (Domain Boundary Guard on out-of-scope query)
5. GET  /api/standards (Search & filter)
6. GET  /api/standards/{standard_number} (Detail & licence varieties)
7. GET  /api/standards/{standard_number}/graph (2D Force graph data)
"""

import sys
import os

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from fastapi.testclient import TestClient
from app.main import app

def run_api_tests():
    print("=" * 80)
    print("SIH-26108 | MILESTONE 2.2 - FASTAPI ENDPOINTS TEST SUITE")
    print("=" * 80)

    client = TestClient(app)
    all_passed = True

    # -------------------------------------------------------------
    # Test 1: Health Check
    # -------------------------------------------------------------
    print("\n[TEST 1] GET /api/health ...", end=" ", flush=True)
    resp = client.get("/api/health")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    health_data = resp.json()
    assert health_data["status"] == "healthy", f"Expected healthy, got {health_data['status']}"
    assert health_data["database"]["connected"] is True
    assert health_data["database"]["embedded_standards_count"] == 400
    print("[PASS]")
    print(f"         Hardware: {health_data['hardware']['device'].upper()} | {health_data['hardware']['gpu'].get('name', 'N/A')}")
    print(f"         Database: Supabase connected (400/400 standards embedded)")

    # -------------------------------------------------------------
    # Test 2: Standard Recommendation + Compliance Suite + Tender Clause
    # -------------------------------------------------------------
    query_wire = "1.5 sq mm fire resistant PVC copper wire for residential building"
    print(f"\n[TEST 2] POST /api/recommend (\"{query_wire}\") ...", end=" ", flush=True)
    resp = client.post("/api/recommend", json={"query": query_wire})
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    rec_data = resp.json()

    assert rec_data["out_of_domain"] is False
    assert rec_data["primary_standard"] is not None
    top_sn = rec_data["primary_standard"]["standard_number"]
    assert "IS 694" in top_sn, f"Expected IS 694, got {top_sn}"

    # Verify Normative Compliance Suite
    suite = rec_data["compliance_suite"]
    assert suite is not None
    assert len(suite["test_methods"]) > 0, "Expected allied test methods"

    # Verify Tender Clause
    clause = rec_data["tender_clause"]
    assert clause is not None
    assert "Bureau of Indian Standards Act, 2016" in clause
    assert "IS 694" in clause

    # Verify Alternatives
    alts = rec_data["alternative_candidates"]
    assert len(alts) > 0, "Expected alternative candidates"

    print("[PASS]")
    print(f"         Primary: {top_sn} (Score: {rec_data['primary_standard']['final_score']})")
    print(f"         Normative Suite: {len(suite['test_methods'])} test methods, {len(suite['components'])} components")
    print(f"         Alternatives: {', '.join([a['standard_number'] for a in alts[:2]])}")
    print(f"         Tender Clause Generated: {len(clause)} chars")

    # -------------------------------------------------------------
    # Test 3: Disambiguation Guard
    # -------------------------------------------------------------
    query_ambig = "150 sq mm cable"
    print(f"\n[TEST 3] POST /api/recommend (\"{query_ambig}\" - Ambiguity Gate) ...", end=" ", flush=True)
    resp = client.post("/api/recommend", json={"query": query_ambig})
    assert resp.status_code == 200
    ambig_data = resp.json()
    dis = ambig_data["disambiguation"]
    assert dis["is_ambiguous"] is True, "Expected is_ambiguous = True for underspecified cable"
    assert dis["question"] is not None and len(dis["question"]) > 5
    assert len(dis["options"]) >= 2
    print("[PASS]")
    print(f"         Ambiguity Flag: TRUE (Confidence Gap: {dis['confidence_gap']})")
    print(f"         Clarifying Question: {dis['question']}")
    print(f"         Selectable Options: {dis['options']}")

    # -------------------------------------------------------------
    # Test 4: Domain Boundary Guard
    # -------------------------------------------------------------
    query_xray = "Digital X-Ray apparatus for hospital diagnostics radiology"
    print(f"\n[TEST 4] POST /api/recommend (\"{query_xray}\" - Boundary Guard) ...", end=" ", flush=True)
    resp = client.post("/api/recommend", json={"query": query_xray})
    assert resp.status_code == 200
    b_data = resp.json()
    assert b_data["out_of_domain"] is True, "Expected out_of_domain = True for X-Ray"
    assert b_data["boundary_message"] is not None
    print("[PASS]")
    print(f"         Out of Domain: TRUE")
    print(f"         Guard Message: {b_data['boundary_message']}")

    # -------------------------------------------------------------
    # Test 5: Standards List & Filters
    # -------------------------------------------------------------
    print("\n[TEST 5] GET /api/standards?dept=ETD&qco_only=true ...", end=" ", flush=True)
    resp = client.get("/api/standards?dept=ETD&qco_only=true&limit=5")
    assert resp.status_code == 200
    stds_list = resp.json()
    assert len(stds_list) > 0
    assert all(s["dept"] == "ETD" for s in stds_list)
    assert all(s["qco_ministry"] is not None for s in stds_list)
    print(f"[PASS] (Retrieved {len(stds_list)} mandatory ETD standards)")

    # -------------------------------------------------------------
    # Test 6: Standard Detail & Licences
    # -------------------------------------------------------------
    print("\n[TEST 6] GET /api/standards/IS 694:2010 ...", end=" ", flush=True)
    resp = client.get("/api/standards/IS 694:2010")
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["standard_number"] == "IS 694:2010"
    assert detail["active_licences"] == 1304
    assert detail["total_isi_licences"] == 1304
    assert len(detail["product_varieties"]) > 10
    print(f"[PASS] (Active Licences: {detail['active_licences']}, Varieties found)")

    # -------------------------------------------------------------
    # Test 7: 2D Force Graph Data
    # -------------------------------------------------------------
    print("\n[TEST 7] GET /api/standards/IS 694:2010/graph ...", end=" ", flush=True)
    resp = client.get("/api/standards/IS 694:2010/graph")
    assert resp.status_code == 200
    graph = resp.json()
    assert graph["standard_number"] == "IS 694:2010"
    assert len(graph["nodes"]) > 1, "Expected graph nodes"
    assert len(graph["links"]) > 0, "Expected graph links"
    print(f"[PASS] ({len(graph['nodes'])} nodes, {len(graph['links'])} links for 2D Force Graph)")

    print("\n" + "=" * 80)
    print("ALL 7 FASTAPI API TESTS PASSED SUCCESSFULLY! [MILESTONE 2.2 COMPLETE]")
    print("=" * 80)

if __name__ == "__main__":
    run_api_tests()
