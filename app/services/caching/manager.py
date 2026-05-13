"""
CacheManager — unified façade for all domain cache services.

Usage:

    from app.services.caching.manager import get_cache_manager

    cache = get_cache_manager()

    # Retrieval
    chunks = await cache.retrieval.get(cpt_codes, icd_codes, query)
    if chunks is None:
        chunks = await pinecone.query(...)
        await cache.retrieval.set(cpt_codes, icd_codes, query, chunks)

    # LLM
    cached_resp = await cache.llm.get("gpt-4o", prompt)
    if cached_resp is None:
        resp = await openai.chat.complete(prompt)
        await cache.llm.set("gpt-4o", prompt, resp.content, ...)

    # Session
    session = await cache.session.get_session(user_id)

    # Clarification
    state = await cache.clarification.get(case_id, attempt)

    # Utility — invalidate everything for a case
    await cache.invalidate_case(case_id)

The manager is a module-level singleton (get_cache_manager()) that is
safe to call from any service layer code. It carries no state beyond its
sub-service instances — all state lives in Redis.
"""

from __future__ import annotations

from functools import lru_cache

import structlog

from app.services.caching.clarification_cache import ClarificationCache
from app.services.caching.embedding_cache import EmbeddingCache
from app.services.caching.llm_cache import LLMCache
from app.services.caching.retrieval_cache import RetrievalCache
from app.services.caching.session_cache import SessionCache

logger = structlog.get_logger(__name__)


class CacheManager:
    """
    Aggregates all domain-specific cache services.

    Properties:
        retrieval      — policy chunk retrieval results
        llm            — LLM API response caching
        embedding      — embedding vector caching
        session        — user session + JWT revocation
        clarification  — per-case clarification state

    Also provides cross-domain helpers:
        invalidate_case(case_id) — purge all caches related to a case
        warm_health_check()      — verify Redis connectivity
    """

    def __init__(self) -> None:
        self.retrieval = RetrievalCache()
        self.llm = LLMCache()
        self.embedding = EmbeddingCache()
        self.session = SessionCache()
        self.clarification = ClarificationCache()

    async def invalidate_case(self, case_id: str) -> dict[str, int]:
        """
        Purge all cache entries associated with a PA case.

        Call this when:
        - A new document is uploaded to a case
        - The case's clinical codes are corrected
        - A case is reopened after being decided

        Returns counts of deleted keys per domain.
        """
        results: dict[str, int] = {}

        # Retrieval: pattern delete (keys embed CPT/ICD hashes, not case_id,
        # so we use the broad case pattern)
        results["retrieval"] = await self.retrieval.invalidate_for_case(case_id)

        # Clarification: explicit per-attempt deletes (max 3)
        results["clarification"] = await self.clarification.invalidate_all_for_case(case_id)

        logger.info(
            "cache.case_invalidated",
            case_id=case_id,
            deleted_by_domain=results,
        )
        return results

    async def warm_health_check(self) -> bool:
        """
        Verify Redis is reachable.

        Returns True if healthy, False otherwise.
        Does NOT raise — intended for health check endpoints.
        """
        from app.services.caching.redis_client import get_redis_health
        return await get_redis_health()

    async def get_stats(self) -> dict[str, object]:
        """
        Return basic cache layer statistics for the /health endpoint.

        Returns a dict suitable for inclusion in health check responses.
        """
        healthy = await self.warm_health_check()
        return {
            "healthy": healthy,
            "domains": ["retrieval", "llm", "embedding", "session", "clarification"],
        }


@lru_cache(maxsize=1)
def get_cache_manager() -> CacheManager:
    """
    Return the singleton CacheManager.

    Safe to call anywhere — initialisation is lazy and the instance is
    stateless beyond wiring up sub-services (all state is in Redis).

    In tests, call get_cache_manager.cache_clear() to reset between test runs.
    """
    return CacheManager()
