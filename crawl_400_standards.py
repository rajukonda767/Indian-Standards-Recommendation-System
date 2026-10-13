"""
crawl_400_standards.py - Rock-solid, resumable, rate-limited HTTP crawler for the 400 MVP standards.

Usage:
    python crawl_400_standards.py

Features:
- Reads selected_400_standards.csv (150 CED + 150 ETD + 100 MTD)
- Calls 6 core BIS endpoints per standard
- Flushes raw responses immediately to raw/detail/<pk_is_id>/<endpointName>.json
- Checkpoints progress in crawl_400_state.json
- Fully resumable: skips already downloaded standards on restart
- Strict polite throttling: 1.0 second delay between requests
- Exponential backoff retry (4 attempts)
- Circuit breaker: stops safely on HTTP 403/429 without losing state
"""

import csv
import json
import logging
import os
import sys
import time
from pathlib import Path
import requests

# ----------------- Configuration -----------------
CSV_PATH = Path("selected_400_standards.csv")
STATE_PATH = Path("crawl_400_state.json")
LOG_PATH = Path("crawl_400.log")
RAW_DETAIL_DIR = Path("raw/detail")

DELAY_BETWEEN_REQUESTS = 1.0  # Strict 1 req/sec
TIMEOUT_SECONDS = 30
MAX_RETRIES = 4

BASE_REVIEW_URL = "https://standardsadmin.bis.gov.in/review-service/"

HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.9",
    "content-type": "application/json",
    "origin": "https://standards.bis.gov.in",
    "referer": "https://standards.bis.gov.in/",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

# The 6 core endpoints required for MVP
ENDPOINTS = [
    ("getWebsiteStandardDetails", {"encId": "{token}", "fromPage": "guestUserPage"}),
    ("getCrossRefDetails",       {"encId": "{token}", "fromPage": "guestUserPage"}),
    ("getAmendmentDetails",      {"standardId": "{token}"}),
    ("getGazettedetails",        {"standardId": "{token}", "fromPage": "guestUserPage"}),
    ("getStandardLicenseDetails",{"standardId": "{token}", "status": "Operative", "page": 1, "limit": 10, "searchText": ""}),
    ("getStandardCRSDetails",    {"standardId": "{token}", "status": "Operative", "page": 1, "limit": 10, "searchText": ""})
]

# ----------------- Logging Setup -----------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

def load_state():
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_state(state):
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")

def request_with_retry(session, url, payload, retries=MAX_RETRIES):
    for attempt in range(retries):
        try:
            r = session.post(url, headers=HEADERS, json=payload, timeout=TIMEOUT_SECONDS)
            if r.status_code == 200:
                try:
                    return r.json()
                except Exception:
                    return {"raw_text": r.text, "warning": "Non-JSON response"}
            elif r.status_code in (403, 429):
                logging.critical(f"CIRCUIT BREAKER: HTTP {r.status_code} received on {url}! Halting crawl.")
                raise SystemExit(f"Rate limited or forbidden (HTTP {r.status_code}). Exiting safely.")
            logging.warning(f"  HTTP {r.status_code} on attempt {attempt + 1} for {url}")
        except requests.RequestException as e:
            logging.warning(f"  Network error on attempt {attempt + 1}: {e}")

        backoff = 2 ** attempt
        time.sleep(backoff)

    raise RuntimeError(f"Failed after {retries} retries: {url}")

def crawl_standard(session, row):
    pk_id = str(row["pk_is_id"]).strip()
    token = row["standardId"].strip()
    std_num = row.get("standardNumber", "").strip()
    dept = row.get("deptCode", "")

    std_dir = RAW_DETAIL_DIR / pk_id
    std_dir.mkdir(parents=True, exist_ok=True)

    bp = {"token": None, "refreshToken": None, "clientId": None, "clientSecret": None, "sub": None}

    for ep_name, payload_template in ENDPOINTS:
        out_file = std_dir / f"{ep_name}.json"
        if out_file.exists():
            continue  # Already downloaded

        # Populate payload
        payload = {}
        for k, v in payload_template.items():
            payload[k] = token if v == "{token}" else v
        payload.update(bp)

        url = f"{BASE_REVIEW_URL}/{ep_name}"
        data = request_with_retry(session, url, payload)
        out_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        time.sleep(DELAY_BETWEEN_REQUESTS)

def main():
    if not CSV_PATH.exists():
        logging.error(f"{CSV_PATH} not found!")
        return

    with open(CSV_PATH, encoding="utf-8-sig") as f:
        standards = list(csv.DictReader(f))

    total = len(standards)
    state = load_state()
    session = requests.Session()

    already_done = sum(1 for s in standards if state.get(str(s["pk_is_id"])) == "DONE")
    logging.info(f"Loaded {total} standards. Previously completed: {already_done}/{total}")

    start_time = time.time()
    for idx, row in enumerate(standards, 1):
        pk_id = str(row["pk_is_id"]).strip()
        std_num = row["standardNumber"]
        dept = row["deptCode"]

        if state.get(pk_id) == "DONE":
            continue

        pct = (idx / total) * 100
        logging.info(f"[{idx}/{total}] ({pct:.1f}%) [{dept}] {std_num} (pk: {pk_id}) - Fetching 6 endpoints...")

        try:
            crawl_standard(session, row)
            state[pk_id] = "DONE"
            save_state(state)
        except SystemExit:
            save_state(state)
            logging.info("Crawler halted safely. Progress saved in crawl_400_state.json.")
            sys.exit(1)
        except Exception as e:
            logging.error(f"Error processing {std_num}: {e}")
            state[pk_id] = f"FAILED: {e}"
            save_state(state)

    elapsed_min = (time.time() - start_time) / 60
    completed = sum(1 for s in standards if state.get(str(s["pk_is_id"])) == "DONE")
    logging.info(f"\n==========================================")
    logging.info(f"Crawl Completed! Total: {completed}/{total} in {elapsed_min:.1f} minutes.")
    logging.info(f"==========================================")

if __name__ == "__main__":
    main()
