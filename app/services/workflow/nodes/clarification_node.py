"""
Clarification node — conditional stage between reasoning and human review.

Interrupt pattern (LangGraph human-in-the-loop):

  1. reasoning_node stores a PENDING ClarificationAttempt in state and sets
     workflow_phase = CLARIFICATION.
  2. Routing sends execution here.
  3. This node calls ClarificationEngine.prepare_question() to enrich the
     question text via LLM, then raises NodeInterrupt which causes LangGraph to:
       a. Persist a checkpoint.
       b. Surface the interrupt payload to the caller (WorkflowRunner).
  4. The external system (provider portal / API endpoint) receives the
     clarification question, gets the answer from the provider, and calls:
         runner.resume_clarification(case_id, attempt_id, response_text)
     which calls graph.update_state() to inject the response.
  5. The graph resumes — this node is called again with the ANSWERED attempt
     visible in state → validates response quality → routes to RETRIEVAL so
     the retrieval + reasoning nodes re-run with the new information.
  6. If max attempts reached or responses are insufficient, escalates to
     HUMAN_REVIEW with escalation reason recorded in state.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

import structlog

from app.services.clarification import ClarificationEngine, get_clarification_engine
from app.services.workflow.nodes.base import BaseNode, NodeContext, NodeInterrupt
from app.services.workflow.state.models import (
    AuditEventType,
    ClarificationStatus,
    WorkflowPhase,
)
from app.services.workflow.state.schema import PAWorkflowState

logger = structlog.get_logger(__name__)


class ClarificationNode(BaseNode):
    """
    Human-in-the-loop clarification checkpoint.

    Uses the ClarificationEngine for:
      - LLM-enriched question generation
      - Response quality validation
      - Escalation decisions
      - Reviewer notifications
    """

    node_name = "clarification_node"

    def __init__(self) -> None:
        super().__init__()
        self._engine: ClarificationEngine | None = None

    def _get_engine(self) -> ClarificationEngine:
        if self._engine is None:
            self._engine = get_clarification_engine()
        return self._engine

    async def execute(
        self, state: PAWorkflowState, nctx: NodeContext
    ) -> dict[str, Any]:
        ctx = nctx.audit_ctx
        engine = self._get_engine()

        attempts = state.get("clarification_attempts", [])
        if not attempts:
            nctx.log.warning("clarification_node.no_attempts_found")
            return {"workflow_phase": WorkflowPhase.HUMAN_REVIEW}

        latest = attempts[-1]
        latest_status = latest.status.value if hasattr(latest.status, "value") else str(latest.status)
        case_id = state.get("case_id", "unknown")

        # ------------------------------------------------------------------
        # Case 1: Latest attempt was answered → validate and route back
        # ------------------------------------------------------------------
        if latest_status == ClarificationStatus.ANSWERED.value:
            return await self._handle_answered(
                state, nctx, ctx, engine, latest, case_id
            )

        # ------------------------------------------------------------------
        # Case 2: Latest attempt timed out → escalation check
        # ------------------------------------------------------------------
        if latest_status == ClarificationStatus.TIMEOUT.value:
            return await self._handle_timeout(state, nctx, ctx, engine, latest, case_id)

        # ------------------------------------------------------------------
        # Case 3: Latest attempt is PENDING → enrich question and interrupt
        # ------------------------------------------------------------------
        return await self._handle_pending(state, nctx, engine, latest, case_id)

    # ------------------------------------------------------------------
    # Branch handlers
    # ------------------------------------------------------------------

    async def _handle_answered(
        self, state, nctx: NodeContext, ctx, engine, latest, case_id: str
    ) -> dict[str, Any]:
        """Validate the response, decide whether to continue or escalate."""
        elapsed_ms = nctx.elapsed_ms()
        nctx.log.info(
            "clarification_node.answered",
            attempt_id=latest.attempt_id,
            responded_by=latest.responded_by,
            response_len=len(latest.response or ""),
        )

        service_type = state.get("service_type", "")
        clinical_summary = self._get_clinical_summary(state)

        # Check if escalation is warranted after this response
        decision = await engine.decide_escalation(
            state=state,
            case_id=case_id,
            service_type=service_type,
            clinical_summary=clinical_summary,
        )

        if decision.is_escalate:
            nctx.log.warning(
                "clarification_node.escalating_after_response",
                case_id=case_id,
                reason=decision.reason.value if decision.reason else "unknown",
            )
            patch: dict[str, Any] = {
                "workflow_phase":  WorkflowPhase.HUMAN_REVIEW,
                "requires_review": True,
                "processing_ms":   elapsed_ms,
                **ctx.event(
                    AuditEventType.CLARIFICATION_RECEIVED,
                    data={
                        "attempt_id":      latest.attempt_id,
                        "attempt_number":  latest.attempt_number,
                        "responded_by":    latest.responded_by,
                        "response_len":    len(latest.response or ""),
                        "escalated":       True,
                        "escalation_reason": decision.reason.value if decision.reason else "unknown",
                    },
                    duration_ms=elapsed_ms,
                ),
            }
            self._track_loop_metric("escalated")
            return patch

        # Route back to retrieval so reasoning re-runs with new info
        self._track_loop_metric("resolved")
        return {
            "workflow_phase": WorkflowPhase.RETRIEVAL,
            "processing_ms":  elapsed_ms,
            **ctx.event(
                AuditEventType.CLARIFICATION_RECEIVED,
                data={
                    "attempt_id":    latest.attempt_id,
                    "attempt_number": latest.attempt_number,
                    "responded_by":  latest.responded_by,
                    "response_len":  len(latest.response or ""),
                    "escalated":     False,
                },
                duration_ms=elapsed_ms,
            ),
        }

    async def _handle_timeout(
        self, state, nctx: NodeContext, ctx, engine, latest, case_id: str
    ) -> dict[str, Any]:
        """Handle a timed-out attempt — always escalates."""
        nctx.log.warning(
            "clarification_node.timed_out",
            attempt_id=latest.attempt_id,
        )
        timeout_patch = await engine.handle_timeout(
            case_id=case_id,
            attempt_id=latest.attempt_id,
            attempt_number=latest.attempt_number,
            question=latest.question,
        )
        self._track_loop_metric("escalated")
        return {
            "workflow_phase":  WorkflowPhase.HUMAN_REVIEW,
            "requires_review": True,
            **timeout_patch,
            **ctx.event(
                AuditEventType.CLARIFICATION_RECEIVED,
                data={
                    "attempt_id": latest.attempt_id,
                    "status":     "timeout",
                    "escalated":  True,
                },
            ),
        }

    async def _handle_pending(
        self, state, nctx: NodeContext, engine, latest, case_id: str
    ) -> dict[str, Any]:
        """Enrich the question via LLM (if needed) then interrupt."""
        service_type = state.get("service_type", "")
        clinical_summary = self._get_clinical_summary(state)

        # If the question text is the bare consolidated list from reasoning_node,
        # try to generate a better LLM-enriched question.
        enriched_question = latest.question
        if latest.generated_by if hasattr(latest, "generated_by") else True:
            try:
                request = await engine.prepare_question(
                    state=state,
                    case_id=case_id,
                    service_type=service_type,
                    clinical_summary=clinical_summary,
                )
                if request:
                    enriched_question = request.question
            except Exception as exc:
                nctx.log.warning(
                    "clarification_node.engine_prepare_failed",
                    case_id=case_id,
                    error=str(exc),
                )

        nctx.log.info(
            "clarification_node.interrupting",
            attempt_id=latest.attempt_id,
            attempt_number=latest.attempt_number,
        )
        self._track_interrupt_metric()

        raise NodeInterrupt({
            "type":              "clarification_required",
            "case_id":           case_id,
            "attempt_id":        latest.attempt_id,
            "attempt_number":    latest.attempt_number,
            "question":          enriched_question,
            "question_category": latest.question_category,
            "missing_criteria":  latest.missing_criteria,
            "asked_at":          latest.asked_at.isoformat()
                                 if hasattr(latest.asked_at, "isoformat")
                                 else str(latest.asked_at),
            "deadline":          latest.deadline.isoformat()
                                 if latest.deadline and hasattr(latest.deadline, "isoformat")
                                 else None,
        })

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_clinical_summary(state: PAWorkflowState) -> str:
        return state.get("clinical_summary", "") or ""

    @staticmethod
    def _track_loop_metric(outcome: str) -> None:
        try:
            from app.monitoring.metrics import CLARIFICATION_LOOPS_TOTAL
            CLARIFICATION_LOOPS_TOTAL.labels(outcome=outcome).inc()
        except Exception:
            pass

    @staticmethod
    def _track_interrupt_metric() -> None:
        try:
            from app.monitoring.metrics import WORKFLOW_INTERRUPTS_TOTAL
            WORKFLOW_INTERRUPTS_TOTAL.labels(interrupt_type="clarification_required").inc()
        except Exception:
            pass


# Module-level callable
clarification_node = ClarificationNode()
