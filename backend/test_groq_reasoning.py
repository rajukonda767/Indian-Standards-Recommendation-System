"""
test_groq_reasoning.py
Tests LLM-1 style call with max_tokens=300 to observe reasoning tokens.
"""
import sys, os, time, json
sys.path.insert(0, r'C:\Users\devag\.gemini\antigravity\scratch\standards\backend')
os.chdir(r'C:\Users\devag\.gemini\antigravity\scratch\standards\backend')
from app.config import settings
from groq import Groq

client = Groq(api_key=settings.GROQ_API_KEY)

SYSTEM_PROMPT = (
    "You are a mention role classifier. "
    "Return ONLY valid JSON: {\"mentions\":{\"m1\":\"role_code\",...}}. "
    "Role codes: required_spec|test_basis|certification_mark|category_label|"
    "vague_reference|noise|needs_review|alternative. "
    "Do NOT output any explanation or reasoning."
)

USER_PROMPT = json.dumps({
    "mentions": {
        "m1": {"raw_text": "IS 269:2015", "context_40": "conforming to IS 269:2015 for OPC cement"},
        "m2": {"raw_text": "IS 694", "context_40": "ISI marked to IS 694 for PVC cable"},
        "m3": {"raw_text": "relevant IS", "context_40": "as per relevant IS standards"},
    }
}, indent=2)

print(f"Model: {settings.GROQ_MODEL}")
print("Testing LLM-1 with max_tokens=300...\n")

t0 = time.time()
resp = client.chat.completions.with_raw_response.create(
    model=settings.GROQ_MODEL,
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": USER_PROMPT},
    ],
    temperature=0.0,
    max_tokens=300,
)
elapsed = round((time.time() - t0) * 1000, 1)

completion = resp.parse()
raw_content = completion.choices[0].message.content or ""

print(f"Latency: {elapsed} ms")
print(f"Prompt tokens: {completion.usage.prompt_tokens}")
print(f"Completion tokens: {completion.usage.completion_tokens}")
print(f"Total tokens: {completion.usage.total_tokens}")

# Check for reasoning tokens field
usage_dict = completion.usage.model_dump() if hasattr(completion.usage, 'model_dump') else vars(completion.usage)
print(f"\nFull usage dict: {usage_dict}")

print(f"\nRaw content length: {len(raw_content)} chars")
print(f"Contains <think> tag: {'<think>' in raw_content.lower()}")
print(f"\nRaw content:\n{raw_content[:500]}")

# Rate limit headers
headers = dict(resp.headers)
print(f"\nRemaining requests: {headers.get('x-ratelimit-remaining-requests')}")
print(f"Remaining tokens:   {headers.get('x-ratelimit-remaining-tokens')}")
print(f"Reset tokens:       {headers.get('x-ratelimit-reset-tokens')}")

# Try to parse
import re
think_stripped = re.sub(r'<think>.*?</think>', '', raw_content, flags=re.DOTALL).strip()
print(f"\nAfter stripping <think>: {think_stripped[:300]}")
try:
    parsed = json.loads(think_stripped)
    print(f"JSON parse: OK → {parsed}")
except Exception as e:
    print(f"JSON parse failed: {e}")
