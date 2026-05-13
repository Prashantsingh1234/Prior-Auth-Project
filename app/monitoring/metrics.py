"""
Prometheus metrics definitions and setup.

Registers custom metrics that are domain-specific to the PA Review Platform.
The prometheus-fastapi-instrumentator library handles generic HTTP metrics
(request count, latency histogram, in-progress gauge).

Custom metrics tracked here:
- OCR confidence scores
- LLM call latency and token usage
- Prior authorization decision distribution (approve/deny/pend)
- Clarification loop counts
- Policy retrieval latency
- Reviewer override rate
- Queue backlog size

Usage in service code:
    from app.monitoring.metrics import METRICS
    METRICS.ocr_confidence.observe(0.95)
    METRICS.pa_decisions_total.labels(decision="APPROVE").inc()
"""

from __future__ import annotations

import structlog
from fastapi import FastAPI
from prometheus_client import Counter, Gauge, Histogram, Summary
from prometheus_fastapi_instrumentator import Instrumentator

logger = structlog.get_logger(__name__)

# ----------------------------------------------------------
# Metric definitions
# ----------------------------------------------------------

# OCR
OCR_CONFIDENCE = Histogram(
    name="pa_ocr_confidence_score",
    documentation="OCR extraction confidence score (0.0–1.0)",
    labelnames=["provider"],  # azure | paddleocr
    buckets=[0.5, 0.6, 0.7, 0.75, 0.80, 0.85, 0.90, 0.95, 0.99, 1.0],
)

OCR_REQUESTS_TOTAL = Counter(
    name="pa_ocr_requests_total",
    documentation="Total OCR requests by provider and outcome",
    labelnames=["provider", "outcome"],  # outcome: success | fallback | failure
)

# LLM
LLM_LATENCY_SECONDS = Histogram(
    name="pa_llm_latency_seconds",
    documentation="LLM API call latency in seconds",
    labelnames=["operation"],  # extraction | reasoning | clarification
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0],
)

LLM_TOKENS_TOTAL = Counter(
    name="pa_llm_tokens_total",
    documentation="Total LLM tokens consumed",
    labelnames=["operation", "token_type"],  # token_type: prompt | completion
)

LLM_ERRORS_TOTAL = Counter(
    name="pa_llm_errors_total",
    documentation="LLM API errors by type",
    labelnames=["error_type"],  # timeout | rate_limit | api_error
)

# Prior Authorization Decisions
PA_DECISIONS_TOTAL = Counter(
    name="pa_decisions_total",
    documentation="Prior authorization decisions by outcome",
    labelnames=["decision", "decision_source"],  # decision: APPROVE|DENY|PEND, source: ai|reviewer_override
)

# Clarification Loops
CLARIFICATION_LOOPS_TOTAL = Counter(
    name="pa_clarification_loops_total",
    documentation="Clarification loop iterations by outcome",
    labelnames=["outcome"],  # resolved | escalated | max_exceeded
)

CLARIFICATION_ATTEMPTS = Histogram(
    name="pa_clarification_attempts",
    documentation="Number of clarification attempts per case",
    buckets=[1, 2, 3],
)

# Policy Retrieval
RETRIEVAL_LATENCY_SECONDS = Histogram(
    name="pa_retrieval_latency_seconds",
    documentation="Pinecone policy retrieval latency in seconds",
    labelnames=["retrieval_type"],  # semantic | hybrid
    buckets=[0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0],
)

RETRIEVAL_RESULTS_COUNT = Histogram(
    name="pa_retrieval_results_count",
    documentation="Number of policy chunks returned per retrieval",
    buckets=[0, 1, 2, 3, 5, 10, 20],
)

# Human Review
REVIEWER_OVERRIDES_TOTAL = Counter(
    name="pa_reviewer_overrides_total",
    documentation="Number of times reviewers overrode AI recommendations",
    labelnames=["original_ai_decision", "reviewer_decision"],
)

REVIEWER_LATENCY_SECONDS = Histogram(
    name="pa_reviewer_latency_seconds",
    documentation="Time between case assignment and reviewer decision",
    buckets=[60, 300, 900, 1800, 3600, 7200, 86400],
)

# Queue
QUEUE_BACKLOG = Gauge(
    name="pa_queue_backlog_size",
    documentation="Number of unprocessed PA requests in the message queue",
    labelnames=["queue_name"],
)

# Cases
PA_CASES_ACTIVE = Gauge(
    name="pa_cases_active",
    documentation="Number of PA cases currently in progress",
)

PA_CASE_PROCESSING_SECONDS = Histogram(
    name="pa_case_processing_seconds",
    documentation="End-to-end PA case processing time in seconds",
    buckets=[30, 60, 120, 300, 600, 1200, 1800, 3600],
)


class PAMetrics:
    """
    Convenience wrapper giving attribute-style access to all metrics.

    Import this singleton:
        from app.monitoring.metrics import METRICS
        METRICS.ocr_confidence.observe(score, labels=["azure"])
    """

    def __init__(self) -> None:
        self.ocr_confidence = OCR_CONFIDENCE
        self.ocr_requests_total = OCR_REQUESTS_TOTAL
        self.llm_latency_seconds = LLM_LATENCY_SECONDS
        self.llm_tokens_total = LLM_TOKENS_TOTAL
        self.llm_errors_total = LLM_ERRORS_TOTAL
        self.pa_decisions_total = PA_DECISIONS_TOTAL
        self.clarification_loops_total = CLARIFICATION_LOOPS_TOTAL
        self.clarification_attempts = CLARIFICATION_ATTEMPTS
        self.retrieval_latency_seconds = RETRIEVAL_LATENCY_SECONDS
        self.retrieval_results_count = RETRIEVAL_RESULTS_COUNT
        self.reviewer_overrides_total = REVIEWER_OVERRIDES_TOTAL
        self.reviewer_latency_seconds = REVIEWER_LATENCY_SECONDS
        self.queue_backlog = QUEUE_BACKLOG
        self.pa_cases_active = PA_CASES_ACTIVE
        self.pa_case_processing_seconds = PA_CASE_PROCESSING_SECONDS


# Module-level singleton
METRICS = PAMetrics()


def setup_metrics(app: FastAPI) -> None:
    """
    Register Prometheus metrics with the FastAPI application.

    Called once during application startup.
    Instruments generic HTTP metrics automatically and exposes /metrics endpoint.
    """
    settings_module = __import__("app.core.config.settings", fromlist=["get_settings"])
    settings = settings_module.get_settings()

    if not settings.prometheus_enabled:
        logger.info("metrics.prometheus_disabled")
        return

    Instrumentator(
        # Exclude health/readiness probes from HTTP metrics
        excluded_handlers=["/api/v1/health", "/api/v1/health/live", "/api/v1/health/ready"],
        # Include response body size in metrics
        body_handlers=[],
        # Group status codes (2xx, 4xx, 5xx) to reduce cardinality
        group_status_codes=False,
    ).instrument(app).expose(
        app,
        endpoint=settings.prometheus_endpoint,
        include_in_schema=False,
        tags=["Monitoring"],
    )

    logger.info(
        "metrics.prometheus_initialized",
        endpoint=settings.prometheus_endpoint,
    )
