"""
Guardrail HTTP middleware.

GuardrailMiddleware runs prompt injection and jailbreak detection on every
inbound API request body before it reaches the route handler.

This protects the platform against:
  - Prompt injection via the HTTP API (malicious PA request submissions)
  - Jailbreak attempts in clarification responses / reviewer notes

It does NOT re-run the full pipeline (that happens inside workflow nodes).
HTTP-layer detection is deliberately fast and coarse-grained.

Paths excluded from HTTP guardrail scanning:
  - /api/v1/health, /metrics, /api/docs, /api/openapi.json
  - Binary content-type requests (PDF, image uploads)

Usage:
    app.add_middleware(GuardrailMiddleware)
"""

from __future__ import annotations

import json
import time
from typing import Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from app.guardrails.config import DEFAULT_POLICY
from app.guardrails.detectors.jailbreak import detect_jailbreak
from app.guardrails.detectors.prompt_injection import detect_prompt_injection
from app.guardrails.models import GuardrailStage

logger = structlog.get_logger(__name__)

# Paths excluded from HTTP-layer guardrail scanning
_EXCLUDED_PATHS = frozenset({
    "/api/v1/health",
    "/api/v1/health/ready",
    "/api/v1/health/live",
    "/metrics",
    "/api/docs",
    "/api/redoc",
    "/api/openapi.json",
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
})

# Binary content-types skip text extraction
_BINARY_CONTENT_TYPES = frozenset({
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/tiff",
    "multipart/form-data",
})

_MAX_BODY_SCAN_BYTES = 32_768   # Only scan first 32 KB


class GuardrailMiddleware(BaseHTTPMiddleware):
    """
    HTTP-layer guardrail middleware for the PA Review Platform API.

    Extracts text from request bodies and runs fast injection/jailbreak
    detection before forwarding to route handlers.
    """

    def __init__(
        self,
        app: ASGIApp,
        injection_threshold: float = 0.80,
        jailbreak_threshold: float = 0.85,
    ) -> None:
        super().__init__(app)
        self._injection_threshold = injection_threshold
        self._jailbreak_threshold = jailbreak_threshold

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip excluded paths
        if request.url.path in _EXCLUDED_PATHS:
            return await call_next(request)

        # Skip binary content types
        content_type = request.headers.get("content-type", "").split(";")[0].strip()
        if content_type in _BINARY_CONTENT_TYPES:
            return await call_next(request)

        # Only scan POST / PUT / PATCH (GET has no meaningful body)
        if request.method not in ("POST", "PUT", "PATCH"):
            return await call_next(request)

        t0 = time.monotonic()
        text_to_scan = await _extract_scan_text(request)

        if text_to_scan:
            injection = await _safe_detect(detect_prompt_injection(
                text_to_scan,
                threshold=self._injection_threshold,
                stage=GuardrailStage.HTTP_REQUEST,
            ))
            jailbreak = await _safe_detect(detect_jailbreak(
                text_to_scan,
                threshold=self._jailbreak_threshold,
                stage=GuardrailStage.HTTP_REQUEST,
            ))

            detected = [v for v in (injection, jailbreak) if v is not None]
            if detected:
                elapsed_ms = (time.monotonic() - t0) * 1000
                logger.warning(
                    "guardrail.http_blocked",
                    path=request.url.path,
                    method=request.method,
                    violations=[v.violation_type.value for v in detected],
                    severities=[v.severity.value for v in detected],
                    elapsed_ms=round(elapsed_ms, 1),
                )
                _emit_prometheus(detected, request.url.path)

                return JSONResponse(
                    status_code=400,
                    content={
                        "error":   "GUARDRAIL_VIOLATION",
                        "message": DEFAULT_POLICY.escalation.fallback_response,
                        "violations": [v.violation_type.value for v in detected],
                    },
                )

        return await call_next(request)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _extract_scan_text(request: Request) -> str:
    """Extract scannable text from the request body (first 32 KB only)."""
    try:
        body = await request.body()
        if not body:
            return ""

        body_slice = body[:_MAX_BODY_SCAN_BYTES]
        content_type = request.headers.get("content-type", "")

        if "application/json" in content_type:
            try:
                data = json.loads(body_slice)
                # Concatenate all string values from the JSON body
                return " ".join(_extract_strings(data))
            except json.JSONDecodeError:
                return body_slice.decode("utf-8", errors="ignore")

        return body_slice.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _extract_strings(obj: object, depth: int = 0) -> list[str]:
    """Recursively extract string values from a JSON-like object."""
    if depth > 5:
        return []
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        result = []
        for v in obj.values():
            result.extend(_extract_strings(v, depth + 1))
        return result
    if isinstance(obj, list):
        result = []
        for item in obj:
            result.extend(_extract_strings(item, depth + 1))
        return result
    return []


async def _safe_detect(coro):
    """Run a detector coroutine and swallow any exceptions."""
    try:
        return await coro
    except Exception as exc:
        logger.debug("guardrail.http_detector_error", error=str(exc))
        return None


def _emit_prometheus(violations, path: str) -> None:
    try:
        from app.guardrails.observability import GUARDRAIL_VIOLATIONS_TOTAL, GUARDRAIL_BLOCKS_TOTAL
        for v in violations:
            GUARDRAIL_VIOLATIONS_TOTAL.labels(
                node="http_middleware",
                violation_type=v.violation_type.value,
                severity=v.severity.value,
            ).inc()
        GUARDRAIL_BLOCKS_TOTAL.labels(node="http_middleware").inc()
    except Exception:
        pass
