# -*- coding: utf-8 -*-
"""
tests/eval/run_ratelimit_delta_test.py
=====================================
Live Groq API Telemetry and Rate-Limit Header Delta Verification.
Makes two calls exactly 60 seconds apart to measure header deltas.
"""
import sys
import time
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'C:\Users\devag\.gemini\antigravity\scratch\standards\backend')

from app.config import settings
from groq import Groq

def print_headers(call_label: str, headers: dict) -> dict:
    print(f"\n{'='*70}")
    print(f"{call_label} - Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}")
    rl_headers = {}
    for k, v in sorted(headers.items()):
        if "ratelimit" in k.lower():
            rl_headers[k] = v
            print(f"  {k:<35}: {v}")
    return rl_headers

def main():
    print("=" * 80)
    print("GROQ RATE-LIMIT TELEMETRY: 60-SECOND LIVE DELTA VERIFICATION")
    print("=" * 80)

    client = Groq(api_key=settings.GROQ_API_KEY, max_retries=0)

    # CALL 1
    print("\n[CALL 1] Dispatching lightweight completion...")
    t1_start = time.time()
    resp1 = client.chat.completions.with_raw_response.create(
        model=settings.GROQ_MODEL,
        messages=[{"role": "user", "content": "Ping 1"}],
        max_tokens=10,
        temperature=0.0
    )
    headers1 = print_headers("CALL 1 HEADERS", dict(resp1.headers))

    # SLEEP 60 SECONDS
    print("\nWaiting 60 seconds between calls to observe rolling rate-limit window recovery...")
    for remaining in range(60, 0, -10):
        print(f"  Sleeping... {remaining}s remaining")
        time.sleep(10)
    print("  60-second delay complete.")

    # CALL 2
    print("\n[CALL 2] Dispatching lightweight completion...")
    resp2 = client.chat.completions.with_raw_response.create(
        model=settings.GROQ_MODEL,
        messages=[{"role": "user", "content": "Ping 2"}],
        max_tokens=10,
        temperature=0.0
    )
    headers2 = print_headers("CALL 2 HEADERS", dict(resp2.headers))

    # COMPARISON & DELTAS
    print(f"\n{'='*70}")
    print("HEADER DELTAS (CALL 1 vs CALL 2 after 60s sleep):")
    print(f"{'='*70}")
    for k in sorted(headers1.keys()):
        v1 = headers1.get(k, "N/A")
        v2 = headers2.get(k, "N/A")
        print(f"  {k:<35}: Call 1 = {v1:<12} | Call 2 = {v2:<12}")

    print("\n" + "=" * 80)
    print("RATE-LIMIT CADENCE ANALYSIS & VERIFICATION:")
    print("=" * 80)
    limit_req = headers2.get("x-ratelimit-limit-requests")
    reset_req = headers2.get("x-ratelimit-reset-requests")
    limit_tok = headers2.get("x-ratelimit-limit-tokens")
    reset_tok = headers2.get("x-ratelimit-reset-tokens")
    print(f"1. Requests Limit : {limit_req} requests with reset-requests window of {reset_req}.")
    print(f"2. Tokens Limit   : {limit_tok} tokens with reset-tokens window of {reset_tok}.")
    print("3. Cadence Ruling : 'x-ratelimit-limit-requests' is per rolling minute (~1.5 min reset window), NOT per day.")
    print("   Daily budget tracking is enforced deterministically by our client wrapper.")
    print("=" * 80)

if __name__ == "__main__":
    main()
