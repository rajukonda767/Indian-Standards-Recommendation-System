"""
fetch_all_lists.py - Fetches complete standards lists for CED and MTD from BIS API.
"""

import csv
import json
import time
from pathlib import Path
import requests

LIST_URL = "https://standardsadmin.bis.gov.in/review-service//getWebsitePSTechDepartmentWise"
API_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.9",
    "content-type": "application/json",
    "origin": "https://standards.bis.gov.in",
    "referer": "https://standards.bis.gov.in/",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

DEPARTMENTS = {
    "CED": {
        "name": "Civil Engineering Department",
        "encId": "eyJpdiI6IjlNTUlublg2eVNlaUt3RUxUSnRBUmc9PSIsInZhbHVlIjoic2hSZXNqRmlnTm9aK1hSejNKM2hiZz09IiwibWFjIjoiZGVmYjMxZTczYzAzN2E2NjJiYTQ2NGMyNjkwMzQzMGI4NmU0MGZkNzQxNDNiMGFmNmU3ODQ5YjJiZGM2NzcyMCIsInRhZyI6IiJ9",
        "csv": "ced_standards_list.csv"
    },
    "MTD": {
        "name": "Metallurgical Engineering Department",
        "encId": "eyJpdiI6InEyMFhZQVFnSDB2ZkVHd3Z6YXNINnc9PSIsInZhbHVlIjoiR0I4N0FvSDdKbFg0clVQSG9oL1lwZz09IiwibWFjIjoiZDU0ZWY3MGEwNDU5MTRiYTg4OGVhYzA1MTgxNTkyZjhkYzBhMDc4YjkyNzExZjk2ZDQzZDQzMTYxYjUwMmQyYSIsInRhZyI6IiJ9",
        "csv": "mtd_standards_list.csv"
    }
}

DELAY = 0.8
PAGE_SIZE = 100

def fetch_department_list(dept_code, dept_info):
    csv_path = Path(dept_info["csv"])
    print(f"\n==========================================")
    print(f"Fetching catalog for {dept_code}: {dept_info['name']}")
    print(f"==========================================")

    session = requests.Session()
    records = []
    offset = 0
    total = None

    while total is None or offset < total:
        payload = {
            "typeSelected": 7,
            "ministryIds": [],
            "sdgIds": [],
            "offset": offset,
            "limit": PAGE_SIZE,
            "encDepartmentId": dept_info["encId"],
            "techCommitteeId": 0,
            "token": None, "refreshToken": None, "clientId": None,
            "clientSecret": None, "sub": None,
        }
        for attempt in range(4):
            try:
                r = session.post(LIST_URL, headers=API_HEADERS, json=payload, timeout=25)
                if r.status_code == 200:
                    break
            except Exception as e:
                print(f"  Retry {attempt+1} on offset {offset}: {e}")
            time.sleep(1.5)

        body = r.json()
        data = body.get("data") or []
        total = body.get("totalRecord", total)
        print(f"  {dept_code} offset={offset} fetched={len(data)} total={total}")
        if not data:
            break
        records.extend(data)
        offset += len(data)
        time.sleep(DELAY)

    # Deduplicate on pk_is_id
    unique = {rec["pk_is_id"]: rec for rec in records}
    cols = ["pk_is_id", "standardNumber", "standardName", "publishedOn", "isStatus",
            "noOfRevision", "typeOfStandardName", "equivalenceTypeName",
            "projectId", "documents", "standardId"]

    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(unique.values())

    print(f"Wrote {len(unique)} unique {dept_code} standards to {csv_path}")

def main():
    for code, info in DEPARTMENTS.items():
        fetch_department_list(code, info)

if __name__ == "__main__":
    main()
