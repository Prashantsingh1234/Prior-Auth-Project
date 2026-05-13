"""
Async Redis client with connection pooling, retry logic, and cache utilities.

Design:
- Single Redis connection pool shared across all requests (init_redis / close_redis)
- All operations are async — never block the event loop
- Key builder enforces consistent namespacing: pa:{domain}:{identifier}:{version}
- Graceful degradation: CacheError is raised but callers should handle it as
  non-fatal since cache is not the source of truth
- Retry with exponential backoff via tenacity for transient Redis failures
- TTL on every key — no unbounded cache growth

Cache key convention:
    policy:{cpt_code}:{version}         policy:95249:v2
    embedding:{content_hash}            embedding:sha256abc
    session:{user_id}                   session:uuid-123
    clarification:{case_id}             clarification:uuid-456
"""

from __future__ import annotations

import json
from typing import Any, TypeVar

import structlog
from redis.asyncio import ConnectionPool, Redis
from redis.asyncio.client import Redis as AsyncRedis
from redis.exceptions import ConnectionError, RedisError, TimeoutError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config.settings import get_settings
from app.core.exceptions.base import CacheError

logger = structlog.get_logger(__name__)

T = TypeVar("T")

# Module-level singleton — initialized in init_redis()
_redis_pool: ConnectionPool | None = None
_redis_client: AsyncRedis | None = None


async def init_redis() -> None:
    """
    Initialize the Redis connection pool.

    Called once during application startup lifespan.
    """
    global _redis_pool, _redis_client

    settings = get_settings()

    connection_kwargs: dict[str, Any] = {
        "max_connections": settings.redis_max_connections,
        "decode_responses": True,
        "socket_connect_timeout": 5,
        "socket_timeout": 5,
        "retry_on_timeout": True,
    }

    if settings.redis_password:
        connection_kwargs["password"] = settings.redis_password.get_secret_value()

    _redis_pool = ConnectionPool.from_url(
        settings.redis_url,
        **connection_kwargs,
    )
    _redis_client = Redis(connection_pool=_redis_pool)

    # Validate connectivity
    try:
        await _redis_client.ping()
        logger.info(
            "redis.connection_pool_initialized",
            url=settings.redis_url.split("@")[-1],  # Log host only, not credentials
            max_connections=settings.redis_max_connections,
        )
    except (ConnectionError, TimeoutError) as exc:
        logger.error("redis.connection_failed", error=str(exc))
        raise


async def close_redis() -> None:
    """
    Close all Redis connections and the connection pool.

    Called during application shutdown lifespan.
    """
    global _redis_client, _redis_pool
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
    if _redis_pool is not None:
        await _redis_pool.aclose()
        _redis_pool = None
    logger.info("redis.connection_pool_closed")


def get_redis() -> AsyncRedis:
    """Return the Redis client singleton — raises if not initialized."""
    if _redis_client is None:
        raise RuntimeError("Redis client not initialized. Call init_redis() first.")
    return _redis_client


async def get_redis_health() -> bool:
    """
    Lightweight Redis connectivity check for the health endpoint.
    Returns True if Redis is reachable, False otherwise.
    """
    if _redis_client is None:
        return False
    try:
        return await _redis_client.ping()
    except Exception:
        return False


# ----------------------------------------------------------
# Key building utilities
# ----------------------------------------------------------

def build_cache_key(*parts: str) -> str:
    """
    Build a namespaced Redis key.

    Args:
        *parts: Key segments joined by ':'

    Returns:
        e.g. build_cache_key("policy", "95249", "v2") → "pa:policy:95249:v2"
    """
    return "pa:" + ":".join(str(p) for p in parts)


# ----------------------------------------------------------
# High-level cache operations with retry
# ----------------------------------------------------------

_TRANSIENT_ERRORS = (ConnectionError, TimeoutError)


@retry(
    retry=retry_if_exception_type(_TRANSIENT_ERRORS),
    wait=wait_exponential(multiplier=0.1, min=0.1, max=2.0),
    stop=stop_after_attempt(3),
    reraise=True,
)
async def cache_get(key: str) -> Any | None:
    """
    Get a JSON-serialized value from Redis.

    Returns None on cache miss or deserialization error.
    Retries on transient connection errors.
    """
    try:
        client = get_redis()
        raw = await client.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except _TRANSIENT_ERRORS:
        raise  # Let tenacity handle retry
    except RedisError as exc:
        logger.warning("redis.get_failed", key=key, error=str(exc))
        raise CacheError(details={"key": key, "operation": "GET"}) from exc
    except json.JSONDecodeError as exc:
        logger.warning("redis.deserialize_failed", key=key, error=str(exc))
        return None  # Treat deserialization failure as cache miss


@retry(
    retry=retry_if_exception_type(_TRANSIENT_ERRORS),
    wait=wait_exponential(multiplier=0.1, min=0.1, max=2.0),
    stop=stop_after_attempt(3),
    reraise=True,
)
async def cache_set(key: str, value: Any, ttl: int | None = None) -> None:
    """
    Store a JSON-serializable value in Redis with optional TTL.

    Args:
        key:   Redis key
        value: Any JSON-serializable Python object
        ttl:   Time-to-live in seconds (defaults to settings.redis_ttl)
    """
    settings = get_settings()
    effective_ttl = ttl if ttl is not None else settings.redis_ttl

    try:
        client = get_redis()
        serialized = json.dumps(value, default=str)
        await client.set(key, serialized, ex=effective_ttl)
        logger.debug("redis.set", key=key, ttl=effective_ttl)
    except _TRANSIENT_ERRORS:
        raise
    except RedisError as exc:
        logger.warning("redis.set_failed", key=key, error=str(exc))
        raise CacheError(details={"key": key, "operation": "SET"}) from exc


async def cache_delete(key: str) -> bool:
    """
    Delete a key from Redis.

    Returns True if the key existed and was deleted, False if it did not exist.
    """
    try:
        client = get_redis()
        deleted_count = await client.delete(key)
        logger.debug("redis.delete", key=key, deleted=bool(deleted_count))
        return bool(deleted_count)
    except RedisError as exc:
        logger.warning("redis.delete_failed", key=key, error=str(exc))
        raise CacheError(details={"key": key, "operation": "DELETE"}) from exc


async def cache_delete_pattern(pattern: str) -> int:
    """
    Delete all keys matching a glob pattern.

    Use cautiously — SCAN-based deletion, not KEYS (safe for production).
    Returns number of deleted keys.
    """
    try:
        client = get_redis()
        deleted = 0
        async for key in client.scan_iter(match=pattern, count=100):
            await client.delete(key)
            deleted += 1
        logger.info("redis.pattern_delete", pattern=pattern, deleted_count=deleted)
        return deleted
    except RedisError as exc:
        logger.warning("redis.pattern_delete_failed", pattern=pattern, error=str(exc))
        raise CacheError(details={"pattern": pattern, "operation": "PATTERN_DELETE"}) from exc
