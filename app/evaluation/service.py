"""
EvaluationService — the main orchestration entry point.

Provides a single facade over:
  - Pipeline execution (run_benchmark, compare_models)
  - Evaluator-driven model routing (get_routing_decision)
  - Metric storage and retrieval (get_model_performance, refresh_summaries)
  - LangSmith experiment logging
  - Automated periodic evaluation (schedule_periodic_eval)

Usage:

    service = EvaluationService.default()

    # Get routing decision for a new case
    decision = await service.get_routing_decision(
        domain=EvalDomain.REASONING,
        complexity=CaseComplexity.HIGH,
    )
    model_to_use = decision.model_id

    # Run a benchmark
    run = await service.run_benchmark(
        pipeline_name="reasoning",
        dataset_name="seed_reasoning",
        model_ids=["gpt-4o", "claude-sonnet-4-6"],
    )

    # Get current performance for a model
    perf = await service.get_model_performance("gpt-4o")
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import structlog

from app.evaluation.datasets import BenchmarkDatasetManager, get_dataset_manager
from app.evaluation.langsmith_client import LangSmithClient, get_langsmith_client
from app.evaluation.models import (
    BenchmarkDataset,
    CaseComplexity,
    EvalDomain,
    EvaluationRun,
    ModelPerformanceSummary,
    RoutingDecision,
)
from app.evaluation.observability import on_eval_complete, on_run_complete, on_routing_decision
from app.evaluation.pipelines.end_to_end_pipeline import EndToEndEvaluationPipeline
from app.evaluation.pipelines.extraction_pipeline import ExtractionEvaluationPipeline
from app.evaluation.pipelines.reasoning_pipeline import ReasoningEvaluationPipeline
from app.evaluation.pipelines.retrieval_pipeline import RetrievalEvaluationPipeline
from app.evaluation.routing.registry import get_model_registry
from app.evaluation.routing.router import EvaluatorDrivenRouter, get_router
from app.evaluation.storage.metrics_store import EvaluationMetricsStore, get_metrics_store

logger = structlog.get_logger(__name__)

_PIPELINE_MAP = {
    "extraction":  ExtractionEvaluationPipeline,
    "retrieval":   RetrievalEvaluationPipeline,
    "reasoning":   ReasoningEvaluationPipeline,
    "end_to_end":  EndToEndEvaluationPipeline,
}

# Performance cache to avoid hammering the DB on every routing call
_PERF_CACHE_TTL_SECONDS = 900  # 15 minutes


class EvaluationService:
    """
    Orchestrates evaluation pipelines, routing, and metric storage.

    One instance per application process — access via EvaluationService.default().
    """

    def __init__(
        self,
        metrics_store: EvaluationMetricsStore,
        dataset_manager: BenchmarkDatasetManager,
        langsmith_client: LangSmithClient,
        router: EvaluatorDrivenRouter,
        policy_name: str = "default",
    ) -> None:
        self._store    = metrics_store
        self._datasets = dataset_manager
        self._ls       = langsmith_client
        self._router   = router
        self._policy   = policy_name

        # Rolling performance cache: model_id → (summary, fetched_at)
        self._perf_cache: dict[str, tuple[ModelPerformanceSummary, datetime]] = {}
        self._perf_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Model routing
    # ------------------------------------------------------------------

    async def get_routing_decision(
        self,
        domain: EvalDomain,
        complexity: CaseComplexity = CaseComplexity.MEDIUM,
        model_ids: list[str] | None = None,
    ) -> RoutingDecision:
        """
        Select the best model for a case based on live evaluation metrics.

        Parameters
        ----------
        domain:      The pipeline domain.
        complexity:  Case complexity estimate.
        model_ids:   Restrict to this set of model IDs (optional).
        """
        candidates = model_ids or [
            m.model_id
            for m in get_model_registry().models_for_domain(domain)
        ]

        summaries = await self._get_cached_performances(candidates, domain)
        decision  = self._router.route(domain, complexity, summaries)

        on_routing_decision(decision)
        return decision

    async def _get_cached_performances(
        self,
        model_ids: list[str],
        domain: EvalDomain,
    ) -> dict[str, ModelPerformanceSummary]:
        async with self._perf_lock:
            now  = datetime.utcnow()
            stale = [
                m for m in model_ids
                if m not in self._perf_cache
                or (now - self._perf_cache[m][1]).total_seconds() > _PERF_CACHE_TTL_SECONDS
            ]
            if stale:
                fresh = await self._store.get_all_model_performances(
                    stale, domain=domain
                )
                for model_id, summary in fresh.items():
                    self._perf_cache[model_id] = (summary, now)

            return {
                m: self._perf_cache[m][0]
                for m in model_ids
                if m in self._perf_cache
            }

    # ------------------------------------------------------------------
    # Benchmark execution
    # ------------------------------------------------------------------

    async def run_benchmark(
        self,
        pipeline_name: str,
        model_ids: list[str],
        dataset_name: str | None = None,
        dataset: BenchmarkDataset | None = None,
        max_cases: int | None = None,
    ) -> EvaluationRun:
        """
        Run a named pipeline against a dataset with one or more models.

        Either `dataset_name` (loads from disk/LangSmith) or `dataset`
        (explicit object) must be provided.
        """
        pipeline_cls = _PIPELINE_MAP.get(pipeline_name)
        if pipeline_cls is None:
            raise ValueError(
                f"Unknown pipeline '{pipeline_name}'. Available: {list(_PIPELINE_MAP)}"
            )

        if dataset is None:
            domain  = _pipeline_domain(pipeline_name)
            dataset = self._datasets.load_or_seed(
                domain, name=dataset_name or f"seed_{domain.value}"
            )

        pipeline = pipeline_cls(langsmith_client=self._ls)
        run      = await pipeline.run(dataset, model_ids, max_cases=max_cases)

        await on_run_complete(run, langsmith_client=self._ls, metrics_store=self._store)

        # Invalidate performance cache for evaluated models
        async with self._perf_lock:
            for model_id in model_ids:
                self._perf_cache.pop(model_id, None)

        return run

    async def compare_models(
        self,
        pipeline_name: str,
        model_ids: list[str],
        dataset_name: str | None = None,
        max_cases: int | None = None,
    ) -> dict[str, Any]:
        """Run benchmark and return a ranked comparison dict."""
        domain   = _pipeline_domain(pipeline_name)
        dataset  = self._datasets.load_or_seed(domain, name=dataset_name or f"seed_{domain.value}")
        pipeline_cls = _PIPELINE_MAP[pipeline_name]
        pipeline = pipeline_cls(langsmith_client=self._ls)
        return await pipeline.compare_models(dataset, model_ids)

    # ------------------------------------------------------------------
    # Performance queries
    # ------------------------------------------------------------------

    async def get_model_performance(
        self,
        model_id: str,
        domain: EvalDomain | None = None,
        window_hours: int = 24,
    ) -> ModelPerformanceSummary | None:
        """Return rolling-window performance stats for a model."""
        return await self._store.get_model_performance(model_id, domain, window_hours)

    async def refresh_performance_cache(
        self,
        domain: EvalDomain | None = None,
    ) -> None:
        """
        Proactively refresh the performance cache for all registered models.
        Call this on a schedule (e.g., every 15 minutes) to keep routing decisions fresh.
        """
        all_model_ids = [m.model_id for m in get_model_registry().all_models()]
        fresh = await self._store.get_all_model_performances(all_model_ids, domain)
        now   = datetime.utcnow()
        async with self._perf_lock:
            for model_id, summary in fresh.items():
                self._perf_cache[model_id] = (summary, now)
        logger.info(
            "eval_service.cache_refreshed",
            models=len(fresh),
            domain=domain.value if domain else "all",
        )

    # ------------------------------------------------------------------
    # Automated periodic evaluation
    # ------------------------------------------------------------------

    async def schedule_periodic_eval(
        self,
        interval_seconds: int = 3600,
        pipeline_name: str = "reasoning",
        model_ids: list[str] | None = None,
        max_cases: int = 20,
    ) -> None:
        """
        Background task: runs a benchmark on a schedule.

        Designed to run as an asyncio background task during app lifespan.
        Stops when the task is cancelled.

        Usage in lifespan:
            task = asyncio.create_task(
                service.schedule_periodic_eval(interval_seconds=3600)
            )
            yield
            task.cancel()
        """
        candidates = model_ids or [
            m.model_id
            for m in get_model_registry().models_for_domain(
                _pipeline_domain(pipeline_name)
            )
        ]
        while True:
            try:
                await asyncio.sleep(interval_seconds)
                logger.info("eval_service.periodic_eval_start", pipeline=pipeline_name)
                run = await self.run_benchmark(
                    pipeline_name=pipeline_name,
                    model_ids=candidates,
                    max_cases=max_cases,
                )
                logger.info(
                    "eval_service.periodic_eval_done",
                    run_id=run.run_id,
                    results=len(run.results),
                )
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("eval_service.periodic_eval_failed", error=str(exc))

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def default(cls, policy_name: str = "default") -> "EvaluationService":
        return cls(
            metrics_store=get_metrics_store(),
            dataset_manager=get_dataset_manager(langsmith_client=get_langsmith_client()),
            langsmith_client=get_langsmith_client(),
            router=get_router(policy_name),
            policy_name=policy_name,
        )


def _pipeline_domain(pipeline_name: str) -> EvalDomain:
    mapping = {
        "extraction": EvalDomain.EXTRACTION,
        "retrieval":  EvalDomain.RETRIEVAL,
        "reasoning":  EvalDomain.REASONING,
        "end_to_end": EvalDomain.END_TO_END,
    }
    return mapping.get(pipeline_name, EvalDomain.END_TO_END)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_service_instance: EvaluationService | None = None


def get_evaluation_service(policy_name: str = "default") -> EvaluationService:
    global _service_instance
    if _service_instance is None:
        _service_instance = EvaluationService.default(policy_name=policy_name)
    return _service_instance
