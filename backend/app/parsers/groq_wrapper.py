# -*- coding: utf-8 -*-
"""
backend/app/parsers/groq_wrapper.py
===================================
Production-Grade Multi-Key Groq Client Wrapper with:
1. Key Pooling & Round-Robin:
   - Round-robins requests across all configured API keys (GROQ_API_KEY, GROQ_API_KEY_2, GROQ_API_KEY_3).
2. Independent Budget Trackers:
   - Each key has its own isolated rolling 60-second input/output token buckets (8,000 TPM / 1,000 OTPM cap)
     and independent daily request/token counters.
3. Key-Specific Persistence:
   - Persists independent telemetry for each key into separate entries in `.groq_budget.json`.
4. Intelligent Failover with Backoff Exhaustion:
   - On 429 RateLimitError, retries with backoff on the current key.
   - If a key's retries are exhausted or its pre-flight budget is exhausted, fails over to the next key in the pool.
5. Global Shared Cache:
   - Shared in-memory content cache keyed by sha256(model, messages, temp, max_tokens, prompt_version).
   - Serves cache hits instantly with zero token consumption and zero key dispatch.
6. Redactor Security Firewall:
   - Prevents unredacted PII from reaching any LLM while protecting 10-digit material codes.
"""
from __future__ import annotations
import os
import time
import json
import re
import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from groq import Groq, RateLimitError, APIError

from app.config import settings
from app.parsers.redactor import Redactor

logger = logging.getLogger("groq_wrapper")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter("[%(levelname)s] [GroqWrapper] %(message)s")
    ch.setFormatter(formatter)
    logger.addHandler(ch)


class BudgetExhaustedError(Exception):
    """Raised when per-minute or daily Groq request or token budgets are exhausted."""
    pass


class UnredactedPIIError(Exception):
    """Raised when an unredacted prompt containing raw PII is passed to the LLM client."""
    pass


def mask_key(k: Optional[str]) -> str:
    """Masks API key for secure logging and display, showing prefix and suffix."""
    if not k:
        return "none"
    k = k.strip()
    if len(k) <= 12:
        return "***"
    return f"{k[:7]}...{k[-6:]}"


class BudgetTracker:
    """
    Tracks input and output token consumption and request usage across
    rolling 60-second windows and persistent 24-hour daily budgets for a specific API key.
    """

    def __init__(
        self,
        key_id: str = "key_1",
        key_preview: str = "",
        max_input_tokens_per_minute: int = 8000,
        max_output_tokens_per_minute: int = 1000,
        max_requests_per_minute: int = 1000,
        max_input_tokens_per_day: int = 500000,
        max_output_tokens_per_day: int = 100000,
        max_requests_per_day: int = 14400,
        persistence_path: Optional[str] = None,
        max_tokens_per_minute: Optional[int] = None,
    ):
        self.key_id = key_id
        self.key_preview = key_preview

        if max_tokens_per_minute is not None:
            max_input_tokens_per_minute = max_tokens_per_minute
            max_output_tokens_per_minute = min(max_output_tokens_per_minute, max_tokens_per_minute)

        self.max_input_tokens_per_minute = max_input_tokens_per_minute
        self.max_output_tokens_per_minute = max_output_tokens_per_minute
        self.max_requests_per_minute = max_requests_per_minute
        self.max_input_tokens_per_day = max_input_tokens_per_day
        self.max_output_tokens_per_day = max_output_tokens_per_day
        self.max_requests_per_day = max_requests_per_day

        # Rolling 60s timestamp lists: (timestamp, tokens)
        self._minute_input_records: List[Tuple[float, int]] = []
        self._minute_output_records: List[Tuple[float, int]] = []
        self._minute_requests: List[float] = []

        # Server-reported rate-limit telemetry
        self.server_remaining_requests: Optional[int] = None
        self.server_remaining_tokens: Optional[int] = None
        self.server_reset_requests: Optional[str] = None
        self.server_reset_tokens: Optional[str] = None

        # Daily persistence path
        self.persistence_path = persistence_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
            ".groq_budget.json"
        )
        self.daily_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.daily_requests = 0
        self.daily_input_tokens = 0
        self.daily_output_tokens = 0

        self._load_persisted_budget()

    def _load_persisted_budget(self) -> None:
        """Loads daily counters from `.groq_budget.json` for this key."""
        if not os.path.exists(self.persistence_path):
            return
        try:
            with open(self.persistence_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return

            # Support nested dict by key_id or legacy flat format for key_1
            key_data = data.get(self.key_id)
            if key_data is None and self.key_id == "key_1" and "daily_requests" in data:
                key_data = data

            if key_data and isinstance(key_data, dict):
                today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                if key_data.get("date") == today:
                    self.daily_date = today
                    self.daily_requests = key_data.get("daily_requests", 0)
                    self.daily_input_tokens = key_data.get("daily_input_tokens", 0)
                    self.daily_output_tokens = key_data.get("daily_output_tokens", 0)
                    self.server_remaining_requests = key_data.get("server_remaining_requests")
                    self.server_remaining_tokens = key_data.get("server_remaining_tokens")
                    self.server_reset_requests = key_data.get("server_reset_requests")
                    self.server_reset_tokens = key_data.get("server_reset_tokens")
                    logger.info(
                        f"Loaded budget for {self.key_id} ({self.key_preview}): reqs={self.daily_requests}, "
                        f"in_tok={self.daily_input_tokens}, out_tok={self.daily_output_tokens}"
                    )
        except Exception as e:
            logger.warning(f"Could not load persisted budget for {self.key_id}: {e}")

    def _save_persisted_budget(self) -> None:
        """Saves current daily counters for this key into `.groq_budget.json`."""
        try:
            existing: Dict[str, Any] = {}
            if os.path.exists(self.persistence_path):
                try:
                    with open(self.persistence_path, "r", encoding="utf-8") as f:
                        loaded = json.load(f)
                        if isinstance(loaded, dict):
                            existing = loaded
                except Exception:
                    existing = {}

            existing[self.key_id] = {
                "date": self.daily_date,
                "key_preview": self.key_preview,
                "daily_requests": self.daily_requests,
                "daily_input_tokens": self.daily_input_tokens,
                "daily_output_tokens": self.daily_output_tokens,
                "daily_total_tokens": self.daily_input_tokens + self.daily_output_tokens,
                "server_remaining_requests": self.server_remaining_requests,
                "server_remaining_tokens": self.server_remaining_tokens,
                "server_reset_requests": self.server_reset_requests,
                "server_reset_tokens": self.server_reset_tokens,
                "last_updated": time.time(),
            }

            with open(self.persistence_path, "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save persisted budget for {self.key_id}: {e}")

    def _check_and_reset_day(self, now_dt: datetime) -> None:
        today = now_dt.strftime("%Y-%m-%d")
        if today != self.daily_date:
            logger.info(f"[{self.key_id}] New UTC day detected ({today} != {self.daily_date}). Resetting daily counters.")
            self.daily_date = today
            self.daily_requests = 0
            self.daily_input_tokens = 0
            self.daily_output_tokens = 0
            self._save_persisted_budget()

    def _cleanup_old_records(self, now: float) -> None:
        min_cutoff = now - 60.0
        self._minute_input_records = [r for r in self._minute_input_records if r[0] >= min_cutoff]
        self._minute_output_records = [r for r in self._minute_output_records if r[0] >= min_cutoff]
        self._minute_requests = [t for t in self._minute_requests if t >= min_cutoff]

    def check_budget_available(self, estimated_input_tokens: int = 100, max_output_tokens: int = 100) -> None:
        """
        Verifies budget for this key before dispatching call.
        Reserves `max_output_tokens` against the 1,000 OTPM cap.
        Raises BudgetExhaustedError if limits are breached.
        """
        now = time.time()
        self._cleanup_old_records(now)
        self._check_and_reset_day(datetime.now(timezone.utc))

        # 1. Server-reported header enforcement
        if self.server_remaining_tokens is not None and self.server_remaining_tokens < (estimated_input_tokens + max_output_tokens):
            raise BudgetExhaustedError(
                f"[{self.key_id}] Server remaining tokens ({self.server_remaining_tokens}) < required "
                f"({estimated_input_tokens + max_output_tokens}). Reset: {self.server_reset_tokens}"
            )
        if self.server_remaining_requests is not None and self.server_remaining_requests <= 0:
            raise BudgetExhaustedError(
                f"[{self.key_id}] Server 0 remaining requests. Reset: {self.server_reset_requests}"
            )

        # 2. Minute Output Token Cap (OTPM = 1,000) - Reserve max_tokens
        cur_min_out = sum(t for _, t in self._minute_output_records)
        if cur_min_out + max_output_tokens > self.max_output_tokens_per_minute:
            raise BudgetExhaustedError(
                f"[{self.key_id}] Minute output token cap (OTPM) exceeded: current={cur_min_out} + "
                f"reserved={max_output_tokens} > limit={self.max_output_tokens_per_minute}"
            )

        # 3. Minute Input Token Cap (8,000 TPM)
        cur_min_in = sum(t for _, t in self._minute_input_records)
        if cur_min_in + estimated_input_tokens > self.max_input_tokens_per_minute:
            raise BudgetExhaustedError(
                f"[{self.key_id}] Minute input token cap exceeded: current={cur_min_in} + "
                f"estimated={estimated_input_tokens} > limit={self.max_input_tokens_per_minute}"
            )

        # 4. Minute Request Limit
        cur_min_reqs = len(self._minute_requests)
        if cur_min_reqs >= self.max_requests_per_minute:
            raise BudgetExhaustedError(
                f"[{self.key_id}] Minute request cap exceeded: {cur_min_reqs}/{self.max_requests_per_minute}"
            )

        # 5. Daily Limits
        if self.daily_requests >= self.max_requests_per_day:
            raise BudgetExhaustedError(
                f"[{self.key_id}] Daily request budget exceeded: {self.daily_requests}/{self.max_requests_per_day}"
            )
        if self.daily_output_tokens + max_output_tokens > self.max_output_tokens_per_day:
            raise BudgetExhaustedError(
                f"[{self.key_id}] Daily output token budget exceeded: {self.daily_output_tokens} + "
                f"{max_output_tokens} > {self.max_output_tokens_per_day}"
            )
        if self.daily_input_tokens + estimated_input_tokens > self.max_input_tokens_per_day:
            raise BudgetExhaustedError(
                f"[{self.key_id}] Daily input token budget exceeded: {self.daily_input_tokens} + "
                f"{estimated_input_tokens} > {self.max_input_tokens_per_day}"
            )

    def record_usage(
        self,
        input_tokens: int,
        output_tokens: int,
        headers: Optional[Dict[str, str]] = None
    ) -> None:
        """Records token and request consumption, updates telemetry, and persists to disk."""
        now = time.time()
        self._minute_input_records.append((now, input_tokens))
        self._minute_output_records.append((now, output_tokens))
        self._minute_requests.append(now)

        self.daily_requests += 1
        self.daily_input_tokens += input_tokens
        self.daily_output_tokens += output_tokens

        if headers:
            rem_req = headers.get("x-ratelimit-remaining-requests")
            rem_tok = headers.get("x-ratelimit-remaining-tokens")
            rst_req = headers.get("x-ratelimit-reset-requests")
            rst_tok = headers.get("x-ratelimit-reset-tokens")

            if rem_req is not None:
                try: self.server_remaining_requests = int(rem_req)
                except ValueError: pass
            if rem_tok is not None:
                try: self.server_remaining_tokens = int(rem_tok)
                except ValueError: pass
            self.server_reset_requests = rst_req
            self.server_reset_tokens = rst_tok

            logger.info(
                f"[{self.key_id} ({self.key_preview})] TELEMETRY: in={input_tokens}, out={output_tokens} | "
                f"rem_req={rem_req}, rem_tok={rem_tok}, rst_req={rst_req}, rst_tok={rst_tok} | "
                f"Daily reqs={self.daily_requests}, total_tok={self.daily_input_tokens + self.daily_output_tokens}"
            )

        self._save_persisted_budget()


@dataclass
class KeySlot:
    """Represents a single Groq API key slot with its dedicated client and tracker."""
    key_id: str
    api_key: str
    key_preview: str
    client: Groq
    tracker: BudgetTracker


class GroqClientWrapper:
    """
    Multi-Key Groq Client Wrapper with:
    - Round-robin key selection across configured keys
    - Independent per-key budget tracking & persistence
    - Retry/backoff on current key before failover to next key
    - Global shared completion cache across all keys
    - Redactor PII firewall
    """

    def __init__(
        self,
        api_keys: Optional[List[str]] = None,
        api_key: Optional[str] = None,
        default_model: Optional[str] = None,
        budget_tracker: Optional[BudgetTracker] = None,
    ):
        self.default_model = default_model or settings.GROQ_MODEL
        self._cache: Dict[str, str] = {}
        self._current_key_idx: int = 0
        self.last_served_slot: Optional[KeySlot] = None

        # Determine keys list
        effective_keys: List[str] = []
        if api_keys:
            effective_keys = [k.strip() for k in api_keys if k and k.strip()]
        elif api_key:
            effective_keys = [api_key.strip()]
        else:
            effective_keys = list(settings.GROQ_API_KEYS)

        if not effective_keys and settings.GROQ_API_KEY:
            effective_keys = [settings.GROQ_API_KEY.strip()]

        # Initialize KeySlots
        self.slots: List[KeySlot] = []
        for idx, k in enumerate(effective_keys, 1):
            key_id = f"key_{idx}"
            preview = mask_key(k)
            tracker = budget_tracker if (idx == 1 and budget_tracker) else BudgetTracker(key_id=key_id, key_preview=preview)
            client = Groq(api_key=k, max_retries=0)
            self.slots.append(KeySlot(
                key_id=key_id,
                api_key=k,
                key_preview=preview,
                client=client,
                tracker=tracker
            ))

        # Backward compatibility attributes (reference primary slot)
        self.api_key = self.slots[0].api_key if self.slots else None
        self.client = self.slots[0].client if self.slots else None
        self.tracker = self.slots[0].tracker if self.slots else BudgetTracker()

    def _compute_cache_key(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        prompt_version: str
    ) -> str:
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "prompt_version": prompt_version,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()

    def _validate_redacted(self, messages: List[Dict[str, str]]) -> None:
        """
        Enforces that no message content contains unredacted PII (emails or phone numbers).
        Protects bare 10-digit material codes from false positive rejection.
        """
        for idx, msg in enumerate(messages):
            content = msg.get("content", "")
            if not content:
                continue
            red_res = Redactor.redact(content)
            if red_res.spans:
                p_types = [f"{s.entity_type}: '{s.original_text}'" for s in red_res.spans]
                raise UnredactedPIIError(
                    f"Refusing Groq API call: Unredacted PII detected in message[{idx}] ({len(red_res.spans)} span(s)): {', '.join(p_types)}. "
                    "Only sanitized text that has passed the redactor may be sent to LLM."
                )

    def create_chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 200,
        prompt_version: str = "v1",
        max_retries: int = 3,
        backoff_base: float = 1.0,
    ) -> str:
        """
        Executes chat completion with round-robin key pooling, failover, budget enforcement,
        and global caching.
        """
        assert max_tokens is not None and max_tokens > 0, "max_tokens must be explicitly provided and > 0"
        target_model = model or self.default_model

        if not self.slots:
            raise ValueError("No Groq API keys configured in pool.")

        # 1. Redactor Security Validation
        self._validate_redacted(messages)

        # 2. Global Shared Content Cache Check
        cache_key = self._compute_cache_key(target_model, messages, temperature, max_tokens, prompt_version)
        if cache_key in self._cache:
            logger.info(f"GLOBAL CACHE HIT: Returning cached LLM completion (key={cache_key[:12]}..., ver={prompt_version}).")
            return self._cache[cache_key]

        # 3. Round-Robin Key Selection
        num_slots = len(self.slots)
        start_idx = self._current_key_idx
        # Advance for the next call
        self._current_key_idx = (self._current_key_idx + 1) % num_slots

        # Ordered candidate list starting from chosen round-robin slot
        candidates = [self.slots[(start_idx + offset) % num_slots] for offset in range(num_slots)]

        estimated_input = sum(len(m.get("content", "").split()) * 2 for m in messages) + 30
        last_error: Optional[Exception] = None

        # 4. Attempt Call Across Candidate Slots (Failover)
        for slot in candidates:
            # Check slot budget
            try:
                slot.tracker.check_budget_available(estimated_input_tokens=estimated_input, max_output_tokens=max_tokens)
            except BudgetExhaustedError as e:
                logger.warning(
                    f"Key {slot.key_id} ({slot.key_preview}) budget exhausted: {e}. "
                    f"Failing over to next key in pool..."
                )
                last_error = e
                continue

            # Key is available: execute with retry/backoff on THIS key
            attempt = 0
            while attempt <= max_retries:
                try:
                    raw_response = slot.client.chat.completions.with_raw_response.create(
                        model=target_model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )

                    # Usage & telemetry recording
                    headers_dict = dict(raw_response.headers.items())
                    parsed = raw_response.parse()
                    in_tok = parsed.usage.prompt_tokens if parsed.usage else estimated_input
                    out_tok = parsed.usage.completion_tokens if parsed.usage else max_tokens
                    slot.tracker.record_usage(in_tok, out_tok, headers_dict)

                    content = parsed.choices[0].message.content or ""
                    # Store in shared global cache
                    self._cache[cache_key] = content
                    self.last_served_slot = slot

                    logger.info(
                        f"COMPLETION SERVED: slot={slot.key_id} ({slot.key_preview}) "
                        f"[tokens: in={in_tok}, out={out_tok}]"
                    )
                    return content

                except RateLimitError as e:
                    attempt += 1
                    if attempt > max_retries:
                        logger.warning(
                            f"Key {slot.key_id} ({slot.key_preview}) exhausted all {max_retries} retries on 429. "
                            f"Failing over to next key in pool..."
                        )
                        last_error = BudgetExhaustedError(
                            f"Key {slot.key_id} ({slot.key_preview}) rate-limit persists after {max_retries} retries: {e}"
                        )
                        break  # Break retry loop, try next slot in candidate list

                    # Honor retry-after header if provided by Groq
                    retry_after_val: Optional[float] = None
                    try:
                        if hasattr(e, "response") and e.response is not None and e.response.headers:
                            raw_ra = e.response.headers.get("retry-after")
                            if raw_ra:
                                retry_after_val = float(raw_ra)
                    except Exception:
                        pass

                    if retry_after_val is None:
                        m_sec = re.search(r'try\s+again\s+in\s+([\d\.]+)\s*s', str(e), re.I)
                        if m_sec:
                            retry_after_val = float(m_sec.group(1))

                    sleep_time = retry_after_val if retry_after_val is not None else (backoff_base * (2 ** (attempt - 1)))
                    if retry_after_val is not None:
                        sleep_time = max(sleep_time + 0.2, 0.5)

                    logger.warning(
                        f"Key {slot.key_id} ({slot.key_preview}) 429 on attempt {attempt}/{max_retries}. "
                        f"Honoring retry-after/backoff: sleeping for {sleep_time:.2f}s..."
                    )
                    time.sleep(sleep_time)

                except Exception as e:
                    attempt += 1
                    if attempt > max_retries or "rate_limit" in str(e).lower():
                        logger.warning(
                            f"Key {slot.key_id} ({slot.key_preview}) failed after {attempt} attempts ({e}). "
                            f"Failing over to next key in pool..."
                        )
                        last_error = BudgetExhaustedError(f"Key {slot.key_id} ({slot.key_preview}) failed: {e}")
                        break
                    sleep_time = backoff_base * (2 ** (attempt - 1))
                    logger.warning(
                        f"Key {slot.key_id} transient error ({e}). Retrying in {sleep_time:.2f}s..."
                    )
                    time.sleep(sleep_time)

        # If all candidate keys were exhausted
        raise BudgetExhaustedError(
            f"All {num_slots} Groq API key(s) in pool exhausted: {last_error}"
        )


# Global singleton instance
_default_wrapper: Optional[GroqClientWrapper] = None

def get_groq_wrapper() -> GroqClientWrapper:
    global _default_wrapper
    if _default_wrapper is None:
        _default_wrapper = GroqClientWrapper()
    return _default_wrapper
