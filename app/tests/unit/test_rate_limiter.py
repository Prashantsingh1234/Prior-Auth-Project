"""
Unit tests for the Redis sliding-window rate limiter.

Verifies:
- Requests under the limit are allowed
- Requests at/over the limit are rejected with 429
- The limiter fails open when Redis is unavailable
- Per-endpoint multipliers scale the limit correctly
- Client identification logic (token > forwarded IP > direct IP)
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException


class TestRateLimiterLogic:
    """Test core sliding-window rate limit logic."""

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        pipe = AsyncMock()
        pipe.zremrangebyscore = MagicMock()
        pipe.zcard = MagicMock()
        pipe.zadd = MagicMock()
        pipe.expire = MagicMock()
        redis.pipeline.return_value.__aenter__ = AsyncMock(return_value=pipe)
        redis.pipeline.return_value.__aexit__ = AsyncMock(return_value=False)
        return redis, pipe

    async def _run_check(self, mock_redis_client, count_result: int, endpoint: str = "review"):
        """Helper: run _check with mocked redis returning count_result."""
        from app.api.dependencies.rate_limiter import rate_limit

        redis_client, pipe = mock_redis_client
        pipe.execute = AsyncMock(return_value=[None, count_result, None, None])

        dep = rate_limit(endpoint)

        mock_request = MagicMock()
        mock_request.headers.get = MagicMock(return_value=None)
        mock_request.client.host = "127.0.0.1"

        mock_user = MagicMock()
        mock_user.sub = "user-uuid-1234"

        with patch(
            "app.api.dependencies.rate_limiter.get_redis",
            return_value=redis_client,
        ):
            await dep.dependency(request=mock_request, current_user=mock_user)

    @pytest.mark.asyncio
    async def test_allows_request_under_limit(self, mock_redis):
        redis_client, pipe = mock_redis
        pipe.execute = AsyncMock(return_value=[None, 5, None, None])

        from app.api.dependencies.rate_limiter import rate_limit

        mock_request = MagicMock()
        mock_request.headers.get = MagicMock(return_value=None)
        mock_request.client.host = "127.0.0.1"
        mock_user = MagicMock()
        mock_user.sub = "user-uuid"

        with patch("app.api.dependencies.rate_limiter.get_redis", return_value=redis_client):
            dep_factory = rate_limit("review")
            # Should not raise
            result = await dep_factory.dependency(request=mock_request, current_user=mock_user)
            assert result is None

    @pytest.mark.asyncio
    async def test_rejects_request_over_limit(self, mock_redis):
        redis_client, pipe = mock_redis
        # Return count above limit for "review" endpoint (multiplier=2.0, base=100 → limit=200)
        pipe.execute = AsyncMock(return_value=[None, 9999, None, None])

        from app.api.dependencies.rate_limiter import rate_limit

        mock_request = MagicMock()
        mock_request.headers.get = MagicMock(return_value=None)
        mock_request.client.host = "127.0.0.1"
        mock_user = MagicMock()
        mock_user.sub = "user-uuid"

        with patch("app.api.dependencies.rate_limiter.get_redis", return_value=redis_client):
            dep_factory = rate_limit("review")
            with pytest.raises(HTTPException) as exc_info:
                await dep_factory.dependency(request=mock_request, current_user=mock_user)
            assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_fails_open_when_redis_unavailable(self):
        """Rate limiter must allow requests through if Redis is down."""
        from app.api.dependencies.rate_limiter import rate_limit

        mock_request = MagicMock()
        mock_request.headers.get = MagicMock(return_value=None)
        mock_request.client.host = "127.0.0.1"
        mock_user = MagicMock()
        mock_user.sub = "user-uuid"

        broken_redis = AsyncMock()
        broken_redis.pipeline.side_effect = ConnectionError("Redis is down")

        with patch("app.api.dependencies.rate_limiter.get_redis", return_value=broken_redis):
            dep_factory = rate_limit("review")
            # Should NOT raise — fail open
            result = await dep_factory.dependency(request=mock_request, current_user=mock_user)
            assert result is None

    @pytest.mark.asyncio
    async def test_fails_open_when_redis_is_none(self):
        """Rate limiter allows requests when Redis client is None."""
        from app.api.dependencies.rate_limiter import rate_limit

        mock_request = MagicMock()
        mock_request.headers.get = MagicMock(return_value=None)
        mock_request.client.host = "127.0.0.1"
        mock_user = MagicMock()
        mock_user.sub = "user-uuid"

        with patch("app.api.dependencies.rate_limiter.get_redis", return_value=None):
            dep_factory = rate_limit("review")
            result = await dep_factory.dependency(request=mock_request, current_user=mock_user)
            assert result is None


class TestEndpointMultipliers:
    """Different endpoints have different rate limit multipliers."""

    @pytest.mark.parametrize("endpoint,expected_multiplier", [
        ("pa_requests", 1.0),
        ("documents", 0.5),
        ("review", 2.0),
        ("cases_list", 5.0),
        ("metrics", 10.0),
        ("clarification", 1.0),
    ])
    def test_endpoint_multipliers(self, endpoint: str, expected_multiplier: float):
        from app.api.dependencies.rate_limiter import _ENDPOINT_MULTIPLIERS
        assert _ENDPOINT_MULTIPLIERS.get(endpoint, 1.0) == expected_multiplier

    def test_unknown_endpoint_defaults_to_one(self):
        from app.api.dependencies.rate_limiter import _ENDPOINT_MULTIPLIERS
        assert _ENDPOINT_MULTIPLIERS.get("unknown_endpoint", 1.0) == 1.0


class TestClientIdentification:
    """Client ID should prefer auth token > forwarded IP > direct IP."""

    def test_uses_user_sub_when_authenticated(self):
        from app.api.dependencies.rate_limiter import _get_client_id

        mock_request = MagicMock()
        mock_request.headers.get = MagicMock(return_value=None)
        mock_request.client.host = "10.0.0.1"

        mock_user = MagicMock()
        mock_user.sub = "user-uuid-abc"

        client_id = _get_client_id(mock_request, mock_user)
        assert "user-uuid-abc" in client_id

    def test_uses_forwarded_ip_when_no_user(self):
        from app.api.dependencies.rate_limiter import _get_client_id

        mock_request = MagicMock()
        mock_request.headers.get = MagicMock(
            side_effect=lambda h: "203.0.113.1" if h == "X-Forwarded-For" else None
        )
        mock_request.client.host = "10.0.0.1"

        client_id = _get_client_id(mock_request, None)
        assert "203.0.113.1" in client_id

    def test_falls_back_to_direct_ip(self):
        from app.api.dependencies.rate_limiter import _get_client_id

        mock_request = MagicMock()
        mock_request.headers.get = MagicMock(return_value=None)
        mock_request.client.host = "192.168.1.100"

        client_id = _get_client_id(mock_request, None)
        assert "192.168.1.100" in client_id

    def test_different_users_have_different_client_ids(self):
        from app.api.dependencies.rate_limiter import _get_client_id

        mock_request = MagicMock()
        mock_request.headers.get = MagicMock(return_value=None)
        mock_request.client.host = "10.0.0.1"

        user_a = MagicMock()
        user_a.sub = "user-aaa"
        user_b = MagicMock()
        user_b.sub = "user-bbb"

        id_a = _get_client_id(mock_request, user_a)
        id_b = _get_client_id(mock_request, user_b)
        assert id_a != id_b
