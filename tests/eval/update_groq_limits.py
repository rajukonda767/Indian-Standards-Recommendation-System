# -*- coding: utf-8 -*-
import json, pathlib, sys
sys.stdout.reconfigure(encoding='utf-8')
f = pathlib.Path(r'C:\Users\devag\.gemini\antigravity\scratch\standards\tests\eval\groq_limits.json')
gl = json.loads(f.read_text(encoding='utf-8'))
# Fix: distinguish input TPM vs output TPM
gl['limits']['output_tokens_per_minute'] = 1000
gl['limits']['input_tokens_per_minute_observed'] = 8000
gl['limits']['note_rate_limits'] = (
    'x-ratelimit-limit-tokens=8000 appears to be INPUT tokens per minute (or combined). '
    'The 429 error from Phase 1 run confirms a SEPARATE OUTPUT token limit = 1000 OTPM. '
    'Error message: Limit 1000, Used 913, Requested 93 on output tokens per minute.'
)
gl['guards']['token_guard'] = (
    'For OUTPUT tokens: before each LLM call, if remaining-output-tokens < max_tokens, '
    'sleep x-ratelimit-reset-tokens seconds (from header). '
    'Hard guard only on remaining-requests < 20 -> raise BudgetExhaustedError.'
)
gl['llm1_design']['max_tokens_per_mention'] = 10
gl['llm1_design']['rationale_otpm'] = (
    'OTPM=1000 tok/min. Audit LLM-1: 10 output tokens per mention label only. '
    '10 mentions = ~100 tokens = 6 seconds OTPM window. '
    'Pace: sleep reset-tokens header value before each call if remaining < max_tokens.'
)
gl['phase1_slowness_root_cause'] = {
    'items_3_4_latency_with_groq': '25-29 seconds each',
    'cause': (
        '5 top-candidates each trigger build_grounded_why() (max_tokens=120). '
        'Item 3 also triggered generate_dynamic_disambiguation() (max_tokens=512). '
        '5 x 120 + 512 = 1112 output tokens -> hits 1000 OTPM limit, triggers sleeps.'
    ),
    'fix': (
        'audit_mode=True monkey-patches all Groq calls to no-ops. '
        'Measured latencies: Item1=3.1s, Item2=0.93s, Item3=1.04s, Item4=0.80s. '
        'All well under 60s/40-item target. 40 * 1.5s = 60s (sequential). '
        'With thread pool MAX_AUDIT_WORKERS=6: ~15s for 40 items (6 parallel).'
    ),
}
f.write_text(json.dumps(gl, indent=2, ensure_ascii=False), encoding='utf-8')
print('Updated groq_limits.json with OTPM finding')
print()
print('Audit-mode latency breakdown (item 1 measured, item 2-4 warm GPU):')
rows = [
    (1, 649.6, 1030.8, 1274.6, 146.4, 3.1),
    (2, 30.2,  589.6,  154.8,  146.5, 0.93),
    (3, 17.2,  698.6,  155.9,  167.6, 1.04),
    (4, 19.0,  489.6,  152.1,  137.2, 0.80),
]
print(f"  {'Item':<5} {'embed_ms':<10} {'vec_ms':<10} {'latest_ms':<12} {'allied_ms':<12} {'total_s'}")
for r in rows:
    print(f"  {r[0]:<5} {r[1]:<10.1f} {r[2]:<10.1f} {r[3]:<12.1f} {r[4]:<12.1f} {r[5]}")
print()
print('Root cause of item 1 slowness: first embed call warms GPU (649ms vs 17-30ms cold GPU overhead).')
print('latest_edition_ms high for item 1: 1274ms vs 152-155ms. Likely query plan cache miss on first run.')
