"""
Fix for Task 1: Fresh-fetch all department encIds from the BIS API itself,
then crawl each department properly.

The fetchDepartmentList endpoint returns the list of all departments with their
current encId tokens. These are the correct tokens to use for list pagination.
"""

import requests, json, csv, time, re, os, pathlib

BASE_URL = "https://standardsadmin.bis.gov.in/review-service//"
HEADERS = {
    "Content-Type": "application/json",
    "Origin": "https://standards.bis.gov.in",
    "Referer": "https://standards.bis.gov.in/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

def fetch_department_list():
    """Fetch all departments from the BIS API to get fresh encId tokens."""
    payload = {
        "token": None, "refreshToken": None,
        "clientId": None, "clientSecret": None, "sub": None
    }
    r = requests.post(BASE_URL + "fetchDepartmentList", json=payload, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()

def main():
    print("Fetching fresh department list...")
    dept_resp = fetch_department_list()
    
    departments = dept_resp.get("data") or dept_resp.get("departmentList") or []
    if not departments:
        # Try alternate structure
        print("Response keys:", list(dept_resp.keys()))
        print("Full response (first 500):", json.dumps(dept_resp)[:500])
        return
    
    print(f"Found {len(departments)} departments:")
    for d in departments:
        print(f"  code={d.get('deptAliasName') or d.get('departmentCode') or d.get('aliasName')} "
              f"  id={d.get('departmentId')} "
              f"  encId={str(d.get('departmentEncId') or d.get('encId') or '')[:30]}...")
    
    # Save for use in main crawler
    with open("fresh_dept_tokens.json", "w") as f:
        json.dump(departments, f, indent=2)
    print("\nSaved to fresh_dept_tokens.json")

if __name__ == "__main__":
    main()
