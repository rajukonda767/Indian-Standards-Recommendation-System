"""
Discovery script using Playwright to intercept all XHR/Fetch requests on BIS standard details page.
"""
import os
import re
import sys
import json
import time
import csv
from pathlib import Path
from playwright.sync_api import sync_playwright

DETAIL_BASE_URL = "https://standards.bis.gov.in/website/standard-details"
DISCOVERY_DIR = Path("raw/discovery")

def sanitize_filename(name):
    # Windows forbidden characters: \ / : * ? " < > |
    return re.sub(r'[\\/*?:"<>|]', '_', name).strip()

def run_discovery(targets=None):
    if not targets:
        targets = ["IS 15086 (Part 10):2026", "IS 694:2010"]

    # Read standards_list.csv to find encrypted standardId for targets
    csv_path = Path("standards_list.csv")
    if not csv_path.exists():
        print("standards_list.csv not found yet!")
        return

    standards_map = {}
    with open(csv_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            std_num = row.get("standardNumber", "").strip()
            standards_map[std_num] = row

    with sync_playwright() as p:
        # Launch browser
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        for target in targets:
            print(f"\n==========================================")
            print(f"Discovering for: {target}")
            print(f"==========================================")
            row = standards_map.get(target)
            if not row:
                # Try finding by prefix match if exact match fails
                matches = [k for k in standards_map if target in k]
                if matches:
                    row = standards_map[matches[0]]
                    print(f"Matched '{target}' to '{matches[0]}'")
                else:
                    print(f"Could not find {target} in standards_list.csv")
                    continue

            standard_number = row["standardNumber"]
            enc_id = row["standardId"]
            pk_is_id = row["pk_is_id"]
            url = f"{DETAIL_BASE_URL}?encryptedId={enc_id}"
            print(f"Target URL: {url} (pk_is_id: {pk_is_id})")

            safe_std_dir = DISCOVERY_DIR / sanitize_filename(standard_number)
            safe_std_dir.mkdir(parents=True, exist_ok=True)

            captured_calls = []
            endpoint_counts = {}

            page = context.new_page()

            def handle_response(response):
                req = response.request
                # Filter for fetch/xhr or bis service endpoints
                req_url = req.url
                if req.resource_type in ["fetch", "xhr"] or "bis.gov.in" in req_url:
                    # Ignore static assets like .js, .css, .woff, .png
                    if any(req_url.endswith(ext) for ext in [".js", ".css", ".png", ".jpg", ".svg", ".woff", ".woff2", ".ico"]):
                        return

                    endpoint_name = req_url.split("?")[0].rstrip("/").split("/")[-1]
                    if not endpoint_name or endpoint_name == "standard-details":
                        return

                    # Extract request details
                    headers = dict(req.headers)
                    post_data = req.post_data
                    parsed_post_data = None
                    if post_data:
                        try:
                            parsed_post_data = json.loads(post_data)
                        except Exception:
                            parsed_post_data = post_data

                    # Extract response details
                    resp_status = response.status
                    resp_body = None
                    try:
                        resp_body = response.json()
                    except Exception:
                        try:
                            resp_body = response.text()
                        except Exception:
                            resp_body = None

                    call_record = {
                        "endpoint": endpoint_name,
                        "url": req_url,
                        "method": req.method,
                        "request_headers": {k: v for k, v in headers.items() if k.lower() in [
                            "content-type", "origin", "referer", "accept", "authorization", "token", "cookie"
                        ]},
                        "request_body": parsed_post_data,
                        "response_status": resp_status,
                        "response_json": resp_body
                    }

                    count = endpoint_counts.get(endpoint_name, 0) + 1
                    endpoint_counts[endpoint_name] = count
                    fname = f"{endpoint_name}.json" if count == 1 else f"{endpoint_name}_{count}.json"
                    
                    file_path = safe_std_dir / fname
                    with open(file_path, "w", encoding="utf-8") as f_out:
                        json.dump(call_record, f_out, ensure_ascii=False, indent=2)

                    captured_calls.append(call_record)
                    print(f"  [Captured] {req.method} {endpoint_name} -> {resp_status} ({fname})")

            page.on("response", handle_response)

            try:
                print("Navigating to page...")
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                # Wait for the main heading or container to appear
                page.wait_for_selector("text=Standard Details", timeout=30000)
                time.sleep(4)  # Let initial XHRs trigger and finish

                # Tabs to click based on standard details UI
                tabs = [
                    "Basic Details",
                    "Classification Details",
                    "Standards Referred",
                    "Amendment",
                    "Gazette Document",
                    "Licence",
                    "Product Manual & SIT",
                    "Laboratory",
                    "Corrigendum",
                    "Summary"
                ]

                for tab_name in tabs:
                    try:
                        tab_el = page.locator(f"text={tab_name}").first
                        if tab_el.count() > 0:
                            print(f"Clicking tab: {tab_name}")
                            tab_el.click(timeout=5000)
                            time.sleep(2)
                    except Exception as e:
                        print(f"  Could not click tab '{tab_name}': {e}")

                time.sleep(3)

            except Exception as e:
                print(f"Error during navigation: {e}")
            finally:
                page.close()

            print(f"Done for {standard_number}. Total endpoints captured: {len(captured_calls)}")

        browser.close()

if __name__ == "__main__":
    run_discovery()
