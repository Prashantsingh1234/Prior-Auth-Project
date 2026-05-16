"""
Pytest configuration and shared fixtures.

Provides:
- test_app: FastAPI app with dependency overrides for DB, Redis
- async_client: async HTTP test client (httpx)
- mock_settings: test-friendly settings
- db_session: in-memory test database session
- mock_redis: mock Redis client

Design:
- All tests run with a fresh settings instance (cache cleared before each test)
- Database uses in-memory SQLite for speed — integration tests target a real MySQL
- Redis is mocked in unit tests, real in integration tests
- Fixtures are scoped appropriately (session/module/function)
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.config.settings import Settings, get_settings
from app.api.dependencies.database import get_db_session
from app.services.caching.redis_client import get_redis


# ----------------------------------------------------------
# Event loop — session-scoped for async tests
# ----------------------------------------------------------

@pytest.fixture(scope="session")
def event_loop_policy():
    """Use the default event loop policy."""
    return asyncio.DefaultEventLoopPolicy()


# ----------------------------------------------------------
# Settings overrides
# ----------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_settings_cache():
    """Clear the lru_cache on settings before each test to allow env patching."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def test_settings() -> Settings:
    """Return test-appropriate settings with safe defaults."""
    return Settings(
        app_name="PA Review Platform (Test)",
        environment="development",
        debug=True,
        secret_key="test-secret-key-minimum-32-chars-long",
        db_host="localhost",
        db_port=3306,
        db_name="pa_test_db",
        db_user="test_user",
        db_password="test_password",  # type: ignore[arg-type]
        redis_url="redis://localhost:6379/1",  # Use DB 1 for tests
        log_level="DEBUG",
        log_format="console",
        prometheus_enabled=False,
    )


# ----------------------------------------------------------
# Database session mock (unit tests)
# ----------------------------------------------------------

@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Async mock database session for unit tests."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.refresh = AsyncMock()
    return session


# ----------------------------------------------------------
# Redis mock (unit tests)
# ----------------------------------------------------------

@pytest.fixture
def mock_redis_client() -> AsyncMock:
    """Async mock Redis client for unit tests."""
    client = AsyncMock()
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock(return_value=True)
    client.delete = AsyncMock(return_value=1)
    client.ping = AsyncMock(return_value=True)
    return client


# ----------------------------------------------------------
# FastAPI test application with overrides
# ----------------------------------------------------------

@pytest.fixture
def app_with_overrides(mock_db_session: AsyncMock, mock_redis_client: AsyncMock) -> FastAPI:
    """
    FastAPI app with infrastructure dependencies replaced by mocks.

    Avoids needing real DB/Redis for unit and most integration tests.
    """
    from app.main import create_application

    test_app = create_application()

    # Override DB dependency
    async def override_get_db() -> AsyncGenerator[AsyncMock, None]:
        yield mock_db_session

    # Override Redis dependency
    def override_get_redis() -> AsyncMock:
        return mock_redis_client

    test_app.dependency_overrides[get_db_session] = override_get_db
    test_app.dependency_overrides[get_redis] = override_get_redis

    return test_app


# ----------------------------------------------------------
# Async HTTP test client
# ----------------------------------------------------------

@pytest_asyncio.fixture
async def async_client(app_with_overrides: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """
    Async HTTP client for testing FastAPI endpoints.

    Uses httpx.ASGITransport to make requests directly against the ASGI app
    without starting a server.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app_with_overrides),
        base_url="http://testserver",
        headers={"Content-Type": "application/json"},
    ) as client:
        yield client


# ----------------------------------------------------------
# JWT auth helpers
# ----------------------------------------------------------

@pytest.fixture
def reviewer_token(test_settings: Settings) -> str:
    """Generate a valid reviewer JWT for authenticated test requests."""
    from app.core.security.jwt import create_access_token
    with patch("app.core.security.jwt.get_settings", return_value=test_settings):
        return create_access_token(
            subject="test-reviewer-uuid",
            role="reviewer",
        )


@pytest.fixture
def admin_token(test_settings: Settings) -> str:
    """Generate a valid admin JWT for admin-role test requests."""
    from app.core.security.jwt import create_access_token
    with patch("app.core.security.jwt.get_settings", return_value=test_settings):
        return create_access_token(
            subject="test-admin-uuid",
            role="admin",
        )


@pytest.fixture
def auth_headers_reviewer(reviewer_token: str) -> dict[str, str]:
    """Authorization headers for a reviewer role request."""
    return {"Authorization": f"Bearer {reviewer_token}"}


@pytest.fixture
def auth_headers_admin(admin_token: str) -> dict[str, str]:
    """Authorization headers for an admin role request."""
    return {"Authorization": f"Bearer {admin_token}"}
