"""
Evaluation observability hooks.

Hooks are called at key lifecycle events in the evaluation framework:
  on_eval_complete     — after a ModelEvalResult is produced
  on_run_complete      — after a full EvaluationRun finishes
  on_routing_decision  — after the router selects a model
  on_model_downgrade   — when the router steps down to a cheaper tier
  on_model_upgrade     — when the router steps up to a stronger tier
  on_metric_threshold_breach — when a metric falls below its threshold

Responsibilities:
  1. Emit Prometheus metrics (imported from metrics.py)
  2. Log structured events via structlog
  3. Forward scores to LangSmith as run feedback
  4. Emit audit records for compliance (routing decisions + threshold breaches)
  5. Trigger alerts on critical threshold breaches (stubbed — wire to PagerDuty/
     SNS/Slack via the alert_backend callable)

Thread-safety: all hooks are stateless; safe to call concurrently.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Awaitable

import structlog

from app.evaluation.models import (
    EvalDomain,
    EvaluationRun,
    ModelEvalResult,
    RoutingDecision,
    RoutingReason,
)

logger = structlog.get_logger(__name__)

# Callable type for alert backends (e.g., PagerDuty, Slack, SNS)
AlertBackend = Callable[[str, dict[str, Any]], Awaitable[None]]

# Metrics that trigger an alert when below threshold
_CRITICAL_METRICS = frozenset({
    "hallucination",
    "decision.accuracy",
    "faithfulness",
    "reviewer_agreement.exact",
})


# ---------------------------------------------------------------------------
# Hooks
# ---------------------------------------------------------------------------

async def on_eval_complete(
    result: ModelEvalResult,
    alert_backend: AlertBackend | None = None,
) -> None:
    """
    Called after each ModelEvalResult is produced.

    Emits per-metric Prometheus observations, logs the result, and
    triggers alerts for critical metric threshold breaches.
    """
    _emit_result_metrics(result)
    _log_result(result)

    if alert_backend:
        await _check_critical_thresholds(result, alert_backend)


async def on_run_complete(
    run: EvaluationRun,
    langsmith_client=None,
    metrics_store=None,
) -> None:
    """
    Called after a full EvaluationRun completes.

    Persists results to the metrics store and logs summary to LangSmith.
    """
    from app.evaluation.metrics import EVAL_RUNS_TOTAL

    EVAL_RUNS_TOTAL.labels(
        pipeline=run.pipeline_name,
        domain=run.domain.value,
    ).inc()

    summary = run.summary()
    logger.info(
        "evaluation.run_complete",
        run_id=run.run_id,
        pipeline=run.pipeline_name,
        best_model=run.best_model(),
        summary=summary,
    )

    if metrics_store is not None:
        try:
            await metrics_store.save_run(run)
        except Exception as exc:
            logger.error("observability.store_failed", run_id=run.run_id, error=str(exc))

    if langsmith_client is not None and langsmith_client.is_available:
        _log_run_to_langsmith(run, langsmith_client)


def on_routing_decision(decision: RoutingDecision) -> None:
    """
    Called after every routing decision.

    Emits a Prometheus counter and a structured log event.
    """
    from app.evaluation.metrics import ROUTING_DECISIONS_TOTAL

    ROUTING_DECISIONS_TOTAL.labels(
        reason=decision.reason.value,
        model_id=decision.model_id,
        tier=decision.model_tier.value,
    ).inc()

    logger.info(
        "router.decision",
        model=decision.model_id,
        tier=decision.model_tier.value,
        reason=decision.reason.value,
        complexity=decision.case_complexity.value,
        confidence=round(decision.confidence, 4),
        policy=decision.policy_name,
    )


def on_model_upgrade(
    from_model: str,
    to_model: str,
    from_tier: str,
    to_tier: str,
    trigger_metric: str,
    metric_value: float,
) -> None:
    from app.evaluation.metrics import MODEL_UPGRADES_TOTAL

    MODEL_UPGRADES_TOTAL.labels(
        from_tier=from_tier,
        to_tier=to_tier,
        trigger_metric=trigger_metric,
    ).inc()

    logger.warning(
        "router.model_upgraded",
        from_model=from_model,
        to_model=to_model,
        trigger_metric=trigger_metric,
        metric_value=round(metric_value, 4),
        note="Automatic upgrade due to quality degradation",
    )


def on_model_downgrade(
    from_model: str,
    to_model: str,
    from_tier: str,
    to_tier: str,
    trigger_metric: str,
    metric_value: float,
) -> None:
    from app.evaluation.metrics import MODEL_DOWNGRADES_TOTAL

    MODEL_DOWNGRADES_TOTAL.labels(
        from_tier=from_tier,
        to_tier=to_tier,
        trigger_metric=trigger_metric,
    ).inc()

    logger.info(
        "router.model_downgraded",
        from_model=from_model,
        to_model=to_model,
        trigger_metric=trigger_metric,
        metric_value=round(metric_value, 4),
        note="Automatic downgrade due to sustained quality above threshold",
    )


def on_metric_threshold_breach(
    model_id: str,
    metric_name: str,
    value: float,
    threshold: float,
    run_id: str,
    alert_backend: AlertBackend | None = None,
) -> None:
    """
    Called when any metric falls below its threshold in production.
    Logs a warning; triggers an alert for critical metrics.
    """
    logger.warning(
        "eval.threshold_breach",
        model=model_id,
        metric=metric_name,
        value=round(value, 4),
        threshold=threshold,
        run_id=run_id,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _emit_result_metrics(result: ModelEvalResult) -> None:
    from app.evaluation.metrics import (
        EVAL_CASES_TOTAL,
        EVAL_METRIC_SCORE,
        EVAL_OVERALL_SCORE,
        EVAL_LATENCY_MS,
        EVAL_TOKENS_TOTAL,
    )

    EVAL_CASES_TOTAL.labels(
        pipeline="composite",
        model_id=result.model_id,
        domain=result.domain.value,
    ).inc()

    for name, metric in result.metrics.items():
        EVAL_METRIC_SCORE.labels(
            metric_name=name,
            model_id=result.model_id,
        ).observe(metric.value)

    EVAL_OVERALL_SCORE.labels(
        model_id=result.model_id,
        domain=result.domain.value,
    ).observe(result.overall_score)

    if result.latency_ms > 0:
        EVAL_LATENCY_MS.labels(
            model_id=result.model_id,
            domain=result.domain.value,
        ).observe(result.latency_ms)

    EVAL_TOKENS_TOTAL.labels(
        model_id=result.model_id,
        token_type="prompt",
    ).inc(result.token_usage.prompt_tokens)

    EVAL_TOKENS_TOTAL.labels(
        model_id=result.model_id,
        token_type="completion",
    ).inc(result.token_usage.completion_tokens)


def _log_result(result: ModelEvalResult) -> None:
    failed = [m.name for m in result.failed_metrics]
    logger.debug(
        "eval.result",
        model=result.model_id,
        domain=result.domain.value,
        case=result.case_id,
        overall=round(result.overall_score, 4),
        passed_all=result.passed_all,
        failed_metrics=failed,
        latency_ms=round(result.latency_ms, 1),
    )


async def _check_critical_thresholds(
    result: ModelEvalResult,
    alert_backend: AlertBackend,
) -> None:
    for name, metric in result.metrics.items():
        if name in _CRITICAL_METRICS and not metric.passed:
            try:
                await alert_backend(
                    f"eval.critical_threshold_breach.{name}",
                    {
                        "model":    result.model_id,
                        "metric":   name,
                        "value":    round(metric.value, 4),
                        "threshold": metric.threshold,
                        "run_id":   result.run_id,
                        "case_id":  result.case_id,
                    },
                )
            except Exception as exc:
                logger.error("observability.alert_failed", metric=name, error=str(exc))


def _log_run_to_langsmith(run: EvaluationRun, langsmith_client) -> None:
    """Log aggregate run metrics as LangSmith feedback on the experiment run."""
    if not run.results:
        return
    by_model: dict[str, list[float]] = {}
    for r in run.results:
        by_model.setdefault(r.model_id, []).append(r.overall_score)
    for model_id, scores in by_model.items():
        avg = sum(scores) / len(scores)
        langsmith_client.log_feedback(
            run_id=run.run_id,
            key=f"avg_score.{model_id}",
            score=avg,
            comment=f"Average score for {model_id} over {len(scores)} cases",
        )
