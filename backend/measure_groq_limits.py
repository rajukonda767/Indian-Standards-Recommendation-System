"""
measure_groq_limits.py
Measures actual Groq rate-limit headers for qwen/qwen3-27b model.
Reads: x-ratelimit-limit-requests, x-ratelimit-limit-tokens,
       x-ratelimit-remaining-requests, x-ratelimit-remaining-tokens,
       x-ratelimit-reset-requests, x-ratelimit-reset-tokens
"""
import sys, os, time, json
sys.path.insert(0, r'C:\Users\devag\.gemini\antigravity\scratch\standards\backend')
os.chdir(r'C:\Users\devag\.gemini\antigravity\scratch\standards\backend')
from app.config import settings
from groq import Groq
import httpx

client = Groq(api_key=settings.GROQ_API_KEY)

# Make a minimal call to read headers
# We use the raw httpx client to see response headers
# Groq SDK wraps httpx; we can access _client._client (the underlying httpx.Client)
print(f"Model: {settings.GROQ_MODEL}")
print("Making minimal Groq call to read rate-limit headers...")

t0 = time.time()
resp = client.chat.completions.with_raw_response.create(
    model=settings.GROQ_MODEL,
    messages=[{"role": "user", "content": "Reply with the single word: OK"}],
    temperature=0.0,
    max_tokens=5,
)
elapsed = round((time.time() - t0) * 1000, 1)

print(f"\nCall latency: {elapsed} ms")
print(f"Completion tokens used: {resp.parse().usage.completion_tokens}")
print(f"Prompt tokens used:     {resp.parse().usage.prompt_tokens}")

print("\n--- Rate Limit Headers ---")
headers = dict(resp.headers)
rl_keys = [k for k in headers if 'ratelimit' in k.lower() or 'x-groq' in k.lower()]
for k in sorted(rl_keys):
    print(f"  {k}: {headers[k]}")

print("\n--- All response headers ---")
for k, v in sorted(headers.items()):
    print(f"  {k}: {v}")
