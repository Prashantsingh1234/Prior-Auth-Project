"""
Abstract evaluation pipeline.

All concrete pipelines (extraction, retrieval, reasoning, end-to-end)
inherit from EvaluationPipeline and override run_case().

Pipeline lifecycle:
  1. pipeline.run(dataset, model_ids)   — evaluates all cases × all models
  2. pipeline.compare_models(...)       — runs and returns ranked comparison
  3. Results accumulate in EvaluationRun and are persisted via the metrics store

Each pipeline is responsible for:
  - Calling the correct service/node (OCR, extraction, retrieval, reasoning)
  - Building EvalInput from the case and the service output
  - Delegating scoring to CompositeEvaluator
  - Logging runs to LangSmith
  - Emitting Prometheus metrics via observability hooks
"""

from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from typing import Any

import structlog

from app.evaluation.evaluators.composite import CompositeEvaluator
from app.evaluation.langsmith_client import LangSmithClient, get_langsmith_client
from app.evaluation.models import (
    BenchmarkCase,
    BenchmarkDataset,
    CaseComplexity,
    EvalDomain,
    EvaluationRun,
    ModelEvalResult,
    ModelTier,
    TokenUsage,
)

logger = structlog.get_logger(__name__)


class EvaluationPipeline(ABC):
    """
    Abstract base for evaluation pipelines.

    Subclasses must implement:
      run_case(case, model_id, model_tier) → ModelEvalResult

    The base class provides:
      run()           — iterate dataset × model_ids, call run_case()
      compare_models() — run() + summarise rankings
      _make_evaluator() — creates a CompositeEvaluator for the domain
    """

    domain: EvalDomain = EvalDomain.END_TO_END

    def __init__(
        self,
        langsmith_client: LangSmithClient | None = None,
    ) -> None:
        self._ls = langsmith_client or get_langsmith_client()

    @abstractmethod
    async def run_case(
        self,
        case: BenchmarkCase,
        model_id: str,
        model_tier: ModelTier,
        run_id: str,
    ) -> ModelEvalResult:
        """
        Execute the pipeline for a single case and model, return a scored result.

        Implementations must:
          1. Call the appropriate service with case inputs
          2. Measure latency and token usage
          3. Build an EvalInput from service output
          4. Call self._make_evaluator(run_id).evaluate(...)
          5. Return the ModelEvalResult
        """

    async def run(
        self,
        dataset: BenchmarkDataset,
        model_ids: list[str],
        model_tiers: dict[str, ModelTier] | None = None,
        max_cases: int | None = None,
    ) -> EvaluationRun:
        """
        Run all models against all cases in the dataset.

        Parameters
        ----------
        dataset:     benchmark dataset
        model_ids:   list of model IDs to evaluate
        model_tiers: optional model_id → tier mapping (defaults to MEDIUM)
        max_cases:   cap on number of cases (useful for quick smoke tests)
        """
        run = EvaluationRun(
            run_id=str(uuid.uuid4()),
            pipeline_name=type(self).__name__,
            dataset_name=dataset.name,
            domain=self.domain,
        )

        cases = dataset.cases[:max_cases] if max_cases else dataset.cases
        tiers = model_tiers or {}

        logger.info(
            "pipeline.run_started",
            pipeline=type(self).__name__,
            models=model_ids,
            cases=len(cases),
            run_id=run.run_id,
        )

        for case in cases:
            for model_id in model_ids:
                tier = tiers.get(model_id, ModelTier.MEDIUM)
                try:
                    result = await self.run_case(case, model_id, tier, run.run_id)
                    run.add_result(result)
                    logger.debug(
                        "pipeline.case_evaluated",
                        model=model_id,
                        case=case.case_id,
                        score=round(result.overall_score, 4),
                    )
                except Exception as exc:
                    logger.error(
                        "pipeline.case_failed",
                        model=model_id,
                        case=case.case_id,
                        error=str(exc),
                    )

        run.completed_at = __import__("datetime").datetime.utcnow()
        logger.info(
            "pipeline.run_complete",
            run_id=run.run_id,
            results=len(run.results),
            summary=run.summary(),
        )
        return run

    async def compare_models(
        self,
        dataset: BenchmarkDataset,
        model_ids: list[str],
        model_tiers: dict[str, ModelTier] | None = None,
    ) -> dict[str, Any]:
        """
        Run all models and return a ranked comparison dict.

        Returns
        -------
        {
            "run_id": ...,
            "best_model": "gpt-4o",
            "rankings": [
                {"model": "gpt-4o", "score": 0.91, "metrics": {...}},
                ...
            ],
        }
        """
        run = await self.run(dataset, model_ids, model_tiers)

        rankings = []
        for model_id in model_ids:
            results = run.results_for_model(model_id)
            if not results:
                continue
            avg_score = sum(r.overall_score for r in results) / len(results)
            avg_metrics: dict[str, float] = {}
            for r in results:
                for name, metric in r.metrics.items():
                    avg_metrics.setdefault(name, []).append(metric.value)  # type: ignore
            avg_metrics = {k: round(sum(v) / len(v), 4) for k, v in avg_metrics.items()}
            rankings.append({
                "model": model_id,
                "score": round(avg_score, 4),
                "metrics": avg_metrics,
                "cases": len(results),
            })

        rankings.sort(key=lambda x: x["score"], reverse=True)
        return {
            "run_id":     run.run_id,
            "best_model": rankings[0]["model"] if rankings else None,
            "rankings":   rankings,
        }

    def _make_evaluator(self, run_id: str) -> CompositeEvaluator:
        return CompositeEvaluator.for_domain(self.domain, run_id=run_id)
