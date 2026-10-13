"""
verify_browser.py - Automated DOM verification using Playwright.
Loads each of the 10 standards in Chromium, scrapes visible UI elements, and compares
against pilot_standards.json.
"""

import json
import re
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

PILOT_JSON_PATH = Path("pilot_standards.json")
VERIFICATION_OUTPUT = Path("verification_results.json")

def verify_all():
    if not PILOT_JSON_PATH.exists():
        print(f"{PILOT_JSON_PATH} does not exist!")
        return

    pilot_data = json.loads(PILOT_JSON_PATH.read_text(encoding="utf-8"))
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()

        for item in pilot_data:
            std_num = item["identity"]["is_number"]
            url = item["source"]["detail_url"]
            print(f"\nVerifying {std_num} via browser: {url}")

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_selector("text=Standard Details", timeout=30000)
                time.sleep(3)

                # Scrape visible elements from DOM
                body_text = page.locator("body").inner_text()

                # Title
                dom_title = None
                # Typically inside the main standard info container
                h3_or_h4 = page.locator("h3, h4, .standard-title, .title").all_inner_texts()
                
                # Check badges / text
                dom_voluntary = "Voluntary Certification" in body_text
                dom_mandatory = "Mandatory" in body_text

                # Department & Committee
                dept_match = re.search(r'Department:\s*([^\n\r]+)', body_text)
                dom_dept = dept_match.group(1).strip() if dept_match else None

                tc_match = re.search(r'Technical Committee:\s*([^\n\r]+)', body_text)
                dom_tc = tc_match.group(1).strip() if tc_match else None

                # Equivalences
                eq_match = re.search(r'(IEC\s+[0-9]+[^\n\r]*)', body_text)
                dom_eq = eq_match.group(1).strip() if eq_match else None

                # Check comparison
                std_results = {
                    "standardNumber": std_num,
                    "url": url,
                    "fields": [
                        {
                            "field": "Standard Number",
                            "api_value": std_num,
                            "dom_found": std_num in body_text,
                            "match": std_num in body_text
                        },
                        {
                            "field": "Department",
                            "api_value": item["classification"]["department"],
                            "dom_value": dom_dept,
                            "match": (dom_dept is not None and "electrotechnical" in dom_dept.lower())
                        },
                        {
                            "field": "Technical Committee",
                            "api_value": item["classification"]["technical_committee"]["full"],
                            "dom_value": dom_tc,
                            "match": (dom_tc is not None and (item["classification"]["technical_committee"]["code"] or "") in dom_tc)
                        },
                        {
                            "field": "Equivalent Standard",
                            "api_value": item["identity"]["equivalent_std"],
                            "dom_value": dom_eq if item["identity"]["equivalent_std"] else None,
                            "match": (item["identity"]["equivalent_std"] in body_text) if item["identity"]["equivalent_std"] else True
                        },
                        {
                            "field": "Certification Type",
                            "api_value": item["certification"]["certification_type"],
                            "dom_value": "Voluntary Certification" if dom_voluntary else ("Mandatory" if dom_mandatory else None),
                            "match": (
                                (item["certification"]["certification_type"] == "Voluntary" and dom_voluntary) or
                                (item["certification"]["certification_type"] == "Mandatory" and dom_mandatory) or
                                (item["certification"]["certification_type"] is None)
                            )
                        }
                    ]
                }
                results.append(std_results)
                print(f"  Verified {std_num}: {len(std_results['fields'])} checks completed.")

            except Exception as e:
                print(f"  Error verifying {std_num}: {e}")
                results.append({
                    "standardNumber": std_num,
                    "error": str(e)
                })

        browser.close()

    VERIFICATION_OUTPUT.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nVerification results saved to {VERIFICATION_OUTPUT}")

if __name__ == "__main__":
    verify_all()
