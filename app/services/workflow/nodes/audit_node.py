"""
Audit node — final stage of every PA workflow execution.

Responsibilities:
  - Emit the WORKFLOW_COMPLETED (or WORKFLOW_FAILED) audit event
  - Update AuditMetadata totals (total_tokens_used, total_processing_ms,
    node_timings) so the audit record is self-contained
  - Optionally persist the audit log to the database (non-blocking — failure
    does not stop the workflow from completing)
  - Transition workflow phase to COMPLETED or FAILED

This node is ALWAYS the last to run, whether the workflow succeeded or
failed, so it can be relied upon to produce a consistent terminal state.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any

import structlog

from app.services.workflow.nodes.base import BaseNode, NodeContext
from app.services.workflow.state.models import (
    AuditEventType,
    AuditMetadata,
    WorkflowPhase,
)
from app.services.workflow.state.schema import PAWorkflowState, state_summary

logger = structlog.get_logger(__name__)


class AuditNode(BaseNode):
    """
    Terminal node — finalises the audit trail and transitions to COMPLETED.

    Always runs, even on error paths.
    """

    node_name = "audit_node"

    async def execute(
        self, state: PAWorkflowState, nctx: NodeContext
    ) -> dict[str, Any]:
        ctx = nctx.audit_ctx
        t0  = time.monotonic()

        is_failed     = state.get("workflow_phase") == WorkflowPhase.FAILED
        event_type    = AuditEventType.WORKFLOW_FAILED if is_failed else AuditEventType.WORKFLOW_COMPLETED
        final_phase   = WorkflowPhase.FAILED if is_failed else WorkflowPhase.COMPLETED
        recommendation = state.get("recommendation")
        total_tokens  = state.get("tokens_used", 0)
        total_ms      = state.get("processing_ms", 0.0)

        nctx.log.info(
            "audit_node.finalising",
            is_failed=is_failed,
            recommendation=recommendation.recommendation_type.value if recommendation else None,
            total_tokens=total_tokens,
            total_ms=round(total_ms, 1),
        )

        # Rebuild AuditMetadata with final totals
        existing_meta: AuditMetadata = state.get("audit_metadata") or AuditMetadata()
        updated_meta = existing_meta.model_copy(update={
            "total_tokens_used":   total_tokens,
            "total_processing_ms": total_ms,
            "updated_at":          datetime.utcnow(),
        })

        elapsed_ms = (time.monotonic() - t0) * 1000
        summary    = state_summary(state)

        # Attempt to persist audit log (non-blocking)
        await self._persist_audit(state, updated_meta, nctx)

        # Emit metrics
        self._emit_metrics(state, recommendation, total_tokens, total_ms)

        nctx.log.info(
            "audit_node.complete",
            summary=summary,
            elapsed_ms=round(elapsed_ms, 1),
        )

        return {
            "workflow_phase":  final_phase,
            "audit_metadata":  updated_meta,
            "processing_ms":   elapsed_ms,
            **ctx.event(
                event_type,
                data={
                    "case_id":               state.get("case_id"),
                    "recommendation_type":   recommendation.recommendation_type.value
                                             if recommendation else None,
                    "confidence_score":      recommendation.confidence_score
                                             if recommendation else 0.0,
                    "total_tokens_used":     total_tokens,
                    "total_processing_ms":   round(total_ms, 1),
                    "documents":             summary["documents"],
                    "policies_retrieved":    summary["policies_retrieved"],
                    "criteria_evaluated":    summary["criteria_evaluated"],
                    "clarification_rounds":  summary["clarifications"],
                    "reviewer_actions":      summary["reviewer_actions"],
                    "audit_events_total":    summary["audit_events"],
                    "error":                 state.get("error"),
                },
                duration_ms=elapsed_ms,
            ),
        }

    async def _persist_audit(
        self,
        state: PAWorkflowState,
        meta: AuditMetadata,
        nctx: NodeContext,
    ) -> None:
        """
        Persist the audit trail to the database.

        Failure here is logged but does NOT raise — the workflow must
        complete successfully even if persistence fails.
        """
        try:
            # Future: persist to pa_audit_logs table via repository
            # from app.db.repositories.audit_repository import AuditRepository
            # await repo.save(state["case_id"], state.get("audit_events", []), meta)
            pass
        except Exception as exc:
            nctx.log.error("audit_node.persist_failed", error=str(exc))

    @staticmethod
    def _emit_metrics(state, recommendation, total_tokens: int, total_ms: float) -> None:
        """Emit Prometheus metrics for the completed workflow."""
        try:
            from app.monitoring.metrics import LLM_TOKENS_TOTAL, LLM_LATENCY_SECONDS
            LLM_TOKENS_TOTAL.labels(
                operation="workflow", token_type="total"
            ).inc(total_tokens)
            LLM_LATENCY_SECONDS.labels(
                operation="workflow"
            ).observe(total_ms / 1000)

            if recommendation:
                from app.monitoring.metrics import PA_RECOMMENDATIONS_TOTAL
                PA_RECOMMENDATIONS_TOTAL.labels(
                    recommendation_type=recommendation.recommendation_type.value
                ).inc()
        except Exception:
            pass


# Module-level callable
audit_node = AuditNode()
