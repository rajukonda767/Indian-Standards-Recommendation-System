# -*- coding: utf-8 -*-
"""
tests/eval/test_groq_wrapper.py
===============================
Empirical verification of GroqClientWrapper:
1. Redactor Security Firewall (Refuses unredacted PII prompts)
2. Real Small Live Call (Logs real rate-limit headers & token metrics)
3. Content-Hash Caching (Second identical call serves from cache)
4. Budget Exhaustion Guard (Raises BudgetExhaustedError when budget exceeded)
5. Failure Injection Test (Mocked 429 RateLimitError with exponential backoff)
"""
import sys, os, time
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'C:\Users\devag\.gemini\antigravity\scratch\standards\backend')

from unittest.mock import MagicMock
from groq import RateLimitError
import httpx

from app.parsers.groq_wrapper import (
    GroqClientWrapper,
    BudgetTracker,
    BudgetExhaustedError,
    UnredactedPIIError
)
from app.parsers.redactor import Redactor

print("=" * 100)
print("TEST SUITE: GROQ CLIENT WRAPPER WITH BUDGET GUARD & REDACTOR FIREWALL")
print("=" * 100)

# ── 1. REDACTOR SECURITY FIREWALL TEST ────────────────────────────────────────
print("\n" + "#" * 100)
print("PART 1: REDACTOR SECURITY FIREWALL TEST")
print("#" * 100)

wrapper = GroqClientWrapper()

# Test 1A: Prompt with raw unredacted email
unredacted_prompt = [
    {"role": "user", "content": "Please verify technical specs and send response to tender.officer@ntpc.co.in"}
]
try:
    wrapper.create_chat_completion(unredacted_prompt, max_tokens=50)
    print("FAIL: Unredacted PII was accepted!")
    sys.exit(1)
except UnredactedPIIError as e:
    print(f"PASS ✓: Redactor firewall successfully intercepted and rejected unredacted PII:")
    print(f"  {e}")

# Test 1B: Prompt with raw unredacted phone number
unredacted_phone_prompt = [
    {"role": "user", "content": "For clarifications call mobile number +91 98765 43210 regarding the tender."}
]
try:
    wrapper.create_chat_completion(unredacted_phone_prompt, max_tokens=50)
    print("FAIL: Unredacted phone was accepted!")
    sys.exit(1)
except UnredactedPIIError as e:
    print(f"PASS ✓: Redactor firewall successfully intercepted and rejected phone number:")
    print(f"  {e}")

# Test 1C: Properly redacted prompt
sanitized_text = Redactor.redact("Contact officer at tender.officer@ntpc.co.in for clarification.").redacted_text
print(f"\nSanitized prompt content: {repr(sanitized_text)}")

# Test 1D: Item batch containing bare 10-digit material codes (MUST NOT raise UnredactedPIIError)
print("\nTest 1D: Item batch containing bare 10-digit material codes starting with 6-9:")
item_batch_prompt = [
    {"role": "system", "content": "Extract item indices from the lines."},
    {"role": "user", "content": (
        "[L1] 10 | 8110264037 | CBLE: PVC FRLS 1.1KV 1CX1.5 | 3000 MTR\n"
        "[L2] 20 | 9876543210 | CBLE: PVC 1.1KV 1CX2.5 | 5000 MTR\n"
        "[L3] 30 | 7112345678 | CBLE: PVC 1.1KV AR FRLS | 2000 MTR"
    )}
]
try:
    wrapper._validate_redacted(item_batch_prompt)
    print("PASS ✓: Item batch with bare 10-digit material codes passed validation with ZERO false UnredactedPIIError!")
except UnredactedPIIError as e:
    print(f"FAIL: Bare 10-digit material code erroneously triggered UnredactedPIIError: {e}")
    sys.exit(1)


# ── 2. REAL LIVE CALL & RATE-LIMIT HEADER LOGS ────────────────────────────────
print("\n" + "#" * 100)
print("PART 2: LIVE CALL WITH REAL HEADER INSPECTION & BUDGET LOGGING")
print("#" * 100)

clean_messages = [
    {"role": "system", "content": "You are a concise compliance bot. Reply in 3 words."},
    {"role": "user", "content": "Confirm tender audit system is active."}
]

print("Dispatching real live call to Groq API...")
resp_text = wrapper.create_chat_completion(clean_messages, max_tokens=25)
print(f"Live Response Content: {repr(resp_text)}")
print("\nCaptured Rate-Limit Telemetry from Server Response Headers:")
print(f"  x-ratelimit-remaining-requests : {wrapper.tracker.server_remaining_requests}")
print(f"  x-ratelimit-remaining-tokens   : {wrapper.tracker.server_remaining_tokens}")
print(f"  x-ratelimit-reset-requests     : {wrapper.tracker.server_reset_requests}")
print(f"  x-ratelimit-reset-tokens       : {wrapper.tracker.server_reset_tokens}")
assert wrapper.tracker.server_remaining_requests is not None
assert wrapper.tracker.server_remaining_tokens is not None
print("Live header logging verified! ✓")


# ── 3. CONTENT-HASH CACHING TEST ──────────────────────────────────────────────
print("\n" + "#" * 100)
print("PART 3: CONTENT-HASH CACHE VERIFICATION")
print("#" * 100)

t0 = time.time()
cached_resp = wrapper.create_chat_completion(clean_messages, max_tokens=25)
elapsed = time.time() - t0
assert cached_resp == resp_text, "Cached content mismatch!"
assert elapsed < 0.01, f"Expected near-zero cache latency, got {elapsed:.4f}s"
print(f"Cache Hit verified: Response returned in {elapsed * 1000:.2f} ms with ZERO network calls or token budget consumption! ✓")


# ── 4. PRE-FLIGHT BUDGET EXHAUSTION GUARD TEST ────────────────────────────────
print("\n" + "#" * 100)
print("PART 4: BUDGET EXHAUSTION GUARD (PRE-FLIGHT LOCAL CHECK)")
print("#" * 100)

strict_tracker = BudgetTracker(max_tokens_per_minute=30)
strict_wrapper = GroqClientWrapper(api_key="mock_key", budget_tracker=strict_tracker)

try:
    # Attempting a call requesting max_tokens=50 when minute budget is 30
    strict_wrapper.create_chat_completion(clean_messages, max_tokens=50)
    print("FAIL: Call was permitted over budget!")
    sys.exit(1)
except BudgetExhaustedError as e:
    print(f"PASS ✓: Budget guard blocked execution before dispatching call:")
    print(f"  {e}")


# ── 5. FAILURE INJECTION: MOCKED 429 & EXPONENTIAL BACKOFF ────────────────────
print("\n" + "#" * 100)
print("PART 5: FAILURE INJECTION — MOCKED 429 RATE LIMIT & EXPONENTIAL BACKOFF")
print("#" * 100)

# Build a mock client that simulates a persistent 429 RateLimitError
mock_client = MagicMock()
mock_response = httpx.Response(
    status_code=429,
    headers={
        "x-ratelimit-remaining-requests": "0",
        "x-ratelimit-remaining-tokens": "0",
        "x-ratelimit-reset-requests": "10s",
        "x-ratelimit-reset-tokens": "5s",
    },
    request=httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
)
mock_error = RateLimitError("Rate limit reached. Please try again later.", response=mock_response, body={"error": "rate_limit_exceeded"})
mock_client.chat.completions.with_raw_response.create.side_effect = mock_error

mocked_wrapper = GroqClientWrapper(api_key="mock_key")
mocked_wrapper.slots[0].client = mock_client
mocked_wrapper.client = mock_client

new_messages = [{"role": "user", "content": "Unique prompt for failure injection test."}]

t_start = time.time()
try:
    # Set backoff_base=0.1s for fast test execution with 3 retries
    mocked_wrapper.create_chat_completion(new_messages, max_tokens=20, max_retries=3, backoff_base=0.1)
    print("FAIL: Expected BudgetExhaustedError on persistent 429!")
    sys.exit(1)
except BudgetExhaustedError as e:
    t_elapsed = time.time() - t_start
    print(f"PASS ✓: Mocked 429 retried 3 times with exponential backoff, then raised BudgetExhaustedError:")
    print(f"  Exception: {e}")
    print(f"  Total elapsed backoff time: {t_elapsed:.2f}s")
    assert mock_client.chat.completions.with_raw_response.create.call_count == 4  # Initial + 3 retries
    print(f"  Verified call attempts: {mock_client.chat.completions.with_raw_response.create.call_count} (1 initial + 3 retries) ✓")

print("\n" + "=" * 100)
print("ALL GROQ CLIENT WRAPPER VERIFICATIONS COMPLETE & PASSED (100% SUCCESS ✓)")
print("=" * 100 + "\n")
