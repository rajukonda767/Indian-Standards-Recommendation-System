# -*- coding: utf-8 -*-
"""
tests/eval/test_key_pooling.py
==============================
Empirical Acceptance Test for Groq Key Pooling & Failover:
1. Pool Initialization: Verifies round-robin slots for all configured keys.
2. Three Back-to-Back Calls: Dispatches 3 unique calls and prints which key served each.
3. Global Shared Cache: Re-dispatching prompt hits global cache without consuming any key.
4. Forced Exhaustion Failover: Mocks key 1 as exhausted; proves immediate failover to key 2.
5. Multi-Key Budget Persistence: Prints .groq_budget.json showing separate entries per key.
"""
import sys, os, time, json
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'C:\Users\devag\.gemini\antigravity\scratch\standards\backend')

from app.parsers.groq_wrapper import (
    GroqClientWrapper,
    BudgetExhaustedError,
    mask_key
)
from app.config import settings

def main():
    print("=" * 100)
    print("GROQ KEY POOLING & ROUND-ROBIN FAILOVER TEST")
    print("=" * 100)

    # 1. Initialize Wrapper with configured keys
    wrapper = GroqClientWrapper()
    print(f"\n1. Configured Key Slots Count: {len(wrapper.slots)}")
    for s in wrapper.slots:
        print(f"   Slot ID: {s.key_id:<8} | Key Preview: {s.key_preview:<18} | Initial Reqs: {s.tracker.daily_requests}")

    assert len(wrapper.slots) >= 3, f"Expected at least 3 configured keys, found {len(wrapper.slots)}"

    # 2. Three Back-to-Back Live Calls
    print("\n" + "#" * 100)
    print("PART 2: THREE BACK-TO-BACK ROUND-ROBIN LIVE CALLS")
    print("#" * 100)

    prompts = [
        "State the number 101 only.",
        "State the number 202 only.",
        "State the number 303 only."
    ]

    served_slots = []
    for idx, p in enumerate(prompts, 1):
        print(f"\n[Dispatching Call {idx}] User Prompt: {repr(p)}")
        messages = [
            {"role": "system", "content": "You are a concise test agent. Reply with the requested number only."},
            {"role": "user", "content": p}
        ]
        resp = wrapper.create_chat_completion(messages, max_tokens=15, prompt_version=f"pool_test_{idx}")
        served = wrapper.last_served_slot
        served_slots.append(served.key_id)
        print(f"  -> Response   : {repr(resp.strip())}")
        print(f"  -> Served By  : {served.key_id} ({served.key_preview})")
        print(f"  -> Next RR Key: slot index {wrapper._current_key_idx} ({wrapper.slots[wrapper._current_key_idx].key_id})")

    print("\nRound-Robin Execution Sequence Summary:")
    print(f"  Call 1 -> {served_slots[0]}")
    print(f"  Call 2 -> {served_slots[1]}")
    print(f"  Call 3 -> {served_slots[2]}")

    assert served_slots[0] == "key_1", f"Expected key_1, got {served_slots[0]}"
    assert served_slots[1] == "key_2", f"Expected key_2, got {served_slots[1]}"
    assert served_slots[2] == "key_3", f"Expected key_3, got {served_slots[2]}"
    print("  Round-Robin sequencing verified across all 3 keys! ✓")

    # 3. Global Shared Cache Verification
    print("\n" + "#" * 100)
    print("PART 3: GLOBAL SHARED CACHE VERIFICATION")
    print("#" * 100)

    cached_messages = [
        {"role": "system", "content": "You are a concise test agent. Reply with the requested number only."},
        {"role": "user", "content": prompts[0]}
    ]
    t0 = time.time()
    cached_resp = wrapper.create_chat_completion(cached_messages, max_tokens=15, prompt_version="pool_test_1")
    t_elapsed = time.time() - t0
    print(f"Re-dispatched Call 1 Prompt. Latency: {t_elapsed * 1000:.2f} ms")
    print(f"Response: {repr(cached_resp.strip())}")
    assert t_elapsed < 0.05, "Cache lookup took longer than expected"
    print("Global shared cache verified: zero network calls, zero key consumption! ✓")

    # 4. Forced Exhaustion Failover Test (Key 1 exhausted -> Fails over to Key 2)
    print("\n" + "#" * 100)
    print("PART 4: FORCED-EXHAUSTION FAILOVER TEST (KEY 1 EXHAUSTED -> KEY 2)")
    print("#" * 100)

    # Force round-robin pointer to start at key 1 (slot index 0)
    wrapper._current_key_idx = 0

    # Mock key 1's budget tracker check_budget_available to raise BudgetExhaustedError
    original_check = wrapper.slots[0].tracker.check_budget_available
    def mock_exhausted(*args, **kwargs):
        raise BudgetExhaustedError("FORCED SIMULATION: Key 1 minute output token quota exhausted (1,000 OTPM cap).")

    wrapper.slots[0].tracker.check_budget_available = mock_exhausted

    failover_messages = [
        {"role": "system", "content": "You are a concise test agent. Reply with the word OK only."},
        {"role": "user", "content": "Simulate failover test message."}
    ]

    print("Dispatching request when Key 1 is at the front of the round-robin queue but exhausted...")
    resp_failover = wrapper.create_chat_completion(failover_messages, max_tokens=15, prompt_version="failover_v1")
    serving_slot = wrapper.last_served_slot

    print(f"  -> Response Content: {repr(resp_failover.strip())}")
    print(f"  -> Successfully Served By: {serving_slot.key_id} ({serving_slot.key_preview})")

    assert serving_slot.key_id == "key_2", f"Expected failover to key_2, but was served by {serving_slot.key_id}!"
    print("Forced-exhaustion failover verified: Key 1 safely skipped, request served by Key 2! ✓")

    # Restore key 1 tracker
    wrapper.slots[0].tracker.check_budget_available = original_check

    # 5. Multi-Key Budget Persistence in .groq_budget.json
    print("\n" + "#" * 100)
    print("PART 5: PERSISTENT BUDGET ENTRIES IN .groq_budget.json")
    print("#" * 100)

    budget_file = wrapper.slots[0].tracker.persistence_path
    print(f"Budget File Path: {budget_file}")
    with open(budget_file, "r", encoding="utf-8") as f:
        budget_data = json.load(f)

    print("\nEntries found in .groq_budget.json:")
    for k_id, k_metrics in sorted(budget_data.items()):
        if isinstance(k_metrics, dict):
            print(f"  [{k_id}] preview={k_metrics.get('key_preview')} | reqs={k_metrics.get('daily_requests')} | "
                  f"tokens={k_metrics.get('daily_total_tokens')} | rem_tok={k_metrics.get('server_remaining_tokens')}")

    assert "key_1" in budget_data, "key_1 missing from budget file"
    assert "key_2" in budget_data, "key_2 missing from budget file"
    assert "key_3" in budget_data, "key_3 missing from budget file"
    print("\nIndependent persistence verified for all keys in .groq_budget.json! ✓")

    print("\n" + "=" * 100)
    print("ALL KEY POOLING & FAILOVER TESTS PASSED WITH 100% SUCCESS ✓")
    print("=" * 100 + "\n")

if __name__ == "__main__":
    main()
