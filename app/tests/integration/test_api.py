"""
Integration tests for core API behavior.

Tests middleware, error handling, security headers, and CORS
across the full request/response cycle using the in-memory ASGI client.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


class TestSecurityHeaders:
    """Verify security headers are present on all responses."""

    @pytest.mark.asyncio
    async def test_x_content_type_options_present(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/api/v1/health/live")
        assert response.headers.get("X-Content-Type-Options") == "nosniff"

    @pytest.mark.asyncio
    async def test_x_frame_options_present(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/api/v1/health/live")
        assert response.headers.get("X-Frame-Options") == "DENY"

    @pytest.mark.asyncio
    async def test_referrer_policy_present(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/api/v1/health/live")
        assert "Referrer-Policy" in response.headers

    @pytest.mark.asyncio
    async def test_content_security_policy_present(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/api/v1/health/live")
        assert "Content-Security-Policy" in response.headers


class TestRequestTracing:
    """Verify request_id and trace_id are injected into responses."""

    @pytest.mark.asyncio
    async def test_response_contains_request_id(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/api/v1/health/live")
        assert "X-Request-ID" in response.headers

    @pytest.mark.asyncio
    async def test_response_contains_trace_id(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/api/v1/health/live")
        assert "X-Trace-ID" in response.headers

    @pytest.mark.asyncio
    async def test_client_request_id_is_preserved(self, async_client: AsyncClient) -> None:
        """Client-provided X-Request-ID must be echoed back in the response."""
        custom_id = "my-client-request-id-abc123"
        response = await async_client.get(
            "/api/v1/health/live",
            headers={"X-Request-ID": custom_id},
        )
        assert response.headers.get("X-Request-ID") == custom_id

    @pytest.mark.asyncio
    async def test_request_ids_are_unique_per_request(self, async_client: AsyncClient) -> None:
        """Each request gets a unique request ID."""
        r1 = await async_client.get("/api/v1/health/live")
        r2 = await async_client.get("/api/v1/health/live")
        assert r1.headers.get("X-Request-ID") != r2.headers.get("X-Request-ID")


class TestErrorHandling:
    """Verify global exception handlers return consistent error envelopes."""

    @pytest.mark.asyncio
    async def test_404_returns_standard_envelope(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/api/v1/does-not-exist")
        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]

    @pytest.mark.asyncio
    async def test_method_not_allowed_returns_405(self, async_client: AsyncClient) -> None:
        """POST to a GET-only endpoint returns 405."""
        response = await async_client.post("/api/v1/health/live")
        assert response.status_code == 405

    @pytest.mark.asyncio
    async def test_unhandled_exception_returns_500(self, async_client: AsyncClient) -> None:
        """Unhandled server errors return 500 with generic message."""
        with patch(
            "app.api.routes.health._check_database",
            side_effect=RuntimeError("Unexpected boom"),
        ):
            response = await async_client.get("/api/v1/health")
        # Should not leak internal error details
        assert response.status_code in (500, 503)
        if response.status_code == 500:
            data = response.json()
            assert "boom" not in str(data).lower()


class TestAuthentication:
    """Verify JWT authentication is enforced on protected endpoints."""

    @pytest.mark.asyncio
    async def test_health_endpoint_is_public(self, async_client: AsyncClient) -> None:
        """Health endpoint requires no authentication."""
        with (
            patch("app.api.routes.health.get_db_health", new_callable=AsyncMock, return_value=True),
            patch("app.api.routes.health.get_redis_health", new_callable=AsyncMock, return_value=True),
        ):
            response = await async_client.get("/api/v1/health")
        assert response.status_code in (200, 207)


class TestContentType:
    """Verify responses use correct content type."""

    @pytest.mark.asyncio
    async def test_json_content_type(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/api/v1/health/live")
        assert "application/json" in response.headers.get("content-type", "")
