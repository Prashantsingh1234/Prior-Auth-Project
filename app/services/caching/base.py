"""
Abstract base cache service.

Wraps the low-level redis_client functions with:
- Domain-scoped structured logging
- Prometheus hit / miss / error tracking
- Graceful fallback: cache failures never propagate to callers
- orjson serialization for speed (falls back to stdlib json)
"""

from __future__ import annotations

from typing import Any, TypeVar

import structlog

from app.core.exceptions.base import CacheError
from app.services.caching.redis_client import (
    cache_delete,
    cache_delete_pattern,
    cache_get,
    cache_set,
)

logger = structlog.get_logger(__name__)

T = TypeVar("T")


class BaseCacheService:
    """
    Domain cache service base.

    Subclasses declare:
        domain: str         — used in log events and metric labels
        default_ttl: int    — seconds; override per-call via ttl= kwarg

    All public methods are safe to call even when Redis is down:
    get() returns None, set() / delete() silently succeed.
    Callers should NEVER depend on cache writes being durable.
    """

    domain: str = "base"
    default_ttl: int = 3_600

    def __init__(self) -> None:
        self._log = structlog.get_logger(
            self.__class__.__name__,
            cache_domain=self.domain,
        )

    # ------------------------------------------------------------------
    # Protected helpers — used by subclass implementations
    # ------------------------------------------------------------------

    async def _get(self, key: str) -> Any | None:
        """
        Fetch and deserialize a cached value.

        Returns None on miss OR on any Redis / deserialization error.
        Errors are logged but NOT re-raised — callers fall through to
        their live data path automatically.
        """
        try:
            value = await cache_get(key)
            if value is None:
                self._track_miss()
                self._log.debug("cache.miss", key=key)
                return None
            self._track_hit()
            self._log.debug("cache.hit", key=key)
            return value
        except CacheError as exc:
            self._track_error("get")
            self._log.warning("cache.get_error", key=key, error=str(exc))
            return None

    async def _set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> None:
        """
        Serialize and store a value.

        Failures are logged and swallowed — a failed write simply means
        the next request will go to the live data source.
        """
        effective_ttl = ttl if ttl is not None else self.default_ttl
        try:
            await cache_set(key, value, ttl=effective_ttl)
            self._log.debug("cache.set", key=key, ttl=effective_ttl)
        except CacheError as exc:
            self._track_error("set")
            self._log.warning("cache.set_error", key=key, error=str(exc))

    async def _delete(self, key: str) -> bool:
        """
        Delete a single key. Returns True if the key existed.
        Failures are logged and swallowed.
        """
        try:
            deleted = await cache_delete(key)
            self._log.debug("cache.delete", key=key, existed=deleted)
            return deleted
        except CacheError as exc:
            self._track_error("delete")
            self._log.warning("cache.delete_error", key=key, error=str(exc))
            return False

    async def _delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching a glob pattern.
        Returns the number of deleted keys.
        """
        try:
            count = await cache_delete_pattern(pattern)
            self._log.info(
                "cache.pattern_delete",
                pattern=pattern,
                deleted_count=count,
            )
            return count
        except CacheError as exc:
            self._track_error("pattern_delete")
            self._log.warning(
                "cache.pattern_delete_error",
                pattern=pattern,
                error=str(exc),
            )
            return 0

    # ------------------------------------------------------------------
    # Metrics helpers
    # ------------------------------------------------------------------

    def _track_hit(self) -> None:
        try:
            from app.monitoring.metrics import CACHE_HITS_TOTAL
            CACHE_HITS_TOTAL.labels(domain=self.domain).inc()
        except Exception:
            pass

    def _track_miss(self) -> None:
        try:
            from app.monitoring.metrics import CACHE_MISSES_TOTAL
            CACHE_MISSES_TOTAL.labels(domain=self.domain).inc()
        except Exception:
            pass

    def _track_error(self, operation: str) -> None:
        try:
            from app.monitoring.metrics import CACHE_ERRORS_TOTAL
            CACHE_ERRORS_TOTAL.labels(
                domain=self.domain, operation=operation
            ).inc()
        except Exception:
            pass
