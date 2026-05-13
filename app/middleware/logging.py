"""
Request / response logging middleware.

Emits one structured log record per HTTP request containing:
- HTTP method and path
- Client IP address
- Response status code
- Request duration in milliseconds
- User agent

This replaces uvicorn's default access log with structured JSON output.
Must be registered AFTER RequestTracingMiddleware so request_id/trace_id
are already bound in structlog context.

Sensitive paths (health checks, metrics) are excluded from access logs
to prevent log spam in high-availability environments.
"""

from __future__ import annotations

import time

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

logger = structlog.get_logger(__name__)

# Paths excluded from access logging (too noisy)
_SKIP_LOG_PATHS: frozenset[str] = frozenset({
    "/api/v1/health",
    "/metrics",
    "/favicon.ico",
})


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Structured access logging middleware.

    Logs every request with timing, status, and client metadata.
    Excludes health/metrics endpoints to prevent log flooding.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Skip noisy health-check and metrics paths
        if request.url.path in _SKIP_LOG_PATHS:
            return await call_next(request)

        start_time = time.monotonic()

        # Capture request metadata before passing to next handler
        method = request.method
        path = request.url.path
        query = str(request.url.query) if request.url.query else ""
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("User-Agent", "unknown")

        # Bind request-level context for all log calls within this handler
        structlog.contextvars.bind_contextvars(
            http_method=method,
            http_path=path,
            client_ip=client_ip,
        )

        logger.info(
            "http.request.received",
            path=path,
            method=method,
            query=query,
            client_ip=client_ip,
            user_agent=user_agent,
        )

        response: Response | None = None
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            # Log unhandled exceptions — the global handler will also catch this
            duration_ms = round((time.monotonic() - start_time) * 1000, 2)
            logger.error(
                "http.request.failed",
                path=path,
                method=method,
                duration_ms=duration_ms,
                exc_info=exc,
            )
            raise
        finally:
            duration_ms = round((time.monotonic() - start_time) * 1000, 2)
            status_code = response.status_code if response is not None else 500

            # Choose log level based on status code
            log_fn = (
                logger.warning if 400 <= status_code < 500
                else logger.error if status_code >= 500
                else logger.info
            )
            log_fn(
                "http.request.completed",
                path=path,
                method=method,
                status_code=status_code,
                duration_ms=duration_ms,
            )

    @staticmethod
    def _get_client_ip(request: Request) -> str:
        """
        Extract real client IP from request.
        Respects X-Forwarded-For header set by reverse proxies/load balancers.
        """
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # X-Forwarded-For can be a comma-separated chain; leftmost is the client
            return forwarded_for.split(",")[0].strip()
        if request.client:
            return request.client.host
        return "unknown"
