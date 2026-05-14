"""
Groundedness checker — validates evidence attribution completeness.

Every MET or NOT_MET determination MUST be backed by at least one citation.
Every citation must have a non-empty quote and explanation.
UNDETERMINED determinations must explain what information is missing.

Groundedness score = grounded_criteria / total_determined_criteria

This is distinct from hallucination detection:
  - Hallucination: cited quote doesn't exist in source
  - Groundedness: no citation at all (claim without evidence)
"""

from __future__ import annotations

import structlog

from app.services.reasoning.guardrails.base import BaseGuardrail, GuardrailContext
from app.services.reasoning.models import (
    GuardrailResult,
    GuardrailViolation,
    ViolationSeverity,
    ViolationType,
)

logger = structlog.get_logger(__name__)

# Fraction of determined criteria that must have citations
GROUNDEDNESS_THRESHOLD = 0.70

# Minimum characters in a rationale to count as explanatory
MIN_RATIONALE_CHARS = 20


class GroundednessChecker(BaseGuardrail):
    """
    Validates that all MET/NOT_MET criteria have evidence citations,
    and that UNDETERMINED criteria explain what is missing.
    """

    name = "groundedness_checker"

    def __init__(self, threshold: float = GROUNDEDNESS_THRESHOLD) -> None:
        self._threshold = threshold

    async def check(self, ctx: GuardrailContext) -> GuardrailResult:
        parsed = ctx.parsed_output
        if not parsed:
            return self._pass()

        violations: list[GuardrailViolation] = []
        determined_count = 0
        grounded_count = 0

        for eval_item in parsed.get("criterion_evaluations", []):
            if not isinstance(eval_item, dict):
                continue

            status = eval_item.get("status", "UNDETERMINED")
            cid = eval_item.get("criterion_id", "unknown")
            citations = eval_item.get("evidence_citations") or []
            rationale = eval_item.get("rationale", "")
            missing_info = eval_item.get("missing_information") or []

            if status in ("MET", "NOT_MET"):
                determined_count += 1

                # Must have at least one citation with non-empty quote
                valid_citations = [
                    c for c in citations
                    if isinstance(c, dict) and c.get("quote", "").strip()
                ]

                if not valid_citations:
                    violations.append(GuardrailViolation(
                        violation_type=ViolationType.GROUNDEDNESS_FAILURE,
                        severity=ViolationSeverity.HIGH,
                        message=(
                            f"Criterion {cid} is {status} but has no evidence citations. "
                            "All determinations require citation of source evidence."
                        ),
                        criterion_id=cid,
                        details={"status": status, "citations_count": len(citations)},
                    ))
                else:
                    grounded_count += 1

                # Rationale must be explanatory
                if len(rationale.strip()) < MIN_RATIONALE_CHARS:
                    violations.append(GuardrailViolation(
                        violation_type=ViolationType.INCOMPLETE_ATTRIBUTION,
                        severity=ViolationSeverity.MEDIUM,
                        message=f"Criterion {cid} rationale is too brief ({len(rationale)} chars)",
                        criterion_id=cid,
                    ))

            elif status == "UNDETERMINED":
                # UNDETERMINED must explain what is missing
                has_explanation = (
                    len(rationale.strip()) >= MIN_RATIONALE_CHARS
                    or bool(missing_info)
                )
                if not has_explanation:
                    violations.append(GuardrailViolation(
                        violation_type=ViolationType.INCOMPLETE_ATTRIBUTION,
                        severity=ViolationSeverity.MEDIUM,
                        message=(
                            f"Criterion {cid} is UNDETERMINED but provides no explanation "
                            "of what information is missing."
                        ),
                        criterion_id=cid,
                    ))

        # Check overall rationale
        overall_rationale = parsed.get("overall_rationale", "")
        if len(overall_rationale.strip()) < MIN_RATIONALE_CHARS:
            violations.append(GuardrailViolation(
                violation_type=ViolationType.INCOMPLETE_ATTRIBUTION,
                severity=ViolationSeverity.MEDIUM,
                message="overall_rationale is absent or too brief",
            ))

        # Compute groundedness score
        if determined_count > 0:
            score = grounded_count / determined_count
            if score < self._threshold:
                logger.warning(
                    "guardrail.groundedness_low",
                    case_id=ctx.case_id,
                    score=round(score, 3),
                    grounded=grounded_count,
                    determined=determined_count,
                )
                # Add a summary violation if below threshold
                violations.append(GuardrailViolation(
                    violation_type=ViolationType.GROUNDEDNESS_FAILURE,
                    severity=ViolationSeverity.HIGH,
                    message=(
                        f"Groundedness score {score:.0%} is below threshold {self._threshold:.0%}. "
                        f"Only {grounded_count}/{determined_count} determined criteria have citations."
                    ),
                    details={"groundedness_score": score},
                ))

        has_blocking = any(
            v.severity in (ViolationSeverity.HIGH, ViolationSeverity.CRITICAL)
            for v in violations
        )
        return GuardrailResult(passed=not has_blocking, violations=violations)
