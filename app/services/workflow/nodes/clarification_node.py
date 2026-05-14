"""
Clarification node — conditional stage between reasoning and human review.

Interrupt pattern (LangGraph human-in-the-loop):

  1. reasoning_node stores a PENDING ClarificationAttempt in state and sets
     workflow_phase = CLARIFICATION.
  2. Routing sends execution here.
  3. This node finds the PENDING attempt and raises NodeInterrupt, which
     causes LangGraph to:
       a. Persist a checkpoint.
       b. Surface the interrupt payload to the caller (WorkflowRunner).
  4. The external system (provider portal / API endpoint) receives the
     clarification question, gets the answer from the provider, and calls:
         runner.resume_clarification(case_id, attempt_id, response_text)
     which calls graph.update_state() to mark the attempt ANSWERED.
  5. The graph resumes — this node is called again with the ANSWERED attempt
     visible in state → it returns a phase transition to RETRIEVAL so the
     retrieval + reasoning nodes re-run with the new information.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any

import structlog

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

    Raises NodeInterrupt when a pending clarification is waiting for a
    response.  Routes to retrieval after the response is received.
    """

    node_name = "clarification_node"

    async def execute(
        self, state: PAWorkflowState, nctx: NodeContext
    ) -> dict[str, Any]:
        ctx = nctx.audit_ctx

        attempts = state.get("clarification_attempts", [])
        if not attempts:
            nctx.log.warning("clarification_node.no_attempts_found")
            return {"workflow_phase": WorkflowPhase.HUMAN_REVIEW}

        # Find the most recent attempt
        latest = attempts[-1]

        # Case 1: Latest attempt was answered → resume to retrieval
        if latest.status == ClarificationStatus.ANSWERED:
            nctx.log.info(
                "clarification_node.answered",
                attempt_id=latest.attempt_id,
                responded_by=latest.responded_by,
            )
            elapsed_ms = nctx.elapsed_ms()
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
                    },
                    duration_ms=elapsed_ms,
                ),
            }

        # Case 2: Latest attempt timed out → skip to human review
        if latest.status == ClarificationStatus.TIMEOUT:
            nctx.log.warning(
                "clarification_node.timed_out",
                attempt_id=latest.attempt_id,
            )
            return {
                "workflow_phase": WorkflowPhase.HUMAN_REVIEW,
                **ctx.event(
                    AuditEventType.CLARIFICATION_RECEIVED,
                    data={
                        "attempt_id": latest.attempt_id,
                        "status":     "timeout",
                    },
                ),
            }

        # Case 3: Latest attempt is PENDING → interrupt and wait
        nctx.log.info(
            "clarification_node.interrupting",
            attempt_id=latest.attempt_id,
            attempt_number=latest.attempt_number,
        )
        raise NodeInterrupt({
            "type":            "clarification_required",
            "case_id":         state.get("case_id"),
            "attempt_id":      latest.attempt_id,
            "attempt_number":  latest.attempt_number,
            "question":        latest.question,
            "question_category": latest.question_category,
            "missing_criteria": latest.missing_criteria,
            "asked_at":        latest.asked_at.isoformat(),
        })


# Module-level callable
clarification_node = ClarificationNode()
