"""
Prometheus metrics for the evaluation framework.

Tracks:
  - Evaluation run counts by pipeline / model / domain
  - Per-metric score distributions (histograms)
  - Routing decision counts by reason / tier
  - Model downgrade / upgrade events
  - Evaluation latency
  - Token usage and cost per model

All metrics use the "eval_" prefix to avoid collisions with application metrics.
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# ---------------------------------------------------------------------------
# Evaluation run counters
# ---------------------------------------------------------------------------

EVAL_RUNS_TOTAL = Counter(
    "eval_runs_total",
    "Total evaluation runs started",
    ["pipeline", "domain"],
)

EVAL_CASES_TOTAL = Counter(
    "eval_cases_total",
    "Total individual cases evaluated",
    ["pipeline", "model_id", "domain"],
)

EVAL_CASE_ERRORS_TOTAL = Counter(
    "eval_case_errors_total",
    "Cases that failed with an error during evaluation",
    ["pipeline", "model_id"],
)

# ---------------------------------------------------------------------------
# Metric score histograms
# ---------------------------------------------------------------------------

_SCORE_BUCKETS = (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1.0)

EVAL_METRIC_SCORE = Histogram(
    "eval_metric_score",
    "Distribution of evaluation metric scores",
    ["metric_name", "model_id"],
    buckets=_SCORE_BUCKETS,
)

EVAL_OVERALL_SCORE = Histogram(
    "eval_overall_score",
    "Distribution of overall (composite) scores per model",
    ["model_id", "domain"],
    buckets=_SCORE_BUCKETS,
)

EVAL_METRIC_PASS_RATE = Gauge(
    "eval_metric_pass_rate",
    "Fraction of recent cases where metric passed threshold (rolling)",
    ["metric_name", "model_id"],
)

# ---------------------------------------------------------------------------
# Decision accuracy
# ---------------------------------------------------------------------------

EVAL_DECISION_ACCURACY = Gauge(
    "eval_decision_accuracy",
    "Rolling decision accuracy for a model",
    ["model_id"],
)

EVAL_REVIEWER_AGREEMENT = Gauge(
    "eval_reviewer_agreement",
    "Rolling reviewer agreement (exact match) for a model",
    ["model_id"],
)

EVAL_HALLUCINATION_RATE = Gauge(
    "eval_hallucination_rate",
    "Rolling hallucination rate (fraction of claims ungrounded)",
    ["model_id"],
)

EVAL_FAITHFULNESS_SCORE = Gauge(
    "eval_faithfulness_score",
    "Rolling faithfulness score",
    ["model_id"],
)

EVAL_GROUNDEDNESS_SCORE = Gauge(
    "eval_groundedness_score",
    "Rolling groundedness score",
    ["model_id"],
)

EVAL_JSON_VALIDATION_RATE = Gauge(
    "eval_json_validation_rate",
    "Fraction of outputs that are valid JSON",
    ["model_id"],
)

# ---------------------------------------------------------------------------
# Retrieval metrics
# ---------------------------------------------------------------------------

EVAL_RETRIEVAL_PRECISION = Gauge(
    "eval_retrieval_precision",
    "Rolling context precision for retrieval",
    ["model_id"],
)

EVAL_RETRIEVAL_RECALL = Gauge(
    "eval_retrieval_recall",
    "Rolling context recall for retrieval",
    ["model_id"],
)

# ---------------------------------------------------------------------------
# Routing metrics
# ---------------------------------------------------------------------------

ROUTING_DECISIONS_TOTAL = Counter(
    "eval_routing_decisions_total",
    "Total routing decisions by reason",
    ["reason", "model_id", "tier"],
)

MODEL_UPGRADES_TOTAL = Counter(
    "eval_model_upgrades_total",
    "Number of times a model was auto-upgraded",
    ["from_tier", "to_tier", "trigger_metric"],
)

MODEL_DOWNGRADES_TOTAL = Counter(
    "eval_model_downgrades_total",
    "Number of times a model was auto-downgraded",
    ["from_tier", "to_tier", "trigger_metric"],
)

# ---------------------------------------------------------------------------
# Latency and cost
# ---------------------------------------------------------------------------

_LATENCY_BUCKETS = (100, 250, 500, 1000, 2000, 5000, 10000, 20000, 30000, 60000)

EVAL_LATENCY_MS = Histogram(
    "eval_latency_ms",
    "Evaluation call latency in milliseconds (model inference only)",
    ["model_id", "domain"],
    buckets=_LATENCY_BUCKETS,
)

EVAL_TOKENS_TOTAL = Counter(
    "eval_tokens_total",
    "Total tokens consumed in evaluations",
    ["model_id", "token_type"],   # token_type: prompt | completion
)

EVAL_COST_USD_TOTAL = Counter(
    "eval_cost_usd_total",
    "Estimated USD cost of evaluation runs",
    ["model_id"],
)

# ---------------------------------------------------------------------------
# Escalation / fallback tracking
# ---------------------------------------------------------------------------

EVAL_ESCALATION_TOTAL = Counter(
    "eval_escalation_total",
    "Cases that resulted in human escalation",
    ["model_id", "reason"],
)

EVAL_FALLBACK_TOTAL = Counter(
    "eval_fallback_total",
    "Times a fallback evaluator was used instead of the primary backend",
    ["evaluator_name", "reason"],
)
