"""
tests/eval/run_eval.py
======================
Evaluation harness for SIH-26108 StandardSphere Tender Audit pipeline.
Usage:
    python tests/eval/run_eval.py                 # stub run (all zeros)
    python tests/eval/run_eval.py --mode full     # runs against both GeM PDFs
    python tests/eval/run_eval.py --budget-check  # abort if remaining_requests < 50

Exit codes:
    0: all hard assertions pass
    1: at least one hard assertion failed
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Path setup ────────────────────────────────────────────────────────────────
BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND_DIR))
os.chdir(str(BACKEND_DIR))

# ── Colours (no unicode, stays CP-1252 safe) ──────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def _green(s): return f"{GREEN}{s}{RESET}"
def _red(s):   return f"{RED}{s}{RESET}"
def _yellow(s): return f"{YELLOW}{s}{RESET}"

# ── Metric accumulator ────────────────────────────────────────────────────────
class Metrics:
    def __init__(self):
        self.req_tp = 0          # required_spec correctly identified
        self.req_fp = 0          # labelled required_spec but not gold
        self.req_fn = 0          # gold required_spec not found or mis-labelled
        self.total_mentions = 0
        self.wrong_role     = 0
        self.ctx_mentions   = 0  # CONTEXT_ONLY source mentions
        self.ctx_promoted   = 0  # CONTEXT_ONLY promoted to required_spec
        self.hallucinated   = 0  # LLM-output IS number not in source text
        self.llm_classified = 0  # total LLM-classified mentions
        self.llm2_verified  = 0  # LLM-2 descriptions verified in source
        self.llm2_dropped   = 0  # LLM-2 descriptions NOT in source -> dropped
        self.stageb_verified  = 0
        self.stageb_hallucinated = 0
        self.resolver_correct = 0
        self.resolver_total   = 0
        self.seg_correct  = 0
        self.seg_total    = 0
        self.wall_time_s  = 0.0
        self.items_processed = 0

    # ── Derived metrics ───────────────────────────────────────────────────────
    def req_precision(self) -> Optional[float]:
        if self.items_processed == 0: return None
        denom = self.req_tp + self.req_fp
        return self.req_tp / denom if denom else None

    def req_recall(self) -> Optional[float]:
        if self.items_processed == 0: return None
        denom = self.req_tp + self.req_fn
        return self.req_tp / denom if denom else None

    def wrong_role_rate(self) -> Optional[float]:
        if self.items_processed == 0: return None
        return self.wrong_role / self.total_mentions if self.total_mentions else None

    def ctx_promotion_rate(self) -> float:
        return self.ctx_promoted / self.ctx_mentions if self.ctx_mentions else 0.0

    def hallucination_rate(self) -> float:
        total = self.llm_classified + self.llm2_verified + self.llm2_dropped + self.stageb_verified + self.stageb_hallucinated
        return self.hallucinated / total if total else 0.0

    def resolver_accuracy(self) -> Optional[float]:
        return self.resolver_correct / self.resolver_total if self.resolver_total else None

    def segmentation_accuracy(self) -> Optional[float]:
        return self.seg_correct / self.seg_total if self.seg_total else None

    # ── Report ────────────────────────────────────────────────────────────────
    def print_table(self, label: str = "Eval Results"):
        targets = {
            "req_precision":      (">=", 0.85),
            "req_recall":         (">=", 0.85),
            "ctx_promotion_rate": ("==", 0.0),
            "hallucination_rate": ("==", 0.0),
        }
        fields = [
            ("required_spec precision",         self.req_precision()),
            ("required_spec recall",             self.req_recall()),
            ("wrong-role rate",                  self.wrong_role_rate()),
            ("CONTEXT_ONLY promotion rate",      self.ctx_promotion_rate()),
            ("hallucination rate (LLM)",         self.hallucination_rate()),
            ("LLM-2 desc verified in source",    self.llm2_verified),
            ("LLM-2 desc dropped (not in src)",  self.llm2_dropped),
            ("Stage-B hallucinated",             self.stageb_hallucinated),
            ("resolver accuracy",                self.resolver_accuracy()),
            ("segmentation accuracy",            self.segmentation_accuracy()),
            ("items processed",                  self.items_processed),
            ("E2E wall time (s)",                round(self.wall_time_s, 2)),
        ]
        print(f"\n{BOLD}=== {label} ==={RESET}")
        print(f"  {'Metric':<40} {'Value':>12}  Status")
        print(f"  {'-'*40} {'-'*12}  {'-'*18}")
        for name, val in fields:
            if val is None:
                display = "N/A"
                status  = _yellow("VACUOUS PASS (0 items)")
            elif isinstance(val, float):
                display = f"{val:.3f}"
                fn_name = name.lower().replace(" ", "_").replace("-", "_").replace("(", "").replace(")", "")
                # Map display names to target keys
                key = {
                    "required_spec_precision": "req_precision",
                    "required_spec_recall":    "req_recall",
                    "context_only_promotion_rate": "ctx_promotion_rate",
                    "hallucination_rate_llm": "hallucination_rate",
                }.get(fn_name, None)
                if key and key in targets:
                    op, tgt = targets[key]
                    passed = (val >= tgt if op == ">=" else val == tgt)
                    status = _green("PASS") if passed else _red(f"FAIL (target {op}{tgt})")
                else:
                    status = ""
            else:
                display = str(val)
                status  = ""
            print(f"  {name:<40} {display:>12}  {status}")

    # ── Hard assertions ───────────────────────────────────────────────────────
    def check_hard_assertions(self) -> bool:
        failures = []
        if self.items_processed == 0:
            print(_yellow("  VACUOUS PASS: 0 items processed — all hard assertions vacuously pass."))
            return True
        if self.hallucination_rate() > 0:
            failures.append(f"hallucination_rate={self.hallucination_rate():.4f} > 0")
        if self.ctx_promotion_rate() > 0:
            failures.append(f"ctx_promotion_rate={self.ctx_promotion_rate():.4f} > 0")
        p = self.req_precision()
        if p is not None and p < 0.85:
            failures.append(f"req_precision={p:.3f} < 0.85")
        if failures:
            print(_red("\n  HARD ASSERTION FAILURES:"))
            for f in failures:
                print(_red(f"    - {f}"))
            return False
        print(_green("\n  All hard assertions PASS."))
        return True


# ── Gold-set runner ────────────────────────────────────────────────────────────

def load_gold_fixtures() -> List[Dict[str, Any]]:
    gold_path = Path(__file__).parent / "gold" / "gold_fixtures.json"
    if not gold_path.exists():
        print(f"Gold fixtures not found at {gold_path}")
        return []
    with open(gold_path, encoding='utf-8') as f:
        return json.load(f)


def run_gold_set(metrics: Metrics) -> None:
    """
    Run the pipeline against gold fixtures.
    Steps 5-7a not yet implemented: accumulates zero counts.
    When Steps 5-7a are implemented, import and call:
        from app.mention.mention_regex import extract_mentions
        from app.mention.verifier import verify_all
        from app.mention.mention_llm import classify_mentions
        from app.resolver.resolver import resolve_all
    """
    fixtures = load_gold_fixtures()
    print(f"\nLoaded {len(fixtures)} gold fixtures.")

    for fx in fixtures:
        expected_mentions = fx.get("expected_mentions", [])
        ctx_tier = fx.get("source_tier", "AUTHORITATIVE")
        if ctx_tier == "CONTEXT_ONLY":
            metrics.ctx_mentions += len(expected_mentions)

        metrics.seg_total += 1  # each fixture = 1 "item"

        # Pipeline stubs — replace with real calls as steps are implemented
        predicted_mentions: List[Dict] = []  # Step 5 output
        predicted_roles:    Dict[str, str] = {}  # Step 7a output

        # Score against gold
        gold_req = [m for m in expected_mentions if m.get("role") == "required_spec"]
        pred_req = [m for m in predicted_mentions if m.get("role") == "required_spec"]

        metrics.req_tp += 0  # will be non-zero after Step 5+7a
        metrics.req_fp += 0
        metrics.req_fn += len(gold_req)
        metrics.total_mentions += len(expected_mentions)

        if ctx_tier == "CONTEXT_ONLY":
            ctx_promoted_in_item = len([m for m in predicted_mentions if m.get("role") == "required_spec"])
            metrics.ctx_promoted += ctx_promoted_in_item

    metrics.seg_correct = 0  # no items segmented yet


def run_gem_pdfs(metrics: Metrics, gem_pdf_paths: List[str]) -> None:
    """Run full pipeline against GeM PDFs. Implemented in Step 10."""
    print("  GeM PDF pipeline not yet implemented (Step 10).")


# ── Budget check ──────────────────────────────────────────────────────────────

def check_groq_budget(min_remaining: int = 50) -> None:
    try:
        from app.config import settings
        from groq import Groq
        client = Groq(api_key=settings.GROQ_API_KEY)
        resp = client.chat.completions.with_raw_response.create(
            model=settings.GROQ_MODEL,
            messages=[{"role": "user", "content": "1"}],
            max_tokens=1,
        )
        remaining = int(resp.headers.get('x-ratelimit-remaining-requests', 9999))
        print(f"  Groq remaining requests: {remaining}")
        if remaining < min_remaining:
            print(_red(f"  ABORT: remaining_requests={remaining} < {min_remaining}. Run again tomorrow."))
            sys.exit(2)
    except Exception as e:
        print(f"  Budget check failed: {e}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Tender Audit Eval Harness")
    parser.add_argument("--mode", choices=["gold", "full"], default="gold",
                        help="'gold' = run gold fixtures only; 'full' = gold + GeM PDFs")
    parser.add_argument("--budget-check", action="store_true",
                        help="Check Groq daily budget before running; abort if < 50 requests remain")
    parser.add_argument("--gem-pdf", nargs="*", default=[],
                        help="Paths to GeM PDF files for full-mode evaluation")
    args = parser.parse_args()

    if args.budget_check:
        print("\n-- Groq budget check --")
        check_groq_budget()

    metrics = Metrics()
    t_start = time.time()

    print("\n-- Gold set evaluation --")
    run_gold_set(metrics)

    if args.mode == "full":
        print("\n-- GeM PDF evaluation --")
        if not args.gem_pdf:
            print("  No --gem-pdf paths provided. Skipping.")
        else:
            run_gem_pdfs(metrics, args.gem_pdf)

    metrics.wall_time_s = time.time() - t_start
    metrics.print_table(label=f"Eval Results (mode={args.mode})")
    passed = metrics.check_hard_assertions()

    print(f"\n{'='*60}")
    if passed:
        print(_green(f"  RESULT: PASS (mode={args.mode})"))
    else:
        print(_red(f"  RESULT: FAIL (see hard assertion failures above)"))
    print(f"{'='*60}\n")

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
