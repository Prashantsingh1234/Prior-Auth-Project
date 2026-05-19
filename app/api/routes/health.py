"""Health check endpoints."""

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

logger = structlog.get_logger(__name__)
router = APIRouter()

_APP_START_TIME = time.monotonic()


async def _check_database() -> ServiceHealthStatus:
    start = time.monotonic()
    try:
        healthy = await asyncio.wait_for(get_db_health(), timeout=3.0)
        latency_ms = round((time.monotonic() - start) * 1000, 2)
        if healthy:
            return ServiceHealthStatus(status="healthy", latency_ms=latency_ms)
        return ServiceHealthStatus(status="unhealthy", latency_ms=latency_ms, message="Database ping returned False")
    except asyncio.TimeoutError:
        return ServiceHealthStatus(status="unhealthy", message="Database check timed out")
    except Exception as exc:
        logger.warning("health.database_check_failed", error=str(exc))
        return ServiceHealthStatus(status="unhealthy", message=f"Database error: {type(exc).__name__}")


@router.get("/health", response_model=HealthResponse, summary="Application health check", tags=["Health"])
async def health_check() -> ORJSONResponse:
    settings = get_settings()
    db_status = await _check_database()
    overall_status = "healthy" if db_status.status == "healthy" else "unhealthy"
    uptime_seconds = round(time.monotonic() - _APP_START_TIME, 1)

    response_body = HealthResponse(
        status=overall_status,
        version=settings.app_version,
        environment=settings.environment,
        uptime_seconds=uptime_seconds,
        services={"database": db_status},
        timestamp=datetime.now(UTC).isoformat(),
    )

    http_status = 200 if overall_status == "healthy" else 503
    logger.info("health.check_complete", overall_status=overall_status, uptime_seconds=uptime_seconds)
    return ORJSONResponse(status_code=http_status, content=response_body.model_dump())


@router.get("/health/live", summary="Liveness probe", tags=["Health"])
async def liveness_probe() -> ORJSONResponse:
    return ORJSONResponse(status_code=200, content={"status": "alive", "timestamp": datetime.now(UTC).isoformat()})


@router.get("/health/ready", summary="Readiness probe", tags=["Health"])
async def readiness_probe() -> ORJSONResponse:
    db_status = await _check_database()
    is_ready = db_status.status == "healthy"
    return ORJSONResponse(
        status_code=200 if is_ready else 503,
        content={"status": "ready" if is_ready else "not_ready", "database": db_status.status},
    )
