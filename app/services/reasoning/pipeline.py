"""
ReasoningPipeline — the primary entry point for the PA reasoning engine.

Bridges the LangGraph workflow state to the multi-model orchestrator.

Responsibilities:
  1. Build GuardrailContext and RouterContext from PAWorkflowState
  2. Build criteria lists from retrieved policies
  3. Build system/user prompts (standard vs advanced per tier)
  4. Call MultiModelOrchestrator.reason()
  5. Convert ReasoningOutput → workflow state patch (EvaluationResult, PARecommendation, ClarificationAttempt)
  6. Log and record Prometheus metrics

This file is the only place that knows about PAWorkflowState — the guardrails
and orchestrator are state-agnostic for testability.

Usage (from reasoning_node.py):
    pipeline = ReasoningPipeline.from_settings()
    patch = await pipeline.evaluate_policy(policy, state, nctx)
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from typing import Any

import structlog

from app.services.reasoning.guardrails.base import GuardrailContext
from app.services.reasoning.models import (
    CriterionStatus,
    ModelTier,
    ReasoningResult,
)
from app.services.reasoning.orchestrator import MultiModelOrchestrator
from app.services.reasoning.prompts import (
    ADVANCED_SYSTEM_PROMPT,
    STANDARD_SYSTEM_PROMPT,
    build_advanced_user_prompt,
    build_standard_user_prompt,
)
from app.services.reasoning.router import RouterContext

logger = structlog.get_logger(__name__)

# Minimum fraction of criteria that must be MET to recommend APPROVE
APPROVE_THRESHOLD = 0.80

# Minimum average confidence for auto-decision (below → human review)
AUTO_DECISION_CONFIDENCE = 0.80


class ReasoningPipeline:
    """
    Full reasoning pipeline for one policy evaluation.

    Converts a PAWorkflowState + RetrievedPolicy → EvaluationResult +
    optional PARecommendation + optional ClarificationAttempt.
    """

    def __init__(self, orchestrator: MultiModelOrchestrator) -> None:
        self._orchestrator = orchestrator
        self._log = structlog.get_logger(self.__class__.__name__)

    async def evaluate_policy(
        self,
        policy,           # RetrievedPolicy
        state: dict,      # PAWorkflowState
        *,
        case_id: str,
        clinical_summary: str,
    ) -> ReasoningResult:
        """
        Evaluate one policy's criteria against the clinical evidence.

        Returns:
            ReasoningResult containing the structured evaluation output.
        """
        t0 = time.perf_counter()

        # Build criteria list for prompt
        criteria_list = [
            {
                "criterion_id":   chunk.chunk_id,
                "criterion_text": chunk.criterion_text,
                "criterion_type": chunk.criterion_type,
                "section":        chunk.section_header,
            }
            for chunk in policy.criteria_chunks
        ]

        # Build policy chunk texts for grounding checks
        policy_chunks = [chunk.criterion_text for chunk in policy.criteria_chunks]

        # Build guardrail context
        guardrail_ctx = GuardrailContext(
            case_id=case_id,
            clinical_summary=clinical_summary,
            policy_chunks=policy_chunks,
            policy_metadata=[{
                "policy_id":      policy.policy_id,
                "policy_version": policy.policy_version,
                "payer_name":     policy.payer_name,
            }],
            query_cpt_codes=list(state.get("extracted_entities", {}).keys())[:5],
            query_icd_codes=self._collect_icd_codes(state),
            extracted_entities=self._serialize_entities(state),
        )

        # Build router context from state signals
        avg_conf = self._avg_extraction_confidence(state)
        router_ctx = RouterContext(
            case_id=case_id,
            extraction_confidence=avg_conf,
            policy_count=len(state.get("retrieved_policies", [])),
            criteria_count=len(criteria_list),
            service_type=state.get("service_type") or "",
            prior_attempt_count=len(state.get("clarification_attempts", [])),
            clarification_attempt_count=len(state.get("clarification_attempts", [])),
            prior_violation_types=[],
        )

        # System prompt: use ADVANCED for LARGE tier
        def system_prompt_for_tier(tier: ModelTier, _: int) -> str:
            return ADVANCED_SYSTEM_PROMPT if tier == ModelTier.LARGE else STANDARD_SYSTEM_PROMPT

        # User prompt builder (called once per attempt so tier can change)
        escalation_reason = ""
        prior_attempts = 0

        def user_prompt_builder(tier: ModelTier, attempt_num: int) -> str:
            nonlocal escalation_reason, prior_attempts
            if tier == ModelTier.LARGE:
                return build_advanced_user_prompt(
                    case_id=case_id,
                    service_type=state.get("service_type") or "",
                    clinical_summary=clinical_summary,
                    policy_id=policy.policy_id,
                    policy_version=policy.policy_version,
                    payer_name=policy.payer_name or "Unknown",
                    criteria_list=criteria_list,
                    escalation_reason=escalation_reason or "Prior attempt did not meet quality thresholds",
                    prior_attempts=attempt_num - 1,
                    violations_summary="",
                )
            return build_standard_user_prompt(
                case_id=case_id,
                service_type=state.get("service_type") or "",
                clinical_summary=clinical_summary,
                policy_id=policy.policy_id,
                policy_version=policy.policy_version,
                payer_name=policy.payer_name or "Unknown",
                criteria_list=criteria_list,
            )

        # Select system prompt based on initial tier
        initial_config = MultiModelOrchestrator().__class__  # for tier detection
        system_prompt = STANDARD_SYSTEM_PROMPT  # will be upgraded in-flight if needed

        result = await self._orchestrator.reason(
            case_id=case_id,
            system_prompt=system_prompt,
            user_prompt_builder=user_prompt_builder,
            guardrail_ctx=guardrail_ctx,
            router_ctx=router_ctx,
        )

        elapsed = (time.perf_counter() - t0) * 1000
        self._log.info(
            "pipeline.policy_evaluated",
            case_id=case_id,
            policy_id=policy.policy_id,
            succeeded=result.succeeded,
            escalations=result.escalations_count,
            total_tokens=result.total_tokens,
            latency_ms=round(elapsed, 1),
        )
        self._track_pipeline_metrics(result)
        return result

    def convert_to_evaluation_result(
        self,
        result: ReasoningResult,
        policy,           # RetrievedPolicy
        model_used: str,
    ):
        """
        Convert a ReasoningResult → EvaluationResult (workflow state model).

        Returns None if the result has no usable output.
        """
        from app.services.workflow.state.models import (
            CriterionEvaluation,
            CriterionMet,
            EvaluationResult,
        )

        output = result.output
        if output is None:
            return None

        status_map = {
            CriterionStatus.MET:          CriterionMet.YES,
            CriterionStatus.NOT_MET:      CriterionMet.NO,
            CriterionStatus.UNDETERMINED:  CriterionMet.UNDETERMINED,
            CriterionStatus.NOT_APPLICABLE: CriterionMet.NOT_APPLICABLE,
        }

        criteria_evals = []
        for cr in output.criterion_evaluations:
            evidence_quotes = [
                c.quote for c in cr.evidence_citations if c.quote
            ]
            criteria_evals.append(CriterionEvaluation(
                criterion_id=cr.criterion_id,
                criterion_text=cr.criterion_text,
                criterion_type=cr.criterion_type,
                met=status_map.get(cr.status, CriterionMet.UNDETERMINED),
                confidence=cr.confidence,
                evidence=evidence_quotes,
                policy_section=cr.policy_section,
                notes=cr.rationale[:500] if cr.rationale else None,
                requires_clarification=cr.requires_clarification,
            ))

        return EvaluationResult(
            policy_id=policy.policy_id,
            policy_version=policy.policy_version,
            criteria_evaluations=criteria_evals,
            model_used=model_used,
            tokens_used=result.total_tokens,
        )

    def build_recommendation(
        self,
        evaluation_results: dict,  # dict[str, EvaluationResult]
        reasoning_result: ReasoningResult,
    ):
        """
        Build a PARecommendation from evaluation results.

        Takes the best evaluation (highest overall score) and applies
        recommendation thresholds.
        """
        from app.services.workflow.state.models import (
            CriterionMet,
            PARecommendation,
            RecommendationType,
        )

        if not evaluation_results:
            return PARecommendation(
                recommendation_type=RecommendationType.PEND_FOR_INFO,
                confidence_score=0.0,
                rationale=["No policy criteria evaluated."],
                requires_human_review=True,
                review_reason="No evaluation results available",
                tokens_used=reasoning_result.total_tokens,
            )

        best_eval = max(evaluation_results.values(), key=lambda e: e.overall_score)
        total = best_eval.criteria_total or 1
        met_frac = best_eval.criteria_met / total
        undetermined_frac = best_eval.criteria_undetermined / total
        avg_conf = (
            sum(c.confidence for c in best_eval.criteria_evaluations) / total
            if best_eval.criteria_evaluations else 0.5
        )

        # Apply guardrail-aware confidence (if escalated, reduce confidence)
        if reasoning_result.escalations_count > 0:
            avg_conf = avg_conf * (1.0 - 0.05 * reasoning_result.escalations_count)

        output = reasoning_result.output
        overall_conf = float(output.overall_confidence) if output else avg_conf

        if met_frac >= APPROVE_THRESHOLD and undetermined_frac <= 0.10:
            rec_type = RecommendationType.APPROVE
            rationale = [
                f"Met {best_eval.criteria_met}/{total} criteria ({met_frac:.0%}).",
                output.overall_rationale[:300] if output else "",
            ]
        elif best_eval.criteria_not_met >= 2 or (best_eval.criteria_met == 0 and total > 0):
            rec_type = RecommendationType.DENY
            rationale = [
                f"Only {best_eval.criteria_met}/{total} criteria met.",
                f"{best_eval.criteria_not_met} criteria explicitly not met.",
                output.overall_rationale[:300] if output else "",
            ]
        else:
            rec_type = RecommendationType.PEND_FOR_INFO
            rationale = [
                f"{best_eval.criteria_undetermined} criteria undetermined.",
                "Additional clinical documentation needed.",
            ]
            overall_conf = min(overall_conf, 0.60)

        requires_review = (
            overall_conf < AUTO_DECISION_CONFIDENCE
            or undetermined_frac > 0.20
            or reasoning_result.requires_human_escalation
            or reasoning_result.escalations_count >= 2
        )

        supporting = [
            c.criterion_text[:100]
            for c in best_eval.criteria_evaluations
            if c.met == CriterionMet.YES
        ]
        conflicting = [
            c.criterion_text[:100]
            for c in best_eval.criteria_evaluations
            if c.met == CriterionMet.NO
        ]
        evidence_refs = [
            e for c in best_eval.criteria_evaluations for e in c.evidence[:2]
        ][:10]

        return PARecommendation(
            recommendation_type=rec_type,
            confidence_score=round(overall_conf, 4),
            rationale=[r for r in rationale if r],
            supporting_criteria=supporting[:5],
            conflicting_criteria=conflicting[:5],
            evidence_references=evidence_refs,
            requires_human_review=requires_review,
            review_reason=(
                f"AI confidence {overall_conf:.0%} below {AUTO_DECISION_CONFIDENCE:.0%} threshold"
                if requires_review else None
            ),
            model_used=reasoning_result.final_tier.value,
            tokens_used=reasoning_result.total_tokens,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _avg_extraction_confidence(state: dict) -> float:
        entities = state.get("extracted_entities", {})
        if not entities:
            return 0.5
        confs = []
        for v in entities.values():
            if hasattr(v, "overall_confidence"):
                confs.append(v.overall_confidence)
            elif isinstance(v, dict):
                confs.append(float(v.get("overall_confidence", 0.5)))
        return sum(confs) / len(confs) if confs else 0.5

    @staticmethod
    def _collect_icd_codes(state: dict) -> list[str]:
        codes: list[str] = []
        for entities in state.get("extracted_entities", {}).values():
            icd_list = (
                entities.icd_codes if hasattr(entities, "icd_codes")
                else entities.get("icd_codes", [])
            )
            for c in icd_list:
                code = c.code if hasattr(c, "code") else str(c)
                if code:
                    codes.append(code)
        return codes[:20]

    @staticmethod
    def _serialize_entities(state: dict) -> dict[str, Any]:
        """Serialize extracted entities to dicts for the guardrail context."""
        result: dict[str, Any] = {}
        for doc_id, entities in state.get("extracted_entities", {}).items():
            if hasattr(entities, "model_dump"):
                result[doc_id] = entities.model_dump()
            elif isinstance(entities, dict):
                result[doc_id] = entities
        return result

    def _track_pipeline_metrics(self, result: ReasoningResult) -> None:
        try:
            from app.monitoring.metrics import (
                LLM_TOKENS_TOTAL,
                REASONING_GUARDRAIL_VIOLATIONS_TOTAL,
            )
            LLM_TOKENS_TOTAL.labels(
                operation=f"reasoning_{result.final_tier.value}",
                token_type="prompt",
            ).inc(result.total_prompt_tokens)
            LLM_TOKENS_TOTAL.labels(
                operation=f"reasoning_{result.final_tier.value}",
                token_type="completion",
            ).inc(result.total_completion_tokens)

            for v in result.guardrail_violations:
                REASONING_GUARDRAIL_VIOLATIONS_TOTAL.labels(
                    violation_type=v.violation_type.value,
                ).inc()
        except Exception:
            pass

    @classmethod
    def from_settings(cls) -> "ReasoningPipeline":
        """Build a ReasoningPipeline from application settings."""
        orchestrator = MultiModelOrchestrator.from_settings()
        return cls(orchestrator=orchestrator)
