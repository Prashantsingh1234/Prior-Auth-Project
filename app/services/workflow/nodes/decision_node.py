"""
Decision node — Stage 7: convert the reviewer's action into the final
PARecommendation and mark the case ready for audit.

Logic:
  - If the reviewer APPROVED or OVERRIDE_APPROVED  → RecommendationType.APPROVE
  - If the reviewer DENIED or OVERRIDE_DENIED      → RecommendationType.DENY
  - If the reviewer PENDED                          → RecommendationType.PEND_FOR_INFO
  - If the reviewer ESCALATED                       → RecommendationType.REFER_MEDICAL_DIRECTOR
  - REQUEST_CLARIFICATION / RETURN_FOR_REWORK are handled in routing, not here;
    if somehow they arrive here, the preliminary AI recommendation is used.

The final PARecommendation records:
  - recommendation_type  (from reviewer action)
  - confidence_score     (1.0 for explicit approvals/denials; lower for overrides)
  - rationale            (reviewer notes + AI rationale merged)
  - requires_human_review = False  (human has already acted)
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any

import structlog

from app.services.workflow.nodes.base import BaseNode, NodeContext
from app.services.workflow.state.models import (
    AuditEventType,
    PARecommendation,
    RecommendationType,
    ReviewerActionType,
    WorkflowPhase,
)
from app.services.workflow.state.schema import PAWorkflowState

logger = structlog.get_logger(__name__)

# Map reviewer action types to recommendation types
_ACTION_TO_REC: dict[ReviewerActionType, RecommendationType] = {
    ReviewerActionType.APPROVE:          RecommendationType.APPROVE,
    ReviewerActionType.DENY:             RecommendationType.DENY,
    ReviewerActionType.PEND:             RecommendationType.PEND_FOR_INFO,
    ReviewerActionType.OVERRIDE_APPROVE: RecommendationType.APPROVE,
    ReviewerActionType.OVERRIDE_DENY:    RecommendationType.DENY,
    ReviewerActionType.ESCALATE:         RecommendationType.REFER_MEDICAL_DIRECTOR,
}


class DecisionNode(BaseNode):
    """
    Record the final PA decision based on the reviewer's action.

    Assembles the final PARecommendation, merges reviewer notes with the AI
    rationale, and transitions the workflow to COMPLETED.
    """

    node_name = "decision_node"

    async def execute(
        self, state: PAWorkflowState, nctx: NodeContext
    ) -> dict[str, Any]:
        ctx = nctx.audit_ctx
        t0  = time.monotonic()

        reviewer_actions = state.get("reviewer_actions", [])
        ai_recommendation = state.get("recommendation")

        if reviewer_actions:
            final_rec = self._build_from_reviewer_action(
                reviewer_actions[-1],
                ai_recommendation,
                state,
            )
        elif ai_recommendation:
            # No reviewer action — use AI recommendation as-is (auto-approve path)
            final_rec = ai_recommendation.model_copy(update={
                "requires_human_review": False,
                "review_reason": None,
            })
        else:
            # No recommendation at all — deny with explanation
            final_rec = PARecommendation(
                recommendation_type=RecommendationType.PEND_FOR_INFO,
                confidence_score=0.0,
                rationale=["Insufficient information to make a determination."],
                requires_human_review=False,
            )

        elapsed_ms = (time.monotonic() - t0) * 1000

        nctx.log.info(
            "decision_node.decided",
            recommendation=final_rec.recommendation_type.value,
            confidence=final_rec.confidence_score,
        )

        return {
            "recommendation":  final_rec,
            "rationale":       final_rec.rationale,
            "workflow_phase":  WorkflowPhase.COMPLETED,
            "processing_ms":   elapsed_ms,
            **ctx.event(
                AuditEventType.RECOMMENDATION_GENERATED,
                data={
                    "recommendation_type": final_rec.recommendation_type.value,
                    "confidence_score":    final_rec.confidence_score,
                    "is_override":         bool(reviewer_actions and reviewer_actions[-1].is_override),
                    "reviewer_id":         reviewer_actions[-1].reviewer_id if reviewer_actions else None,
                },
                duration_ms=elapsed_ms,
            ),
        }

    @staticmethod
    def _build_from_reviewer_action(
        action,
        ai_recommendation: PARecommendation | None,
        state: PAWorkflowState,
    ) -> PARecommendation:
        """Convert a ReviewerAction into the final PARecommendation."""
        rec_type = _ACTION_TO_REC.get(
            action.action_type,
            ai_recommendation.recommendation_type if ai_recommendation
            else RecommendationType.PEND_FOR_INFO,
        )

        # Confidence: explicit approve/deny = high; override = moderate
        if action.action_type in (ReviewerActionType.APPROVE, ReviewerActionType.DENY):
            confidence = 1.0
        elif action.is_override:
            confidence = 0.95
        else:
            confidence = 0.90

        # Merge AI rationale with reviewer notes
        rationale: list[str] = []
        if ai_recommendation and ai_recommendation.rationale:
            rationale.extend(ai_recommendation.rationale[:3])
        if action.notes:
            rationale.append(f"Reviewer ({action.reviewer_id}): {action.notes}")
        if action.override_reason:
            rationale.append(f"Override reason: {action.override_reason}")
        if not rationale:
            rationale = [f"Decision made by reviewer {action.reviewer_id}."]

        return PARecommendation(
            recommendation_type=rec_type,
            confidence_score=confidence,
            rationale=rationale,
            supporting_criteria=ai_recommendation.supporting_criteria if ai_recommendation else [],
            conflicting_criteria=ai_recommendation.conflicting_criteria if ai_recommendation else [],
            evidence_references=ai_recommendation.evidence_references if ai_recommendation else [],
            requires_human_review=False,
            review_reason=None,
            model_used=ai_recommendation.model_used if ai_recommendation else None,
            tokens_used=ai_recommendation.tokens_used if ai_recommendation else 0,
        )


# Module-level callable
decision_node = DecisionNode()
