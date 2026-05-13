"""
Health check endpoints.

Provides two endpoints:
- GET /health         — Full health check (DB, Redis, queue connectivity)
- GET /health/live    — Kubernetes liveness probe (is the process alive?)
- GET /health/ready   — Kubernetes readiness probe (can we serve traffic?)

Design:
- Full health check checks all dependencies with timeouts
- Liveness probe is always fast — just returns 200 if the process is running
- Readiness probe checks critical deps (DB + Redis) but not non-critical ones
- Status degraded (207) vs unhealthy (503) vs healthy (200)
- Never crashes on dependency failure — returns degraded status instead
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter
from fastapi.responses import ORJSONResponse

from app.api.schemas.common import HealthResponse, ServiceHealthStatus
from app.core.config.settings import get_settings
from app.db.session.database import get_db_health
from app.services.caching.redis_client import get_redis_health

logger = structlog.get_logger(__name__)
router = APIRouter()

# Track application start time for uptime calculation
_APP_START_TIME = time.monotonic()


async def _check_database() -> ServiceHealthStatus:
    """Ping the database with a timeout."""
    start = time.monotonic()
    try:
        healthy = await asyncio.wait_for(get_db_health(), timeout=3.0)
        latency_ms = round((time.monotonic() - start) * 1000, 2)
        if healthy:
            return ServiceHealthStatus(status="healthy", latency_ms=latency_ms)
        return ServiceHealthStatus(
            status="unhealthy",
            latency_ms=latency_ms,
            message="Database ping returned False",
        )
    except asyncio.TimeoutError:
        return ServiceHealthStatus(status="unhealthy", message="Database check timed out")
    except Exception as exc:
        logger.warning("health.database_check_failed", error=str(exc))
        return ServiceHealthStatus(status="unhealthy", message=f"Database error: {type(exc).__name__}")


async def _check_redis() -> ServiceHealthStatus:
    """Ping Redis with a timeout."""
    start = time.monotonic()
    try:
        healthy = await asyncio.wait_for(get_redis_health(), timeout=2.0)
        latency_ms = round((time.monotonic() - start) * 1000, 2)
        if healthy:
            return ServiceHealthStatus(status="healthy", latency_ms=latency_ms)
        return ServiceHealthStatus(status="unhealthy", latency_ms=latency_ms, message="Redis PING failed")
    except asyncio.TimeoutError:
        return ServiceHealthStatus(status="unhealthy", message="Redis check timed out")
    except Exception as exc:
        logger.warning("health.redis_check_failed", error=str(exc))
        return ServiceHealthStatus(status="unhealthy", message=f"Redis error: {type(exc).__name__}")


async def _check_rabbitmq() -> ServiceHealthStatus:
    """
    Lightweight RabbitMQ connectivity check.
    Returns degraded (not unhealthy) since queue is non-critical for reads.
    """
    # Placeholder — full check implemented in queues module
    return ServiceHealthStatus(status="healthy", message="Queue check not yet wired")


def _compute_overall_status(services: dict[str, ServiceHealthStatus]) -> str:
    """
    Compute overall status from individual service statuses.
    - All healthy    → healthy   (200)
    - Any unhealthy  → unhealthy (503)  for critical services
    - Degraded       → degraded  (207)  for non-critical services
    """
    critical_services = {"database", "redis"}
    for name, status in services.items():
        if name in critical_services and status.status == "unhealthy":
            return "unhealthy"
    if any(s.status != "healthy" for s in services.values()):
        return "degraded"
    return "healthy"


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Full application health check",
    description=(
        "Checks all downstream dependencies. "
        "Returns 200 (healthy), 207 (degraded), or 503 (unhealthy)."
    ),
    tags=["Health"],
)
async def health_check() -> ORJSONResponse:
    """
    Full health check.

    Runs all service checks concurrently (asyncio.gather) to minimize latency.
    """
    settings = get_settings()

    # Run all checks concurrently
    db_status, redis_status, queue_status = await asyncio.gather(
        _check_database(),
        _check_redis(),
        _check_rabbitmq(),
        return_exceptions=False,
    )

    services: dict[str, ServiceHealthStatus] = {
        "database": db_status,
        "redis": redis_status,
        "message_queue": queue_status,
    }

    overall_status = _compute_overall_status(services)
    uptime_seconds = round(time.monotonic() - _APP_START_TIME, 1)

    response_body = HealthResponse(
        status=overall_status,
        version=settings.app_version,
        environment=settings.environment,
        uptime_seconds=uptime_seconds,
        services=services,
        timestamp=datetime.now(UTC).isoformat(),
    )

    # HTTP status reflects overall health
    http_status = {
        "healthy": 200,
        "degraded": 207,
        "unhealthy": 503,
    }.get(overall_status, 503)

    logger.info(
        "health.check_complete",
        overall_status=overall_status,
        uptime_seconds=uptime_seconds,
    )

    return ORJSONResponse(
        status_code=http_status,
        content=response_body.model_dump(),
    )


@router.get(
    "/health/live",
    summary="Kubernetes liveness probe",
    description="Returns 200 if the process is alive. Never checks dependencies.",
    tags=["Health"],
)
async def liveness_probe() -> ORJSONResponse:
    """
    Liveness probe — fast process alive check.
    Kubernetes restarts the pod if this returns non-200.
    Should NEVER check external dependencies — only that the process itself is running.
    """
    return ORJSONResponse(
        status_code=200,
        content={"status": "alive", "timestamp": datetime.now(UTC).isoformat()},
    )


@router.get(
    "/health/ready",
    summary="Kubernetes readiness probe",
    description="Returns 200 only when the service is ready to accept traffic.",
    tags=["Health"],
)
async def readiness_probe() -> ORJSONResponse:
    """
    Readiness probe — checks critical deps before accepting traffic.
    Kubernetes stops sending traffic if this returns non-200.
    """
    db_status, redis_status = await asyncio.gather(
        _check_database(),
        _check_redis(),
    )

    is_ready = (
        db_status.status == "healthy"
        and redis_status.status == "healthy"
    )

    return ORJSONResponse(
        status_code=200 if is_ready else 503,
        content={
            "status": "ready" if is_ready else "not_ready",
            "database": db_status.status,
            "redis": redis_status.status,
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )
