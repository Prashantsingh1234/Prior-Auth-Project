"""
Embedding vector cache.

For a given text and model, the embedding is always identical. There is
no semantic reason to ever re-compute an embedding for the same input, so
we use a 24-hour TTL — long enough to survive a service restart, short
enough to pick up model upgrades (we'd bump CACHE_VERSION on a model change).

Key: pa:v1:embedding:{model}:{sha256(text)[:16]}

Storage size: A 1536-dim float32 vector ≈ 6 KB serialized as JSON.
Redis memory is cheap vs. OpenAI API cost — this cache has the best
cost:benefit ratio in the entire caching layer.
"""

from __future__ import annotations

from app.services.caching.base import BaseCacheService
from app.services.caching.keys import TTL, embedding_key


class EmbeddingCache(BaseCacheService):
    """Cache for OpenAI / sentence-transformer embedding vectors."""

    domain = "embedding"
    default_ttl = TTL.EMBEDDING

    async def get(self, model: str, text: str) -> list[float] | None:
        """
        Return a cached embedding vector, or None on miss.

        Args:
            model: Embedding model identifier (e.g. "text-embedding-3-small")
            text:  The input text whose embedding was computed

        Returns:
            List of floats (the embedding vector) or None.
        """
        key = embedding_key(model, text)
        result = await self._get(key)
        if result is None:
            return None
        try:
            return [float(v) for v in result]
        except (TypeError, ValueError):
            await self._delete(key)
            return None

    async def set(
        self,
        model: str,
        text: str,
        vector: list[float],
        ttl: int | None = None,
    ) -> None:
        """
        Store an embedding vector.

        Args:
            model:  Embedding model identifier
            text:   Source text (used for key derivation)
            vector: The embedding vector
            ttl:    Override default TTL (seconds)
        """
        key = embedding_key(model, text)
        await self._set(key, vector, ttl=ttl)

    async def get_batch(
        self, model: str, texts: list[str]
    ) -> dict[str, list[float] | None]:
        """
        Batch-fetch embeddings for multiple texts.

        Returns a dict mapping each text to its cached vector (or None).
        Use this to minimise round-trips when checking a batch of texts
        before calling the embedding API for any missing entries.
        """
        results: dict[str, list[float] | None] = {}
        for text in texts:
            results[text] = await self.get(model, text)
        return results

    async def set_batch(
        self,
        model: str,
        embeddings: dict[str, list[float]],
        ttl: int | None = None,
    ) -> None:
        """
        Batch-store embeddings for multiple texts.

        Args:
            embeddings: Dict mapping text → vector
        """
        for text, vector in embeddings.items():
            await self.set(model, text, vector, ttl=ttl)

    async def invalidate(self, model: str, text: str) -> bool:
        """Delete the cached embedding for a specific text."""
        key = embedding_key(model, text)
        return await self._delete(key)
