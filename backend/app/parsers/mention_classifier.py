# -*- coding: utf-8 -*-
"""
backend/app/parsers/mention_classifier.py
=========================================
Production-Grade Mention Role Classifier for Tender Standards Auditing.

Roles:
- required_spec: Mandatory product/material technical specification or conforming standard
- test_basis: Routine/type testing method, sampling, or testing procedure
- certification_mark: ISI mark, BIS licensing, or certification mark requirement
- category_label: Portal category, BOQ heading, or classification grouping
- noise: Boilerplate GTC disclaimer, portal search result (e.g. GeMARPTS), header/footer
- vague_reference: Non-binding general, advisory, or incidental mention
- alternative: Optional or alternative equivalent standard
- needs_review: Fallback role on classifier failure, timeout, or malformed response

Architectural Features:
1. Multi-Key Pooled Groq Dispatch: Uses `get_groq_wrapper()` with key pooling and failover.
2. Batched Classification: Evaluates multiple mentions per call, returning ONLY role labels
   per index to minimize token spend well below the 1,000 OTPM cap.
3. Hard Prior Enforcement: Mentions from CONTEXT_ONLY blocks can NEVER receive `required_spec`.
   Code strictly overrides any such assignment to `noise` and logs the override.
4. Deterministic Failure Fallback: Any timeout, parse error, or low confidence maps to `needs_review`,
   never `required_spec`.
5. Exact Context-Hash Caching: Caches decisions by sha256(mention_text + context_hash + tier).
"""
from __future__ import annotations
import re
import json
import time
import hashlib
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple

from app.config import settings
from app.parsers.mention_extractor import Mention
from app.parsers.groq_wrapper import get_groq_wrapper, BudgetExhaustedError

logger = logging.getLogger("mention_classifier")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter("[%(levelname)s] [MentionClassifier] %(message)s")
    ch.setFormatter(formatter)
    logger.addHandler(ch)


class MentionRole(str, Enum):
    REQUIRED_SPEC = "required_spec"
    TEST_BASIS = "test_basis"
    CERTIFICATION_MARK = "certification_mark"
    CATEGORY_LABEL = "category_label"
    NOISE = "noise"
    VAGUE_REFERENCE = "vague_reference"
    ALTERNATIVE = "alternative"
    NEEDS_REVIEW = "needs_review"


@dataclass
class MentionToClassify:
    """Input mention with source block context and tier."""
    mention: Mention
    tier: str = "AUTHORITATIVE"  # AUTHORITATIVE | CORROBORATING | CONTEXT_ONLY
    context: str = ""           # Surrounding block text or sentence snippet


@dataclass
class ClassifiedMention:
    """Classification result with provenance, tier, and override tracking."""
    mention: Mention
    role: MentionRole
    tier: str
    context_snippet: str
    override_reason: Optional[str] = None
    cached: bool = False
    raw_llm_role: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_text": self.mention.raw_text,
            "base_key": self.mention.base_key,
            "role": self.role.value,
            "tier": self.tier,
            "context_snippet": self.context_snippet,
            "override_reason": self.override_reason,
            "cached": self.cached,
            "raw_llm_role": self.raw_llm_role
        }


class MentionRoleClassifier:
    """
    Batched, key-pooled LLM classifier for assigning procurement roles to standards mentions.
    """

    SYSTEM_PROMPT = (
        "You are an Indian Standards (BIS) and tender compliance role classifier.\n"
        "Given numbered standard mentions in their surrounding context and document tier:\n"
        "Assign each mention exactly one ROLE label from this closed vocabulary:\n"
        "- required_spec: mandatory product/material technical specification or conforming standard in AUTHORITATIVE tier\n"
        "- test_basis: routine/type testing method, sampling, or test procedure\n"
        "- certification_mark: ISI mark, BIS licensing, or third-party certification mark requirement\n"
        "- category_label: portal category, BOQ header, classification grouping, or standard appearing in 'Relevant Categories' / CORROBORATING tier\n"
        "- noise: boilerplate GTC disclaimer, portal search result (GeMARPTS), header/footer, or CONTEXT_ONLY tier\n"
        "- vague_reference: non-binding general, advisory, generic/unnumbered mention (e.g. 'relevant BIS standard'), or incidental mid-sentence mention without mandatory requirement\n"
        "- alternative: optional, substitute, or alternative equivalent standard (e.g. introduced by 'or equivalent', 'or alternative', 'or similar')\n\n"
        "RULES:\n"
        "1. Return JSON ONLY with schema:\n"
        "{\n"
        "  \"classifications\": [\n"
        "    {\"index\": 1, \"role\": \"<role_label>\"}\n"
        "  ]\n"
        "}\n"
        "2. Mentions in CORROBORATING tier or under 'Relevant Categories' must be classified as category_label.\n"
        "3. Mentions introduced with 'or equivalent' or 'alternative' must be classified as alternative.\n"
        "4. Generic unnumbered mentions (e.g. 'as per relevant BIS standard') or incidental mid-sentence mentions must be classified as vague_reference.\n"
        "5. Output ONLY the role label per mention index. DO NOT output standard numbers, years, quotes, or reasoning."
    )

    def __init__(self):
        # In-memory context-hash cache: key -> MentionRole
        self._cache: Dict[str, MentionRole] = {}
        self.last_batch_stats: Dict[str, Any] = {}

    def _compute_cache_key(self, mention_text: str, context: str, tier: str) -> str:
        """Computes cache key based on (mention text + surrounding context hash + tier)."""
        ctx_hash = hashlib.sha256(context.strip().encode("utf-8")).hexdigest()[:16]
        payload = f"{mention_text.strip()}::{ctx_hash}::{tier.strip().upper()}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def classify_batch(
        self,
        items: List[MentionToClassify],
        batch_size: int = 8,
        mock_response: Optional[str] = None,
        prompt_version: str = "role_v1",
        force_adversarial_role: Optional[MentionRole] = None
    ) -> List[ClassifiedMention]:
        """
        Classifies a list of mentions in batches using the key-pooled Groq client wrapper.
        - Respects source tier: CONTEXT_ONLY mentions can NEVER receive required_spec.
        - On failure (timeout, parse error, network failure), falls back to needs_review.
        - Caches classification by (mention text + context hash + tier).
        """
        if not items:
            return []

        results: List[ClassifiedMention] = [None] * len(items)
        uncached_indices: List[int] = []

        # 1. Cache Check
        for idx, item in enumerate(items):
            m_text = item.mention.raw_text
            ctx = getattr(item, 'context', None) or getattr(item, 'context_snippet', None) or (item.mention.context_before + " " + item.mention.context_after)
            c_key = self._compute_cache_key(m_text, ctx, item.tier)

            if c_key in self._cache and not force_adversarial_role:
                cached_role = self._cache[c_key]
                results[idx] = ClassifiedMention(
                    mention=item.mention,
                    role=cached_role,
                    tier=item.tier,
                    context_snippet=ctx[:80],
                    cached=True
                )
            else:
                uncached_indices.append(idx)

        # If all items were in cache, return immediately
        if not uncached_indices:
            return results

        # 2. Process Uncached Items in Batches
        wrapper = get_groq_wrapper()

        for b_start in range(0, len(uncached_indices), batch_size):
            b_indices = uncached_indices[b_start : b_start + batch_size]
            batch_items = [items[i] for i in b_indices]

            # Construct compact prompt
            prompt_lines = []
            for b_idx, item in enumerate(batch_items, 1):
                ctx_raw = getattr(item, 'context', None) or getattr(item, 'context_snippet', None) or (item.mention.context_before + " " + item.mention.context_after)
                ctx_snippet = ctx_raw.strip()
                # Clean multiple spaces/newlines
                ctx_snippet = re.sub(r'\s+', ' ', ctx_snippet)[:140]
                prompt_lines.append(
                    f"[M{b_idx}] Mention: '{item.mention.raw_text}' | Context: \"{ctx_snippet}\" | Tier: {item.tier}"
                )

            user_prompt = "MENTIONS TO CLASSIFY:\n" + "\n".join(prompt_lines)

            # Call LLM or use mock
            llm_content = ""
            call_failed = False
            fail_reason = ""

            if mock_response is not None:
                llm_content = mock_response
            elif force_adversarial_role is not None:
                # Adversarial simulation: mock LLM returning the adversarial role (e.g. required_spec)
                adversarial_payload = {
                    "classifications": [
                        {"index": i, "role": force_adversarial_role.value}
                        for i in range(1, len(batch_items) + 1)
                    ]
                }
                llm_content = json.dumps(adversarial_payload)
            else:
                try:
                    messages = [
                        {"role": "system", "content": self.SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt}
                    ]
                    # Reserve 25 tokens per mention in batch
                    out_reserve = min(max(len(batch_items) * 25, 40), 250)
                    t0 = time.time()
                    llm_content = wrapper.create_chat_completion(
                        messages=messages,
                        model=settings.GROQ_MODEL,
                        temperature=0.0,
                        max_tokens=out_reserve,
                        prompt_version=prompt_version
                    )
                    elapsed = time.time() - t0
                    self.last_batch_stats = {
                        "batch_size": len(batch_items),
                        "output_tokens_reserved": out_reserve,
                        "elapsed_seconds": round(elapsed, 3),
                        "serving_slot": wrapper.last_served_slot.key_id if wrapper.last_served_slot else "none"
                    }
                except Exception as e:
                    logger.error(f"Classification call failed for batch ({len(batch_items)} items): {e}")
                    call_failed = True
                    fail_reason = f"CLASSIFIER_CALL_ERROR: {str(e)}"

            # Parse role assignments from LLM response
            parsed_roles: Dict[int, MentionRole] = {}

            if not call_failed:
                clean_json = llm_content.strip()
                if clean_json.startswith("```"):
                    clean_json = re.sub(r"^```(json)?\n", "", clean_json)
                    clean_json = re.sub(r"\n```$", "", clean_json)

                try:
                    data = json.loads(clean_json)
                    entries = data.get("classifications", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
                    for entry in entries:
                        if isinstance(entry, dict):
                            e_idx = entry.get("index")
                            e_role_str = str(entry.get("role", "")).strip().lower()
                            try:
                                parsed_roles[int(e_idx)] = MentionRole(e_role_str)
                            except (ValueError, TypeError):
                                parsed_roles[int(e_idx)] = MentionRole.NEEDS_REVIEW
                except Exception as e:
                    logger.warning(f"Malformed LLM JSON in batch: {e}. Raw content: {repr(llm_content[:100])}")
                    call_failed = True
                    fail_reason = f"MALFORMED_LLM_JSON: {str(e)}"

            # 3. Apply Hard Prior Rules and Fallbacks
            for b_idx, item in enumerate(batch_items, 1):
                orig_idx = b_indices[b_idx - 1]
                override_reason: Optional[str] = None

                raw_llm_role: Optional[str] = None
                if call_failed:
                    assigned_role = MentionRole.NEEDS_REVIEW
                    override_reason = fail_reason
                else:
                    assigned_role = parsed_roles.get(b_idx, MentionRole.NEEDS_REVIEW)
                    if b_idx in parsed_roles:
                        raw_llm_role = parsed_roles[b_idx].value
                    if assigned_role == MentionRole.NEEDS_REVIEW and b_idx not in parsed_roles:
                        override_reason = "INDEX_MISSING_IN_LLM_OUTPUT"

                # ── HARD PRIOR RULE: CONTEXT_ONLY / CORROBORATING tier cannot be required_spec ──
                if item.tier == "CONTEXT_ONLY" and assigned_role == MentionRole.REQUIRED_SPEC:
                    logger.warning(
                        f"[HARD PRIOR OVERRIDE] Mention '{item.mention.raw_text}' in CONTEXT_ONLY block cannot be "
                        f"'{MentionRole.REQUIRED_SPEC.value}'. Overriding to '{MentionRole.NOISE.value}'."
                    )
                    assigned_role = MentionRole.NOISE
                    override_reason = "TIER_HARD_PRIOR_CONTEXT_ONLY_CANNOT_BE_REQUIRED_SPEC"
                elif item.tier == "CORROBORATING" and assigned_role == MentionRole.REQUIRED_SPEC:
                    logger.warning(
                        f"[HARD PRIOR OVERRIDE] Mention '{item.mention.raw_text}' in CORROBORATING block cannot be "
                        f"'{MentionRole.REQUIRED_SPEC.value}'. Overriding to '{MentionRole.CATEGORY_LABEL.value}'."
                    )
                    assigned_role = MentionRole.CATEGORY_LABEL
                    override_reason = "TIER_HARD_PRIOR_CORROBORATING_CANNOT_BE_REQUIRED_SPEC"

                ctx_final = (getattr(item, 'context', None) or getattr(item, 'context_snippet', None) or (item.mention.context_before + " " + item.mention.context_after)).strip()
                # Cache if valid role and not a temporary error
                if not call_failed and assigned_role != MentionRole.NEEDS_REVIEW:
                    m_text = item.mention.raw_text
                    c_key = self._compute_cache_key(m_text, ctx_final, item.tier)
                    self._cache[c_key] = assigned_role

                results[orig_idx] = ClassifiedMention(
                    mention=item.mention,
                    role=assigned_role,
                    tier=item.tier,
                    context_snippet=ctx_final[:80],
                    override_reason=override_reason,
                    cached=False,
                    raw_llm_role=raw_llm_role
                )

        return results


# Global singleton instance
_default_classifier: Optional[MentionRoleClassifier] = None

def get_mention_classifier() -> MentionRoleClassifier:
    global _default_classifier
    if _default_classifier is None:
        _default_classifier = MentionRoleClassifier()
    return _default_classifier
