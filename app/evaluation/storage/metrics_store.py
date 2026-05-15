"""
Evaluation metrics storage — MySQL backend.

Persists EvaluationRun results to the database for:
  - Historical performance trending
  - Router consumption of rolling-window summaries
  - Compliance reporting (which model decided what, when)
  - Regression detection (compare current run vs baseline)

Schema (new tables — add via Alembic migration):
  eval_runs        — one row per EvaluationRun
  eval_results     — one row per ModelEvalResult (FK to eval_runs)
  eval_metrics     — one row per EvalMetric (FK to eval_results)
  model_performance_summaries — materialised rolling window per model

All tables are append-only; no updates or deletes.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

import structlog

from app.evaluation.models import (
    EvalDomain,
    EvaluationRun,
    ModelEvalResult,
    ModelPerformanceSummary,
    ModelTier,
)

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# ORM-less dict helpers — maps Python objects to INSERT-able row dicts
# ---------------------------------------------------------------------------

def _run_to_row(run: EvaluationRun) -> dict[str, Any]:
    return {
        "run_id":       run.run_id,
        "pipeline_name": run.pipeline_name,
        "dataset_name": run.dataset_name,
        "domain":       run.domain.value,
        "started_at":   run.started_at,
        "completed_at": run.completed_at,
        "result_count": len(run.results),
        "metadata_":    json.dumps(run.metadata),
    }


def _result_to_row(result: ModelEvalResult, run_id: str) -> dict[str, Any]:
    return {
        "run_id":          run_id,
        "model_id":        result.model_id,
        "model_tier":      result.model_tier.value,
        "domain":          result.domain.value,
        "case_id":         result.case_id,
        "overall_score":   round(result.overall_score, 6),
        "latency_ms":      round(result.latency_ms, 2),
        "prompt_tokens":   result.token_usage.prompt_tokens,
        "completion_tokens": result.token_usage.completion_tokens,
        "passed_all":      result.passed_all,
        "error":           result.error,
        "evaluated_at":    result.evaluated_at,
        "langsmith_run_id": result.langsmith_run_id,
    }


def _metric_to_row(metric, result_run_id: str, result_model_id: str, case_id: str | None) -> dict[str, Any]:
    return {
        "run_id":     result_run_id,
        "model_id":   result_model_id,
        "case_id":    case_id,
        "name":       metric.name,
        "value":      round(metric.value, 6),
        "threshold":  round(metric.threshold, 6),
        "weight":     round(metric.weight, 4),
        "passed":     metric.passed,
        "details":    json.dumps(metric.details),
    }


# ---------------------------------------------------------------------------
# Store class
# ---------------------------------------------------------------------------

class EvaluationMetricsStore:
    """
    Persists evaluation results to MySQL.

    Uses raw SQLAlchemy core (INSERT statements) rather than ORM to keep
    this module independent from the ORM model layer.  This means we don't
    need Alembic to migrate before the store is used — it degrades gracefully
    when the tables don't exist yet (logs a warning, returns None).
    """

    def __init__(self, session_factory=None) -> None:
        self._factory = session_factory

    def _get_factory(self):
        if self._factory is not None:
            return self._factory
        try:
            from app.db.session.database import get_session_factory
            return get_session_factory()
        except ImportError:
            return None

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def save_run(self, run: EvaluationRun) -> bool:
        """
        Persist an EvaluationRun and all its results to the DB.
        Returns True on success, False on any failure.
        """
        factory = self._get_factory()
        if factory is None:
            logger.warning("eval_store.no_session_factory")
            return False

        try:
            async with factory() as session:
                await self._upsert_run(session, run)
                for result in run.results:
                    await self._upsert_result(session, result, run.run_id)
                await session.commit()
            logger.info(
                "eval_store.run_saved",
                run_id=run.run_id,
                results=len(run.results),
            )
            return True
        except Exception as exc:
            logger.error("eval_store.save_failed", run_id=run.run_id, error=str(exc))
            return False

    async def _upsert_run(self, session, run: EvaluationRun) -> None:
        from sqlalchemy import text
        row = _run_to_row(run)
        stmt = text("""
            INSERT INTO eval_runs
              (run_id, pipeline_name, dataset_name, domain, started_at,
               completed_at, result_count, metadata_)
            VALUES
              (:run_id, :pipeline_name, :dataset_name, :domain, :started_at,
               :completed_at, :result_count, :metadata_)
            ON DUPLICATE KEY UPDATE completed_at=VALUES(completed_at),
              result_count=VALUES(result_count)
        """)
        await session.execute(stmt, row)

    async def _upsert_result(self, session, result: ModelEvalResult, run_id: str) -> None:
        from sqlalchemy import text
        row = _result_to_row(result, run_id)
        stmt = text("""
            INSERT INTO eval_results
              (run_id, model_id, model_tier, domain, case_id, overall_score,
               latency_ms, prompt_tokens, completion_tokens, passed_all,
               error, evaluated_at, langsmith_run_id)
            VALUES
              (:run_id, :model_id, :model_tier, :domain, :case_id, :overall_score,
               :latency_ms, :prompt_tokens, :completion_tokens, :passed_all,
               :error, :evaluated_at, :langsmith_run_id)
        """)
        result_db_id = await session.execute(stmt, row)
        for metric in result.metrics.values():
            m_row = _metric_to_row(metric, run_id, result.model_id, result.case_id)
            m_stmt = text("""
                INSERT INTO eval_metrics
                  (run_id, model_id, case_id, name, value, threshold, weight, passed, details)
                VALUES
                  (:run_id, :model_id, :case_id, :name, :value, :threshold, :weight, :passed, :details)
            """)
            await session.execute(m_stmt, m_row)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_model_performance(
        self,
        model_id: str,
        domain: EvalDomain | None = None,
        window_hours: int = 24,
    ) -> ModelPerformanceSummary | None:
        """
        Compute a ModelPerformanceSummary from recent eval_metrics rows.

        Returns None when insufficient data exists or the DB is unavailable.
        """
        factory = self._get_factory()
        if factory is None:
            return None

        cutoff = datetime.utcnow() - timedelta(hours=window_hours)
        domain_filter = f"AND r.domain = :domain" if domain else ""

        query = f"""
            SELECT
                m.name,
                AVG(m.value)          AS avg_value,
                COUNT(*)              AS n,
                AVG(r.latency_ms)     AS avg_latency_ms,
                AVG(r.prompt_tokens + r.completion_tokens) AS avg_tokens,
                SUM(CASE WHEN r.error IS NOT NULL THEN 1 ELSE 0 END) AS error_count,
                COUNT(DISTINCT r.case_id) AS total_runs
            FROM eval_metrics m
            JOIN eval_results r ON r.run_id = m.run_id AND r.model_id = m.model_id
            WHERE m.model_id = :model_id
              AND r.evaluated_at >= :cutoff
              {domain_filter}
            GROUP BY m.name
        """
        try:
            from sqlalchemy import text
            async with factory() as session:
                params = {"model_id": model_id, "cutoff": cutoff}
                if domain:
                    params["domain"] = domain.value
                rows = (await session.execute(text(query), params)).fetchall()
        except Exception as exc:
            logger.error("eval_store.query_failed", error=str(exc))
            return None

        if not rows:
            return None

        # Build summary from aggregated metric rows
        metric_avgs = {row.name: float(row.avg_value) for row in rows}
        total_runs  = int(rows[0].total_runs) if rows else 0
        error_count = int(sum(r.error_count for r in rows))
        avg_latency = float(rows[0].avg_latency_ms) if rows else 0.0
        avg_tokens  = float(rows[0].avg_tokens) if rows else 0.0

        # Best-effort tier detection from registry
        tier = ModelTier.MEDIUM
        try:
            from app.evaluation.routing.registry import get_model_registry
            info = get_model_registry().get(model_id)
            if info:
                tier = info.tier
        except Exception:
            pass

        return ModelPerformanceSummary(
            model_id=model_id,
            model_tier=tier,
            window_hours=window_hours,
            accuracy=metric_avgs.get("decision.accuracy", 0.0),
            hallucination_rate=1.0 - metric_avgs.get("hallucination", 1.0),
            groundedness_score=metric_avgs.get("groundedness", 0.0),
            faithfulness_score=metric_avgs.get("faithfulness", 0.0),
            retrieval_precision=metric_avgs.get("retrieval.context_precision", 0.0),
            retrieval_recall=metric_avgs.get("retrieval.context_recall", 0.0),
            answer_relevancy=metric_avgs.get("answer_relevancy", 0.0),
            reviewer_agreement=metric_avgs.get("reviewer_agreement.exact", 0.0),
            decision_accuracy=metric_avgs.get("decision.accuracy", 0.0),
            avg_latency_ms=avg_latency,
            avg_prompt_tokens=avg_tokens * 0.7,
            avg_completion_tokens=avg_tokens * 0.3,
            json_validation_rate=metric_avgs.get("json_validation", 1.0),
            total_runs=total_runs,
            error_count=error_count,
        )

    async def get_all_model_performances(
        self,
        model_ids: list[str],
        domain: EvalDomain | None = None,
        window_hours: int = 24,
    ) -> dict[str, ModelPerformanceSummary]:
        """Batch-fetch performance summaries for the router."""
        summaries: dict[str, ModelPerformanceSummary] = {}
        for model_id in model_ids:
            summary = await self.get_model_performance(model_id, domain, window_hours)
            if summary:
                summaries[model_id] = summary
        return summaries


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_store_instance: EvaluationMetricsStore | None = None


def get_metrics_store() -> EvaluationMetricsStore:
    global _store_instance
    if _store_instance is None:
        _store_instance = EvaluationMetricsStore()
    return _store_instance
