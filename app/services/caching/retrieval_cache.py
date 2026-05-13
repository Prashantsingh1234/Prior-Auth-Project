"""
Retrieval cache — stores Pinecone/RAG policy chunk results.

Why cache retrieval?
  A retrieval query for CPT 95249 + ICD E11.9 returns the same top-K
  policy chunks every time (until the index is updated). Caching saves
  ~100–500ms per case and reduces Pinecone read units.

Invalidation strategy:
  Call invalidate_for_codes() whenever the Pinecone index is re-indexed
  for a CPT/ICD combination (Step 5 pipeline hook).
"""

from __future__ import annotations

from typing import Any

from app.services.caching.base import BaseCacheService
from app.services.caching.keys import (
    TTL,
    case_invalidation_pattern,
    retrieval_key,
)


class RetrievalCache(BaseCacheService):
    """Cache for hybrid RAG retrieval results."""

    domain = "retrieval"
    default_ttl = TTL.RETRIEVAL

    async def get(
        self,
        cpt_codes: list[str],
        icd_codes: list[str],
        query: str,
    ) -> list[dict[str, Any]] | None:
        """
        Return cached policy chunks for this clinical query, or None.

        Args:
            cpt_codes: CPT procedure codes from the case
            icd_codes: ICD-10 diagnosis codes from the case
            query:     Semantic query string derived from clinical notes

        Returns:
            List of chunk dicts (each has 'text', 'score', 'metadata')
            or None on cache miss.
        """
        key = retrieval_key(cpt_codes, icd_codes, query)
        result = await self._get(key)
        if result is not None:
            return list(result)
        return None

    async def set(
        self,
        cpt_codes: list[str],
        icd_codes: list[str],
        query: str,
        chunks: list[dict[str, Any]],
        ttl: int | None = None,
    ) -> None:
        """
        Store retrieval results.

        Args:
            chunks: List of retrieved policy chunks with scores and metadata.
            ttl:    Override default TTL (seconds).
        """
        key = retrieval_key(cpt_codes, icd_codes, query)
        await self._set(key, chunks, ttl=ttl)

    async def invalidate(
        self,
        cpt_codes: list[str],
        icd_codes: list[str],
        query: str,
    ) -> bool:
        """Delete the cache entry for a specific query."""
        key = retrieval_key(cpt_codes, icd_codes, query)
        return await self._delete(key)

    async def invalidate_for_case(self, case_id: str) -> int:
        """
        Delete all retrieval cache entries associated with a case.

        Called when a case's clinical codes change or new documents arrive.
        Uses SCAN-based pattern deletion — safe for production Redis.
        """
        pattern = case_invalidation_pattern(case_id)
        return await self._delete_pattern(pattern)
