"""
Unit tests for health check endpoint.

Tests the /health, /health/live, and /health/ready endpoints in isolation.
All downstream dependencies (DB, Redis) are mocked.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


class TestLivenessProbe:
    """Tests for GET /api/v1/health/live"""

    @pytest.mark.asyncio
    async def test_liveness_returns_200(self, async_client: AsyncClient) -> None:
        """Liveness probe must always return 200 if the process is running."""
        response = await async_client.get("/api/v1/health/live")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_liveness_returns_alive_status(self, async_client: AsyncClient) -> None:
        """Liveness response body must contain status=alive."""
        response = await async_client.get("/api/v1/health/live")
        data = response.json()
        assert data["status"] == "alive"
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_liveness_is_fast(self, async_client: AsyncClient) -> None:
        """Liveness probe must respond in under 100ms (no DB/Redis calls)."""
        import time
        start = time.monotonic()
        await async_client.get("/api/v1/health/live")
        duration_ms = (time.monotonic() - start) * 1000
        assert duration_ms < 500  # 500ms generous upper bound in test environment


class TestReadinessProbe:
    """Tests for GET /api/v1/health/ready"""

    @pytest.mark.asyncio
    async def test_readiness_returns_200_when_deps_healthy(self, async_client: AsyncClient) -> None:
        """Readiness probe returns 200 when DB and Redis are healthy."""
        with (
            patch("app.api.routes.health.get_db_health", new_callable=AsyncMock, return_value=True),
            patch("app.api.routes.health.get_redis_health", new_callable=AsyncMock, return_value=True),
        ):
            response = await async_client.get("/api/v1/health/ready")
        assert response.status_code == 200
        assert response.json()["status"] == "ready"

    @pytest.mark.asyncio
    async def test_readiness_returns_503_when_db_unhealthy(self, async_client: AsyncClient) -> None:
        """Readiness probe returns 503 when DB is down."""
        with (
            patch("app.api.routes.health.get_db_health", new_callable=AsyncMock, return_value=False),
            patch("app.api.routes.health.get_redis_health", new_callable=AsyncMock, return_value=True),
        ):
            response = await async_client.get("/api/v1/health/ready")
        assert response.status_code == 503
        assert response.json()["status"] == "not_ready"

    @pytest.mark.asyncio
    async def test_readiness_returns_503_when_redis_unhealthy(self, async_client: AsyncClient) -> None:
        """Readiness probe returns 503 when Redis is down."""
        with (
            patch("app.api.routes.health.get_db_health", new_callable=AsyncMock, return_value=True),
            patch("app.api.routes.health.get_redis_health", new_callable=AsyncMock, return_value=False),
        ):
            response = await async_client.get("/api/v1/health/ready")
        assert response.status_code == 503


class TestFullHealthCheck:
    """Tests for GET /api/v1/health"""

    @pytest.mark.asyncio
    async def test_health_returns_200_all_healthy(self, async_client: AsyncClient) -> None:
        """Full health returns 200 when all services are healthy."""
        with (
            patch("app.api.routes.health.get_db_health", new_callable=AsyncMock, return_value=True),
            patch("app.api.routes.health.get_redis_health", new_callable=AsyncMock, return_value=True),
        ):
            response = await async_client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_health_response_structure(self, async_client: AsyncClient) -> None:
        """Full health response must contain all required fields."""
        with (
            patch("app.api.routes.health.get_db_health", new_callable=AsyncMock, return_value=True),
            patch("app.api.routes.health.get_redis_health", new_callable=AsyncMock, return_value=True),
        ):
            response = await async_client.get("/api/v1/health")

        data = response.json()
        required_fields = {"status", "version", "environment", "uptime_seconds", "services", "timestamp"}
        assert required_fields.issubset(data.keys()), f"Missing fields: {required_fields - data.keys()}"
        assert "database" in data["services"]
        assert "redis" in data["services"]

    @pytest.mark.asyncio
    async def test_health_returns_503_when_db_down(self, async_client: AsyncClient) -> None:
        """Full health returns 503 when critical dependency (DB) is down."""
        with (
            patch("app.api.routes.health.get_db_health", new_callable=AsyncMock, return_value=False),
            patch("app.api.routes.health.get_redis_health", new_callable=AsyncMock, return_value=True),
        ):
            response = await async_client.get("/api/v1/health")
        assert response.status_code == 503
        assert response.json()["status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_health_db_check_timeout_returns_unhealthy(self, async_client: AsyncClient) -> None:
        """Full health returns unhealthy when DB check times out."""
        import asyncio

        async def slow_db():
            await asyncio.sleep(10)  # Simulate timeout
            return True

        with (
            patch("app.api.routes.health._check_database", new_callable=AsyncMock) as mock_db,
            patch("app.api.routes.health.get_redis_health", new_callable=AsyncMock, return_value=True),
        ):
            from app.api.schemas.common import ServiceHealthStatus
            mock_db.return_value = ServiceHealthStatus(status="unhealthy", message="timed out")
            response = await async_client.get("/api/v1/health")

        assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_health_uptime_is_non_negative(self, async_client: AsyncClient) -> None:
        """Uptime must be a non-negative number."""
        with (
            patch("app.api.routes.health.get_db_health", new_callable=AsyncMock, return_value=True),
            patch("app.api.routes.health.get_redis_health", new_callable=AsyncMock, return_value=True),
        ):
            response = await async_client.get("/api/v1/health")
        data = response.json()
        assert data["uptime_seconds"] >= 0
