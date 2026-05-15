"""
Audit middleware for FastAPI/Starlette.

AuditMiddleware sits inside the existing middleware stack (after
RequestTracingMiddleware so request_id/trace_id are already set):

  TrustedHostMiddleware
  CORSMiddleware
  SecurityHeadersMiddleware
  RequestTracingMiddleware   ← injects request_id, trace_id
  AuditMiddleware            ← this file (NEW)
  RequestLoggingMiddleware

Responsibilities:
  1. Build an AuditContext from the incoming request (pulls request_id /
     trace_id injected by RequestTracingMiddleware from structlog contextvars).
  2. Bind that context to the audit contextvars for the duration of the request.
  3. On completion: emit an API_REQUEST audit record via the AuditWriter queue.
  4. Never block the response — audit write is fire-and-forget.

Skips:
  - Health/readiness probes (too noisy, not compliance-relevant)
  - Metrics scrape endpoint
  - OPTIONS preflight (CORS)

User identity:
  Extracts the caller's user_id from the X-User-ID request header (set by
  the auth layer upstream) or from a decoded JWT if present.  Falls back
  to None (anonymous / not-yet-authed).
"""

from __future__ import annotations

import time
from typing import Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.audit.context import (
    AuditContext,
    build_context_from_request,
    reset_audit_context,
    set_audit_context,
)
from app.audit.events import api_request_event
from app.audit.models import AuditActorType
from app.audit.writer import emit

logger = structlog.get_logger(__name__)

# Paths that are excluded from API-request audit records
_SKIP_PATHS = frozenset({
    "/api/v1/health",
    "/api/v1/health/live",
    "/api/v1/health/ready",
    "/metrics",
    "/api/metrics",
    "/favicon.ico",
})

# Paths that should be treated as reviewer (human user) actions
_REVIEWER_PATHS_PREFIX = "/api/v1/review"


def _extract_user_id(request: Request) -> str | None:
    """Extract user_id from X-User-ID header (set by auth middleware upstream)."""
    return request.headers.get("X-User-ID") or request.headers.get("x-user-id")


def _extract_session_id(request: Request) -> str | None:
    """Extract session_id from X-Session-ID header or cookie."""
    return (
        request.headers.get("X-Session-ID")
        or request.cookies.get("session_id")
    )


def _extract_actor_type(request: Request) -> AuditActorType:
    """Infer actor type from request path and headers."""
    path = request.url.path
    if path.startswith(_REVIEWER_PATHS_PREFIX):
        return AuditActorType.REVIEWER
    # Service-to-service calls often carry X-Service-Name
    if request.headers.get("X-Service-Name"):
        return AuditActorType.EXTERNAL_SERVICE
    if request.headers.get("X-User-ID") or request.headers.get("Authorization"):
        return AuditActorType.USER
    return AuditActorType.SYSTEM


def _get_client_ip(request: Request) -> str | None:
    """Extract real client IP, respecting X-Forwarded-For from reverse proxies."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else None


class AuditMiddleware(BaseHTTPMiddleware):
    """
    Per-request audit context injection and API request logging.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip non-auditable paths
        if request.url.path in _SKIP_PATHS or request.method == "OPTIONS":
            return await call_next(request)

        t0 = time.monotonic()

        # Build audit context from request metadata
        # request_id and trace_id were already injected by RequestTracingMiddleware
        # into structlog contextvars; read them back from the request state or headers.
        request_id = (
            getattr(request.state, "request_id", None)
            or request.headers.get("X-Request-ID")
        )
        trace_id = (
            getattr(request.state, "trace_id", None)
            or request.headers.get("X-Trace-ID")
        )

        audit_ctx = build_context_from_request(
            request_id=request_id,
            trace_id=trace_id,
            user_id=_extract_user_id(request),
            session_id=_extract_session_id(request),
            actor_ip=_get_client_ip(request),
            actor_user_agent=request.headers.get("User-Agent"),
            actor_type=_extract_actor_type(request),
        )

        # Bind to contextvars for the full request duration
        token = set_audit_context(audit_ctx)

        error_message: str | None = None
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception as exc:
            error_message = str(exc)
            status_code = 500
            raise
        finally:
            duration_ms = (time.monotonic() - t0) * 1000

            # Emit audit record — never raises, never blocks
            try:
                record = api_request_event(
                    method=request.method,
                    path=request.url.path,
                    status_code=status_code,
                    duration_ms=duration_ms,
                    query_params=dict(request.query_params),
                    error_message=error_message,
                )
                emit(record)
            except Exception as exc:
                logger.error(
                    "audit.middleware.emit_failed",
                    path=request.url.path,
                    error=str(exc),
                )

            # Reset context to prevent leakage between requests
            reset_audit_context(token)
