"""
LangSmith HTTP tracing middleware.

LangSmithTracingMiddleware:
  - Reads X-LangSmith-Run-ID from incoming request headers
  - Stores the run-id in a contextvar so WorkflowRunner can correlate
    the HTTP request with the LangSmith top-level run
  - On the way out, adds X-LangSmith-Run-URL to the response so callers
    can navigate directly to the LangSmith trace for the request

Context variable:
    _langsmith_run_id_var   — str | None, the active run-id for this request

Usage:
    app.add_middleware(LangSmithTracingMiddleware)

    # Inside a request handler or service:
    from app.tracing.middleware import get_request_run_id
    run_id = get_request_run_id()   # None if not set
"""

from __future__ import annotations

import contextvars
from typing import Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.tracing.config import get_langsmith_config

logger = structlog.get_logger(__name__)

# Contextvar holding the LangSmith run-id for the current HTTP request
_langsmith_run_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "langsmith_run_id", default=None
)

_HEADER_RUN_ID  = "X-LangSmith-Run-ID"
_HEADER_RUN_URL = "X-LangSmith-Run-URL"


def get_request_run_id() -> str | None:
    """Return the LangSmith run-id bound to the current request, or None."""
    return _langsmith_run_id_var.get()


def set_request_run_id(run_id: str | None) -> None:
    """Set the LangSmith run-id for the current request context."""
    _langsmith_run_id_var.set(run_id)


def _build_run_url(run_id: str) -> str | None:
    """Build the LangSmith UI URL for a given run-id."""
    try:
        cfg = get_langsmith_config()
        if not cfg.is_active:
            return None
        project = cfg.project or "default"
        return f"https://smith.langchain.com/o/default/projects/p/{project}/runs/{run_id}"
    except Exception:
        return None


class LangSmithTracingMiddleware(BaseHTTPMiddleware):
    """
    Starlette middleware that propagates LangSmith trace context via HTTP headers.

    Incoming:
        X-LangSmith-Run-ID: <uuid>   → stored in contextvar for WorkflowRunner

    Outgoing:
        X-LangSmith-Run-URL: <url>   → set when a run-id exists
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        run_id = request.headers.get(_HEADER_RUN_ID)

        token = _langsmith_run_id_var.set(run_id)

        try:
            response: Response = await call_next(request)
        finally:
            _langsmith_run_id_var.reset(token)

        # Add run URL to response for client-side linking
        if run_id:
            url = _build_run_url(run_id)
            if url:
                response.headers[_HEADER_RUN_URL] = url

        return response
