"""
Composite evaluator — runs all domain evaluators in one pass.

CompositeEvaluator is the primary entry point for pipeline code.  It
fans out to all registered evaluators concurrently, collects every
EvalMetric, and assembles a complete ModelEvalResult.

Evaluator registration:
  All evaluators are instantiated once at module load (stateless, safe to
  share across coroutines).  The set can be restricted per domain using
  the `domains` parameter of CompositeEvaluator.__init__().

Concurrency:
  All evaluators run concurrently via asyncio.gather.  Total wall-clock
  time equals the slowest single evaluator rather than the sum.

JSON validation:
  An additional lightweight check measures what fraction of tool outputs
  are valid JSON — tracked as a separate EvalMetric.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any

import structlog

from app.evaluation.evaluators.base import BaseEvaluator, EvalInput
from app.evaluation.evaluators.decision import DecisionAccuracyEvaluator
from app.evaluation.evaluators.faithfulness import FaithfulnessEvaluator
from app.evaluation.evaluators.groundedness import GroundednessEvaluator
from app.evaluation.evaluators.hallucination import HallucinationEvaluator
from app.evaluation.evaluators.relevancy import AnswerRelevancyEvaluator
from app.evaluation.evaluators.retrieval import RetrievalEvaluator
from app.evaluation.evaluators.reviewer import ReviewerAgreementEvaluator
from app.evaluation.models import (
    EvalDomain,
    EvalMetric,
    ModelEvalResult,
    ModelTier,
    TokenUsage,
)

logger = structlog.get_logger(__name__)

# All available evaluators, keyed by name
_ALL_EVALUATORS: dict[str, BaseEvaluator] = {
    "hallucination":     HallucinationEvaluator(),
    "faithfulness":      FaithfulnessEvaluator(),
    "groundedness":      GroundednessEvaluator(),
    "retrieval":         RetrievalEvaluator(),
    "answer_relevancy":  AnswerRelevancyEvaluator(),
    "reviewer_agreement": ReviewerAgreementEvaluator(),
    "decision_accuracy": DecisionAccuracyEvaluator(),
}

# Default evaluator sets per domain
_DOMAIN_EVALUATORS: dict[EvalDomain, list[str]] = {
    EvalDomain.EXTRACTION:    ["hallucination", "faithfulness", "groundedness"],
    EvalDomain.RETRIEVAL:     ["retrieval", "answer_relevancy"],
    EvalDomain.REASONING:     [
        "hallucination", "faithfulness", "groundedness",
        "answer_relevancy", "reviewer_agreement", "decision_accuracy",
    ],
    EvalDomain.CLARIFICATION: ["hallucination", "faithfulness", "answer_relevancy"],
    EvalDomain.END_TO_END:    list(_ALL_EVALUATORS.keys()),
}


def _is_valid_json(text: str) -> bool:
    try:
        json.loads(text)
        return True
    except (json.JSONDecodeError, TypeError):
        return False


class CompositeEvaluator:
    """
    Runs all registered evaluators concurrently and returns a ModelEvalResult.

    Parameters
    ----------
    domain:
        Controls which evaluator subset is activated.
    evaluator_names:
        Optional override — explicitly name which evaluators to run.
        Ignored when None; overrides domain selection when provided.
    run_id:
        Shared run identifier (ties results to an EvaluationRun).
    """

    def __init__(
        self,
        domain: EvalDomain = EvalDomain.END_TO_END,
        evaluator_names: list[str] | None = None,
        run_id: str | None = None,
    ) -> None:
        self._run_id = run_id or str(uuid.uuid4())
        self._domain = domain

        if evaluator_names is not None:
            self._evaluators = {
                name: _ALL_EVALUATORS[name]
                for name in evaluator_names
                if name in _ALL_EVALUATORS
            }
        else:
            names = _DOMAIN_EVALUATORS.get(domain, list(_ALL_EVALUATORS.keys()))
            self._evaluators = {n: _ALL_EVALUATORS[n] for n in names}

    async def evaluate(
        self,
        inp: EvalInput,
        model_id: str,
        model_tier: ModelTier = ModelTier.MEDIUM,
        case_id: str | None = None,
        token_usage: TokenUsage | None = None,
        latency_ms: float = 0.0,
        langsmith_run_id: str | None = None,
    ) -> ModelEvalResult:
        """
        Fan out to all evaluators concurrently and assemble the result.

        Evaluator errors are captured as low-score EvalMetrics rather than
        propagating — the result is always complete.
        """
        t0 = time.monotonic()

        result = ModelEvalResult(
            run_id=self._run_id,
            model_id=model_id,
            model_tier=model_tier,
            domain=self._domain,
            case_id=case_id,
            latency_ms=latency_ms,
            token_usage=token_usage or TokenUsage(),
            raw_output=inp.generated_output or None,
            langsmith_run_id=langsmith_run_id,
        )

        # Run all evaluators concurrently
        tasks = [
            evaluator.evaluate_safe(inp)
            for evaluator in self._evaluators.values()
        ]
        metric_lists: list[list[EvalMetric]] = await asyncio.gather(*tasks)

        for metrics in metric_lists:
            for metric in metrics:
                result.add_metric(metric)

        # JSON validation check
        if inp.generated_output:
            result.add_metric(EvalMetric(
                name="json_validation",
                value=1.0 if _is_valid_json(inp.generated_output) else 0.0,
                threshold=0.9,
                weight=0.5,
                details={"checked": True},
            ))

        eval_time_ms = (time.monotonic() - t0) * 1000
        logger.debug(
            "composite_evaluator.complete",
            model=model_id,
            domain=self._domain.value,
            overall_score=round(result.overall_score, 4),
            metrics_count=len(result.metrics),
            eval_time_ms=round(eval_time_ms, 1),
        )

        return result

    @classmethod
    def for_domain(cls, domain: EvalDomain, run_id: str | None = None) -> "CompositeEvaluator":
        """Factory: create a CompositeEvaluator pre-configured for a domain."""
        return cls(domain=domain, run_id=run_id)
