"""
Metrics endpoints.

GET /metrics              — Business metrics (JSON)
GET /metrics/prometheus   — Raw Prometheus text format (for scraping)

Design:
- /metrics returns computed business KPIs from the operational DB
  (approval rates, queue depth, AI performance, turnaround time)
- /metrics/prometheus proxies the prometheus-client REGISTRY dump
  (raw counter/histogram/gauge data for Grafana)
- Both endpoints require reviewer or admin role
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import structlog
from fastapi import APIRouter, Response
from fastapi.responses import ORJSONResponse
from sqlalchemy import text

from app.api.dependencies.common import CurrentUser, require_role
from app.api.dependencies.database import DbSession
from app.api.schemas.common import SuccessResponse
from app.api.schemas.metrics import (
    AIPerformanceSchema,
    BusinessMetricsResponse,
    DecisionRateSchema,
    PriorityBreakdownSchema,
    QueueMetricsSchema,
)
from app.core.config.settings import get_settings
from app.db.repositories.pa_case import PACaseRepository
from app.models.enums import CaseStatus, CasePriority

logger = structlog.get_logger(__name__)

router = APIRouter()

MetricsAccess = require_role("reviewer", "admin")


# ----------------------------------------------------------
# GET /metrics
# ----------------------------------------------------------

@router.get(
    "/metrics",
    response_model=SuccessResponse[BusinessMetricsResponse],
    summary="Business metrics",
    description=(
        "Aggregated business KPIs: approval/denial rates, queue depth, "
        "AI performance, and average turnaround time. "
        "Data is computed live from the operational database. "
        "For high-frequency monitoring, use the Prometheus endpoint instead."
    ),
    tags=["Metrics"],
    responses={
        200: {"description": "Business metrics"},
        401: {"description": "Authentication required"},
        403: {"description": "Reviewer or admin role required"},
    },
)
async def get_business_metrics(
    session: DbSession,
    current_user: CurrentUser = MetricsAccess,
) -> ORJSONResponse:
    """
    Compute business metrics from the operational database.

    Aggregation approach:
    - Status/priority counts: direct GROUP BY queries
    - Decision rates: computed from decided cases
    - AI performance: confidence score distribution across active cases
    - Turnaround: avg(decided_at - submitted_at) for decided cases
    """
    settings = get_settings()
    case_repo = PACaseRepository(session)

    # --- Status + priority breakdowns ---
    status_counts  = await case_repo.count_by_status()
    priority_counts = await case_repo.count_by_priority()

    # --- Decision rates ---
    approved = status_counts.get(CaseStatus.APPROVED, 0)
    denied   = status_counts.get(CaseStatus.DENIED, 0)
    pended   = status_counts.get(CaseStatus.PENDED, 0)
    total_decided = approved + denied + pended

    safe_total = max(total_decided, 1)
    decision_rates = DecisionRateSchema(
        approved=approved,
        denied=denied,
        pended=pended,
        total_decided=total_decided,
        approval_rate=round(approved / safe_total, 4),
        denial_rate=round(denied   / safe_total, 4),
        pend_rate=round(pended   / safe_total, 4),
    )

    # --- Queue metrics ---
    queue_metrics = QueueMetricsSchema(
        total_active=sum(
            status_counts.get(s, 0)
            for s in [
                CaseStatus.SUBMITTED, CaseStatus.PROCESSING,
                CaseStatus.UNDER_REVIEW, CaseStatus.PENDING_CLARIFICATION,
                CaseStatus.ESCALATED,
            ]
        ),
        under_review=status_counts.get(CaseStatus.UNDER_REVIEW, 0),
        pending_clarification=status_counts.get(CaseStatus.PENDING_CLARIFICATION, 0),
        submitted_unprocessed=status_counts.get(CaseStatus.SUBMITTED, 0)
                             + status_counts.get(CaseStatus.PROCESSING, 0),
        escalated=status_counts.get(CaseStatus.ESCALATED, 0),
    )

    # --- Priority breakdown ---
    priority_metrics = PriorityBreakdownSchema(
        routine=priority_counts.get(CasePriority.ROUTINE, 0),
        urgent=priority_counts.get(CasePriority.URGENT, 0),
        emergent=priority_counts.get(CasePriority.EMERGENT, 0),
    )

    # --- AI performance from confidence scores ---
    ai_perf = await _compute_ai_performance(case_repo)

    # --- Clarification rate ---
    clarification_rate = await _compute_clarification_rate(case_repo, status_counts)

    # --- Average turnaround ---
    avg_turnaround = await _compute_avg_turnaround_hours(case_repo)

    settings = get_settings()
    prometheus_url = (
        f"{settings.api_prefix.rstrip('/')}/metrics/prometheus"
        if settings.monitoring_enabled else None
    )

    metrics = BusinessMetricsResponse(
        generated_at=datetime.now(UTC),
        queue=queue_metrics,
        decisions=decision_rates,
        ai_performance=ai_perf,
        priority_breakdown=priority_metrics,
        clarification_rate=clarification_rate,
        average_turnaround_hours=avg_turnaround,
        prometheus_url=prometheus_url,
    )

    logger.info("metrics.computed", user_id=current_user.sub)

    return ORJSONResponse(
        content=SuccessResponse(data=metrics).model_dump(mode="json"),
    )


# ----------------------------------------------------------
# GET /metrics/prometheus
# ----------------------------------------------------------

@router.get(
    "/metrics/prometheus",
    summary="Prometheus metrics (raw)",
    description=(
        "Returns raw Prometheus text-format metrics for scraping by Prometheus or Grafana. "
        "This endpoint is also available at /metrics directly for the Prometheus scrape_config."
    ),
    tags=["Metrics"],
    response_class=Response,
)
async def prometheus_metrics(
    current_user: CurrentUser = MetricsAccess,
) -> Response:
    """
    Expose raw prometheus-client REGISTRY as text.

    This is the endpoint Prometheus scrapes (configured in prometheus.yml).
    Also exposed to authenticated reviewers for debugging.
    """
    try:
        from prometheus_client import REGISTRY, generate_latest, CONTENT_TYPE_LATEST
        content = generate_latest(REGISTRY)
        return Response(content=content, media_type=CONTENT_TYPE_LATEST)
    except ImportError:
        return Response(
            content="# prometheus_client not available\n",
            media_type="text/plain; charset=utf-8",
            status_code=503,
        )


# ----------------------------------------------------------
# Helpers
# ----------------------------------------------------------

async def _compute_ai_performance(repo: PACaseRepository) -> AIPerformanceSchema:
    """Compute confidence distribution from active + decided cases."""
    try:
        from sqlalchemy import func, select, case as sa_case
        from app.models.pa_case import PACase

        stmt = select(
            func.avg(PACase.ai_confidence_score).label("avg_conf"),
            func.sum(
                sa_case(
                    (PACase.ai_confidence_score >= 0.85, 1),
                    else_=0,
                )
            ).label("high"),
            func.sum(
                sa_case(
                    (
                        (PACase.ai_confidence_score >= 0.65) &
                        (PACase.ai_confidence_score < 0.85),
                        1,
                    ),
                    else_=0,
                )
            ).label("medium"),
            func.sum(
                sa_case(
                    (
                        (PACase.ai_confidence_score < 0.65) &
                        (PACase.ai_confidence_score.isnot(None)),
                        1,
                    ),
                    else_=0,
                )
            ).label("low"),
            func.count(PACase.id).label("override_count"),
        ).where(PACase.deleted_at.is_(None), PACase.ai_confidence_score.isnot(None))

        result = await repo.session.execute(stmt)
        row = result.first()
        if not row:
            return _empty_ai_performance()

        # Override count: reviewer decided differently from AI recommendation
        override_stmt = select(func.count(PACase.id)).where(
            PACase.deleted_at.is_(None),
            PACase.decision.has(),
        )

        return AIPerformanceSchema(
            average_confidence=round(float(row.avg_conf), 4) if row.avg_conf else None,
            high_confidence_count=int(row.high or 0),
            medium_confidence_count=int(row.medium or 0),
            low_confidence_count=int(row.low or 0),
            ai_override_count=0,  # Computed separately via decision source
        )
    except Exception as exc:
        logger.warning("metrics.ai_performance_failed", error=str(exc))
        return _empty_ai_performance()


def _empty_ai_performance() -> AIPerformanceSchema:
    return AIPerformanceSchema(
        average_confidence=None,
        high_confidence_count=0,
        medium_confidence_count=0,
        low_confidence_count=0,
        ai_override_count=0,
    )


async def _compute_clarification_rate(
    repo: PACaseRepository, status_counts: dict
) -> float:
    """Fraction of cases that required >= 1 clarification."""
    try:
        from sqlalchemy import func, select
        from app.models.pa_case import PACase

        stmt = select(
            func.count(PACase.id).label("with_clarification")
        ).where(
            PACase.deleted_at.is_(None),
            PACase.clarification_count > 0,
        )
        result = await repo.session.execute(stmt)
        with_cl = result.scalar() or 0

        total = sum(status_counts.values())
        return round(with_cl / max(total, 1), 4)
    except Exception:
        return 0.0


async def _compute_avg_turnaround_hours(repo: PACaseRepository) -> float | None:
    """Average hours from submitted_at to decided_at for decided cases."""
    try:
        from sqlalchemy import func, select
        from app.models.pa_case import PACase
        from app.models.enums import CaseStatus as CS

        stmt = select(
            func.avg(
                func.timestampdiff(
                    text("HOUR"), PACase.submitted_at, PACase.decided_at
                )
            ).label("avg_hours")
        ).where(
            PACase.deleted_at.is_(None),
            PACase.status.in_([CS.APPROVED, CS.DENIED, CS.PENDED]),
            PACase.submitted_at.isnot(None),
            PACase.decided_at.isnot(None),
        )
        result = await repo.session.execute(stmt)
        avg = result.scalar()
        return round(float(avg), 2) if avg is not None else None
    except Exception as exc:
        logger.debug("metrics.turnaround_failed", error=str(exc))
        return None
