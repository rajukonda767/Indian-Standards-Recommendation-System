"""
BIS published-standards crawler (Step 1: list API, Step 2: sample detail pages).

Usage:
    pip install requests
    python bis_fetch.py list                 # crawl ALL ETD standards -> raw/list/*.json + standards_list.csv
    python bis_fetch.py detail --n 5         # save raw HTML of the first 5 detail pages -> raw/detail/
    python bis_fetch.py detail --n 5 --pk 67107   # or one specific pk_is_id

Be polite: 1 request/second, retries with backoff. Check robots.txt / terms first.
"""
import argparse
import csv
import json
import time
from pathlib import Path

import requests

LIST_URL = "https://standardsadmin.bis.gov.in/review-service//getWebsitePSTechDepartmentWise"
DETAIL_URL = "https://standards.bis.gov.in/website/standard-details"

# Encrypted id of the Electrotechnical Department, copied from your cURL.
ETD_DEPT_ID = (
    "eyJpdiI6ImJVb0FWOXNKazBEMldDa3ZXSXNlZHc9PSIsInZhbHVlIjoiQ0orb0RqMnNJTHRKY3RGRWVWakZPdz09"
    "IiwibWFjIjoiZDU0ZGEwNzRhYzk2OTMyMmQxMGMwNjZlNjI1ZjliZmUzN2IwYTI0YTViZTBhNjVjMmMwZWI1MWM2"
    "OTY3MDUwYyIsInRhZyI6IiJ9"
)

RAW = Path("raw")
LIST_DIR = RAW / "list"
DETAIL_DIR = RAW / "detail"
DELAY = 1.0          # seconds between requests
PAGE_SIZE = 100      # the site uses 12; larger may or may not be accepted (script adapts)

API_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.9",
    "content-type": "application/json",
    "origin": "https://standards.bis.gov.in",
    "referer": "https://standards.bis.gov.in/",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36",
}
HTML_HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "accept-language": "en-US,en;q=0.9",
    "referer": "https://www.bis.gov.in/",
    "user-agent": API_HEADERS["user-agent"],
}


def request_with_retry(session, method, url, retries=4, **kw):
    for attempt in range(retries):
        try:
            r = session.request(method, url, timeout=30, **kw)
            if r.status_code == 200:
                return r
            print(f"  HTTP {r.status_code} on attempt {attempt + 1}")
        except requests.RequestException as e:
            print(f"  error on attempt {attempt + 1}: {e}")
        time.sleep(2 ** attempt)
    raise RuntimeError(f"Failed after {retries} attempts: {url}")


def fetch_list(tech_committee_id=0, type_selected=7):
    """Page through the list API. offset is 0-based (offset 12 -> slNo 13)."""
    LIST_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    records, offset, total = [], 0, None

    while total is None or offset < total:
        payload = {
            "typeSelected": type_selected, "ministryIds": [], "sdgIds": [],
            "offset": offset, "limit": PAGE_SIZE,
            "encDepartmentId": ETD_DEPT_ID, "techCommitteeId": tech_committee_id,
            "token": None, "refreshToken": None, "clientId": None,
            "clientSecret": None, "sub": None,
        }
        r = request_with_retry(session, "POST", LIST_URL, headers=API_HEADERS, json=payload)
        body = r.json()
        data = body.get("data") or []
        total = body.get("totalRecord", total)
        (LIST_DIR / f"tc{tech_committee_id}_offset{offset}.json").write_text(
            json.dumps(body, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"offset={offset} got={len(data)} total={total}")
        if not data:
            break
        records.extend(data)
        offset += len(data)      # adapts if the server caps the page size
        time.sleep(DELAY)

    # de-duplicate on pk_is_id
    unique = {rec["pk_is_id"]: rec for rec in records}
    print(f"Fetched {len(records)} rows, {len(unique)} unique, server total {total}")
    return list(unique.values())


def save_csv(records, path="standards_list.csv"):
    cols = ["pk_is_id", "standardNumber", "standardName", "publishedOn", "isStatus",
            "noOfRevision", "typeOfStandardName", "equivalenceTypeName",
            "projectId", "documents", "standardId"]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(records)
    Path("standards_list.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records), encoding="utf-8")
    print(f"Wrote {path} and standards_list.jsonl")


def fetch_detail_samples(n=5, pk=None):
    """Save the raw HTML of detail pages so we can see what the server returns."""
    DETAIL_DIR.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader(open("standards_list.csv", encoding="utf-8-sig")))
    if pk:
        rows = [r for r in rows if r["pk_is_id"] == str(pk)]
    session = requests.Session()
    for row in rows[:n]:
        r = request_with_retry(session, "GET", DETAIL_URL, headers=HTML_HEADERS,
                               params={"encryptedId": row["standardId"]})
        out = DETAIL_DIR / f"{row['pk_is_id']}.html"
        out.write_text(r.text, encoding="utf-8")
        has_data = row["standardNumber"].split(":")[0] in r.text
        print(f"{row['standardNumber']}: {len(r.text)} bytes, standard number in HTML: {has_data} -> {out}")
        time.sleep(DELAY)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["list", "detail"])
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--pk", type=int)
    ap.add_argument("--committee", type=int, default=0, help="techCommitteeId (0 = all)")
    args = ap.parse_args()

    if args.mode == "list":
        save_csv(fetch_list(tech_committee_id=args.committee))
    else:
        fetch_detail_samples(args.n, args.pk)
