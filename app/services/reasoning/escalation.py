"""
Escalation engine — tracks violations and decides when to upgrade model tier.

The escalation engine has two responsibilities:
  1. Per-attempt: given the guardrail violations from an attempt, decide
     whether to escalate to a stronger model (and which trigger applies).
  2. Per-case: if escalation counts exceed MAX_ESCALATIONS, trigger a
     human reviewer workflow instead of continuing to retry.

Escalation decision table:
  ┌──────────────────────────────────┬──────────────────────────────────┐
  │ Trigger                          │ Action                           │
  ├──────────────────────────────────┼──────────────────────────────────┤
  │ HALLUCINATION (HIGH rate)        │ Escalate + flag for human review │
  │ SCHEMA_FAILURE (HIGH)            │ Escalate (may be model bug)      │
  │ GROUNDEDNESS_WEAK (HIGH)         │ Escalate                         │
  │ LOW_CONFIDENCE (< 0.40)          │ Escalate                         │
  │ LOW_CONFIDENCE (0.40–0.65)       │ Escalate if MEDIUM, skip SMALL   │
  │ UNSAFE_OUTPUT (CRITICAL)         │ Block + human review             │
  │ PROVIDER_FAILURE / TIMEOUT       │ Escalate                         │
  │ REPEATED_VIOLATIONS (≥ N)        │ Human review                     │
  └──────────────────────────────────┴──────────────────────────────────┘
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

import structlog

from app.services.reasoning.models import (
    EscalationTrigger,
    GuardrailResult,
    GuardrailViolation,
    ModelTier,
    ViolationSeverity,
    ViolationType,
)

logger = structlog.get_logger(__name__)

# Maximum escalation attempts before forcing human review
MAX_ESCALATIONS = 3

# Violation accumulation threshold for automatic human escalation
MAX_CUMULATIVE_VIOLATIONS = 8


@dataclass
class EscalationDecision:
    """
    Result from the escalation engine for one attempt.

    is_escalate: True → retry with a stronger model
    human_review: True → send to human reviewer (do not retry with LLM)
    next_tier: The model tier to escalate to (None if no escalation)
    trigger: What triggered the decision
    reason: Human-readable explanation
    """
    is_escalate:    bool
    human_review:   bool
    next_tier:      ModelTier | None
    trigger:        EscalationTrigger | None
    reason:         str


@dataclass
class EscalationRecord:
    """History entry for one escalation event."""
    attempt_number:   int
    from_tier:        ModelTier
    to_tier:          ModelTier | None
    trigger:          EscalationTrigger
    timestamp:        datetime = field(default_factory=lambda: datetime.now(UTC))
    violations:       list[str] = field(default_factory=list)


class EscalationEngine:
    """
    Determines whether to escalate to a stronger model or trigger human review.

    Thread-safe for concurrent cases because all state is passed in, not stored.
    """

    def __init__(
        self,
        max_escalations: int = MAX_ESCALATIONS,
        max_cumulative_violations: int = MAX_CUMULATIVE_VIOLATIONS,
    ) -> None:
        self._max_esc = max_escalations
        self._max_violations = max_cumulative_violations

    def evaluate(
        self,
        current_tier: ModelTier,
        guardrail_result: GuardrailResult,
        escalation_history: list[EscalationRecord],
        *,
        case_id: str,
    ) -> EscalationDecision:
        """
        Evaluate whether to escalate based on the latest guardrail result.

        Args:
            current_tier:       The tier that just ran.
            guardrail_result:   Result from PostLLMValidator for this attempt.
            escalation_history: All escalation events for this case so far.
            case_id:            For logging.

        Returns:
            EscalationDecision with action and rationale.
        """
        violations = guardrail_result.violations

        # 1. Critical violations → immediate human review
        if guardrail_result.has_critical:
            trigger = EscalationTrigger.UNSAFE_OUTPUT
            logger.error(
                "escalation.critical_human_review",
                case_id=case_id,
                tier=current_tier.value,
            )
            return EscalationDecision(
                is_escalate=False,
                human_review=True,
                next_tier=None,
                trigger=trigger,
                reason="Critical safety violation detected — routing to human reviewer",
            )

        # 2. Too many escalations already → human review
        if len(escalation_history) >= self._max_esc:
            all_violation_types = [
                v for record in escalation_history for v in record.violations
            ]
            total = len(all_violation_types)
            if total >= self._max_violations or len(escalation_history) >= self._max_esc:
                logger.warning(
                    "escalation.max_escalations_human_review",
                    case_id=case_id,
                    escalations=len(escalation_history),
                )
                return EscalationDecision(
                    is_escalate=False,
                    human_review=True,
                    next_tier=None,
                    trigger=EscalationTrigger.REPEATED_VIOLATIONS,
                    reason=(
                        f"Maximum escalations ({self._max_esc}) reached after "
                        f"{total} cumulative violations — routing to human reviewer"
                    ),
                )

        # 3. Already at LARGE → human review if still failing
        if current_tier == ModelTier.LARGE and not guardrail_result.passed:
            logger.warning("escalation.large_model_failed", case_id=case_id)
            return EscalationDecision(
                is_escalate=False,
                human_review=True,
                next_tier=None,
                trigger=EscalationTrigger.REPEATED_VIOLATIONS,
                reason="LARGE model failed guardrails — escalating to human reviewer",
            )

        # 4. No HIGH violations → no escalation needed
        if not guardrail_result.has_high:
            return EscalationDecision(
                is_escalate=False,
                human_review=False,
                next_tier=None,
                trigger=None,
                reason="All guardrails passed",
            )

        # 5. Determine escalation trigger from violation types
        trigger, reason = self._pick_trigger(violations, current_tier)
        next_tier = self._next_tier(current_tier)

        logger.info(
            "escalation.escalating",
            case_id=case_id,
            from_tier=current_tier.value,
            to_tier=next_tier.value if next_tier else "human",
            trigger=trigger.value if trigger else "unknown",
        )

        return EscalationDecision(
            is_escalate=True,
            human_review=False,
            next_tier=next_tier,
            trigger=trigger,
            reason=reason,
        )

    def _pick_trigger(
        self,
        violations: list[GuardrailViolation],
        current_tier: ModelTier,
    ) -> tuple[EscalationTrigger, str]:
        """Pick the most significant escalation trigger from violations."""
        type_priority = [
            (ViolationType.HALLUCINATION,        EscalationTrigger.HALLUCINATION_DETECTED),
            (ViolationType.UNSAFE_CONTENT,       EscalationTrigger.UNSAFE_OUTPUT),
            (ViolationType.SCHEMA_INVALID,       EscalationTrigger.SCHEMA_FAILURE),
            (ViolationType.GROUNDEDNESS_FAILURE, EscalationTrigger.GROUNDEDNESS_WEAK),
            (ViolationType.EVIDENCE_MISSING,     EscalationTrigger.EVIDENCE_MISSING),
            (ViolationType.LOW_CONFIDENCE,       EscalationTrigger.LOW_CONFIDENCE),
            (ViolationType.TRUNCATED_OUTPUT,     EscalationTrigger.SCHEMA_FAILURE),
            (ViolationType.PROVIDER_ERROR,       EscalationTrigger.PROVIDER_FAILURE),
            (ViolationType.TIMEOUT,              EscalationTrigger.TIMEOUT),
        ]
        violation_types = {v.violation_type for v in violations}
        for vtype, trigger in type_priority:
            if vtype in violation_types:
                msgs = [v.message for v in violations if v.violation_type == vtype]
                return trigger, msgs[0] if msgs else trigger.value

        return EscalationTrigger.REPEATED_VIOLATIONS, "Multiple guardrail violations"

    @staticmethod
    def _next_tier(current: ModelTier) -> ModelTier:
        """Return the next tier up."""
        if current == ModelTier.SMALL:
            return ModelTier.MEDIUM
        return ModelTier.LARGE

    def record_escalation(
        self,
        history: list[EscalationRecord],
        *,
        attempt_number: int,
        from_tier: ModelTier,
        to_tier: ModelTier | None,
        trigger: EscalationTrigger,
        violations: list[GuardrailViolation],
    ) -> None:
        """Append an escalation record to the mutable history list."""
        history.append(EscalationRecord(
            attempt_number=attempt_number,
            from_tier=from_tier,
            to_tier=to_tier,
            trigger=trigger,
            violations=[v.violation_type.value for v in violations],
        ))
        self._track_escalation_metric(trigger, from_tier)

    def _track_escalation_metric(
        self, trigger: EscalationTrigger, tier: ModelTier
    ) -> None:
        try:
            from app.monitoring.metrics import REASONING_ESCALATIONS_TOTAL
            REASONING_ESCALATIONS_TOTAL.labels(
                trigger=trigger.value,
                from_tier=tier.value,
            ).inc()
        except Exception:
            pass
