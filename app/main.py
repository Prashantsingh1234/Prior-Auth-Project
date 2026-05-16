"""
FastAPI application factory.

Entry point for the PA Review Platform backend.

Architecture:
- create_application() is a factory function (not a module-level side effect)
  This makes the app importable in tests without starting the server
- Lifespan context manager handles all startup/shutdown infrastructure
- Middleware stack is registered in dependency order (outermost to innermost)
- Exception handlers are centralized in core/exceptions/handlers.py
- Routers are registered with versioned prefix /api/v1
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

from app.api.routes import health
from app.core.config.settings import get_settings
from app.core.exceptions.handlers import register_exception_handlers
from app.core.logging.setup import configure_logging
from app.db.session.database import close_db_connection, init_db_connection
from app.audit.middleware import AuditMiddleware
from app.audit.writer import get_audit_writer
from app.middleware.logging import RequestLoggingMiddleware
from app.middleware.security import SecurityHeadersMiddleware
from app.middleware.tracing import RequestTracingMiddleware
from app.monitoring.metrics import setup_metrics
from app.services.caching.redis_client import close_redis, init_redis
from app.tracing.config import configure_langsmith
from app.tracing.middleware import LangSmithTracingMiddleware
from app.guardrails.middleware import GuardrailMiddleware
from app.security.auth import auth_router, user_router

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan context manager.

    Startup:  initializes all infrastructure connections in order
    Shutdown: closes all connections gracefully in reverse order

    FastAPI calls this automatically via the lifespan= parameter.
    """
    startup_start = time.monotonic()

    # --- STARTUP ---

    # Logging must be configured first so subsequent startup logs are structured
    configure_logging()
    logger.info(
        "application.startup.begin",
        environment=get_settings().environment,
        version=get_settings().app_version,
    )

    # LangSmith — configure before DB init so env vars are set before any
    # LangChain imports that read LANGCHAIN_TRACING_V2 at import time
    try:
        langsmith_cfg = configure_langsmith()
        logger.info(
            "application.startup.langsmith_configured",
            active=langsmith_cfg.is_active,
            project=langsmith_cfg.project,
        )
    except Exception as exc:
        logger.warning("application.startup.langsmith_failed", error=str(exc))

    # Database connection pool
    try:
        await init_db_connection()
        logger.info("application.startup.database_ready")
    except Exception as exc:
        logger.error("application.startup.database_failed", error=str(exc), exc_info=exc)
        raise  # Cannot start without DB

    # Redis connection pool
    try:
        await init_redis()
        logger.info("application.startup.redis_ready")
    except Exception as exc:
        # Redis failure is logged but doesn't prevent startup
        # (cache is non-critical; app degrades gracefully)
        logger.warning("application.startup.redis_failed", error=str(exc))

    # Prometheus metrics registration
    setup_metrics(app)
    logger.info("application.startup.metrics_ready")

    # Audit writer — start after DB is ready (writer flushes to DB)
    try:
        await get_audit_writer().start()
        logger.info("application.startup.audit_writer_ready")
    except Exception as exc:
        # Audit writer failure is non-fatal: structlog fallback is always active
        logger.warning("application.startup.audit_writer_failed", error=str(exc))

    startup_duration = round(time.monotonic() - startup_start, 3)
    logger.info(
        "application.startup.complete",
        duration_seconds=startup_duration,
        version=get_settings().app_version,
    )

    # --- APPLICATION RUNS HERE ---
    yield

    # --- SHUTDOWN ---
    logger.info("application.shutdown.begin")

    # Audit writer — drain before closing DB to ensure all records are persisted
    try:
        await get_audit_writer().stop(drain_timeout=30.0)
        logger.info("application.shutdown.audit_writer_stopped")
    except Exception as exc:
        logger.warning("application.shutdown.audit_writer_stop_failed", error=str(exc))

    try:
        await close_redis()
        logger.info("application.shutdown.redis_closed")
    except Exception as exc:
        logger.warning("application.shutdown.redis_close_failed", error=str(exc))

    try:
        await close_db_connection()
        logger.info("application.shutdown.database_closed")
    except Exception as exc:
        logger.warning("application.shutdown.database_close_failed", error=str(exc))

    logger.info("application.shutdown.complete")


def create_application() -> FastAPI:
    """
    Application factory.

    Creates, configures, and returns the FastAPI instance.
    Called once at module load time to produce the `app` singleton.
    """
    settings = get_settings()

    app = FastAPI(
        title=settings.api_title,
        version=settings.app_version,
        description=(
            "AI-Assisted Prior Authorization Review Platform. "
            "Clinical decision support for insurance prior authorization workflows. "
            "AI recommendations are advisory only — human reviewers retain final authority."
        ),
        # Disable Swagger/ReDoc in production to reduce attack surface
        docs_url="/api/docs" if settings.docs_enabled else None,
        redoc_url="/api/redoc" if settings.docs_enabled else None,
        openapi_url="/api/openapi.json" if settings.docs_enabled else None,
        # Use orjson for 3-5x faster JSON serialization
        default_response_class=ORJSONResponse,
        # Lifespan replaces the deprecated on_event handlers
        lifespan=lifespan,
        # OpenAPI tags ordering
        openapi_tags=[
            {"name": "Health", "description": "Application health and readiness probes"},
            {"name": "PA Requests", "description": "Prior authorization submission and retrieval"},
            {"name": "Cases", "description": "PA case management"},
            {"name": "Review", "description": "Human reviewer workflow"},
            {"name": "Clarification", "description": "Clarification loop management"},
            {"name": "Metrics", "description": "Application metrics"},
        ],
    )

    # ----------------------------------------------------------
    # Middleware registration (outermost wrapper first)
    #
    # Execution order for incoming requests (top → bottom):
    #   1. TrustedHostMiddleware        — security boundary
    #   2. CORSMiddleware               — cross-origin headers
    #   3. SecurityHeadersMiddleware    — response hardening
    #   4. RequestTracingMiddleware     — inject request_id / trace_id
    #   5. LangSmithTracingMiddleware   — propagate X-LangSmith-Run-ID contextvar
    #   6. AuditMiddleware              — bind AuditContext, emit API_REQUEST record
    #   7. GuardrailMiddleware          — AI injection/jailbreak detection on HTTP bodies
    #   8. RequestLoggingMiddleware     — structured access logging
    #
    # LangSmithTracingMiddleware sits after RequestTracingMiddleware so the
    # request already has a trace_id, and before AuditMiddleware so LangSmith
    # run context is available when audit events are emitted.
    #
    # For responses, middleware executes in reverse order (bottom → top)
    # ----------------------------------------------------------

    # 1. Trusted host validation (production only — prevents Host header injection)
    if settings.is_production:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=settings.allowed_hosts,
        )

    # 2. CORS — must be before tracing/logging so preflight requests are handled
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Trace-ID", "X-LangSmith-Run-URL"],
    )

    # 3. Security headers — added to every response
    app.add_middleware(SecurityHeadersMiddleware)

    # 4. Request tracing — must come before LangSmith and audit so IDs are available
    app.add_middleware(RequestTracingMiddleware)

    # 5. LangSmith — propagate run-id contextvar; adds X-LangSmith-Run-URL to responses
    app.add_middleware(LangSmithTracingMiddleware)

    # 6. Audit — binds AuditContext to contextvars for the full request duration
    app.add_middleware(AuditMiddleware)

    # 7. AI guardrail middleware — scans POST/PUT/PATCH bodies for injection/jailbreak
    app.add_middleware(GuardrailMiddleware)

    # 8. Request/response logging — innermost, has full request context
    app.add_middleware(RequestLoggingMiddleware)

    # ----------------------------------------------------------
    # Exception handlers
    # ----------------------------------------------------------
    register_exception_handlers(app)

    # ----------------------------------------------------------
    # Routers
    # ----------------------------------------------------------
    app.include_router(
        health.router,
        prefix=settings.api_prefix,
        tags=["Health"],
    )

    # Auth and user management
    app.include_router(auth_router, prefix=settings.api_prefix)
    app.include_router(user_router, prefix=settings.api_prefix)

    # Future module routers — uncomment as each module is implemented:
    # from app.api.routes import pa_request, cases, review, clarification
    # app.include_router(pa_request.router, prefix=settings.api_prefix, tags=["PA Requests"])
    # app.include_router(cases.router, prefix=settings.api_prefix, tags=["Cases"])
    # app.include_router(review.router, prefix=settings.api_prefix, tags=["Review"])
    # app.include_router(clarification.router, prefix=settings.api_prefix, tags=["Clarification"])

    return app


# Create the application singleton
# This is imported by uvicorn/gunicorn: uvicorn app.main:app
app = create_application()


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.is_development,
        # Disable uvicorn's default logging — we use structlog
        log_config=None,
        # Disable uvicorn access log — handled by RequestLoggingMiddleware
        access_log=False,
        # Use uvloop for better async performance
        loop="uvloop",
        # Workers managed externally (Gunicorn or K8s replicas)
        workers=1,
    )
