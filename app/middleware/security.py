"""
Security headers middleware.

Injects HTTP security headers into every response to defend against common
web vulnerabilities: clickjacking, MIME sniffing, XSS, information disclosure.

Headers applied:
- X-Content-Type-Options        prevent MIME sniffing
- X-Frame-Options               prevent clickjacking
- X-XSS-Protection              legacy XSS filter (belt-and-suspenders)
- Referrer-Policy               limit referrer information leakage
- Content-Security-Policy       restrict resource loading (API-only, no browser)
- Permissions-Policy            disable browser feature APIs (camera, mic, etc.)
- Strict-Transport-Security     HTTPS enforcement (production only)
- X-Powered-By removed          prevent server fingerprinting

Reference: OWASP Secure Headers Project
"""

from __future__ import annotations

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.core.config.settings import get_settings

logger = structlog.get_logger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Adds security headers to all HTTP responses.

    Uses the settings.is_production flag to conditionally include
    HSTS (only safe once HTTPS is confirmed in production).
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        settings = get_settings()
        self._is_production = settings.is_production

        # Pre-compute static headers dict to avoid repeated dict construction
        self._headers: dict[str, str] = {
            # Prevent MIME type sniffing — forces browser to honor declared Content-Type
            "X-Content-Type-Options": "nosniff",
            # Prevent embedding in iframes — mitigates clickjacking
            "X-Frame-Options": "DENY",
            # Legacy XSS filter — belt-and-suspenders for old browsers
            "X-XSS-Protection": "1; mode=block",
            # Limit referrer header to same origin only
            "Referrer-Policy": "strict-origin-when-cross-origin",
            # CSP: this is a pure API backend — no scripts, no styles, no images loaded
            "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
            # Disable browser feature APIs that a healthcare API backend never needs
            "Permissions-Policy": (
                "camera=(), microphone=(), geolocation=(), "
                "payment=(), usb=(), interest-cohort=()"
            ),
        }

        # HSTS: only in production — adding HSTS on HTTP breaks non-HTTPS dev environments
        if self._is_production:
            # max-age=31536000 = 1 year; includeSubDomains + preload for full coverage
            self._headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)

        # Inject all security headers
        for header_name, header_value in self._headers.items():
            response.headers[header_name] = header_value

        # Remove headers that leak server implementation details
        response.headers.pop("Server", None)
        response.headers.pop("X-Powered-By", None)

        return response
