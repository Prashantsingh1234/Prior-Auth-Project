"""
Business metric exporters for the PA Review Platform.

Provides computed / derived metrics that cannot be expressed as simple
Prometheus counters or histograms at the point of observation:

  - Approval / denial / pend rates (rolling windows over decision counters)
  - Queue depth polling (set by WorkflowRunner after each state transition)
  - System health summary gauge
  - SLO target tracking

These exporters are called periodically by a background task registered
during application startup (see app/monitoring/tasks.py), or updated
inline at the point an event occurs.

Usage — inline update:
    from app.monitoring.exporters import record_decision, record_queue_depth
    record_decision("APPROVE")
    record_queue_depth("pa_workflow", pending_count)

Usage — background collector:
    from app.monitoring.exporters import run_metric_collection_loop
    asyncio.create_task(run_metric_collection_loop())
"""

from __future__ import annotations

import asyncio
import time
from typing import Literal

import structlog
from prometheus_client import Counter, Gauge, Histogram

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Decision rate metrics (separate from the workflow-level PA_DECISIONS_TOTAL
# which tracks post-review final decisions; these track AI recommendation rates)
# ---------------------------------------------------------------------------

_AI_RECOMMENDATION_TOTAL = Counter(
    "pa_ai_recommendation_total",
    "AI recommendation counts used to compute approval / denial rates",
    labelnames=["recommendation"],  # approve | deny | pend | refer
)

_APPROVAL_RATE_GAUGE = Gauge(
    "pa_approval_rate_ratio",
    "Rolling approval rate — approvals / (approvals + denials) over last scrape window",
)

_DENIAL_RATE_GAUGE = Gauge(
    "pa_denial_rate_ratio",
    "Rolling denial rate — denials / (approvals + denials) over last scrape window",
)

_PEND_RATE_GAUGE = Gauge(
    "pa_pend_rate_ratio",
    "Rolling pend rate — pends / total AI recommendations over last scrape window",
)

# Cumulative snapshots used for rate computation between scrape intervals
_snapshot: dict[str, float] = {
    "approve": 0.0,
    "deny": 0.0,
    "pend": 0.0,
    "refer": 0.0,
}

# ---------------------------------------------------------------------------
# Clarification frequency
# ---------------------------------------------------------------------------

_CLARIFICATION_RATE_GAUGE = Gauge(
    "pa_clarification_frequency_ratio",
    "Fraction of cases that required at least one clarification loop",
)

_clarification_snapshot: dict[str, float] = {
    "cases_total": 0.0,
    "cases_with_clarification": 0.0,
}

# ---------------------------------------------------------------------------
# System-error aggregate gauge
# ---------------------------------------------------------------------------

_SYSTEM_ERROR_GAUGE = Gauge(
    "pa_system_errors_active",
    "Number of unresolved system errors (LLM failures + DB errors + Redis errors)",
)

# ---------------------------------------------------------------------------
# SLO tracking
# ---------------------------------------------------------------------------

_SLO_LATENCY_P95_GAUGE = Gauge(
    "pa_slo_workflow_latency_p95_seconds",
    "Estimated p95 end-to-end workflow latency (updated each collection cycle)",
)

_SLO_AVAILABILITY_GAUGE = Gauge(
    "pa_slo_availability_ratio",
    "Fraction of requests returning 2xx/3xx over last collection window",
)

# ---------------------------------------------------------------------------
# Public helper functions (called inline by service code)
# ---------------------------------------------------------------------------


def record_decision(
    recommendation: Literal["approve", "deny", "pend", "refer"],
    *,
    source: Literal["ai", "reviewer_override"] = "ai",
) -> None:
    """Increment the AI recommendation counter and refresh rate gauges."""
    _AI_RECOMMENDATION_TOTAL.labels(recommendation=recommendation).inc()
    _snapshot[recommendation] = _snapshot.get(recommendation, 0.0) + 1.0
    _refresh_rate_gauges()


def record_clarification_event(*, required: bool) -> None:
    """
    Call once per case completion.

    required=True  → case needed a clarification loop
    required=False → case completed without clarification
    """
    _clarification_snapshot["cases_total"] += 1.0
    if required:
        _clarification_snapshot["cases_with_clarification"] += 1.0
    _refresh_clarification_gauge()


def record_queue_depth(queue_name: str, depth: int) -> None:
    """Set current queue backlog depth.  Thread-safe (GIL + atomic gauge.set)."""
    from app.monitoring.metrics import METRICS
    METRICS.queue_backlog.labels(queue_name=queue_name).set(depth)


def record_system_error(delta: int = 1) -> None:
    """Increment active system error counter."""
    _SYSTEM_ERROR_GAUGE.inc(delta)


def clear_system_error(delta: int = 1) -> None:
    """Decrement active system error counter (error resolved)."""
    _SYSTEM_ERROR_GAUGE.dec(delta)


# ---------------------------------------------------------------------------
# Internal gauge refresh helpers
# ---------------------------------------------------------------------------


def _refresh_rate_gauges() -> None:
    approve = _snapshot["approve"]
    deny    = _snapshot["deny"]
    pend    = _snapshot["pend"]
    refer   = _snapshot["refer"]
    decided = approve + deny
    total   = decided + pend + refer

    if decided > 0:
        _APPROVAL_RATE_GAUGE.set(approve / decided)
        _DENIAL_RATE_GAUGE.set(deny / decided)
    if total > 0:
        _PEND_RATE_GAUGE.set(pend / total)


def _refresh_clarification_gauge() -> None:
    total = _clarification_snapshot["cases_total"]
    with_clarification = _clarification_snapshot["cases_with_clarification"]
    if total > 0:
        _CLARIFICATION_RATE_GAUGE.set(with_clarification / total)


# ---------------------------------------------------------------------------
# Background metric collection loop (optional)
# ---------------------------------------------------------------------------

_COLLECTION_INTERVAL_SECONDS = 30


async def run_metric_collection_loop() -> None:
    """
    Long-running async task that refreshes computed gauges periodically.

    Start during application lifespan:
        asyncio.create_task(run_metric_collection_loop())
    """
    logger.info("monitoring.exporter_loop.started", interval_s=_COLLECTION_INTERVAL_SECONDS)
    while True:
        try:
            await _collect_once()
        except asyncio.CancelledError:
            logger.info("monitoring.exporter_loop.cancelled")
            return
        except Exception as exc:
            logger.warning("monitoring.exporter_loop.error", error=str(exc))
        await asyncio.sleep(_COLLECTION_INTERVAL_SECONDS)


async def _collect_once() -> None:
    """Refresh all derived / polled metrics in one pass."""
    _refresh_rate_gauges()
    _refresh_clarification_gauge()
    await _poll_queue_depths()
    await _poll_system_health()


async def _poll_queue_depths() -> None:
    """Poll Redis or DB for queue depths and update gauges."""
    try:
        from app.services.caching.redis_client import get_redis
        redis = get_redis()
        # Check pending workflow jobs stored as a sorted set
        pending = await redis.zcard("pa:workflow:pending")
        record_queue_depth("pa_workflow", int(pending or 0))

        clarification_pending = await redis.zcard("pa:clarification:pending")
        record_queue_depth("clarification", int(clarification_pending or 0))

        review_pending = await redis.zcard("pa:review:pending")
        record_queue_depth("human_review", int(review_pending or 0))
    except Exception as exc:
        logger.debug("monitoring.queue_poll.failed", error=str(exc))


async def _poll_system_health() -> None:
    """Check infrastructure connectivity and update system error gauge."""
    errors = 0

    # Redis connectivity
    try:
        from app.services.caching.redis_client import get_redis
        redis = get_redis()
        await redis.ping()
    except Exception:
        errors += 1

    # DB connectivity — cheap query
    try:
        from app.db.session.database import get_db_session
        async with get_db_session() as session:
            await session.execute(__import__("sqlalchemy", fromlist=["text"]).text("SELECT 1"))
    except Exception:
        errors += 1

    _SYSTEM_ERROR_GAUGE.set(errors)
