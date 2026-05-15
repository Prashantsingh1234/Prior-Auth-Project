"""
Evaluation framework data models.

Core types for the AI model evaluation system:

  EvalMetric               — single scored metric with pass/fail status
  ModelEvalResult          — all metrics for one model × one input
  EvaluationRun            — a full run (N models × M cases)
  RoutingDecision          — router's model selection + rationale
  BenchmarkCase            — a labeled test case
  BenchmarkDataset         — versioned collection of test cases
  ModelPerformanceSummary  — aggregated rolling-window stats per model
  TokenUsage               — prompt + completion token accounting
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class ModelTier(str, Enum):
    """Processing tier — maps to cost/capability trade-off."""
    FAST   = "fast"    # haiku-class: high volume, simple tasks
    MEDIUM = "medium"  # sonnet-class: balanced accuracy/cost
    STRONG = "strong"  # opus-class: complex reasoning, edge cases


class CaseComplexity(str, Enum):
    """Estimated complexity of a PA case."""
    LOW      = "low"
    MEDIUM   = "medium"
    HIGH     = "high"
    CRITICAL = "critical"


class EvalDomain(str, Enum):
    """Which pipeline/domain this evaluation covers."""
    EXTRACTION    = "extraction"
    RETRIEVAL     = "retrieval"
    REASONING     = "reasoning"
    CLARIFICATION = "clarification"
    END_TO_END    = "end_to_end"


class RoutingReason(str, Enum):
    """Why the router selected a specific model."""
    DEFAULT              = "default"
    COMPLEXITY_UPGRADE   = "complexity_upgrade"
    PERFORMANCE_DOWNGRADE = "performance_downgrade"
    PERFORMANCE_UPGRADE  = "performance_upgrade"
    COST_EFFICIENCY      = "cost_efficiency"
    POLICY_OVERRIDE      = "policy_override"
    FALLBACK             = "fallback"


# ---------------------------------------------------------------------------
# Core metric container
# ---------------------------------------------------------------------------

@dataclass
class EvalMetric:
    """
    A single scored evaluation metric.

    value:     0.0–1.0 (higher is always better — callers invert if needed)
    threshold: minimum acceptable value for `passed` to be True
    weight:    relative importance in composite score computation
    """
    name:      str
    value:     float
    threshold: float
    weight:    float = 1.0
    details:   dict[str, Any] = field(default_factory=dict)
    # Populated in __post_init__
    passed:    bool = field(init=False)

    def __post_init__(self) -> None:
        self.passed = self.value >= self.threshold

    def weighted_value(self) -> float:
        return self.value * self.weight


# ---------------------------------------------------------------------------
# Token + cost accounting
# ---------------------------------------------------------------------------

@dataclass
class TokenUsage:
    prompt_tokens:     int = 0
    completion_tokens: int = 0

    @property
    def total(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def cost_usd(
        self,
        cost_per_1k_prompt: float,
        cost_per_1k_completion: float,
    ) -> float:
        return (
            self.prompt_tokens     / 1_000 * cost_per_1k_prompt
            + self.completion_tokens / 1_000 * cost_per_1k_completion
        )


# ---------------------------------------------------------------------------
# Per-run result
# ---------------------------------------------------------------------------

@dataclass
class ModelEvalResult:
    """
    Evaluation result for a single model on a single input.

    Aggregates all metrics produced by all evaluators for that run.
    """
    run_id:           str
    model_id:         str
    model_tier:       ModelTier
    domain:           EvalDomain
    case_id:          str | None = None
    latency_ms:       float = 0.0
    token_usage:      TokenUsage = field(default_factory=TokenUsage)
    metrics:          dict[str, EvalMetric] = field(default_factory=dict)
    error:            str | None = None
    evaluated_at:     datetime = field(default_factory=datetime.utcnow)
    # Raw output stored for traceability / human review
    raw_output:       str | None = None
    # LangSmith run URL for cross-referencing in the observability layer
    langsmith_run_id: str | None = None

    def add_metric(self, metric: EvalMetric) -> None:
        self.metrics[metric.name] = metric

    @property
    def overall_score(self) -> float:
        """Weighted average across all collected metrics."""
        if not self.metrics:
            return 0.0
        total_weight = sum(m.weight for m in self.metrics.values())
        if total_weight == 0:
            return 0.0
        return sum(m.weighted_value() for m in self.metrics.values()) / total_weight

    @property
    def passed_all(self) -> bool:
        return all(m.passed for m in self.metrics.values())

    @property
    def failed_metrics(self) -> list[EvalMetric]:
        return [m for m in self.metrics.values() if not m.passed]

    def metric_value(self, name: str, default: float = 0.0) -> float:
        m = self.metrics.get(name)
        return m.value if m else default


# ---------------------------------------------------------------------------
# Full evaluation run
# ---------------------------------------------------------------------------

@dataclass
class EvaluationRun:
    """
    A full evaluation run: one or more models evaluated on a dataset.

    One EvaluationRun is created per pipeline execution.  Results accumulate
    via add_result() and are persisted to the metrics store on completion.
    """
    run_id:        str = field(default_factory=lambda: str(uuid.uuid4()))
    pipeline_name: str = ""
    dataset_name:  str = ""
    domain:        EvalDomain = EvalDomain.END_TO_END
    results:       list[ModelEvalResult] = field(default_factory=list)
    started_at:    datetime = field(default_factory=datetime.utcnow)
    completed_at:  datetime | None = None
    metadata:      dict[str, Any] = field(default_factory=dict)

    def add_result(self, result: ModelEvalResult) -> None:
        self.results.append(result)

    def results_for_model(self, model_id: str) -> list[ModelEvalResult]:
        return [r for r in self.results if r.model_id == model_id]

    def best_model(self, metric_name: str | None = None) -> str | None:
        """Return the model_id with the highest overall (or metric-specific) score."""
        if not self.results:
            return None
        if metric_name:
            scored = [
                (r.model_id, r.metric_value(metric_name))
                for r in self.results
                if metric_name in r.metrics
            ]
        else:
            scored = [(r.model_id, r.overall_score) for r in self.results]
        return max(scored, key=lambda x: x[1])[0] if scored else None

    def summary(self) -> dict[str, Any]:
        by_model: dict[str, list[float]] = {}
        for r in self.results:
            by_model.setdefault(r.model_id, []).append(r.overall_score)
        return {
            "run_id":    self.run_id,
            "pipeline":  self.pipeline_name,
            "dataset":   self.dataset_name,
            "models": {
                model: {
                    "avg_score": round(sum(s) / len(s), 4),
                    "min_score": round(min(s), 4),
                    "max_score": round(max(s), 4),
                    "runs":      len(s),
                }
                for model, s in by_model.items()
            },
        }


# ---------------------------------------------------------------------------
# Router output
# ---------------------------------------------------------------------------

@dataclass
class RoutingDecision:
    """Record of a single model routing decision."""
    model_id:        str
    model_tier:      ModelTier
    reason:          RoutingReason
    case_complexity: CaseComplexity
    confidence:      float                          # 0.0–1.0
    scores:          dict[str, float] = field(default_factory=dict)  # per-model composite
    decided_at:      datetime = field(default_factory=datetime.utcnow)
    policy_name:     str = "default"
    notes:           str = ""


# ---------------------------------------------------------------------------
# Benchmark dataset
# ---------------------------------------------------------------------------

class BenchmarkCase(BaseModel):
    """A single labeled test case."""
    case_id:   str = Field(default_factory=lambda: str(uuid.uuid4()))
    domain:    EvalDomain
    complexity: CaseComplexity = CaseComplexity.MEDIUM

    # --- Input ---
    input_text:   str
    context_docs: list[str] = Field(default_factory=list)
    query:        str | None = None

    # --- Ground truth ---
    expected_output:          str | None = None
    expected_entities:        dict[str, Any] = Field(default_factory=dict)
    expected_verdict:         str | None = None      # APPROVE / DENY / PEND
    ground_truth_policies:    list[str] = Field(default_factory=list)
    ground_truth_answer:      str | None = None

    # --- Metadata ---
    source:     str = "manual"   # manual / synthetic / production
    tags:       list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata:   dict[str, Any] = Field(default_factory=dict)


class BenchmarkDataset(BaseModel):
    """A versioned collection of benchmark cases."""
    dataset_id:           str = Field(default_factory=lambda: str(uuid.uuid4()))
    name:                 str
    description:          str = ""
    version:              str = "1.0.0"
    domain:               EvalDomain
    cases:                list[BenchmarkCase] = Field(default_factory=list)
    created_at:           datetime = Field(default_factory=datetime.utcnow)
    langsmith_dataset_id: str | None = None

    def add_case(self, case: BenchmarkCase) -> None:
        self.cases.append(case)

    def filter_by_complexity(self, complexity: CaseComplexity) -> list[BenchmarkCase]:
        return [c for c in self.cases if c.complexity == complexity]

    def size_by_complexity(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for c in self.cases:
            counts[c.complexity.value] = counts.get(c.complexity.value, 0) + 1
        return counts


# ---------------------------------------------------------------------------
# Aggregated model performance (used by router)
# ---------------------------------------------------------------------------

@dataclass
class ModelPerformanceSummary:
    """
    Rolling-window performance statistics for a single model.

    Populated by the metrics store from recent EvaluationRun results.
    The router reads this to decide whether to upgrade or downgrade a model.
    """
    model_id:   str
    model_tier: ModelTier
    window_hours: int = 24

    # --- Quality metrics (0.0–1.0, higher is better) ---
    accuracy:            float = 0.0
    hallucination_rate:  float = 0.0   # lower is better
    groundedness_score:  float = 0.0
    faithfulness_score:  float = 0.0
    retrieval_precision: float = 0.0
    retrieval_recall:    float = 0.0
    answer_relevancy:    float = 0.0
    reviewer_agreement:  float = 0.0
    decision_accuracy:   float = 0.0

    # --- Operational metrics ---
    avg_latency_ms:       float = 0.0
    p95_latency_ms:       float = 0.0
    avg_prompt_tokens:    float = 0.0
    avg_completion_tokens: float = 0.0
    avg_cost_usd:         float = 0.0

    # --- Quality/reliability flags ---
    json_validation_rate: float = 1.0   # fraction of valid JSON outputs
    escalation_rate:      float = 0.0
    fallback_rate:        float = 0.0

    # --- Volume ---
    total_runs:  int = 0
    error_count: int = 0

    updated_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def error_rate(self) -> float:
        return self.error_count / max(self.total_runs, 1)

    @property
    def composite_quality_score(self) -> float:
        """
        Weighted quality score for router ranking.

        Hallucination is weighted negatively and double-counted because
        in a healthcare context a hallucinated clinical claim can cause
        patient harm.
        """
        return (
            0.20 * self.accuracy
            + 0.20 * (1.0 - self.hallucination_rate)  # inverted
            + 0.15 * self.groundedness_score
            + 0.15 * self.faithfulness_score
            + 0.10 * self.reviewer_agreement
            + 0.10 * self.answer_relevancy
            + 0.05 * self.retrieval_precision
            + 0.05 * self.retrieval_recall
        )

    @property
    def cost_efficiency_score(self) -> float:
        """Quality-per-dollar proxy (higher = better value)."""
        if self.avg_cost_usd <= 0:
            return self.composite_quality_score
        return self.composite_quality_score / self.avg_cost_usd
