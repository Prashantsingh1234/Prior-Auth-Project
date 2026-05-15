"""
Reviewer override handler.

Validates and applies reviewer overrides to an existing DecisionResult.

Override rules:
  - reviewer_id and override_reason are required
  - override_reason must be at least 20 characters (prevents blank justifications)
  - A reviewer cannot override a verdict to the same verdict (no-op guard)
  - REFER_MEDICAL_DIRECTOR can only be overridden by a senior reviewer flag
  - Override confidence is always ≤ 0.95 to signal human involvement

The handler is synchronous — callers do not await it.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

import structlog

from app.services.decision.confidence import ConfidenceBreakdown
from app.services.decision.models import (
    ConfidenceFlag,
    DecisionResult,
    DecisionRuleType,
    DecisionVerdict,
    OverrideDecision,
    OverrideRequest,
)
from app.services.decision.rationale import RationaleFormatter

logger = structlog.get_logger(__name__)

# Minimum characters for override_reason to be considered meaningful
_MIN_REASON_LENGTH = 20

# Confidence assigned to override decisions
_OVERRIDE_CONFIDENCE = 0.95

# Verdicts that require an additional "senior reviewer" flag to override
_PROTECTED_VERDICTS = frozenset({DecisionVerdict.REFER_MEDICAL_DIRECTOR})

# Map from target_verdict back to the human-facing label
_VERDICT_LABELS = {
    DecisionVerdict.APPROVE:               "APPROVE",
    DecisionVerdict.DENY:                  "DENY",
    DecisionVerdict.PEND_FOR_INFO:         "PEND FOR INFO",
    DecisionVerdict.REFER_MEDICAL_DIRECTOR: "REFER TO MEDICAL DIRECTOR",
}


class OverrideHandler:
    """
    Validates and applies reviewer overrides.

    Usage:
        handler = OverrideHandler()
        result = handler.apply(original_result, override_request)
        if result.override_applied:
            # use result.final_result
        else:
            # result.validation_errors explains why it was rejected
    """

    def __init__(self, allow_medical_director_override: bool = False) -> None:
        self._allow_md_override = allow_medical_director_override
        self._formatter = RationaleFormatter()

    def apply(
        self,
        original: DecisionResult,
        request: OverrideRequest,
    ) -> OverrideDecision:
        """
        Validate and apply an override to an existing DecisionResult.

        Returns an OverrideDecision with override_applied=False if
        validation fails (validation_errors will be non-empty).
        """
        errors = self._validate(original, request)
        if errors:
            logger.warning(
                "decision.override.rejected",
                reviewer_id=request.reviewer_id,
                errors=errors,
            )
            return OverrideDecision(
                original_result=original,
                override_request=request,
                final_result=original,
                override_applied=False,
                validation_errors=errors,
            )

        final = self._build_overridden_result(original, request)
        logger.info(
            "decision.override.applied",
            reviewer_id=request.reviewer_id,
            original_verdict=original.verdict.value,
            new_verdict=final.verdict.value,
            override_id=final.decision_id,
        )
        return OverrideDecision(
            original_result=original,
            override_request=request,
            final_result=final,
            override_applied=True,
            validation_errors=[],
        )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate(
        self,
        original: DecisionResult,
        request: OverrideRequest,
    ) -> list[str]:
        errors: list[str] = []

        if not request.reviewer_id or not request.reviewer_id.strip():
            errors.append("reviewer_id is required.")

        if not request.override_reason or len(request.override_reason.strip()) < _MIN_REASON_LENGTH:
            errors.append(
                f"override_reason must be at least {_MIN_REASON_LENGTH} characters "
                f"(got {len(request.override_reason or '')})."
            )

        if request.target_verdict == original.verdict:
            errors.append(
                f"Override target verdict ({request.target_verdict.value}) is the same "
                "as the current verdict — no change would be made."
            )

        if (
            original.verdict in _PROTECTED_VERDICTS
            and not self._allow_md_override
        ):
            errors.append(
                "Overriding a REFER_MEDICAL_DIRECTOR decision requires senior reviewer privileges."
            )

        return errors

    # ------------------------------------------------------------------
    # Result builder
    # ------------------------------------------------------------------

    def _build_overridden_result(
        self,
        original: DecisionResult,
        request: OverrideRequest,
    ) -> DecisionResult:
        """Build a new DecisionResult that applies the override."""
        from uuid import uuid4

        # Build override confidence breakdown — fixed score, record that override fired
        override_conf = ConfidenceBreakdown(
            final_score=_OVERRIDE_CONFIDENCE,
            criterion_confidence_avg=original.confidence.criterion_confidence_avg,
            coverage_score=original.confidence.coverage_score,
            evidence_quality_score=original.confidence.evidence_quality_score,
            extraction_confidence=original.confidence.extraction_confidence,
            penalties=0.0,
            bonuses=0.0,
            flags=[ConfidenceFlag.HIGH_CRITERION_AGREEMENT],  # Reviewer is explicit
            total_criteria=original.confidence.total_criteria,
            met_count=original.confidence.met_count,
            not_met_count=original.confidence.not_met_count,
            undetermined_count=original.confidence.undetermined_count,
            not_applicable_count=original.confidence.not_applicable_count,
            criteria_with_evidence=original.confidence.criteria_with_evidence,
        )

        # Generate override rationale
        rationale_lines, supporting, denying, evidence = self._formatter.format(
            verdict=request.target_verdict,
            rule_match=type("_R", (), {
                "rule_type": DecisionRuleType.OVERRIDE,
                "verdict": request.target_verdict,
                "triggered_by": f"Reviewer override by {request.reviewer_id}",
                "blocking_criteria": original.denying_criteria,
                "missing_criteria": [],
            })(),
            criterion_decisions=original.criterion_decisions,
            confidence=override_conf,
            override_request=request,
        )

        return DecisionResult(
            decision_id=str(uuid4()),
            verdict=request.target_verdict,
            rule_applied=DecisionRuleType.OVERRIDE,
            confidence=override_conf,
            criterion_decisions=original.criterion_decisions,
            rationale_lines=rationale_lines,
            supporting_criteria=supporting if supporting else original.supporting_criteria,
            denying_criteria=denying if denying else original.denying_criteria,
            evidence_references=original.evidence_references,
            requires_human_review=False,    # Reviewer has already acted
            review_reason=None,
            policies_evaluated=original.policies_evaluated,
            criteria_total=original.criteria_total,
            model_used=original.model_used,
            tokens_used=original.tokens_used,
            decided_at=datetime.now(UTC),
            is_override=True,
        )
