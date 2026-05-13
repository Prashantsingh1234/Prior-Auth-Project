"""
LLM response cache.

With temperature=0 (our default), identical prompts produce identical
LLM outputs. Caching saves $0.002–$0.06 per cache hit and ~1–10s
of latency on repeated reasoning calls.

Key design:
  Key = pa:v1:llm:{model}:{sha256(prompt)[:16]}
  Including the model name prevents cross-model cache pollution
  if we switch from gpt-4o to a fine-tuned variant.

Cache TTL: 1 hour — short enough that policy updates reach the LLM
after a daily re-index, long enough to handle burst traffic on the same case.
"""

from __future__ import annotations

from typing import Any

from app.services.caching.base import BaseCacheService
from app.services.caching.keys import TTL, llm_key


# Typed container for a cached LLM response
class LLMCacheEntry:
    """Represents a cached LLM response with metadata."""

    __slots__ = ("content", "model", "prompt_tokens", "completion_tokens", "cached_at")

    def __init__(
        self,
        content: str | dict,
        model: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cached_at: str | None = None,
    ) -> None:
        self.content = content
        self.model = model
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.cached_at = cached_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "model": self.model,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "cached_at": self.cached_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LLMCacheEntry":
        return cls(
            content=data["content"],
            model=data["model"],
            prompt_tokens=data.get("prompt_tokens", 0),
            completion_tokens=data.get("completion_tokens", 0),
            cached_at=data.get("cached_at"),
        )


class LLMCache(BaseCacheService):
    """Cache for LLM API responses keyed by model + prompt hash."""

    domain = "llm"
    default_ttl = TTL.LLM

    async def get(
        self,
        model: str,
        prompt: str | list[dict],
    ) -> LLMCacheEntry | None:
        """
        Return a cached LLM response, or None on miss.

        Args:
            model:  LLM model identifier (e.g. "gpt-4o")
            prompt: Raw prompt string or chat messages list

        Returns:
            LLMCacheEntry with content + token counts, or None.
        """
        key = llm_key(model, prompt)
        data = await self._get(key)
        if data is None:
            return None
        try:
            return LLMCacheEntry.from_dict(data)
        except (KeyError, TypeError):
            # Corrupt or schema-mismatched cache entry — treat as miss
            await self._delete(key)
            return None

    async def set(
        self,
        model: str,
        prompt: str | list[dict],
        content: str | dict,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        ttl: int | None = None,
    ) -> None:
        """
        Store an LLM response.

        Args:
            model:             Model that produced the response
            prompt:            The input prompt (used for key derivation)
            content:           Response text or structured dict
            prompt_tokens:     Input token count (for metrics/cost tracking)
            completion_tokens: Output token count
            ttl:               Override default TTL (seconds)
        """
        from datetime import UTC, datetime
        key = llm_key(model, prompt)
        entry = LLMCacheEntry(
            content=content,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cached_at=datetime.now(UTC).isoformat(),
        )
        await self._set(key, entry.to_dict(), ttl=ttl)

    async def invalidate(self, model: str, prompt: str | list[dict]) -> bool:
        """Explicitly delete a single LLM cache entry."""
        key = llm_key(model, prompt)
        return await self._delete(key)
