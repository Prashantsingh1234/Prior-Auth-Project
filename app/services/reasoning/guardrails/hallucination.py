"""
Hallucination detector for LLM reasoning outputs.

Checks that evidence citations in the LLM output actually appear in the
source documents (retrieved policy chunks + clinical summary).

Algorithm:
  For each evidence_citation.quote in the output:
    1. Attempt exact substring match against all source texts
    2. If no exact match, attempt fuzzy match (token overlap ≥ threshold)
    3. If neither matches, flag as potential hallucination

Hallucination score = unverified_citations / total_citations
  > HALLUCINATION_HARD_THRESHOLD → HIGH severity (reject)
  > HALLUCINATION_SOFT_THRESHOLD → MEDIUM severity (escalate)
"""

from __future__ import annotations

import re
import structlog

from app.services.reasoning.guardrails.base import BaseGuardrail, GuardrailContext
from app.services.reasoning.models import (
    GuardrailResult,
    GuardrailViolation,
    ViolationSeverity,
    ViolationType,
)

logger = structlog.get_logger(__name__)

# Fraction of unverified citations that triggers rejection
HALLUCINATION_HARD_THRESHOLD = 0.40

# Fraction that triggers escalation (but not rejection)
HALLUCINATION_SOFT_THRESHOLD = 0.20

# Token overlap ratio for fuzzy matching
FUZZY_OVERLAP_THRESHOLD = 0.60

# Minimum citation quote length to check (very short quotes may false-positive)
MIN_QUOTE_LENGTH = 10


def _tokenize(text: str) -> set[str]:
    """Simple whitespace + punctuation tokenizer."""
    tokens = re.findall(r"[a-zA-Z0-9]+", text.lower())
    return set(tokens)


def _fuzzy_match(quote: str, source: str, threshold: float = FUZZY_OVERLAP_THRESHOLD) -> bool:
    """
    Check if a quote is sufficiently covered by a source text using token overlap.

    Returns True if the fraction of quote tokens found in source >= threshold.
    """
    q_tokens = _tokenize(quote)
    s_tokens = _tokenize(source)
    if not q_tokens:
        return True  # empty quote is trivially grounded
    overlap = len(q_tokens & s_tokens)
    return overlap / len(q_tokens) >= threshold


def _check_quote_in_sources(quote: str, sources: list[str]) -> tuple[bool, str]:
    """
    Check if a quote appears (exactly or fuzzily) in any source.

    Returns (found, match_type) where match_type is 'exact', 'fuzzy', or 'none'.
    """
    if len(quote) < MIN_QUOTE_LENGTH:
        return True, "too_short"

    # Normalize quote for comparison
    normalized_quote = quote.strip().lower()

    for source in sources:
        normalized_source = source.lower()
        # Exact substring match (case-insensitive)
        if normalized_quote in normalized_source:
            return True, "exact"

    # Fuzzy match fallback
    for source in sources:
        if _fuzzy_match(quote, source):
            return True, "fuzzy"

    return False, "none"


class HallucinationDetector(BaseGuardrail):
    """
    Detects hallucinated evidence citations.

    Only checks citations where status is MET or NOT_MET — UNDETERMINED
    criteria may legitimately have no citations.
    """

    name = "hallucination_detector"

    def __init__(
        self,
        hard_threshold: float = HALLUCINATION_HARD_THRESHOLD,
        soft_threshold: float = HALLUCINATION_SOFT_THRESHOLD,
    ) -> None:
        self._hard = hard_threshold
        self._soft = soft_threshold

    async def check(self, ctx: GuardrailContext) -> GuardrailResult:
        parsed = ctx.parsed_output
        if not parsed:
            return self._pass()  # nothing to check

        all_sources = [ctx.clinical_summary] + ctx.policy_chunks
        all_sources = [s for s in all_sources if s]

        if not all_sources:
            # No source texts to verify against — cannot check, skip
            return self._pass()

        violations: list[GuardrailViolation] = []
        total_citations = 0
        unverified_citations = 0

        for eval_item in parsed.get("criterion_evaluations", []):
            if not isinstance(eval_item, dict):
                continue

            status = eval_item.get("status", "UNDETERMINED")
            cid = eval_item.get("criterion_id", "unknown")

            # Only check citations for determined statuses
            if status not in ("MET", "NOT_MET"):
                continue

            citations = eval_item.get("evidence_citations", [])
            if not isinstance(citations, list):
                continue

            for citation in citations:
                if not isinstance(citation, dict):
                    continue

                quote = citation.get("quote", "").strip()
                if not quote:
                    continue

                total_citations += 1
                found, match_type = _check_quote_in_sources(quote, all_sources)

                if not found:
                    unverified_citations += 1
                    violations.append(GuardrailViolation(
                        violation_type=ViolationType.HALLUCINATION,
                        severity=ViolationSeverity.HIGH,
                        message=(
                            f"Citation quote in criterion {cid} does not appear in source documents"
                        ),
                        criterion_id=cid,
                        details={
                            "quote_preview": quote[:100],
                            "match_type": match_type,
                        },
                    ))

        # Compute hallucination rate
        if total_citations == 0:
            return self._pass()

        hallucination_rate = unverified_citations / total_citations

        if hallucination_rate >= self._hard:
            logger.error(
                "guardrail.hallucination_detected",
                case_id=ctx.case_id,
                rate=round(hallucination_rate, 3),
                unverified=unverified_citations,
                total=total_citations,
            )
            return self._fail(violations)

        if hallucination_rate >= self._soft:
            # Escalate to larger model but don't hard-reject
            for v in violations:
                v.severity = ViolationSeverity.MEDIUM
            logger.warning(
                "guardrail.hallucination_soft",
                case_id=ctx.case_id,
                rate=round(hallucination_rate, 3),
            )
            return GuardrailResult(passed=True, violations=violations)

        # Low hallucination rate — pass with any individual violations as warnings
        for v in violations:
            v.severity = ViolationSeverity.LOW
        return GuardrailResult(passed=True, violations=violations)
