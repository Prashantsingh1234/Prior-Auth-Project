"""
Reranking pipeline for retrieved policy chunks.

Two reranker implementations, used in order:

  1. CohereReranker     — Calls Cohere's /rerank endpoint for semantic reranking.
                          Best quality; requires COHERE_API_KEY in settings.

  2. ScoreFusionReranker — Pure Python fallback.  Combines the RRF/multi-signal
                           score with the raw vector score via a weighted blend.
                           Zero-latency; always available.

The RerankerPipeline selects the best available reranker based on configuration,
with automatic fallback if the Cohere call fails.

Usage:
    pipeline = RerankerPipeline.from_settings()
    reranked = await pipeline.rerank(
        query="CGM coverage for type 2 diabetes",
        matches=fused_matches,
        top_n=5,
    )
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any

import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from app.services.vector.schemas import RetrievalMatch

logger = structlog.get_logger(__name__)

# Cohere model to use for reranking
COHERE_RERANK_MODEL = "rerank-english-v3.0"

# Maximum number of documents Cohere accepts per call
COHERE_MAX_DOCS = 1000

# Maximum characters of chunk_text sent to Cohere (to control token cost)
COHERE_MAX_TEXT_CHARS = 512


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class BaseReranker(ABC):
    """Interface for all reranker implementations."""

    @abstractmethod
    async def rerank(
        self,
        query: str,
        matches: list[RetrievalMatch],
        top_n: int,
    ) -> list[RetrievalMatch]:
        """
        Rerank matches for the given query.

        Returns at most top_n matches sorted by descending relevance score.
        The score field is updated to the reranker's score.
        """


# ---------------------------------------------------------------------------
# Cohere reranker
# ---------------------------------------------------------------------------

class CohereReranker(BaseReranker):
    """
    Semantic reranking using the Cohere Rerank API.

    The Cohere model reads both the query and the full chunk text and produces
    a relevance score that is generally more accurate than cosine similarity
    for complex multi-criteria policy language.

    Requires cohere>=5.0 (`pip install cohere`).
    """

    def __init__(self, api_key: str, model: str = COHERE_RERANK_MODEL) -> None:
        import cohere  # type: ignore[import]
        self._client = cohere.AsyncClientV2(api_key=api_key)
        self._model = model
        self._log = structlog.get_logger(self.__class__.__name__)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    async def rerank(
        self,
        query: str,
        matches: list[RetrievalMatch],
        top_n: int,
    ) -> list[RetrievalMatch]:
        if not matches:
            return []

        # Cohere accepts a list of plain strings
        documents = [
            m.metadata.chunk_text[:COHERE_MAX_TEXT_CHARS]
            for m in matches[:COHERE_MAX_DOCS]
        ]

        response = await self._client.rerank(
            model=self._model,
            query=query,
            documents=documents,
            top_n=min(top_n, len(documents)),
            return_documents=False,
        )

        # Map Cohere result indices back to original matches
        reranked: list[RetrievalMatch] = []
        for result in response.results:
            original = matches[result.index]
            reranked.append(
                original.model_copy(update={"score": float(result.relevance_score)})
            )

        self._log.debug(
            "reranker.cohere_complete",
            input_count=len(matches),
            output_count=len(reranked),
            model=self._model,
        )
        return reranked

    @classmethod
    def from_settings(cls) -> "CohereReranker":
        from app.core.config.settings import get_settings
        settings = get_settings()
        api_key = getattr(settings, "cohere_api_key", None)
        if not api_key:
            raise ValueError("COHERE_API_KEY not configured")
        return cls(api_key=api_key)


# ---------------------------------------------------------------------------
# Score-fusion fallback reranker
# ---------------------------------------------------------------------------

class ScoreFusionReranker(BaseReranker):
    """
    Fallback reranker using weighted blending of existing scores.

    Combines:
      - The current match.score (from RRF / multi-signal scorer)
      - A position-based penalty (earlier in original list → higher bonus)

    This produces a deterministic, zero-latency reranking that respects
    the ordering signal from the upstream retrieval pipeline without making
    external API calls.
    """

    def __init__(self, position_weight: float = 0.15) -> None:
        self._pos_weight = position_weight

    async def rerank(
        self,
        query: str,
        matches: list[RetrievalMatch],
        top_n: int,
    ) -> list[RetrievalMatch]:
        if not matches:
            return []

        n = len(matches)
        result: list[tuple[float, RetrievalMatch]] = []
        for i, match in enumerate(matches):
            # Position bonus: 1.0 for rank 1, decays linearly to 0
            pos_bonus = (n - i) / n
            fused = (1.0 - self._pos_weight) * match.score + self._pos_weight * pos_bonus
            result.append((fused, match.model_copy(update={"score": fused})))

        result.sort(key=lambda t: t[0], reverse=True)
        return [m for _, m in result[:top_n]]


# ---------------------------------------------------------------------------
# Pipeline with fallback
# ---------------------------------------------------------------------------

class RerankerPipeline:
    """
    Reranking pipeline with primary (Cohere) and fallback (score-fusion).

    If Cohere is unavailable or disabled, falls back to ScoreFusionReranker
    transparently.

    Args:
        primary:   Primary reranker (Cohere).  None to skip.
        fallback:  Fallback reranker.  Defaults to ScoreFusionReranker.
        enabled:   If False, skips reranking entirely and returns top-N by score.
    """

    def __init__(
        self,
        primary: BaseReranker | None = None,
        fallback: BaseReranker | None = None,
        enabled: bool = True,
    ) -> None:
        self._primary = primary
        self._fallback = fallback or ScoreFusionReranker()
        self._enabled = enabled
        self._log = structlog.get_logger(self.__class__.__name__)

    async def rerank(
        self,
        query: str,
        matches: list[RetrievalMatch],
        top_n: int,
    ) -> list[RetrievalMatch]:
        """
        Rerank the given matches for the query.

        Falls back to ScoreFusionReranker if the primary reranker raises.
        """
        if not self._enabled or not matches:
            return sorted(matches, key=lambda m: m.score, reverse=True)[:top_n]

        if self._primary is not None:
            try:
                result = await self._primary.rerank(query, matches, top_n)
                self._log.debug("reranker.primary_used", top_n=len(result))
                return result
            except Exception as exc:
                self._log.warning(
                    "reranker.primary_failed_falling_back",
                    error=str(exc),
                    reranker_type=type(self._primary).__name__,
                )
                from app.monitoring.metrics import LLM_ERRORS_TOTAL
                try:
                    LLM_ERRORS_TOTAL.labels(error_type="reranker_error").inc()
                except Exception:
                    pass

        result = await self._fallback.rerank(query, matches, top_n)
        self._log.debug("reranker.fallback_used", top_n=len(result))
        return result

    @classmethod
    def from_settings(cls) -> "RerankerPipeline":
        """
        Build a RerankerPipeline from application settings.

        Attempts to create a CohereReranker if COHERE_API_KEY is set and
        reranking is enabled.  Falls back to ScoreFusionReranker otherwise.
        """
        try:
            from app.core.config.settings import get_settings
            settings = get_settings()
            enabled = getattr(settings, "reranking_enabled", True)
            cohere_key = getattr(settings, "cohere_api_key", None)
        except Exception:
            enabled = True
            cohere_key = None

        primary: BaseReranker | None = None
        if enabled and cohere_key:
            try:
                primary = CohereReranker(api_key=cohere_key)
                logger.info("reranker.cohere_initialized", model=COHERE_RERANK_MODEL)
            except Exception as exc:
                logger.warning("reranker.cohere_init_failed", error=str(exc))

        if primary is None:
            logger.info("reranker.using_score_fusion_fallback")

        return cls(primary=primary, fallback=ScoreFusionReranker(), enabled=enabled)

    @classmethod
    def disabled(cls) -> "RerankerPipeline":
        """Return a no-op pipeline that just sorts by score."""
        return cls(enabled=False)
