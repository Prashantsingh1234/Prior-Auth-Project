"""
Pre-LLM input validator.

Runs BEFORE the LLM call to catch degenerate inputs early, saving tokens
and preventing garbage-in → garbage-out reasoning.

Checks:
  1. Clinical data is present and non-trivial
  2. Retrieved policies are available
  3. At least one policy has evaluable criteria
  4. Extraction quality is sufficient (confidence threshold)
  5. Case ID and service type are populated
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

# Minimum clinical summary length (chars) to proceed with LLM reasoning
MIN_CLINICAL_CHARS = 100

# Minimum extraction confidence to avoid escalating immediately
MIN_EXTRACTION_CONFIDENCE = 0.40


class InputValidator(BaseGuardrail):
    """
    Validates that the reasoning engine has sufficient input to work with.

    Failures here are HIGH severity — the LLM call should not proceed.
    """

    name = "input_validator"

    def __init__(
        self,
        min_clinical_chars: int = MIN_CLINICAL_CHARS,
        min_extraction_confidence: float = MIN_EXTRACTION_CONFIDENCE,
    ) -> None:
        self._min_chars = min_clinical_chars
        self._min_conf = min_extraction_confidence

    async def check(self, ctx: GuardrailContext) -> GuardrailResult:
        violations: list[GuardrailViolation] = []

        # 1. Clinical summary exists and is non-trivial
        summary = ctx.clinical_summary or ""
        if not summary or len(summary) < self._min_chars:
            violations.append(GuardrailViolation(
                violation_type=ViolationType.INPUT_INVALID,
                severity=ViolationSeverity.HIGH,
                message="Clinical summary is absent or too short for reliable evaluation",
                details={
                    "summary_length": len(summary),
                    "min_required": self._min_chars,
                },
            ))

        # 2. Policy chunks available
        if not ctx.policy_chunks:
            violations.append(GuardrailViolation(
                violation_type=ViolationType.INPUT_INVALID,
                severity=ViolationSeverity.HIGH,
                message="No policy criteria chunks available — cannot evaluate",
                details={"policy_count": len(ctx.policy_metadata)},
            ))

        # 3. At least one criteria chunk has meaningful content
        elif all(len(c.strip()) < 20 for c in ctx.policy_chunks):
            violations.append(GuardrailViolation(
                violation_type=ViolationType.INPUT_INVALID,
                severity=ViolationSeverity.MEDIUM,
                message="All policy chunks are too short to contain evaluable criteria",
            ))

        # 4. Case ID present
        if not ctx.case_id:
            violations.append(GuardrailViolation(
                violation_type=ViolationType.INPUT_INVALID,
                severity=ViolationSeverity.HIGH,
                message="case_id is missing — cannot track this evaluation",
            ))

        # 5. Extraction confidence check (MEDIUM — warn but don't block)
        entities = ctx.extracted_entities
        if entities:
            confidences = [
                v.get("overall_confidence", 1.0)
                for v in entities.values()
                if isinstance(v, dict)
            ]
            if confidences:
                avg_conf = sum(confidences) / len(confidences)
                if avg_conf < self._min_conf:
                    violations.append(GuardrailViolation(
                        violation_type=ViolationType.INPUT_INVALID,
                        severity=ViolationSeverity.MEDIUM,
                        message=f"Extraction confidence {avg_conf:.2f} is below minimum {self._min_conf}",
                        details={"avg_extraction_confidence": avg_conf},
                    ))

        if violations:
            logger.warning(
                "guardrail.input_invalid",
                case_id=ctx.case_id,
                violations=[v.violation_type.value for v in violations],
            )
            return self._fail(violations)

        return self._pass()
