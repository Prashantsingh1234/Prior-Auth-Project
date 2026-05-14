"""
Reasoning node — Stage 4 of the PA review workflow.

Responsibilities:
  - Evaluate each criterion in every retrieved policy against the extracted
    clinical evidence using GPT-4o
  - Produce EvaluationResult per policy with per-criterion MET/NOT_MET/UNDETERMINED
  - If undetermined criteria exist AND clarification is not exhausted:
      generate a targeted clarification question and store a PENDING
      ClarificationAttempt in state
  - Set a preliminary PARecommendation (before human review)
  - Transition workflow phase to CLARIFICATION or HUMAN_REVIEW

The LLM is given a structured JSON schema so output can be parsed reliably.
Temperature=0 for determinism.  Tenacity retries on rate-limit / timeout.
"""

from __future__ import annotations

import json
import time
from typing import Any

import structlog
from openai import AsyncOpenAI, APITimeoutError, RateLimitError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.services.workflow.nodes.base import BaseNode, NodeContext
from app.services.workflow.state import mutations
from app.services.workflow.state.models import (
    AuditEventType,
    ClarificationAttempt,
    ClarificationStatus,
    CriterionEvaluation,
    CriterionMet,
    EvaluationResult,
    PARecommendation,
    RecommendationType,
    WorkflowPhase,
)
from app.services.workflow.state.schema import (
    PAWorkflowState,
    clarification_exhausted,
    current_clarification_count,
)

logger = structlog.get_logger(__name__)

_MODEL       = "gpt-4o"
_TEMPERATURE = 0.0
_MAX_CRITERIA_PER_CALL = 15   # Batch criteria to stay within token budget
_MIN_CONFIDENCE_FOR_AUTO = 0.80  # Below this, always require human review

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """
You are a clinical prior authorization specialist evaluating whether a medical case meets insurance coverage criteria.

Your task:
1. Review the clinical evidence provided.
2. Evaluate each policy criterion as MET, NOT_MET, or UNDETERMINED.
3. For each criterion, provide supporting evidence from the clinical notes.
4. Be objective and evidence-based. Do NOT infer or assume information not present.

IMPORTANT RULES:
- "met": "yes"  → Clear evidence in clinical notes supports this criterion
- "met": "no"   → Clinical notes explicitly contradict this criterion, or required condition is absent
- "met": "undetermined" → Insufficient evidence to decide; clarification may be needed
- confidence: Your certainty in the determination (0.0 = unsure, 1.0 = certain)
- evidence: Direct quotes or references from the clinical data
- If information is ambiguous, use "undetermined" and specify what is missing

Return valid JSON only. No explanatory text outside the JSON.
""".strip()

_USER_PROMPT_TEMPLATE = """
CLINICAL EVIDENCE:
{clinical_summary}

POLICY: {policy_id} v{policy_version}
Payer: {payer_name}

CRITERIA TO EVALUATE:
{criteria_json}

Respond with this JSON structure:
{{
  "evaluations": [
    {{
      "criterion_id": "criterion identifier",
      "met": "yes" | "no" | "undetermined",
      "confidence": 0.0-1.0,
      "evidence": ["exact quote from clinical data"],
      "notes": "brief explanation",
      "requires_clarification": true | false,
      "clarification_question": "specific question if requires_clarification is true, else null"
    }}
  ],
  "overall_assessment": "brief overall assessment",
  "missing_information": ["item 1 that would help determine undetermined criteria"]
}}
"""


class ReasoningNode(BaseNode):
    """
    AI-powered policy criterion evaluation node.

    Evaluates each retrieved policy criterion against the extracted clinical
    evidence using GPT-4o structured output.
    """

    node_name = "reasoning_node"

    def __init__(self) -> None:
        super().__init__()
        self._client: AsyncOpenAI | None = None

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            from app.core.config.settings import get_settings
            s = get_settings()
            self._client = AsyncOpenAI(
                api_key=s.openai_api_key.get_secret_value(),
                timeout=s.openai_request_timeout,
            )
        return self._client

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

        clinical_summary = self._build_clinical_summary(state)
        nctx.log.info(
            "reasoning_node.evaluating",
            policies=len(policies),
            clinical_chars=len(clinical_summary),
        )

        evaluation_results: dict[str, EvaluationResult] = {}
        total_tokens = 0
        all_undetermined_questions: list[str] = []

        for policy in policies[:3]:   # Evaluate top-3 most relevant policies
            try:
                eval_result, tokens, questions = await self._evaluate_policy(
                    policy, clinical_summary, nctx
                )
                evaluation_results[eval_result.dedup_key] = eval_result
                total_tokens += tokens
                all_undetermined_questions.extend(questions)
            except Exception as exc:
                nctx.log.error(
                    "reasoning_node.policy_eval_failed",
                    policy_id=policy.policy_id,
                    error=str(exc),
                )

        elapsed_ms = (time.monotonic() - t0) * 1000

        # Determine if clarification is needed
        needs_clarification = (
            bool(all_undetermined_questions)
            and not clarification_exhausted(state)
        )

        patch: dict[str, Any] = {
            "evaluation_results": evaluation_results,
            "tokens_used":        total_tokens,
            "processing_ms":      elapsed_ms,
            **ctx.event(
                AuditEventType.CRITERIA_EVALUATED,
                data={
                    "policies_evaluated": len(evaluation_results),
                    "needs_clarification": needs_clarification,
                    "undetermined_count": len(all_undetermined_questions),
                    "total_tokens": total_tokens,
                },
                duration_ms=elapsed_ms,
            ),
        }

        if needs_clarification:
            # Generate a single consolidated clarification question
            question = self._consolidate_questions(all_undetermined_questions)
            attempt_num = current_clarification_count(state) + 1
            attempt = ClarificationAttempt(
                attempt_number=attempt_num,
                question=question,
                question_category="clinical_evidence",
                missing_criteria=all_undetermined_questions[:5],
                status=ClarificationStatus.PENDING,
            )
            patch.update(mutations.with_clarification_sent(attempt, ctx))
            patch["workflow_phase"] = WorkflowPhase.CLARIFICATION
        else:
            # Build preliminary recommendation before human review
            prelim = self._build_preliminary_recommendation(
                evaluation_results, total_tokens
            )
            patch["recommendation"] = prelim
            patch["rationale"] = prelim.rationale
            patch["workflow_phase"] = WorkflowPhase.HUMAN_REVIEW

        return patch

    # ------------------------------------------------------------------
    # Policy evaluation
    # ------------------------------------------------------------------

    async def _evaluate_policy(
        self,
        policy,
        clinical_summary: str,
        nctx: NodeContext,
    ) -> tuple[EvaluationResult, int, list[str]]:
        """Evaluate all criteria in one policy.  Returns (result, tokens, questions)."""
        criteria_data = [
            {
                "criterion_id": chunk.chunk_id,
                "criterion_text": chunk.criterion_text,
                "criterion_type": chunk.criterion_type,
                "section": chunk.section_header,
            }
            for chunk in policy.criteria_chunks
        ]

        prompt = _USER_PROMPT_TEMPLATE.format(
            clinical_summary=clinical_summary[:6000],
            policy_id=policy.policy_id,
            policy_version=policy.policy_version,
            payer_name=policy.payer_name or "Unknown",
            criteria_json=json.dumps(criteria_data[:_MAX_CRITERIA_PER_CALL], indent=2),
        )

        raw, tokens = await self._call_llm(prompt)
        evaluations_data = raw.get("evaluations", [])

        criteria_evals: list[CriterionEvaluation] = []
        clarification_questions: list[str] = []

        for ed in evaluations_data:
            met_str = str(ed.get("met", "undetermined")).lower()
            met = {
                "yes": CriterionMet.YES,
                "no":  CriterionMet.NO,
            }.get(met_str, CriterionMet.UNDETERMINED)

            crit_eval = CriterionEvaluation(
                criterion_id=ed.get("criterion_id", ""),
                criterion_text=next(
                    (c.criterion_text for c in policy.criteria_chunks
                     if c.chunk_id == ed.get("criterion_id")),
                    ed.get("criterion_id", ""),
                ),
                met=met,
                confidence=float(ed.get("confidence", 0.5)),
                evidence=ed.get("evidence", []),
                notes=ed.get("notes"),
                requires_clarification=bool(ed.get("requires_clarification", False)),
            )
            criteria_evals.append(crit_eval)

            q = ed.get("clarification_question")
            if q and met == CriterionMet.UNDETERMINED:
                clarification_questions.append(q)

        result = EvaluationResult(
            policy_id=policy.policy_id,
            policy_version=policy.policy_version,
            criteria_evaluations=criteria_evals,
            model_used=_MODEL,
            tokens_used=tokens,
        )
        return result, tokens, clarification_questions

    # ------------------------------------------------------------------
    # LLM call with retry
    # ------------------------------------------------------------------

    @retry(
        retry=retry_if_exception_type((APITimeoutError, RateLimitError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    async def _call_llm(self, user_prompt: str) -> tuple[dict, int]:
        response = await self._get_client().chat.completions.create(
            model=_MODEL,
            temperature=_TEMPERATURE,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": user_prompt},
            ],
        )
        content = response.choices[0].message.content or "{}"
        tokens  = response.usage.total_tokens if response.usage else 0
        try:
            return json.loads(content), tokens
        except json.JSONDecodeError:
            return {}, tokens

    # ------------------------------------------------------------------
    # Helpers
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
                lines.append("ICD Codes: " + ", ".join(
                    c.code for c in entities.icd_codes
                ))

            if entities.cpt_codes:
                lines.append("CPT Codes: " + ", ".join(
                    c.code for c in entities.cpt_codes
                ))

            if entities.medications:
                lines.append("Medications: " + "; ".join(
                    f"{m.name} {m.dose or ''} {m.frequency or ''}".strip()
                    for m in entities.medications
                ))

            if entities.hba1c_readings:
                lines.append("HbA1c: " + ", ".join(
                    f"{h.value}% ({h.date or 'no date'})"
                    for h in entities.hba1c_readings
                ))

            if entities.lab_values:
                lines.append("Lab Values: " + "; ".join(
                    f"{lv.test_name} {lv.value} {lv.unit or ''}"
                    for lv in entities.lab_values[:8]
                ))

            if entities.symptoms:
                lines.append("Symptoms: " + "; ".join(
                    s.name for s in entities.symptoms
                ))

            if entities.treatment_history:
                lines.append("Treatment History: " + "; ".join(
                    t.treatment for t in entities.treatment_history[:5]
                ))

            # Clarification responses (if any)
            for attempt in state.get("clarification_attempts", []):
                if attempt.response and attempt.status.value == "answered":
                    lines.append(
                        f"[Clarification #{attempt.attempt_number}] "
                        f"Q: {attempt.question} "
                        f"A: {attempt.response}"
                    )

        return "\n".join(lines) if lines else "No clinical data available."

    @staticmethod
    def _consolidate_questions(questions: list[str]) -> str:
        """Combine multiple clarification questions into one coherent request."""
        if len(questions) == 1:
            return questions[0]
        bullet_list = "\n".join(f"• {q}" for q in questions[:5])
        return (
            "To complete the prior authorization review, please provide clarification "
            f"on the following:\n{bullet_list}"
        )

    @staticmethod
    def _build_preliminary_recommendation(
        evaluation_results: dict[str, EvaluationResult],
        tokens: int,
    ) -> PARecommendation:
        """
        Generate a preliminary PARecommendation from evaluation results.

        This is the AI's suggested decision before human review.
        """
        if not evaluation_results:
            return PARecommendation(
                recommendation_type=RecommendationType.PEND_FOR_INFO,
                confidence_score=0.0,
                rationale=["No policy criteria were evaluated."],
                requires_human_review=True,
                review_reason="No evaluation results available",
                tokens_used=tokens,
            )

        # Use the best-scored policy evaluation
        best_eval = max(evaluation_results.values(), key=lambda e: e.overall_score)

        total     = best_eval.criteria_total or 1
        met_frac  = best_eval.criteria_met / total
        undetermined_frac = best_eval.criteria_undetermined / total
        avg_conf  = (
            sum(c.confidence for c in best_eval.criteria_evaluations) / total
            if best_eval.criteria_evaluations else 0.5
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

        if met_frac >= 0.80 and undetermined_frac <= 0.10:
            rec_type    = RecommendationType.APPROVE
            rationale   = [
                f"Met {best_eval.criteria_met}/{total} criteria ({met_frac:.0%}).",
                f"Policy: {best_eval.policy_id} v{best_eval.policy_version}.",
                "Clinical evidence supports medical necessity.",
            ]
            confidence  = min(met_frac * avg_conf, 1.0)
        elif best_eval.criteria_not_met >= 2 or (best_eval.criteria_met == 0 and total > 0):
            rec_type    = RecommendationType.DENY
            rationale   = [
                f"Only {best_eval.criteria_met}/{total} criteria met.",
                f"{best_eval.criteria_not_met} criteria explicitly not met.",
                "Clinical evidence does not support medical necessity.",
            ]
            confidence  = min((1.0 - met_frac) * avg_conf, 1.0)
        else:
            rec_type    = RecommendationType.PEND_FOR_INFO
            rationale   = [
                f"{best_eval.criteria_undetermined} criteria undetermined.",
                "Additional clinical documentation may be needed.",
            ]
            confidence  = 0.5

        requires_review = avg_conf < _MIN_CONFIDENCE_FOR_AUTO or undetermined_frac > 0.20

        return PARecommendation(
            recommendation_type=rec_type,
            confidence_score=round(confidence, 4),
            rationale=rationale,
            supporting_criteria=supporting[:5],
            conflicting_criteria=conflicting[:5],
            evidence_references=[
                e for c in best_eval.criteria_evaluations for e in c.evidence[:2]
            ][:10],
            requires_human_review=requires_review,
            review_reason=(
                f"AI confidence {confidence:.0%} — below {_MIN_CONFIDENCE_FOR_AUTO:.0%} threshold"
                if requires_review else None
            ),
            model_used=_MODEL,
            tokens_used=tokens,
        )


# Module-level callable
reasoning_node = ReasoningNode()
