"""
Human review node — human-in-the-loop approval checkpoint.

Interrupt pattern:

  1. After reasoning (or clarification), execution arrives here.
  2. The node checks state for reviewer_actions.
  3. If no reviewer action yet → raises NodeInterrupt with the full AI assessment
     as the interrupt payload.  LangGraph checkpoints and pauses.
  4. External system (reviewer dashboard / API) calls:
         runner.resume_review(case_id, reviewer_action)
     which calls graph.update_state() to append the ReviewerAction.
  5. Graph resumes — this node is re-called, sees the new reviewer action,
     and returns normally so routing can proceed to decision_node.

The interrupt payload includes the AI recommendation + evaluation summary
so the reviewer UI can present everything needed to make a decision.
"""

from __future__ import annotations

import time
from typing import Any

import structlog

from app.services.workflow.nodes.base import BaseNode, NodeContext, NodeInterrupt
from app.services.workflow.state.models import (
    AuditEventType,
    WorkflowPhase,
)
from app.services.workflow.state.schema import PAWorkflowState

logger = structlog.get_logger(__name__)


class HumanReviewNode(BaseNode):
    """
    Wait for a human reviewer to act on the AI recommendation.

    Raises NodeInterrupt on first entry.
    Returns normally once a ReviewerAction is present in state.
    """

    node_name = "human_review_node"

    async def execute(
        self, state: PAWorkflowState, nctx: NodeContext
    ) -> dict[str, Any]:
        ctx = nctx.audit_ctx

        reviewer_actions = state.get("reviewer_actions", [])

        # Check for a NEW action added since last entry
        # (LangGraph may re-invoke the node after update_state; we use the action
        # appended there as the signal that the reviewer has decided.)
        if reviewer_actions:
            latest = reviewer_actions[-1]
            nctx.log.info(
                "human_review_node.action_received",
                reviewer_id=latest.reviewer_id,
                action_type=latest.action_type.value,
                is_override=latest.is_override,
            )
            elapsed_ms = nctx.elapsed_ms()
            return {
                "workflow_phase": WorkflowPhase.COMPLETED,  # routing will refine this
                "processing_ms":  elapsed_ms,
                **ctx.event(
                    AuditEventType.REVIEWER_ACTION,
                    data={
                        "action_id":     latest.action_id,
                        "reviewer_id":   latest.reviewer_id,
                        "action_type":   latest.action_type.value,
                        "is_override":   latest.is_override,
                        "override_reason": latest.override_reason,
                    },
                    duration_ms=elapsed_ms,
                ),
            }

        # No reviewer action yet — build the interrupt payload and pause
        recommendation = state.get("recommendation")
        evaluation_summary = self._build_evaluation_summary(state)

        interrupt_payload = {
            "type":    "human_review_required",
            "case_id": state.get("case_id"),
            "pa_request_id": state.get("pa_request_id"),
            "member_id":     state.get("member_id"),
            "service_type":  state.get("service_type"),
            "ai_recommendation": {
                "type":       recommendation.recommendation_type.value if recommendation else None,
                "confidence": recommendation.confidence_score if recommendation else 0.0,
                "rationale":  recommendation.rationale if recommendation else [],
                "requires_human_review": recommendation.requires_human_review if recommendation else True,
                "review_reason": recommendation.review_reason if recommendation else None,
            } if recommendation else None,
            "evaluation_summary": evaluation_summary,
            "clarification_attempts": len(state.get("clarification_attempts", [])),
        }

        nctx.log.info(
            "human_review_node.interrupting",
            case_id=state.get("case_id"),
            recommendation=interrupt_payload["ai_recommendation"],
        )
        raise NodeInterrupt(interrupt_payload)

    @staticmethod
    def _build_evaluation_summary(state: PAWorkflowState) -> list[dict]:
        """Compact summary of evaluation results for the reviewer UI."""
        summaries = []
        for key, result in state.get("evaluation_results", {}).items():
            summaries.append({
                "policy_id":        result.policy_id,
                "policy_version":   result.policy_version,
                "criteria_met":     result.criteria_met,
                "criteria_not_met": result.criteria_not_met,
                "criteria_undetermined": result.criteria_undetermined,
                "criteria_total":   result.criteria_total,
                "overall_score":    result.overall_score,
                "not_met_criteria": [
                    {"text": c.criterion_text[:120], "notes": c.notes}
                    for c in result.criteria_evaluations
                    if c.met.value == "no"
                ][:3],
            })
        return summaries


# Module-level callable
human_review_node = HumanReviewNode()
