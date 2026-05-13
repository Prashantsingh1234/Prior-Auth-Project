"""
Request tracing middleware.

Injects a unique request_id and trace_id into every request:
- request_id: UUID per HTTP request (generated here or from X-Request-ID header)
- trace_id: UUID for distributed tracing correlation across services

Both IDs are:
1. Bound to structlog context variables (available in all logs for that request)
2. Added to the response headers so clients can correlate logs
3. Stored in request.state for access in route handlers

This middleware must wrap the logging middleware so IDs are available when
RequestLoggingMiddleware emits its log records.
"""

from __future__ import annotations

import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

logger = structlog.get_logger(__name__)


class RequestTracingMiddleware(BaseHTTPMiddleware):
    """
    Injects request_id and trace_id into structlog context and response headers.

    Header precedence:
    - X-Request-ID: use value from client if present (idempotent retries),
      otherwise generate a new UUID4
    - X-Trace-ID: always generated server-side
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Respect client-provided request ID for retry correlation
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        trace_id = str(uuid.uuid4())

        # Store on request.state so route handlers can access them
        request.state.request_id = request_id
        request.state.trace_id = trace_id

        # Bind to structlog context — all log calls within this request
        # will automatically include these fields
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            trace_id=trace_id,
        )

        response = await call_next(request)

        # Propagate IDs to caller for client-side correlation
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Trace-ID"] = trace_id

        return response
