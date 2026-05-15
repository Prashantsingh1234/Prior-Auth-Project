"""
DecisionEngine — primary entry point for the PA decision service.

Orchestrates the full decision pipeline:
  1. Assemble DecisionInput from PAWorkflowState
  2. Run the deterministic rules engine (ALL PASS / ANY FAIL / MISSING INFO)
  3. Calculate multi-factor confidence score
  4. Determine human review routing
  5. Format structured rationale
  6. Convert to PARecommendation for workflow state storage
  7. Apply reviewer overrides when requested
  8. Emit structured audit log entries and Prometheus metrics

Usage (from decision_node.py):
    engine = DecisionEngine()
    result = await engine.decide(state)
    recommendation = engine.to_recommendation(result)

    # Override path
    override_request = OverrideRequest(reviewer_id=..., target_verdict=..., override_reason=...)
    override_decision = engine.apply_override(result, override_request)
    final_recommendation = engine.to_recommendation(override_decision.final_result)
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

import structlog

from app.services.decision.confidence import ConfidenceCalculator
from app.services.decision.models import (
    DecisionInput,
    DecisionResult,
    DecisionRuleType,
    DecisionVerdict,
    OverrideDecision,
    OverrideRequest,
)
from app.services.decision.override import OverrideHandler
from app.services.decision.rationale import RationaleFormatter
from app.services.decision.rules import DecisionRulesEngine

logger = structlog.get_logger(__name__)

# Confidence below which requires_human_review is always True
AUTO_DECISION_CONFIDENCE = 0.80


class DecisionEngine:
    """
    Deterministic, multi-factor PA decision engine.

    One instance can be reused across many cases — all state is per-call.
    """

    def __init__(
        self,
        rules_engine: DecisionRulesEngine | None = None,
        confidence_calculator: ConfidenceCalculator | None = None,
        rationale_formatter: RationaleFormatter | None = None,
        override_handler: OverrideHandler | None = None,
    ) -> None:
        self._rules       = rules_engine or DecisionRulesEngine()
        self._confidence  = confidence_calculator or ConfidenceCalculator()
        self._rationale   = rationale_formatter or RationaleFormatter()
        self._override    = override_handler or OverrideHandler()
        self._log         = structlog.get_logger(self.__class__.__name__)

    # ------------------------------------------------------------------
    # Primary async entry point
    # ------------------------------------------------------------------

    async def decide(
        self,
        state: dict,         # PAWorkflowState
        *,
        case_id: str | None = None,
    ) -> DecisionResult:
        """
        Run the full decision pipeline for one PA case.

        Reads from PAWorkflowState and returns a DecisionResult.
        The caller persists it via to_recommendation().
        """
        t0 = time.perf_counter()
        cid = case_id or state.get("case_id", "unknown")

        decision_input = self._assemble_input(state, cid)

        result = self._run_pipeline(decision_input)

        elapsed_ms = (time.perf_counter() - t0) * 1000
        self._log.info(
            "decision.engine.decided",
            case_id=cid,
            verdict=result.verdict.value,
            rule=result.rule_applied.value,
            confidence=result.confidence_score,
            requires_review=result.requires_human_review,
            latency_ms=round(elapsed_ms, 1),
        )
        self._track_decision_metrics(result)
        return result

    # ------------------------------------------------------------------
    # Override application
    # ------------------------------------------------------------------

    def apply_override(
        self,
        original: DecisionResult,
        request: OverrideRequest,
    ) -> OverrideDecision:
        """
        Apply a reviewer override to an existing DecisionResult.

        Returns an OverrideDecision — check override_applied and
        validation_errors before using final_result.
        """
        result = self._override.apply(original, request)
        if result.override_applied:
            self._track_override_metrics(
                original_verdict=original.verdict,
                new_verdict=result.final_result.verdict,
                reviewer_id=request.reviewer_id,
            )
        return result

    # ------------------------------------------------------------------
    # Conversion to workflow state model
    # ------------------------------------------------------------------

    @staticmethod
    def to_recommendation(result: DecisionResult):
        """
        Convert a DecisionResult → PARecommendation (workflow state model).

        This is the only place that knows about PARecommendation, keeping
        the decision engine itself free of LangGraph state dependencies.
        """
        from app.services.workflow.state.models import (
            PARecommendation,
            RecommendationType,
        )

        verdict_map = {
            DecisionVerdict.APPROVE:               RecommendationType.APPROVE,
            DecisionVerdict.DENY:                  RecommendationType.DENY,
            DecisionVerdict.PEND_FOR_INFO:         RecommendationType.PEND_FOR_INFO,
            DecisionVerdict.REFER_MEDICAL_DIRECTOR: RecommendationType.REFER_MEDICAL_DIRECTOR,
        }

        return PARecommendation(
            recommendation_type=verdict_map[result.verdict],
            confidence_score=result.confidence_score,
            rationale=result.rationale_lines,
            supporting_criteria=result.supporting_criteria,
            conflicting_criteria=result.denying_criteria,
            evidence_references=result.evidence_references,
            requires_human_review=result.requires_human_review,
            review_reason=result.review_reason,
            model_used=result.model_used or "decision_engine_v1",
            tokens_used=result.tokens_used,
        )

    # ------------------------------------------------------------------
    # Pipeline internals
    # ------------------------------------------------------------------

    @staticmethod
    def _assemble_input(state: dict, case_id: str) -> DecisionInput:
        """Build a DecisionInput from PAWorkflowState."""
        entities = state.get("extracted_entities", {})
        extraction_conf = 0.5
        if entities:
            confs = []
            for v in entities.values():
                conf = getattr(v, "overall_confidence", None)
                if conf is None and isinstance(v, dict):
                    conf = v.get("overall_confidence")
                if conf is not None:
                    confs.append(float(conf))
            if confs:
                extraction_conf = sum(confs) / len(confs)

        ai_rec = state.get("recommendation")
        model_used: str | None = None
        tokens_used = 0
        if ai_rec:
            model_used = getattr(ai_rec, "model_used", None)
            tokens_used = int(getattr(ai_rec, "tokens_used", 0) or 0)

        return DecisionInput(
            case_id=case_id,
            service_type=state.get("service_type", "") or "",
            evaluation_results=state.get("evaluation_results", {}),
            clarification_attempts=state.get("clarification_attempts", []),
            extraction_confidence=extraction_conf,
            prior_recommendation=ai_rec,
            model_used=model_used,
            tokens_used=tokens_used,
        )

    def _run_pipeline(self, inp: DecisionInput) -> DecisionResult:
        """Core synchronous pipeline: rules → confidence → routing → rationale."""

        # ── Step 1: Deterministic rules ──────────────────────────────────
        rule_match, criterion_decisions = self._rules.evaluate(inp.evaluation_results)
        policy_conflict = self._rules.check_policy_conflict(inp.evaluation_results)

        # ── Step 2: Confidence calculation ───────────────────────────────
        confidence = self._confidence.calculate(
            criterion_decisions=criterion_decisions,
            verdict=rule_match.verdict,
            rule_type=rule_match.rule_type,
            extraction_confidence=inp.extraction_confidence,
            policy_conflict=policy_conflict,
        )

        # ── Step 3: Human review routing ─────────────────────────────────
        requires_review, review_reason = self._confidence.requires_human_review(
            confidence, rule_match.verdict
        )

        # Policy conflict always flags for review
        if policy_conflict and not requires_review:
            requires_review = True
            review_reason = "Conflicting signals across evaluated policies"

        # Undetermined criteria with APPROVE verdict → always review
        if (
            rule_match.verdict == DecisionVerdict.APPROVE
            and rule_match.rule_type == DecisionRuleType.ALL_PASS
            and confidence.undetermined_count > 0
        ):
            requires_review = True
            review_reason = (
                review_reason
                or f"{confidence.undetermined_count} criteria remain undetermined"
            )

        # ── Step 4: Rationale formatting ─────────────────────────────────
        rationale_lines, supporting, denying, evidence = self._rationale.format(
            verdict=rule_match.verdict,
            rule_match=rule_match,
            criterion_decisions=criterion_decisions,
            confidence=confidence,
        )

        return DecisionResult(
            verdict=rule_match.verdict,
            rule_applied=rule_match.rule_type,
            confidence=confidence,
            criterion_decisions=criterion_decisions,
            rationale_lines=rationale_lines,
            supporting_criteria=supporting,
            denying_criteria=denying,
            evidence_references=evidence,
            requires_human_review=requires_review,
            review_reason=review_reason,
            policies_evaluated=len(inp.evaluation_results),
            criteria_total=len(criterion_decisions),
            model_used=inp.model_used,
            tokens_used=inp.tokens_used,
        )

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    @staticmethod
    def _track_decision_metrics(result: DecisionResult) -> None:
        try:
            from app.monitoring.metrics import (
                PA_DECISIONS_TOTAL,
                PA_RECOMMENDATIONS_TOTAL,
                REASONING_CONFIDENCE_SCORE,
            )
            verdict_label = result.verdict.value.upper()
            PA_DECISIONS_TOTAL.labels(
                decision=verdict_label,
                decision_source="ai",
            ).inc()
            PA_RECOMMENDATIONS_TOTAL.labels(
                recommendation_type=result.verdict.value,
            ).inc()
            REASONING_CONFIDENCE_SCORE.observe(result.confidence_score)
        except Exception:
            pass

    @staticmethod
    def _track_override_metrics(
        *,
        original_verdict: DecisionVerdict,
        new_verdict: DecisionVerdict,
        reviewer_id: str,
    ) -> None:
        try:
            from app.monitoring.metrics import (
                PA_DECISIONS_TOTAL,
                REVIEWER_OVERRIDES_TOTAL,
            )
            PA_DECISIONS_TOTAL.labels(
                decision=new_verdict.value.upper(),
                decision_source="reviewer_override",
            ).inc()
            REVIEWER_OVERRIDES_TOTAL.labels(
                original_ai_decision=original_verdict.value,
                reviewer_decision=new_verdict.value,
            ).inc()
        except Exception:
            pass


# Module-level singleton
_engine_instance: DecisionEngine | None = None


def get_decision_engine() -> DecisionEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = DecisionEngine()
    return _engine_instance
