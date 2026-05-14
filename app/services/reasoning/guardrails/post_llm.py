"""
Post-LLM composite validator.

Runs all post-LLM guardrails in a defined order and aggregates results.
Guardrail execution order matters: schema must pass before others can run.

Pipeline order:
  1. SafetyChecker       — block PII / harmful content immediately (CRITICAL)
  2. SchemaValidator     — must pass for structured parsing (HIGH)
  3. HallucinationDetector — citation verification (HIGH if rate > threshold)
  4. GroundednessChecker  — attribution completeness (HIGH if below threshold)
  5. MedicalTerminologyValidator — code/value sanity (MEDIUM soft check)
  6. ConfidenceThresholdChecker  — enforce minimum confidence (MEDIUM/HIGH)

Short-circuit: if SafetyChecker or SchemaValidator fails with CRITICAL/HIGH,
subsequent checks are skipped to avoid running on invalid output.
"""

from __future__ import annotations

import json
import time
from typing import Any

import structlog

from app.services.reasoning.guardrails.base import GuardrailContext
from app.services.reasoning.guardrails.groundedness import GroundednessChecker
from app.services.reasoning.guardrails.hallucination import HallucinationDetector
from app.services.reasoning.guardrails.medical import MedicalTerminologyValidator
from app.services.reasoning.guardrails.safety import SafetyChecker
from app.services.reasoning.guardrails.schema import SchemaValidator
from app.services.reasoning.models import (
    GuardrailResult,
    GuardrailViolation,
    ViolationSeverity,
    ViolationType,
)

logger = structlog.get_logger(__name__)

# Minimum overall_confidence accepted without escalation
MIN_CONFIDENCE_THRESHOLD = 0.65

# Minimum reasoning_quality accepted
MIN_QUALITY_THRESHOLD = 0.50


class ConfidenceThresholdChecker:
    """Validates that confidence scores meet minimum thresholds."""

    name = "confidence_threshold_checker"

    def __init__(
        self,
        min_confidence: float = MIN_CONFIDENCE_THRESHOLD,
        min_quality: float = MIN_QUALITY_THRESHOLD,
    ) -> None:
        self._min_conf = min_confidence
        self._min_qual = min_quality

    async def check(self, ctx: GuardrailContext) -> GuardrailResult:
        parsed = ctx.parsed_output
        violations: list[GuardrailViolation] = []

        if not parsed:
            return GuardrailResult(passed=True, guardrail_name=self.name)

        overall_conf = float(parsed.get("overall_confidence", 1.0))
        if overall_conf < self._min_conf:
            severity = ViolationSeverity.HIGH if overall_conf < 0.40 else ViolationSeverity.MEDIUM
            violations.append(GuardrailViolation(
                violation_type=ViolationType.LOW_CONFIDENCE,
                severity=severity,
                message=(
                    f"overall_confidence {overall_conf:.2f} is below minimum {self._min_conf}. "
                    "Escalating to stronger model."
                ),
                details={"overall_confidence": overall_conf, "threshold": self._min_conf},
            ))

        quality = float(parsed.get("reasoning_quality", 1.0))
        if quality < self._min_qual:
            violations.append(GuardrailViolation(
                violation_type=ViolationType.LOW_CONFIDENCE,
                severity=ViolationSeverity.MEDIUM,
                message=f"reasoning_quality {quality:.2f} below minimum {self._min_qual}",
                details={"reasoning_quality": quality},
            ))

        # Count per-criterion low confidence
        evals = parsed.get("criterion_evaluations", [])
        low_conf_criteria = [
            e.get("criterion_id", "?")
            for e in evals
            if isinstance(e, dict) and float(e.get("confidence", 1.0)) < 0.50
        ]
        if len(low_conf_criteria) > len(evals) * 0.50 and evals:
            violations.append(GuardrailViolation(
                violation_type=ViolationType.LOW_CONFIDENCE,
                severity=ViolationSeverity.MEDIUM,
                message=(
                    f"More than half of criteria ({len(low_conf_criteria)}/{len(evals)}) "
                    "have confidence < 0.50"
                ),
                details={"low_confidence_criteria": low_conf_criteria[:10]},
            ))

        has_blocking = any(
            v.severity in (ViolationSeverity.HIGH, ViolationSeverity.CRITICAL)
            for v in violations
        )
        return GuardrailResult(
            passed=not has_blocking,
            violations=violations,
            guardrail_name=self.name,
        )


class PostLLMValidator:
    """
    Composite post-LLM validator.

    Runs all guardrails in order and aggregates violations.
    Returns a single GuardrailResult representing the combined outcome.
    """

    def __init__(
        self,
        min_confidence: float = MIN_CONFIDENCE_THRESHOLD,
        min_quality: float = MIN_QUALITY_THRESHOLD,
        hallucination_hard_threshold: float = 0.40,
        groundedness_threshold: float = 0.70,
    ) -> None:
        self._safety      = SafetyChecker()
        self._schema      = SchemaValidator()
        self._hallucinate = HallucinationDetector(hard_threshold=hallucination_hard_threshold)
        self._grounding   = GroundednessChecker(threshold=groundedness_threshold)
        self._medical     = MedicalTerminologyValidator()
        self._confidence  = ConfidenceThresholdChecker(min_confidence, min_quality)

    async def validate(
        self,
        raw_output: str,
        ctx: GuardrailContext,
    ) -> GuardrailResult:
        """
        Run the full post-LLM validation pipeline.

        Args:
            raw_output: Raw string from the LLM (before parsing).
            ctx:        Guardrail context with source documents etc.

        Returns:
            Aggregate GuardrailResult with all violations.
        """
        t0 = time.perf_counter()
        ctx.raw_output = raw_output

        all_violations: list[GuardrailViolation] = []
        passed = True

        # --- Stage 1: Safety (short-circuit on CRITICAL) ---
        safety_result = await self._safety.check(ctx)
        all_violations.extend(safety_result.violations)
        if safety_result.has_critical:
            logger.error("guardrail.critical_safety_failure", case_id=ctx.case_id)
            return self._aggregate(False, all_violations, t0)

        # --- Stage 2: Schema (short-circuit if output can't be parsed) ---
        # First try to parse the raw JSON
        parsed: dict[str, Any] | None = None
        try:
            parsed = json.loads(raw_output)
            ctx.parsed_output = parsed
        except (json.JSONDecodeError, ValueError):
            all_violations.append(GuardrailViolation(
                violation_type=ViolationType.SCHEMA_INVALID,
                severity=ViolationSeverity.HIGH,
                message="LLM output is not valid JSON — cannot proceed with further checks",
            ))
            return self._aggregate(False, all_violations, t0)

        schema_result = await self._schema.check(ctx)
        all_violations.extend(schema_result.violations)
        if not schema_result.passed:
            logger.warning("guardrail.schema_failure", case_id=ctx.case_id)
            # Schema failure = can't trust structure → skip remaining checks
            return self._aggregate(False, all_violations, t0)

        # --- Stage 3: Hallucination ---
        hallucination_result = await self._hallucinate.check(ctx)
        all_violations.extend(hallucination_result.violations)
        if not hallucination_result.passed:
            passed = False

        # --- Stage 4: Groundedness ---
        groundedness_result = await self._grounding.check(ctx)
        all_violations.extend(groundedness_result.violations)
        if not groundedness_result.passed:
            passed = False

        # --- Stage 5: Medical terminology (soft) ---
        medical_result = await self._medical.check(ctx)
        all_violations.extend(medical_result.violations)
        # Medical is soft — only block on HIGH/CRITICAL
        if medical_result.has_high or medical_result.has_critical:
            passed = False

        # --- Stage 6: Confidence thresholds ---
        confidence_result = await self._confidence.check(ctx)
        all_violations.extend(confidence_result.violations)
        if not confidence_result.passed:
            passed = False

        result = self._aggregate(passed, all_violations, t0, corrected_output=parsed)

        logger.info(
            "guardrail.post_validation_complete",
            case_id=ctx.case_id,
            passed=passed,
            violation_count=len(all_violations),
            latency_ms=round(result.latency_ms, 1),
        )
        self._track_metrics(ctx.case_id, result)
        return result

    def _aggregate(
        self,
        passed: bool,
        violations: list[GuardrailViolation],
        t0: float,
        corrected_output: dict | None = None,
    ) -> GuardrailResult:
        return GuardrailResult(
            passed=passed,
            violations=violations,
            corrected_output=corrected_output,
            guardrail_name="post_llm_validator",
            latency_ms=(time.perf_counter() - t0) * 1000,
        )

    def _track_metrics(self, case_id: str, result: GuardrailResult) -> None:
        try:
            from app.monitoring.metrics import (
                GUARDRAIL_VIOLATIONS_TOTAL,
                GUARDRAIL_PASS_RATE,
            )
            for v in result.violations:
                GUARDRAIL_VIOLATIONS_TOTAL.labels(
                    violation_type=v.violation_type.value,
                    severity=v.severity.value,
                ).inc()
            GUARDRAIL_PASS_RATE.labels(
                result="pass" if result.passed else "fail"
            ).inc()
        except Exception:
            pass
