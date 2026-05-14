"""
Reasoning node — Stage 4 of the PA review workflow.

Delegates to the production-grade ReasoningPipeline which provides:
  - Multi-model orchestration (SMALL → MEDIUM → LARGE)
  - Enterprise guardrails (schema, hallucination, groundedness, safety)
  - Automatic escalation on guardrail failures
  - Human reviewer escalation after repeated violations
  - Full observability (structured logs + Prometheus metrics)
"""

from __future__ import annotations

import time
from typing import Any

import structlog

from app.services.reasoning import ReasoningPipeline
from app.services.workflow.nodes.base import BaseNode, NodeContext
from app.services.workflow.state import mutations
from app.services.workflow.state.models import (
    AuditEventType,
    ClarificationAttempt,
    ClarificationStatus,
    WorkflowPhase,
)
from app.services.workflow.state.schema import (
    PAWorkflowState,
    clarification_exhausted,
    current_clarification_count,
)

logger = structlog.get_logger(__name__)


class ReasoningNode(BaseNode):
    """
    AI-powered policy criterion evaluation node.

    Uses the multi-model ReasoningPipeline with full guardrail enforcement.
    Automatically escalates to human review if guardrails cannot be satisfied.
    """

    node_name = "reasoning_node"

    def __init__(self) -> None:
        super().__init__()
        self._pipeline: ReasoningPipeline | None = None

    def _get_pipeline(self) -> ReasoningPipeline:
        if self._pipeline is None:
            self._pipeline = ReasoningPipeline.from_settings()
        return self._pipeline

    async def execute(
        self, state: PAWorkflowState, nctx: NodeContext
    ) -> dict[str, Any]:
        ctx = nctx.audit_ctx
        t0  = time.monotonic()

        policies = state.get("retrieved_policies", [])
        if not policies:
            nctx.log.warning("reasoning_node.no_policies")
            return {
                "workflow_phase": WorkflowPhase.HUMAN_REVIEW,
                **ctx.event(
                    AuditEventType.CRITERIA_EVALUATED,
                    data={"policies": 0, "skipped": True},
                ),
            }

        case_id = state.get("case_id", "unknown")
        clinical_summary = self._build_clinical_summary(state)
        pipeline = self._get_pipeline()

        nctx.log.info(
            "reasoning_node.evaluating",
            policies=len(policies),
            clinical_chars=len(clinical_summary),
        )

        evaluation_results: dict = {}
        total_tokens = 0
        all_clarification_questions: list[str] = []
        human_escalation_required = False
        escalation_reason: str | None = None
        final_reasoning_result = None

        for policy in policies[:3]:  # Evaluate top-3 most relevant policies
            try:
                reasoning_result = await pipeline.evaluate_policy(
                    policy, state,
                    case_id=case_id,
                    clinical_summary=clinical_summary,
                )

                total_tokens += reasoning_result.total_tokens

                if reasoning_result.requires_human_escalation:
                    human_escalation_required = True
                    escalation_reason = reasoning_result.escalation_reason
                    nctx.log.warning(
                        "reasoning_node.human_escalation_required",
                        policy_id=policy.policy_id,
                        reason=escalation_reason,
                    )
                    continue

                if reasoning_result.succeeded:
                    eval_result = pipeline.convert_to_evaluation_result(
                        reasoning_result, policy,
                        model_used=reasoning_result.final_tier.value,
                    )
                    if eval_result:
                        evaluation_results[eval_result.dedup_key] = eval_result
                        final_reasoning_result = reasoning_result

                        # Collect clarification questions from UNDETERMINED criteria
                        if reasoning_result.output:
                            for cr in reasoning_result.output.criterion_evaluations:
                                if cr.requires_clarification and cr.clarification_question:
                                    all_clarification_questions.append(cr.clarification_question)

            except Exception as exc:
                nctx.log.error(
                    "reasoning_node.policy_eval_failed",
                    policy_id=policy.policy_id,
                    error=str(exc),
                    exc_info=True,
                )

        elapsed_ms = (time.monotonic() - t0) * 1000

        # If ALL policies required human escalation and none succeeded
        if not evaluation_results and human_escalation_required:
            nctx.log.warning(
                "reasoning_node.all_escalated_to_human",
                case_id=case_id,
                reason=escalation_reason,
            )
            patch: dict[str, Any] = {
                "workflow_phase": WorkflowPhase.HUMAN_REVIEW,
                "requires_review": True,
                "tokens_used":  total_tokens,
                "processing_ms": elapsed_ms,
                **ctx.event(
                    AuditEventType.CRITERIA_EVALUATED,
                    data={
                        "policies_evaluated": 0,
                        "human_escalation": True,
                        "escalation_reason": escalation_reason,
                        "total_tokens": total_tokens,
                    },
                    duration_ms=elapsed_ms,
                ),
            }
            try:
                from app.monitoring.metrics import REASONING_HUMAN_ESCALATIONS_TOTAL
                reason_label = (escalation_reason or "unknown")[:50].replace(" ", "_").lower()
                REASONING_HUMAN_ESCALATIONS_TOTAL.labels(reason=reason_label).inc()
            except Exception:
                pass
            return patch

        needs_clarification = (
            bool(all_clarification_questions)
            and not clarification_exhausted(state)
        )

        patch = {
            "evaluation_results": evaluation_results,
            "tokens_used":        total_tokens,
            "processing_ms":      elapsed_ms,
            **ctx.event(
                AuditEventType.CRITERIA_EVALUATED,
                data={
                    "policies_evaluated":  len(evaluation_results),
                    "needs_clarification": needs_clarification,
                    "undetermined_count":  len(all_clarification_questions),
                    "total_tokens":        total_tokens,
                    "escalations":         (
                        final_reasoning_result.escalations_count
                        if final_reasoning_result else 0
                    ),
                },
                duration_ms=elapsed_ms,
            ),
        }

        if needs_clarification:
            question = self._consolidate_questions(all_clarification_questions)
            attempt_num = current_clarification_count(state) + 1
            attempt = ClarificationAttempt(
                attempt_number=attempt_num,
                question=question,
                question_category="clinical_evidence",
                missing_criteria=all_clarification_questions[:5],
                status=ClarificationStatus.PENDING,
            )
            patch.update(mutations.with_clarification_sent(attempt, ctx))
            patch["workflow_phase"] = WorkflowPhase.CLARIFICATION
        else:
            prelim = pipeline.build_recommendation(
                evaluation_results, final_reasoning_result
            ) if final_reasoning_result else self._pend_recommendation(total_tokens)
            patch["recommendation"]   = prelim
            patch["rationale"]        = prelim.rationale
            patch["workflow_phase"]   = WorkflowPhase.HUMAN_REVIEW

        return patch

    # ------------------------------------------------------------------
    # Helpers (kept here for clinical_summary — may be shared later)
    # ------------------------------------------------------------------

    @staticmethod
    def _build_clinical_summary(state: PAWorkflowState) -> str:
        """Format extracted entities as a dense clinical summary string."""
        lines: list[str] = []

        for entities in state.get("extracted_entities", {}).values():
            if entities.patient:
                p = entities.patient
                if p.patient_name:
                    lines.append(f"Patient: {p.patient_name}")
                if p.date_of_birth:
                    lines.append(f"DOB: {p.date_of_birth}")
                if p.gender:
                    lines.append(f"Gender: {p.gender}")

            if entities.diagnoses:
                lines.append("Diagnoses: " + "; ".join(
                    d.name for d in entities.diagnoses if d.name
                ))
            if entities.icd_codes:
                lines.append("ICD Codes: " + ", ".join(c.code for c in entities.icd_codes))
            if entities.cpt_codes:
                lines.append("CPT Codes: " + ", ".join(c.code for c in entities.cpt_codes))
            if entities.medications:
                lines.append("Medications: " + "; ".join(
                    f"{m.name} {m.dose or ''} {m.frequency or ''}".strip()
                    for m in entities.medications
                ))
            if entities.hba1c_readings:
                lines.append("HbA1c: " + ", ".join(
                    f"{h.value}% ({h.date or 'no date'})" for h in entities.hba1c_readings
                ))
            if entities.lab_values:
                lines.append("Lab Values: " + "; ".join(
                    f"{lv.test_name} {lv.value} {lv.unit or ''}"
                    for lv in entities.lab_values[:8]
                ))
            if entities.symptoms:
                lines.append("Symptoms: " + "; ".join(s.name for s in entities.symptoms))
            if entities.treatment_history:
                lines.append("Treatment History: " + "; ".join(
                    t.treatment for t in entities.treatment_history[:5]
                ))

            for attempt in state.get("clarification_attempts", []):
                if attempt.response and attempt.status.value == "answered":
                    lines.append(
                        f"[Clarification #{attempt.attempt_number}] "
                        f"Q: {attempt.question} A: {attempt.response}"
                    )

        return "\n".join(lines) if lines else "No clinical data available."

    @staticmethod
    def _consolidate_questions(questions: list[str]) -> str:
        if len(questions) == 1:
            return questions[0]
        bullet_list = "\n".join(f"• {q}" for q in questions[:5])
        return (
            "To complete the prior authorization review, please provide clarification "
            f"on the following:\n{bullet_list}"
        )

    @staticmethod
    def _pend_recommendation(tokens: int):
        from app.services.workflow.state.models import PARecommendation, RecommendationType
        return PARecommendation(
            recommendation_type=RecommendationType.PEND_FOR_INFO,
            confidence_score=0.0,
            rationale=["Guardrail escalation required human review — no AI recommendation available."],
            requires_human_review=True,
            review_reason="All policy evaluations required human escalation",
            tokens_used=tokens,
        )


# Module-level callable
reasoning_node = ReasoningNode()
