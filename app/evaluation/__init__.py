"""
AI Evaluation Framework for the PA Review Platform.

Integrates LangSmith, DeepEval, and RAGAS to provide:
  - Automated evaluation of 11 quality metrics per model
  - Evaluator-driven model routing with auto up/downgrade
  - Benchmark datasets for all evaluation domains
  - Prometheus observability for all evaluation events

Quick start:

    from app.evaluation import get_evaluation_service, EvalDomain, CaseComplexity

    service = get_evaluation_service()

    # Route a case to the best model
    decision = await service.get_routing_decision(
        domain=EvalDomain.REASONING,
        complexity=CaseComplexity.HIGH,
    )
    model_id = decision.model_id

    # Run a benchmark
    run = await service.run_benchmark(
        pipeline_name="reasoning",
        model_ids=["gpt-4o", "claude-sonnet-4-6"],
    )
"""

from app.evaluation.models import (
    BenchmarkCase,
    BenchmarkDataset,
    CaseComplexity,
    EvalDomain,
    EvalMetric,
    EvaluationRun,
    ModelEvalResult,
    ModelPerformanceSummary,
    ModelTier,
    RoutingDecision,
    RoutingReason,
    TokenUsage,
)
from app.evaluation.service import EvaluationService, get_evaluation_service
from app.evaluation.routing.router import EvaluatorDrivenRouter, get_router
from app.evaluation.routing.policy import get_policy, POLICIES
from app.evaluation.routing.registry import ModelInfo, get_model_registry
from app.evaluation.datasets import BenchmarkDatasetManager, get_dataset_manager
from app.evaluation.langsmith_client import LangSmithClient, get_langsmith_client

__all__ = [
    # Models
    "BenchmarkCase",
    "BenchmarkDataset",
    "CaseComplexity",
    "EvalDomain",
    "EvalMetric",
    "EvaluationRun",
    "ModelEvalResult",
    "ModelPerformanceSummary",
    "ModelTier",
    "RoutingDecision",
    "RoutingReason",
    "TokenUsage",
    # Service
    "EvaluationService",
    "get_evaluation_service",
    # Routing
    "EvaluatorDrivenRouter",
    "get_router",
    "get_policy",
    "POLICIES",
    # Registry
    "ModelInfo",
    "get_model_registry",
    # Datasets
    "BenchmarkDatasetManager",
    "get_dataset_manager",
    # LangSmith
    "LangSmithClient",
    "get_langsmith_client",
]
