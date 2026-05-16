"""
Redis sliding-window rate limiter.

Uses a sorted set per client to implement a precise sliding-window algorithm:
- Key:   rate_limit:<client_id>
- Score: Unix timestamp (float) for each request
- Range: ZREMRANGEBYSCORE removes entries older than the current window

This prevents the "boundary burst" problem of fixed-window counters.

Usage:
    @router.post("/pa-requests")
    async def create_pa_request(
        _: None = Depends(rate_limit_dependency("pa_requests")),
    ):
        ...
"""

from __future__ import annotations

import time
from typing import Annotated

import structlog
from fastapi import Depends, Request
from redis.asyncio import Redis

from app.core.config.settings import get_settings
from app.core.exceptions.base import RateLimitExceededError
from app.services.caching.redis_client import get_redis_client

logger = structlog.get_logger(__name__)

# Per-endpoint multipliers relative to base rate limit
_ENDPOINT_MULTIPLIERS: dict[str, float] = {
    "pa_requests":    1.0,   # POST /pa-requests — base rate
    "review":         2.0,   # Review actions — more lenient
    "clarification":  2.0,   # Clarification responses
    "cases_list":     5.0,   # GET /cases — read-heavy, more generous
    "metrics":       10.0,   # GET /metrics — internal, very generous
    "documents":      0.5,   # File uploads — tighter
}


def _get_client_identifier(request: Request) -> str:
    """
    Determine the rate limit bucket identifier for this request.

    Priority: X-Forwarded-For (behind proxy) → Real-IP header → direct IP.
    User authenticated requests are scoped per-user, not per-IP.
    """
    # Prefer user-scoped limiting if auth header is present
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        # Use first 16 chars of token as stable per-user key (no decode needed)
        token_prefix = auth_header[7:23]
        return f"user:{token_prefix}"

    # Fall back to IP-based
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return f"ip:{forwarded.split(',')[0].strip()}"

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return f"ip:{real_ip}"

    client_host = request.client.host if request.client else "unknown"
    return f"ip:{client_host}"


async def _sliding_window_check(
    redis: Redis,
    key: str,
    limit: int,
    window_seconds: int,
) -> tuple[bool, int, float]:
    """
    Sliding-window rate limit check using Redis sorted sets.

    Returns:
        (is_allowed, remaining_requests, retry_after_seconds)
    """
    now = time.time()
    window_start = now - window_seconds

    pipeline = redis.pipeline()
    pipeline.zremrangebyscore(key, 0, window_start)   # Prune expired
    pipeline.zcard(key)                                # Count current
    pipeline.zadd(key, {str(now): now})               # Add this request
    pipeline.expire(key, window_seconds + 1)          # TTL cleanup
    results = await pipeline.execute()

    current_count: int = results[1]

    if current_count >= limit:
        # Undo the zadd — request is not allowed
        await redis.zrem(key, str(now))
        retry_after = window_seconds - (now - window_start)
        return False, 0, retry_after

    remaining = max(0, limit - current_count - 1)
    return True, remaining, 0.0


def rate_limit(endpoint: str = "default") -> Annotated:
    """
    Factory that returns a per-endpoint rate-limit dependency.

    Args:
        endpoint: Named endpoint key that maps to a limit multiplier.

    Usage:
        RateLimit = Depends(rate_limit("pa_requests"))
    """
    async def _check(
        request: Request,
        redis: Redis = Depends(get_redis_client),
    ) -> None:
        settings = get_settings()

        if not settings.rate_limiting_enabled:
            return

        base_limit   = settings.rate_limit_requests
        window       = settings.rate_limit_window_seconds
        multiplier   = _ENDPOINT_MULTIPLIERS.get(endpoint, 1.0)
        effective_limit = max(1, int(base_limit * multiplier))

        client_id = _get_client_identifier(request)
        redis_key = f"rl:{endpoint}:{client_id}"

        try:
            allowed, remaining, retry_after = await _sliding_window_check(
                redis, redis_key, effective_limit, window,
            )
        except Exception as exc:
            # Redis unavailable — fail open (don't block requests)
            logger.warning(
                "rate_limiter.redis_unavailable",
                endpoint=endpoint,
                error=str(exc),
            )
            return

        # Expose rate-limit headers regardless of allowed/denied
        request.state.rate_limit_remaining = remaining
        request.state.rate_limit_limit     = effective_limit
        request.state.rate_limit_window    = window

        if not allowed:
            logger.warning(
                "rate_limiter.limit_exceeded",
                endpoint=endpoint,
                client_id=client_id,
                limit=effective_limit,
                retry_after=retry_after,
            )
            raise RateLimitExceededError(
                details={
                    "limit": effective_limit,
                    "window_seconds": window,
                    "retry_after_seconds": round(retry_after, 1),
                }
            )

        logger.debug(
            "rate_limiter.allowed",
            endpoint=endpoint,
            client_id=client_id,
            remaining=remaining,
        )

    return Depends(_check)
