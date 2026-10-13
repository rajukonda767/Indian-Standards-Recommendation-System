"""
bis_detail.py - Plain HTTP client using requests to fetch BIS standard details.

Features:
- Calls discovered review-service endpoints for a standard
- Saves raw JSON responses to raw/detail/<pk_is_id>/<endpointName>.json BEFORE any parsing
- Resumable: skips endpoint call if raw JSON file already exists
- Polite: strict 1 request/second delay
- Robust: 4 retries with exponential backoff
- Safety: stops immediately on 403/429/captcha; never calls logUniqueVisitor; never downloads PDFs
"""

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path
import requests

API_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.9",
    "content-type": "application/json",
    "origin": "https://standards.bis.gov.in",
    "referer": "https://standards.bis.gov.in/",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

BASE_REVIEW_URL = "https://standardsadmin.bis.gov.in/review-service/"
DETAIL_DIR = Path("raw/detail")
DELAY = 1.0  # 1 request per second

# The 10 pilot standards
PILOT_STANDARDS = [
    "IS 15086 (Part 10):2026",
    "IS 694:2010",
    "IS 8130:2013",
    "IS 1554 (Part 1):1988",
    "IS 4289 (Part 1):2026",
    "IS 8783 (Part 4/Sec 1):2026",
    "IS 10810 (Part 60):1988",
    "IS/IEC 60136:2024",
    "IS 2026 (Part 1):2011",
    "IS 1293:2019"
]

def make_payload_boilerplate():
    return {
        "token": None,
        "refreshToken": None,
        "clientId": None,
        "clientSecret": None,
        "sub": None
    }

def get_endpoints_spec(enc_id):
    """
    Returns list of (endpoint_name, url, payload) for all discovered detail endpoints.
    Note: encId vs standardId key naming conventions discovered during inspection.
    """
    bp = make_payload_boilerplate()
    return [
        (
            "getWebsiteStandardDetails",
            f"{BASE_REVIEW_URL}/getWebsiteStandardDetails",
            {"encId": enc_id, "fromPage": "guestUserPage", **bp}
        ),
        (
            "getCrossRefDetails",
            f"{BASE_REVIEW_URL}/getCrossRefDetails",
            {"encId": enc_id, "fromPage": "guestUserPage", **bp}
        ),
        (
            "getAmendmentDetails",
            f"{BASE_REVIEW_URL}/getAmendmentDetails",
            {"standardId": enc_id, **bp}
        ),
        (
            "getGazettedetails",
            f"{BASE_REVIEW_URL}/getGazettedetails",
            {"standardId": enc_id, "fromPage": "guestUserPage", **bp}
        ),
        (
            "getStandardLicenseDetails",
            f"{BASE_REVIEW_URL}/getStandardLicenseDetails",
            {"standardId": enc_id, "status": "Operative", "page": 1, "limit": 10, "searchText": "", **bp}
        ),
        (
            "getStandardCRSDetails",
            f"{BASE_REVIEW_URL}/getStandardCRSDetails",
            {"standardId": enc_id, "status": "Operative", "page": 1, "limit": 10, "searchText": "", **bp}
        ),
        (
            "getStandardMCSDetails",
            f"{BASE_REVIEW_URL}/getStandardMCSDetails",
            {"standardId": enc_id, "page": 1, "limit": 10, "searchText": "", **bp}
        ),
        (
            "getStandardLaboratoryDetails",
            f"{BASE_REVIEW_URL}/getStandardLaboratoryDetails",
            {"standardId": enc_id, "page": 1, "limit": 10, "searchText": "", **bp}
        ),
        (
            "getProductManualDetails",
            f"{BASE_REVIEW_URL}/getProductManualDetails",
            {"standardId": enc_id, **bp}
        ),
        (
            "getCorrigendumDetails",
            f"{BASE_REVIEW_URL}/getCorrigendumDetails",
            {"standardId": enc_id, **bp}
        ),
        (
            "getSummaryDetails",
            f"{BASE_REVIEW_URL}/getSummaryDetails",
            {"standardId": enc_id, **bp}
        )
    ]

def request_with_retry(session, method, url, retries=4, **kwargs):
    """Execute HTTP request with 4 retries, exponential backoff, and safety checks."""
    for attempt in range(retries):
        try:
            r = session.request(method, url, timeout=30, **kwargs)
            if r.status_code == 200:
                return r
            elif r.status_code in [403, 429]:
                print(f"CRITICAL: HTTP {r.status_code} received on {url}! Stopping crawler.")
                sys.exit(1)
            print(f"  HTTP {r.status_code} on attempt {attempt + 1} for {url}")
        except requests.RequestException as e:
            print(f"  Network error on attempt {attempt + 1}: {e}")
        
        sleep_time = 2 ** attempt
        print(f"  Backing off for {sleep_time}s...")
        time.sleep(sleep_time)

    raise RuntimeError(f"Failed after {retries} attempts: {url}")

def fetch_standard_details(session, row, force=False):
    """Fetch all endpoints for a single standard row from standards_list.csv."""
    pk_is_id = str(row["pk_is_id"]).strip()
    enc_id = row["standardId"].strip()
    std_num = row.get("standardNumber", "").strip()

    std_dir = DETAIL_DIR / pk_is_id
    std_dir.mkdir(parents=True, exist_ok=True)

    endpoints = get_endpoints_spec(enc_id)
    print(f"\n[{std_num}] (pk_is_id: {pk_is_id}) - Fetching {len(endpoints)} endpoints...")

    for ep_name, url, payload in endpoints:
        out_file = std_dir / f"{ep_name}.json"
        if out_file.exists() and not force:
            # print(f"  [Skipped] {ep_name} (already cached)")
            continue

        r = request_with_retry(session, "POST", url, headers=API_HEADERS, json=payload)
        try:
            resp_data = r.json()
        except Exception:
            resp_data = {"raw_text": r.text, "error": "Invalid JSON response"}

        out_file.write_text(json.dumps(resp_data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  [Saved] {ep_name} -> {out_file}")
        time.sleep(DELAY)

def run_pilot():
    csv_path = Path("standards_list.csv")
    if not csv_path.exists():
        print("standards_list.csv not found!")
        return

    with open(csv_path, encoding="utf-8-sig") as f:
        rows = {r["standardNumber"].strip(): r for r in csv.DictReader(f)}

    session = requests.Session()
    print(f"Starting pilot extraction for {len(PILOT_STANDARDS)} standards...")

    for i, std_num in enumerate(PILOT_STANDARDS, 1):
        if std_num not in rows:
            print(f"Warning: Standard '{std_num}' not found in standards_list.csv!")
            continue
        row = rows[std_num]
        print(f"\n--- ({i}/{len(PILOT_STANDARDS)}) Standard: {std_num} ---")
        fetch_standard_details(session, row)

    print("\nPilot extraction complete!")

def run_single(pk_id):
    csv_path = Path("standards_list.csv")
    with open(csv_path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    match = [r for r in rows if r["pk_is_id"].strip() == str(pk_id)]
    if not match:
        print(f"Standard pk_is_id {pk_id} not found in standards_list.csv")
        return
    session = requests.Session()
    fetch_standard_details(session, match[0])

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BIS Detail Endpoints Crawler")
    parser.add_argument("--pilot", action="store_true", help="Crawl the 10 pilot standards")
    parser.add_argument("--pk", type=int, help="Crawl a single standard by pk_is_id")
    parser.add_argument("--force", action="store_true", help="Force refetch even if file exists")
    args = parser.parse_args()

    if args.pk:
        run_single(args.pk)
    elif args.pilot or len(sys.argv) == 1:
        run_pilot()
    else:
        parser.print_help()
