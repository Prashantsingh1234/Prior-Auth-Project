"""
Async cache decorators.

@cached          — transparent read-through cache for async functions
@invalidate_cache — explicit cache invalidation on write operations

Usage:

    from app.services.caching.decorators import cached, invalidate_cache
    from app.services.caching.keys import TTL

    # Cache the return value for 30 minutes
    @cached(
        key_func=lambda case_id: f"pa:v1:case:summary:{case_id}",
        ttl=TTL.CASE_SUMMARY,
        domain="case",
    )
    async def get_case_summary(case_id: str) -> dict:
        ...

    # Delete related cache entries after a write
    @invalidate_cache(
        keys_func=lambda self, case_id, **_: [
            f"pa:v1:case:summary:{case_id}",
        ]
    )
    async def update_case_status(self, case_id: str, ...) -> PACase:
        ...
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any

import structlog

from app.services.caching.redis_client import (
    cache_delete,
    cache_get,
    cache_set,
)

logger = structlog.get_logger(__name__)


def cached(
    key_func: Callable[..., str],
    ttl: int,
    domain: str = "generic",
    skip_cache_kwarg: str = "skip_cache",
) -> Callable:
    """
    Transparent read-through cache decorator for async functions.

    Args:
        key_func:          Called with the same positional + keyword args as
                           the decorated function to produce the Redis key.
        ttl:               Time-to-live in seconds.
        domain:            Label for logging and metrics.
        skip_cache_kwarg:  If True is passed for this kwarg, the cache is
                           bypassed and the live result is fetched + stored.

    Cache misses and errors both fall through to the live function.
    The decorated function signature is preserved (functools.wraps).
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            skip = kwargs.pop(skip_cache_kwarg, False)

            key = key_func(*args, **kwargs)

            if not skip:
                try:
                    cached_value = await cache_get(key)
                    if cached_value is not None:
                        logger.debug(
                            "cache.decorator.hit",
                            domain=domain,
                            key=key,
                        )
                        _inc_hits(domain)
                        return cached_value
                except Exception as exc:
                    logger.warning(
                        "cache.decorator.get_error",
                        domain=domain,
                        key=key,
                        error=str(exc),
                    )
                _inc_misses(domain)

            # Cache miss or skip — call the live function
            result = await func(*args, **kwargs)

            if result is not None:
                try:
                    await cache_set(key, result, ttl=ttl)
                    logger.debug(
                        "cache.decorator.stored",
                        domain=domain,
                        key=key,
                        ttl=ttl,
                    )
                except Exception as exc:
                    logger.warning(
                        "cache.decorator.set_error",
                        domain=domain,
                        key=key,
                        error=str(exc),
                    )

            return result

        return wrapper

    return decorator


def invalidate_cache(
    keys_func: Callable[..., list[str]],
    domain: str = "generic",
) -> Callable:
    """
    Invalidate one or more cache keys after a successful write.

    Args:
        keys_func: Called with the same args as the decorated function;
                   must return a list of Redis keys to delete.
        domain:    Label for logging.

    The decorated function runs first. If it raises, keys are NOT deleted.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = await func(*args, **kwargs)

            keys = keys_func(*args, **kwargs)
            for key in keys:
                try:
                    deleted = await cache_delete(key)
                    logger.debug(
                        "cache.invalidated",
                        domain=domain,
                        key=key,
                        existed=deleted,
                    )
                except Exception as exc:
                    logger.warning(
                        "cache.invalidation_error",
                        domain=domain,
                        key=key,
                        error=str(exc),
                    )

            return result

        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# Metrics helpers (lazy import to avoid circular deps)
# ---------------------------------------------------------------------------

def _inc_hits(domain: str) -> None:
    try:
        from app.monitoring.metrics import CACHE_HITS_TOTAL
        CACHE_HITS_TOTAL.labels(domain=domain).inc()
    except Exception:
        pass


def _inc_misses(domain: str) -> None:
    try:
        from app.monitoring.metrics import CACHE_MISSES_TOTAL
        CACHE_MISSES_TOTAL.labels(domain=domain).inc()
    except Exception:
        pass
