"""
Decision node — Stage 7 of the PA review workflow.

Two decision paths:

  AI-decision path (no reviewer action):
    Delegates to DecisionEngine which runs deterministic rules:
      ALL PASS  → APPROVE
      ANY FAIL  → DENY
      MISSING INFO → PEND
    Then calculates multi-factor confidence and formats structured rationale.

  Reviewer-action path (reviewer_actions non-empty):
    Uses the reviewer's explicit action as the ground truth.
    If the reviewer is overriding an AI decision (OVERRIDE_APPROVE /
    OVERRIDE_DENY), the override is validated and applied via OverrideHandler,
    which records provenance and adjusts rationale accordingly.

Both paths produce a final PARecommendation and transition the workflow to
WorkflowPhase.COMPLETED.
"""

from __future__ import annotations

import time
from typing import Any

import structlog

from app.services.decision import DecisionEngine, OverrideRequest, DecisionVerdict, get_decision_engine
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

# Map reviewer action types → target DecisionVerdict for override path
_ACTION_TO_VERDICT = {
    ReviewerActionType.APPROVE:          DecisionVerdict.APPROVE,
    ReviewerActionType.DENY:             DecisionVerdict.DENY,
    ReviewerActionType.PEND:             DecisionVerdict.PEND_FOR_INFO,
    ReviewerActionType.OVERRIDE_APPROVE: DecisionVerdict.APPROVE,
    ReviewerActionType.OVERRIDE_DENY:    DecisionVerdict.DENY,
    ReviewerActionType.ESCALATE:         DecisionVerdict.REFER_MEDICAL_DIRECTOR,
}


class DecisionNode(BaseNode):
    """
    Final decision node — applies deterministic rules + reviewer actions.

    Uses DecisionEngine for AI-path decisions and OverrideHandler for
    reviewer overrides.  Both paths emit full audit events.
    """

    node_name = "decision_node"

    def __init__(self) -> None:
        super().__init__()
        self._engine: DecisionEngine | None = None

    def _get_engine(self) -> DecisionEngine:
        if self._engine is None:
            self._engine = get_decision_engine()
        return self._engine

    async def execute(
        self, state: PAWorkflowState, nctx: NodeContext
    ) -> dict[str, Any]:
        ctx = nctx.audit_ctx
        t0 = time.monotonic()
        engine = self._get_engine()
        case_id = state.get("case_id", "unknown")

        reviewer_actions = state.get("reviewer_actions", [])

        if reviewer_actions:
            final_rec, is_override, reviewer_id = await self._reviewer_path(
                state=state,
                engine=engine,
                reviewer_actions=reviewer_actions,
                nctx=nctx,
                case_id=case_id,
            )
        else:
            final_rec = await self._ai_path(state, engine, nctx, case_id)
            is_override = False
            reviewer_id = None

        elapsed_ms = (time.monotonic() - t0) * 1000
        nctx.log.info(
            "decision_node.decided",
            recommendation=final_rec.recommendation_type.value,
            confidence=final_rec.confidence_score,
            is_override=is_override,
            reviewer_id=reviewer_id,
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
                    "is_override":         is_override,
                    "reviewer_id":         reviewer_id,
                    "requires_review":     final_rec.requires_human_review,
                    "rationale_lines":     len(final_rec.rationale),
                },
                duration_ms=elapsed_ms,
            ),
        }

    # ------------------------------------------------------------------
    # AI-decision path
    # ------------------------------------------------------------------

    async def _ai_path(
        self,
        state: PAWorkflowState,
        engine: DecisionEngine,
        nctx: NodeContext,
        case_id: str,
    ) -> PARecommendation:
        """Run the deterministic decision engine on evaluation results."""
        evaluation_results = state.get("evaluation_results", {})

        if not evaluation_results:
            nctx.log.warning("decision_node.no_evaluation_results", case_id=case_id)
            return PARecommendation(
                recommendation_type=RecommendationType.PEND_FOR_INFO,
                confidence_score=0.0,
                rationale=["No policy criteria were evaluated. Manual review required."],
                requires_human_review=True,
                review_reason="No evaluation results available",
            )

        result = await engine.decide(state, case_id=case_id)
        return engine.to_recommendation(result)

    # ------------------------------------------------------------------
    # Reviewer-action path
    # ------------------------------------------------------------------

    async def _reviewer_path(
        self,
        *,
        state: PAWorkflowState,
        engine: DecisionEngine,
        reviewer_actions: list,
        nctx: NodeContext,
        case_id: str,
    ) -> tuple[PARecommendation, bool, str | None]:
        """
        Apply the latest reviewer action.

        For direct decisions (APPROVE/DENY/PEND/ESCALATE): build directly.
        For overrides (OVERRIDE_APPROVE/OVERRIDE_DENY): run AI engine first,
        then apply override through OverrideHandler for full provenance.
        """
        action = reviewer_actions[-1]
        action_type = action.action_type

        is_override = action.is_override
        reviewer_id = action.reviewer_id

        # --- Direct reviewer decision (not an override) ---
        if action_type in (
            ReviewerActionType.APPROVE,
            ReviewerActionType.DENY,
            ReviewerActionType.PEND,
            ReviewerActionType.ESCALATE,
        ):
            rec = self._build_direct_decision(action, state.get("recommendation"))
            nctx.log.info(
                "decision_node.reviewer_direct_decision",
                case_id=case_id,
                action=action_type.value,
                reviewer_id=reviewer_id,
            )
            return rec, False, reviewer_id

        # --- Override path: run AI engine then apply override ---
        target_verdict = _ACTION_TO_VERDICT.get(action_type)
        if target_verdict is None:
            nctx.log.warning(
                "decision_node.unhandled_action_type",
                action_type=action_type.value,
                case_id=case_id,
            )
            # Fall back to AI decision
            rec = await self._ai_path(state, engine, nctx, case_id)
            return rec, False, None

        # Run AI decision to get the baseline result
        evaluation_results = state.get("evaluation_results", {})
        ai_result = None
        if evaluation_results:
            ai_result = await engine.decide(state, case_id=case_id)

        if ai_result is None:
            # No AI result to override — build directly
            rec = self._build_direct_decision(action, state.get("recommendation"))
            return rec, True, reviewer_id

        override_req = OverrideRequest(
            reviewer_id=reviewer_id,
            reviewer_name=action.reviewer_name,
            target_verdict=target_verdict,
            override_reason=action.override_reason or action.notes or "Reviewer override",
            clinical_notes=action.notes or "",
        )

        override = engine.apply_override(ai_result, override_req)

        if override.override_applied:
            nctx.log.info(
                "decision_node.override_applied",
                case_id=case_id,
                original_verdict=ai_result.verdict.value,
                new_verdict=override.final_result.verdict.value,
                reviewer_id=reviewer_id,
            )
            rec = engine.to_recommendation(override.final_result)
        else:
            nctx.log.warning(
                "decision_node.override_rejected",
                case_id=case_id,
                errors=override.validation_errors,
            )
            # Override invalid — use direct build as fallback
            rec = self._build_direct_decision(action, state.get("recommendation"))

        return rec, override.override_applied, reviewer_id

    @staticmethod
    def _build_direct_decision(
        action,
        ai_recommendation: PARecommendation | None,
    ) -> PARecommendation:
        """Build a PARecommendation directly from a reviewer action."""
        from app.services.workflow.state.models import RecommendationType

        rec_type_map = {
            ReviewerActionType.APPROVE:          RecommendationType.APPROVE,
            ReviewerActionType.DENY:             RecommendationType.DENY,
            ReviewerActionType.PEND:             RecommendationType.PEND_FOR_INFO,
            ReviewerActionType.OVERRIDE_APPROVE: RecommendationType.APPROVE,
            ReviewerActionType.OVERRIDE_DENY:    RecommendationType.DENY,
            ReviewerActionType.ESCALATE:         RecommendationType.REFER_MEDICAL_DIRECTOR,
        }
        rec_type = rec_type_map.get(
            action.action_type,
            ai_recommendation.recommendation_type if ai_recommendation
            else RecommendationType.PEND_FOR_INFO,
        )

        confidence = 1.0 if action.action_type in (
            ReviewerActionType.APPROVE, ReviewerActionType.DENY
        ) else 0.95

        rationale: list[str] = []
        if ai_recommendation and ai_recommendation.rationale:
            rationale.extend(ai_recommendation.rationale[:3])
        if action.notes:
            rationale.append(
                f"Reviewer ({action.reviewer_id}): {action.notes}"
            )
        if action.override_reason:
            rationale.append(f"Override reason: {action.override_reason}")
        if not rationale:
            rationale = [f"Decision by reviewer {action.reviewer_id}."]

        return PARecommendation(
            recommendation_type=rec_type,
            confidence_score=confidence,
            rationale=rationale,
            supporting_criteria=ai_recommendation.supporting_criteria if ai_recommendation else [],
            conflicting_criteria=ai_recommendation.conflicting_criteria if ai_recommendation else [],
            evidence_references=ai_recommendation.evidence_references if ai_recommendation else [],
            requires_human_review=False,
            review_reason=None,
            model_used=ai_recommendation.model_used if ai_recommendation else "reviewer",
            tokens_used=ai_recommendation.tokens_used if ai_recommendation else 0,
        )


# Module-level callable
decision_node = DecisionNode()
