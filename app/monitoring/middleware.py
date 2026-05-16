"""
HTTP monitoring middleware.

Adds business-context metrics beyond what prometheus-fastapi-instrumentator
covers automatically (generic HTTP counters + latency histogram).

Extra instrumentation:
  - Active request gauge (by route group)
  - Business-error categorization (4xx vs 5xx vs upstream)
  - Request size tracking
  - Per-role latency (injected after auth middleware resolves the JWT)
"""

from __future__ import annotations

import time
from typing import Callable

import structlog
from prometheus_client import Counter, Gauge, Histogram
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Additional metrics (instrumentator already covers generic HTTP latency/count)
# ---------------------------------------------------------------------------

_ACTIVE_REQUESTS = Gauge(
    "pa_http_active_requests",
    "Number of in-flight HTTP requests",
    labelnames=["route_group"],
)

_REQUEST_SIZE_BYTES = Histogram(
    "pa_http_request_body_bytes",
    "HTTP request body size in bytes",
    labelnames=["route_group"],
    buckets=[0, 512, 1_024, 4_096, 16_384, 65_536, 262_144, 1_048_576],
)

_RESPONSE_SIZE_BYTES = Histogram(
    "pa_http_response_body_bytes",
    "HTTP response body size in bytes",
    labelnames=["route_group", "status_class"],
    buckets=[0, 512, 1_024, 4_096, 16_384, 65_536, 262_144],
)

_ERROR_TOTAL = Counter(
    "pa_http_errors_total",
    "HTTP error responses by category",
    labelnames=["route_group", "error_category"],
    # error_category: client_error | server_error | upstream_timeout
)

_ROLE_LATENCY = Histogram(
    "pa_http_latency_by_role_seconds",
    "Request latency segmented by authenticated user role",
    labelnames=["route_group", "role"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
)


# ---------------------------------------------------------------------------
# Route grouping
# ---------------------------------------------------------------------------

_ROUTE_GROUPS: list[tuple[str, str]] = [
    ("/api/v1/auth",    "auth"),
    ("/api/v1/users",   "users"),
    ("/api/v1/health",  "health"),
    ("/api/v1/cases",   "cases"),
    ("/api/v1/pa",      "pa_requests"),
    ("/api/v1/review",  "review"),
    ("/metrics",        "metrics"),
]


def _route_group(path: str) -> str:
    for prefix, group in _ROUTE_GROUPS:
        if path.startswith(prefix):
            return group
    return "other"


def _status_class(status_code: int) -> str:
    if status_code < 400:
        return "2xx_3xx"
    if status_code < 500:
        return "4xx"
    return "5xx"


def _error_category(status_code: int) -> str | None:
    if status_code >= 500:
        return "server_error"
    if status_code >= 400:
        return "client_error"
    return None


class RequestMetricsMiddleware(BaseHTTPMiddleware):
    """
    Starlette middleware that emits business-context Prometheus metrics.

    Does NOT duplicate what prometheus-fastapi-instrumentator already tracks.
    Safe to stack before or after instrumentator — operates independently.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        group = _route_group(request.url.path)

        # Skip metrics endpoint itself to avoid cardinality explosion
        if group == "metrics":
            return await call_next(request)

        _ACTIVE_REQUESTS.labels(route_group=group).inc()

        # Request body size (Content-Length header; 0 if absent)
        content_length = int(request.headers.get("content-length", 0) or 0)
        if content_length > 0:
            _REQUEST_SIZE_BYTES.labels(route_group=group).observe(content_length)

        t0 = time.perf_counter()
        try:
            response: Response = await call_next(request)
        except Exception:
            _ACTIVE_REQUESTS.labels(route_group=group).dec()
            _ERROR_TOTAL.labels(route_group=group, error_category="server_error").inc()
            raise
        finally:
            _ACTIVE_REQUESTS.labels(route_group=group).dec()

        elapsed = time.perf_counter() - t0
        sc = response.status_code
        sc_class = _status_class(sc)

        # Response size (Content-Length if set by handler)
        resp_length = int(response.headers.get("content-length", 0) or 0)
        if resp_length > 0:
            _RESPONSE_SIZE_BYTES.labels(route_group=group, status_class=sc_class).observe(resp_length)

        # Error counters
        err_cat = _error_category(sc)
        if err_cat:
            _ERROR_TOTAL.labels(route_group=group, error_category=err_cat).inc()

        # Per-role latency — role is injected into request.state by auth dependency
        role = getattr(request.state, "user_role", "anonymous")
        _ROLE_LATENCY.labels(route_group=group, role=role).observe(elapsed)

        return response
