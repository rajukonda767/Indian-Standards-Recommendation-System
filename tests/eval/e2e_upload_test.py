# -*- coding: utf-8 -*-
"""
tests/eval/e2e_upload_test.py
=============================
End-to-end test: upload both real GeM PDFs through POST /api/audit/upload,
poll until done, then print full scorecard + first 3 items expanded.
"""
import sys, os, time, json
sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

import urllib.request
import urllib.parse

BASE = "http://127.0.0.1:8000/api/audit"
PDF1 = r"C:\Users\devag\Downloads\Techical Specifications 1.pdf"
PDF2 = r"C:\Users\devag\Downloads\_Uploads_job_45941.pdf"

# ── Multipart upload helper ────────────────────────────────────────────────
def upload_files(paths, doc_type="gem"):
    boundary = "----PythonBoundary12345"
    body_parts = []
    for p in paths:
        fname = os.path.basename(p)
        with open(p, "rb") as f:
            data = f.read()
        body_parts.append(
            f'--{boundary}\r\n'
            f'Content-Disposition: form-data; name="files"; filename="{fname}"\r\n'
            f'Content-Type: application/octet-stream\r\n\r\n'.encode() + data + b'\r\n'
        )
    body_parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="doc_type"\r\n\r\n{doc_type}\r\n'.encode()
    )
    body_parts.append(f'--{boundary}--\r\n'.encode())
    body = b''.join(body_parts)
    req = urllib.request.Request(
        f"{BASE}/upload",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())

def poll_job(job_id, interval=2.0, timeout=300):
    start = time.time()
    while time.time() - start < timeout:
        with urllib.request.urlopen(f"{BASE}/jobs/{job_id}", timeout=15) as r:
            job = json.loads(r.read())
        done = job.get("done_items", 0)
        total = job.get("total_items", 0)
        status = job.get("status", "?")
        elapsed = time.time() - start
        print(f"  [{elapsed:5.1f}s] {status} — {done}/{total} items done", flush=True)
        if status in ("done", "failed", "timeout"):
            return job
        time.sleep(interval)
    raise TimeoutError(f"Job {job_id} did not finish within {timeout}s")

def get_results(job_id):
    with urllib.request.urlopen(f"{BASE}/jobs/{job_id}/results", timeout=15) as r:
        return json.loads(r.read())

# ── Upload both PDFs in one job ───────────────────────────────────────────
print("=" * 80)
print("E2E: Uploading PDF-1 + PDF-2 through POST /api/audit/upload")
print("=" * 80)

t0 = time.time()
job = upload_files([PDF1, PDF2], doc_type="gem")
print(f"\nJob created: {job['id']}")
print(f"Status: {job['status']} | Total items: {job.get('total_items', '?')}")
print("\nPolling for completion...")

job = poll_job(job["id"], interval=2.0, timeout=300)
elapsed = time.time() - t0

print(f"\nJob finished: {job['status']} in {elapsed:.1f}s")
print(f"Total items: {job.get('total_items')} | Done: {job.get('done_items')}\n")

if job["status"] != "done":
    print("ERROR:", job.get("error_msg"))
    sys.exit(1)

# ── Fetch full results ────────────────────────────────────────────────────
results = get_results(job["id"])
sc = results["scorecard"]

print("=" * 80)
print("SCORECARD")
print("=" * 80)
print(f"Coverage       : {sc['coverage']['display']}  (denominator: {sc['coverage']['denominator']})")
print(f"Currency       : {sc['currency']['display']}  (denominator: {sc['currency']['denominator']})")
print(f"QCO Compliance : {sc['qco_compliance']['display']}  (denominator: {sc['qco_compliance']['denominator']})")

print("\nStatus Counts:")
for status, cnt in results.get("status_counts", {}).items():
    print(f"  {status:<20}: {cnt}")

print("\n" + "=" * 80)
print(f"ITEMS (showing first 5 of {len(results['items'])})")
print("=" * 80)
for item in results["items"][:5]:
    print(f"\n#{item['seq_no']}  [{item['status'].upper()}]  badge={item['badge_color']}")
    print(f"  Desc: {item['description'][:100]}")
    if item["cited_standards"]:
        for cs in item["cited_standards"]:
            print(f"  Cited: {cs['raw_citation']} → resolved: {cs['resolved_standard_number']} ({cs['resolved_year']})")
    else:
        print(f"  Cited: (none)")
    for f in item["findings"]:
        print(f"  [{f['severity'].upper()}] {f['code']}: {f['message'][:80]}")
    if item["recommended_standards"]:
        for r in item["recommended_standards"]:
            print(f"  → Recommend: {r['recommended']}:{r['year']}  — {r['reason']}")

print("\n" + "=" * 80)
print("E2E TEST COMPLETE")
print("=" * 80)
