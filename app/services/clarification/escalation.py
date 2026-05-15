"""
Clarification escalation engine.

Evaluates the current clarification state and decides whether the loop
should escalate to human review and why.

Escalation triggers (checked in priority order):
  1. Max attempts reached (MAX_CLARIFICATION_ATTEMPTS exhausted)
  2. Timeout on latest attempt
  3. Persistently insufficient responses (quality below threshold)
  4. Repeated same question (deduplication failed)
  5. Critical unresolved gaps (CRITICAL-priority items still open)
  6. Clinical complexity or policy ambiguity signals
"""

from __future__ import annotations

from typing import Any

import structlog

from app.services.clarification.models import (
    ClarificationEscalationDecision,
    EscalationReason,
    MissingInfoAnalysis,
    QuestionPriority,
    ResponseQualityLevel,
)

logger = structlog.get_logger(__name__)

# Maximum rounds before mandatory escalation
MAX_CLARIFICATION_ATTEMPTS = 3

# Minimum fraction of attempts with sufficient responses to avoid escalation
MIN_SUFFICIENT_RESPONSE_FRACTION = 0.50

# Quality threshold below which a response is considered insufficient
INSUFFICIENT_QUALITY_SCORE = 0.40


class ClarificationEscalationEngine:
    """
    Stateless escalation evaluator for the clarification loop.

    Called after each clarification cycle to decide whether to continue
    or route to human review.
    """

    def evaluate(
        self,
        *,
        case_id: str,
        attempts: list[Any],           # list[ClarificationAttempt]
        analysis: MissingInfoAnalysis | None,
    ) -> ClarificationEscalationDecision:
        """
        Evaluate whether escalation is warranted.

        Returns a ClarificationEscalationDecision.  If is_escalate=True the
        caller should route to HUMAN_REVIEW.
        """
        if not attempts:
            return ClarificationEscalationDecision(
                is_escalate=False,
                reason=None,
                message="No attempts made yet.",
            )

        # Rule 1: Max attempts reached
        if len(attempts) >= MAX_CLARIFICATION_ATTEMPTS:
            return self._escalate(
                reason=EscalationReason.MAX_ATTEMPTS_REACHED,
                message=(
                    f"Maximum clarification attempts ({MAX_CLARIFICATION_ATTEMPTS}) "
                    "reached without resolving outstanding criteria."
                ),
                context={
                    "attempt_count": len(attempts),
                    "max_attempts":  MAX_CLARIFICATION_ATTEMPTS,
                },
            )

        latest = attempts[-1]
        latest_status = getattr(latest.status, "value", str(latest.status))

        # Rule 2: Latest attempt timed out
        if latest_status == "timeout":
            return self._escalate(
                reason=EscalationReason.TIMEOUT,
                message="Provider did not respond within the required timeframe.",
                context={"attempt_id": latest.attempt_id},
            )

        # Rule 3: Persistently insufficient responses
        answered = [a for a in attempts if getattr(a.status, "value", str(a.status)) == "answered"]
        if len(answered) >= 2:
            insufficient_count = sum(
                1 for a in answered
                if self._is_insufficient(a)
            )
            if insufficient_count / len(answered) > (1 - MIN_SUFFICIENT_RESPONSE_FRACTION):
                return self._escalate(
                    reason=EscalationReason.INSUFFICIENT_RESPONSE,
                    message=(
                        f"{insufficient_count}/{len(answered)} responses were insufficient. "
                        "Unable to obtain adequate clinical information."
                    ),
                    context={"insufficient_count": insufficient_count},
                )

        # Rule 4: Repeated same question (duplicate detection)
        if self._repeated_same_question(attempts):
            return self._escalate(
                reason=EscalationReason.REPEATED_SAME_QUESTION,
                message="The same question has been sent multiple times without a new answer.",
                context={},
            )

        # Rule 5: Critical items remain unresolved after attempts
        if analysis and analysis.critical_count > 0:
            critical_still_open = sum(
                1 for item in analysis.prioritized_items
                if item.priority == QuestionPriority.CRITICAL and not item.already_asked
            )
            if critical_still_open > 0 and len(attempts) >= 2:
                return self._escalate(
                    reason=EscalationReason.CLINICAL_COMPLEXITY,
                    message=(
                        f"{critical_still_open} critical clinical gap(s) remain unresolved "
                        "after multiple clarification attempts. Human review required."
                    ),
                    context={"critical_open": critical_still_open},
                )

        return ClarificationEscalationDecision(
            is_escalate=False,
            reason=None,
            message="Clarification loop may continue.",
            notify_reviewer=False,
        )

    @staticmethod
    def _is_insufficient(attempt) -> bool:
        """Return True if the attempt's response quality was poor."""
        response = attempt.response or ""
        if len(response.strip()) < 15:
            return True
        # Very short responses that are likely non-answers
        non_answers = {"n/a", "na", "none", "unknown", "not applicable", "no"}
        if response.strip().lower() in non_answers:
            return True
        return False

    @staticmethod
    def _repeated_same_question(attempts: list[Any]) -> bool:
        """
        Return True if the two most recent attempts asked nearly the same question.
        """
        if len(attempts) < 2:
            return False
        import re
        def tokens(text: str) -> set[str]:
            return set(re.findall(r"\b\w+\b", text.lower()))

        q1 = tokens(attempts[-1].question or "")
        q2 = tokens(attempts[-2].question or "")
        if not q1 or not q2:
            return False
        overlap = len(q1 & q2) / len(q1 | q2)
        return overlap >= 0.75

    @staticmethod
    def _escalate(
        *,
        reason: EscalationReason,
        message: str,
        context: dict[str, Any],
    ) -> ClarificationEscalationDecision:
        logger.info(
            "clarification.escalation.triggered",
            reason=reason.value,
            message=message,
        )
        return ClarificationEscalationDecision(
            is_escalate=True,
            reason=reason,
            message=message,
            context=context,
            notify_reviewer=True,
        )
