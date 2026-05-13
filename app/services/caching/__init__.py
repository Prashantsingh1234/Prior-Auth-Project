"""
Caching package — Redis-backed domain cache services.

Primary entry point:

    from app.services.caching import get_cache_manager

    cache = get_cache_manager()
    chunks = await cache.retrieval.get(cpt_codes, icd_codes, query)

Individual services can also be imported directly when only one domain
is needed:

    from app.services.caching import EmbeddingCache
    embed_cache = EmbeddingCache()
"""

from app.services.caching.clarification_cache import ClarificationCache, ClarificationState
from app.services.caching.decorators import cached, invalidate_cache
from app.services.caching.embedding_cache import EmbeddingCache
from app.services.caching.keys import TTL, content_hash
from app.services.caching.llm_cache import LLMCache, LLMCacheEntry
from app.services.caching.manager import CacheManager, get_cache_manager
from app.services.caching.redis_client import (
    build_cache_key,
    cache_delete,
    cache_delete_pattern,
    cache_get,
    cache_set,
    close_redis,
    get_redis,
    get_redis_health,
    init_redis,
)
from app.services.caching.retrieval_cache import RetrievalCache
from app.services.caching.session_cache import SessionCache

__all__ = [
    # Manager (preferred entry point)
    "CacheManager",
    "get_cache_manager",
    # Domain services
    "RetrievalCache",
    "LLMCache",
    "LLMCacheEntry",
    "EmbeddingCache",
    "SessionCache",
    "ClarificationCache",
    "ClarificationState",
    # Decorators
    "cached",
    "invalidate_cache",
    # Key utilities
    "TTL",
    "content_hash",
    # Low-level client (used by infrastructure code)
    "init_redis",
    "close_redis",
    "get_redis",
    "get_redis_health",
    "build_cache_key",
    "cache_get",
    "cache_set",
    "cache_delete",
    "cache_delete_pattern",
]
