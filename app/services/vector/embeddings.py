"""
Embedding generation pipeline.

Uses OpenAI's embeddings API (text-embedding-3-small by default) with:
- Cache-first lookup via EmbeddingCache (24-hour TTL)
- Batch API calls to minimize latency and cost
- Automatic retry via tenacity on transient OpenAI errors
- Token and latency metrics tracking
- Graceful error escalation

Embedding dimensions:
    text-embedding-3-small  →  1536  (default, best cost:quality ratio)
    text-embedding-3-large  →  3072  (higher accuracy, 2× cost)
    text-embedding-ada-002  →  1536  (legacy, not recommended for new work)
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import structlog
from openai import AsyncOpenAI, APIError, APITimeoutError, RateLimitError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config.settings import get_settings
from app.core.exceptions.base import PABaseException
from app.services.caching.embedding_cache import EmbeddingCache

if TYPE_CHECKING:
    pass

logger = structlog.get_logger(__name__)

# Dimensions for each supported model
EMBEDDING_DIMENSIONS: dict[str, int] = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}

# Retry on transient OpenAI errors only
_OPENAI_TRANSIENT_ERRORS = (APITimeoutError, RateLimitError)


class EmbeddingError(PABaseException):
    """Raised when embedding generation fails after all retries."""
    status_code = 503
    error_code = "EMBEDDING_ERROR"


class EmbeddingService:
    """
    Async embedding generation with cache-first lookup and batch support.

    Usage:
        service = EmbeddingService.from_settings()
        vector = await service.embed_text("CGM device prior auth criteria...")
        vectors = await service.embed_batch(["text1", "text2", "text3"])
    """

    # Pinecone / OpenAI hard limit — do not exceed
    MAX_BATCH_SIZE = 100

    def __init__(
        self,
        openai_api_key: str,
        model: str = "text-embedding-3-small",
        timeout: int = 30,
    ) -> None:
        self._client = AsyncOpenAI(
            api_key=openai_api_key,
            timeout=timeout,
        )
        self._model = model
        self._dimension = EMBEDDING_DIMENSIONS.get(model, 1536)
        self._cache = EmbeddingCache()
        self._log = structlog.get_logger(
            self.__class__.__name__,
            model=model,
        )

    @classmethod
    def from_settings(cls) -> "EmbeddingService":
        """Factory that reads configuration from Settings."""
        settings = get_settings()
        if not settings.openai_api_key:
            raise EmbeddingError(
                details={"reason": "OPENAI_API_KEY not configured"}
            )
        return cls(
            openai_api_key=settings.openai_api_key.get_secret_value(),
            model="text-embedding-3-small",
            timeout=settings.openai_request_timeout,
        )

    @property
    def model(self) -> str:
        return self._model

    @property
    def dimension(self) -> int:
        return self._dimension

    # ------------------------------------------------------------------
    # Single text embedding (cache-first)
    # ------------------------------------------------------------------

    async def embed_text(self, text: str) -> list[float]:
        """
        Generate (or retrieve from cache) the embedding for a single text.

        Args:
            text: The text to embed. Will be truncated to ~8000 tokens
                  by the API if longer.

        Returns:
            List[float] embedding vector.
        """
        if not text or not text.strip():
            raise EmbeddingError(details={"reason": "Empty text cannot be embedded"})

        # Cache lookup
        cached = await self._cache.get(self._model, text)
        if cached is not None:
            self._log.debug("embedding.cache_hit", text_len=len(text))
            return cached

        # API call
        vector = await self._call_api([text])
        single_vector = vector[0]

        # Store in cache (fire-and-forget)
        await self._cache.set(self._model, text, single_vector)

        return single_vector

    # ------------------------------------------------------------------
    # Batch embedding (cache-first, one API call for all misses)
    # ------------------------------------------------------------------

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for multiple texts in one API call.

        Cache is checked first; only cache-missing texts hit the API.
        Preserves input order in the output list.

        Args:
            texts: List of texts to embed. Must be non-empty.

        Returns:
            List of embedding vectors in the same order as input.
        """
        if not texts:
            return []

        # Batch cache lookup
        cached_map = await self._cache.get_batch(self._model, texts)

        # Identify texts not in cache
        misses = [t for t in texts if cached_map[t] is None]

        if misses:
            self._log.debug(
                "embedding.batch_api_call",
                total=len(texts),
                misses=len(misses),
            )
            # Process in sub-batches respecting API limit
            miss_vectors: list[list[float]] = []
            for i in range(0, len(misses), self.MAX_BATCH_SIZE):
                sub_batch = misses[i : i + self.MAX_BATCH_SIZE]
                sub_vectors = await self._call_api(sub_batch)
                miss_vectors.extend(sub_vectors)

            # Store misses in cache and update the map
            for text, vector in zip(misses, miss_vectors):
                cached_map[text] = vector
                await self._cache.set(self._model, text, vector)

        return [cached_map[t] for t in texts]  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Internal API caller with retry
    # ------------------------------------------------------------------

    @retry(
        retry=retry_if_exception_type(_OPENAI_TRANSIENT_ERRORS),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=10.0),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def _call_api(self, texts: list[str]) -> list[list[float]]:
        """
        Call the OpenAI Embeddings API and return vectors.

        Retries up to 3× on transient errors (timeout, rate limit).
        Raises EmbeddingError on non-retryable API failures.
        """
        start = time.perf_counter()
        try:
            response = await self._client.embeddings.create(
                model=self._model,
                input=texts,
            )
            latency_ms = (time.perf_counter() - start) * 1000

            vectors = [item.embedding for item in response.data]
            total_tokens = response.usage.total_tokens if response.usage else 0

            self._log.info(
                "embedding.api_success",
                count=len(texts),
                tokens=total_tokens,
                latency_ms=round(latency_ms, 1),
            )
            self._track_metrics(total_tokens, latency_ms)
            return vectors

        except _OPENAI_TRANSIENT_ERRORS:
            raise  # Let tenacity handle retry

        except APIError as exc:
            self._log.error(
                "embedding.api_error",
                error=str(exc),
                status_code=getattr(exc, "status_code", None),
            )
            raise EmbeddingError(details={"error": str(exc)}) from exc

    # ------------------------------------------------------------------
    # Sparse vector generation (for hybrid search)
    # ------------------------------------------------------------------

    def build_sparse_vector(
        self,
        text: str,
        medical_codes: list[str],
        vocab_size: int = 30_000,
    ) -> "SparseVectorData":
        """
        Build a BM25-style sparse vector for hybrid Pinecone retrieval.

        Maps each medical code (CPT, ICD-10) to a vocabulary index using
        a deterministic hash, weighted by inverse document frequency (IDF)
        approximation. This improves recall for exact code lookups that
        semantic embeddings sometimes miss.

        Args:
            text:          Source text (used for term frequency)
            medical_codes: CPT + ICD codes associated with the document
            vocab_size:    Size of the virtual vocabulary (hash modulus)

        Returns:
            SparseVectorData with indices and weights.
        """
        from app.services.vector.sparse import build_medical_sparse_vector
        return build_medical_sparse_vector(text, medical_codes, vocab_size)

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def _track_metrics(self, total_tokens: int, latency_ms: float) -> None:
        try:
            from app.monitoring.metrics import LLM_TOKENS_TOTAL, LLM_LATENCY_SECONDS
            LLM_TOKENS_TOTAL.labels(
                operation="embedding", token_type="total"
            ).inc(total_tokens)
            LLM_LATENCY_SECONDS.labels(operation="embedding").observe(
                latency_ms / 1000
            )
        except Exception:
            pass


# Named tuple returned by build_sparse_vector (avoids circular import from schemas)
class SparseVectorData:
    __slots__ = ("indices", "values")

    def __init__(self, indices: list[int], values: list[float]) -> None:
        self.indices = indices
        self.values = values
