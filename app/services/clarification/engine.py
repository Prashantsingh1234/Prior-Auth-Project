"""
ClarificationEngine — main orchestrator for the clarification loop.

Called by the ClarificationNode after reasoning identifies UNDETERMINED
criteria.  Decides whether to:
  - Generate and send a new clarification question
  - Validate a received response and update state
  - Escalate to human review

Workflow integration points:
  - reasoning_node creates a bare ClarificationAttempt(PENDING) with
    missing_criteria populated; the engine enriches the question via LLM.
  - clarification_node calls engine.process_pending() on interrupt entry
    to potentially upgrade the question text before persisting.
  - clarification_node calls engine.process_response() when an answer arrives
    to validate quality and decide next action.
  - engine.decide_escalation() is called at the end of each cycle when the
    attempt limit is reached or responses are consistently insufficient.
"""

from __future__ import annotations

import time
from typing import Any

import structlog

from app.services.clarification.detector import MissingInfoDetector
from app.services.clarification.escalation import ClarificationEscalationEngine
from app.services.clarification.generator import ClarificationQuestionGenerator
from app.services.clarification.models import (
    ClarificationEscalationDecision,
    ClarificationRequest,
    ClarificationResponse,
    EscalationReason,
    MissingInfoAnalysis,
    NotificationEvent,
    NotificationPayload,
    ResponseQualityLevel,
)
from app.services.clarification.notifier import ReviewerNotifier
from app.services.clarification.state_manager import ClarificationStateManager

logger = structlog.get_logger(__name__)

# Maximum clarification rounds before mandatory escalation
MAX_CLARIFICATION_ATTEMPTS = 3

# Minimum quality score to consider a response sufficient
MIN_QUALITY_SCORE = 0.40


class ClarificationEngine:
    """
    Orchestrates the full clarification lifecycle for one PA case.
    """

    def __init__(
        self,
        detector: MissingInfoDetector,
        generator: ClarificationQuestionGenerator,
        state_manager: ClarificationStateManager,
        escalation_engine: ClarificationEscalationEngine,
        notifier: ReviewerNotifier,
    ) -> None:
        self._detector = detector
        self._generator = generator
        self._state_manager = state_manager
        self._escalation_engine = escalation_engine
        self._notifier = notifier
        self._log = structlog.get_logger(self.__class__.__name__)

    # ------------------------------------------------------------------
    # Entry points
    # ------------------------------------------------------------------

    async def prepare_question(
        self,
        *,
        state: dict,           # PAWorkflowState
        case_id: str,
        service_type: str,
        clinical_summary: str,
    ) -> ClarificationRequest | None:
        """
        Analyse evaluation gaps and generate an enriched clarification question.

        Called by reasoning_node (or clarification_node on first entry) to
        produce the best possible question before interrupting the graph.

        Returns None if no actionable gaps are found or the attempt limit
        has been reached.
        """
        t0 = time.monotonic()

        clarification_attempts = state.get("clarification_attempts", [])
        attempt_count = len(clarification_attempts)

        if attempt_count >= MAX_CLARIFICATION_ATTEMPTS:
            self._log.info(
                "clarification.engine.max_attempts_reached",
                case_id=case_id,
                attempt_count=attempt_count,
            )
            return None

        evaluation_results = state.get("evaluation_results", {})
        if not evaluation_results:
            self._log.warning(
                "clarification.engine.no_evaluation_results",
                case_id=case_id,
            )
            return None

        analysis = self._detector.detect(
            case_id=case_id,
            evaluation_results=evaluation_results,
            clarification_attempts=clarification_attempts,
        )

        if not analysis.actionable_items:
            self._log.info(
                "clarification.engine.no_actionable_items",
                case_id=case_id,
                total_items=len(analysis.items),
            )
            return None

        request = await self._generator.generate(
            analysis=analysis,
            case_id=case_id,
            service_type=service_type,
            clinical_summary=clinical_summary,
        )

        elapsed_ms = (time.monotonic() - t0) * 1000
        self._log.info(
            "clarification.engine.question_prepared",
            case_id=case_id,
            question_preview=request.question[:80],
            generated_by=request.generated_by,
            priority=request.priority.value,
            latency_ms=round(elapsed_ms, 1),
        )
        self._track_question_metric(case_id, request)
        return request

    async def process_response(
        self,
        *,
        state: dict,           # PAWorkflowState
        case_id: str,
        attempt_id: str,
        response_text: str,
        responded_by: str = "provider",
    ) -> tuple[ClarificationResponse, dict[str, Any]]:
        """
        Validate a received provider response and build a state patch.

        Returns:
            (ClarificationResponse, state_patch)
            The caller merges state_patch into the workflow state.
        """
        attempts = state.get("clarification_attempts", [])
        matched = next((a for a in attempts if a.attempt_id == attempt_id), None)

        if matched is None:
            self._log.error(
                "clarification.engine.attempt_not_found",
                case_id=case_id,
                attempt_id=attempt_id,
            )
            clarification_response = ClarificationResponse(
                attempt_id=attempt_id,
                response_text=response_text,
                responded_by=responded_by,
                response_quality=ResponseQualityLevel.INSUFFICIENT,
                quality_score=0.0,
                addresses_question=False,
            )
            return clarification_response, {}

        clarification_response = await self._state_manager.validate_response(
            case_id=case_id,
            attempt=matched,
            response_text=response_text,
            responded_by=responded_by,
        )

        state_patch = self._state_manager.build_answered_patch(
            attempt=matched,
            response_text=response_text,
            responded_by=responded_by,
            quality=clarification_response.response_quality,
        )

        self._log.info(
            "clarification.engine.response_processed",
            case_id=case_id,
            attempt_id=attempt_id,
            quality=clarification_response.response_quality.value,
            score=clarification_response.quality_score,
        )

        await self._notifier.notify(NotificationPayload(
            event=NotificationEvent.CLARIFICATION_ANSWERED,
            case_id=case_id,
            attempt_id=attempt_id,
            attempt_number=matched.attempt_number,
            question=matched.question,
            response=response_text,
        ))
        self._track_response_metric(clarification_response)
        return clarification_response, state_patch

    async def decide_escalation(
        self,
        *,
        state: dict,
        case_id: str,
        service_type: str,
        clinical_summary: str,
    ) -> ClarificationEscalationDecision:
        """
        Decide whether the clarification loop should escalate to human review.

        Called when:
          - Max attempts reached
          - Response quality is persistently insufficient
          - A timeout occurs
        """
        attempts = state.get("clarification_attempts", [])
        evaluation_results = state.get("evaluation_results", {})

        analysis: MissingInfoAnalysis | None = None
        if evaluation_results:
            analysis = self._detector.detect(
                case_id=case_id,
                evaluation_results=evaluation_results,
                clarification_attempts=attempts,
            )

        decision = self._escalation_engine.evaluate(
            case_id=case_id,
            attempts=attempts,
            analysis=analysis,
        )

        if decision.is_escalate:
            self._log.warning(
                "clarification.engine.escalating",
                case_id=case_id,
                reason=decision.reason.value if decision.reason else "unknown",
                message=decision.message,
            )
            if decision.notify_reviewer:
                await self._notifier.notify(NotificationPayload(
                    event=NotificationEvent.ESCALATED_TO_REVIEWER,
                    case_id=case_id,
                    attempt_number=len(attempts),
                    reason=decision.reason.value if decision.reason else None,
                    metadata=decision.context,
                ))

        return decision

    async def handle_timeout(
        self,
        *,
        case_id: str,
        attempt_id: str,
        attempt_number: int,
        question: str,
    ) -> dict[str, Any]:
        """
        Mark an attempt as timed out and notify.

        Returns a state patch to be merged by the caller.
        """
        self._log.warning(
            "clarification.engine.timeout",
            case_id=case_id,
            attempt_id=attempt_id,
        )
        await self._notifier.notify(NotificationPayload(
            event=NotificationEvent.CLARIFICATION_TIMEOUT,
            case_id=case_id,
            attempt_id=attempt_id,
            attempt_number=attempt_number,
            question=question,
        ))
        return self._state_manager.build_timeout_patch(attempt_id=attempt_id)

    # ------------------------------------------------------------------
    # Metrics helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _track_question_metric(case_id: str, request: ClarificationRequest) -> None:
        try:
            from app.monitoring.metrics import CLARIFICATION_QUESTION_GENERATED_TOTAL
            CLARIFICATION_QUESTION_GENERATED_TOTAL.labels(
                generated_by=request.generated_by,
                category=request.question_category,
            ).inc()
        except Exception:
            pass

    @staticmethod
    def _track_response_metric(response: ClarificationResponse) -> None:
        try:
            from app.monitoring.metrics import CLARIFICATION_RESPONSE_QUALITY_TOTAL
            CLARIFICATION_RESPONSE_QUALITY_TOTAL.labels(
                quality=response.response_quality.value,
            ).inc()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_settings(cls) -> "ClarificationEngine":
        """Build the full engine from application settings."""
        detector = MissingInfoDetector()
        generator = ClarificationQuestionGenerator.from_settings()
        state_manager = ClarificationStateManager.from_settings()
        escalation_engine = ClarificationEscalationEngine()
        notifier = ReviewerNotifier.from_settings()
        return cls(
            detector=detector,
            generator=generator,
            state_manager=state_manager,
            escalation_engine=escalation_engine,
            notifier=notifier,
        )


# Module-level singleton (lazy-initialised on first access)
_engine_instance: ClarificationEngine | None = None


def get_clarification_engine() -> ClarificationEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = ClarificationEngine.from_settings()
    return _engine_instance
