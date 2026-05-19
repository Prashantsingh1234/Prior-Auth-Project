"""
FastAPI application entry point.

PA Review Platform — backend for prior authorization workflow.
Architecture: FastAPI + MySQL + JWT auth.
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import ORJSONResponse
from starlette.responses import RedirectResponse

import app.models  # noqa: F401 — registers all ORM mappers before any query runs
from app.api.routes import health
from app.core.config.settings import get_settings
from app.core.exceptions.handlers import register_exception_handlers
from app.core.logging.setup import configure_logging
from app.db.session.database import close_db_connection, init_db_connection
from app.middleware.logging import RequestLoggingMiddleware
from app.middleware.security import SecurityHeadersMiddleware
from app.security.auth import auth_router, user_router

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    startup_start = time.monotonic()

    configure_logging()
    logger.info(
        "application.startup.begin",
        environment=get_settings().environment,
        version=get_settings().app_version,
    )

    try:
        await init_db_connection()
        logger.info("application.startup.database_ready")
    except Exception as exc:
        logger.error("application.startup.database_failed", error=str(exc), exc_info=exc)
        raise

    startup_duration = round(time.monotonic() - startup_start, 3)
    logger.info("application.startup.complete", duration_seconds=startup_duration)

    yield

    logger.info("application.shutdown.begin")

    try:
        await close_db_connection()
        logger.info("application.shutdown.database_closed")
    except Exception as exc:
        logger.warning("application.shutdown.database_close_failed", error=str(exc))

    logger.info("application.shutdown.complete")


def create_application() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="PA Review Platform",
        version=settings.app_version,
        description=(
            "Prior Authorization Review Platform. "
            "Supports providers submitting PA requests and reviewers making decisions. "
            "AI recommendations are advisory — reviewers retain final authority."
        ),
        docs_url=f"{settings.api_prefix}/docs" if settings.docs_enabled else None,
        redoc_url=f"{settings.api_prefix}/redoc" if settings.docs_enabled else None,
        openapi_url=f"{settings.api_prefix}/openapi.json" if settings.docs_enabled else None,
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
        openapi_tags=[
            {"name": "Health",        "description": "Health and readiness probes"},
            {"name": "Auth",          "description": "Authentication and session management"},
            {"name": "PA Requests",   "description": "Prior authorization submission"},
            {"name": "Cases",         "description": "Case management"},
            {"name": "Review",        "description": "Reviewer decision workflow"},
            {"name": "Clarification", "description": "Clarification requests between providers and reviewers"},
            {"name": "Policies",      "description": "Policy ingestion and embedding management"},
        ],
    )

    # ── Middleware (outermost first) ───────────────────────────────────────────
    # Back-compat redirects for older docs locations.
    if settings.docs_enabled and settings.api_prefix:
        @app.get("/docs", include_in_schema=False)
        async def _docs_redirect():
            return RedirectResponse(url=f"{settings.api_prefix}/docs")

        @app.get("/redoc", include_in_schema=False)
        async def _redoc_redirect():
            return RedirectResponse(url=f"{settings.api_prefix}/redoc")

        @app.get("/openapi.json", include_in_schema=False)
        async def _openapi_redirect():
            return RedirectResponse(url=f"{settings.api_prefix}/openapi.json")

    if settings.is_production:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestLoggingMiddleware)

    # ── Exception handlers ────────────────────────────────────────────────────
    register_exception_handlers(app)

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(health.router, prefix=settings.api_prefix, tags=["Health"])
    app.include_router(auth_router,   prefix=settings.api_prefix)
    app.include_router(user_router,   prefix=settings.api_prefix)

    from app.api.routes import pa_requests, cases, review, clarification, policies
    app.include_router(pa_requests.router,   prefix=settings.api_prefix)
    app.include_router(cases.router,         prefix=settings.api_prefix)
    app.include_router(review.router,        prefix=settings.api_prefix)
    app.include_router(clarification.router, prefix=settings.api_prefix)
    app.include_router(policies.router,      prefix=settings.api_prefix)

    return app


app = create_application()


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.is_development,
        log_config=None,
        access_log=False,
    )
