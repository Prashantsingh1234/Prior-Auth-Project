"""
Embedding worker — processes EmbeddingTask messages.

Execution:
  1. Generate vector embedding via OpenAI text-embedding-3-small (or configured model)
  2. Upsert vector + metadata into Pinecone
  3. Cache embedding in Redis for TTL to avoid re-embedding identical text
  4. Emit monitoring metrics
"""

from __future__ import annotations

import hashlib

import structlog

from app.queues.consumer import BaseConsumer
from app.queues.models import AnyTask, EmbeddingTask
from app.queues.topology import QUEUE_SPECS
from app.monitoring.metrics import METRICS

logger = structlog.get_logger(__name__)


class EmbeddingWorker(BaseConsumer):

    queue_spec = QUEUE_SPECS["embedding"]

    async def process(self, task: AnyTask) -> None:
        assert isinstance(task, EmbeddingTask), f"Expected EmbeddingTask, got {type(task)}"
        log = logger.bind(
            task_id=task.task_id,
            chunk_id=task.chunk_id,
            document_id=task.document_id,
        )
        log.info("embedding_worker.started", model=task.model, text_len=len(task.text))

        # 1. Check cache (avoid re-embedding identical text)
        cache_key = _embedding_cache_key(task.model, task.text)
        vector = await self._get_cached_embedding(cache_key)

        if vector is None:
            vector = await self._generate_embedding(task)
            await self._cache_embedding(cache_key, vector)

        # 2. Upsert into Pinecone
        await self._upsert_vector(task, vector)

        METRICS.llm_tokens_total.labels(
            operation="embedding", token_type="prompt"
        ).inc(_estimate_tokens(task.text))

        log.info(
            "embedding_worker.completed",
            chunk_id=task.chunk_id,
            dim=len(vector),
        )

    # ------------------------------------------------------------------

    async def _get_cached_embedding(self, cache_key: str) -> list[float] | None:
        try:
            from app.services.caching.redis_client import get_redis
            import json
            redis = get_redis()
            cached = await redis.get(cache_key)
            if cached:
                METRICS.cache_hits_total.labels(domain="embedding").inc()
                return json.loads(cached)
        except Exception:
            pass
        METRICS.cache_misses_total.labels(domain="embedding").inc()
        return None

    async def _cache_embedding(self, cache_key: str, vector: list[float]) -> None:
        try:
            from app.services.caching.redis_client import get_redis
            from app.services.caching.keys import TTL_EMBEDDING
            import json
            redis = get_redis()
            await redis.setex(cache_key, TTL_EMBEDDING, json.dumps(vector))
        except Exception as exc:
            logger.debug("embedding_worker.cache_write_failed", error=str(exc))

    async def _generate_embedding(self, task: EmbeddingTask) -> list[float]:
        """Call OpenAI embeddings API and return the float vector."""
        import time
        from openai import AsyncOpenAI
        from app.core.config.settings import get_settings

        settings = get_settings()
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY not configured — cannot generate embeddings")

        client = AsyncOpenAI(
            api_key=settings.openai_api_key.get_secret_value(),
            timeout=30,
        )
        t0 = time.perf_counter()
        resp = await client.embeddings.create(model=task.model, input=task.text)
        elapsed = time.perf_counter() - t0

        METRICS.llm_latency_seconds.labels(operation="embedding").observe(elapsed)
        return resp.data[0].embedding

    async def _upsert_vector(self, task: EmbeddingTask, vector: list[float]) -> None:
        """Upsert the embedding into Pinecone under task.namespace."""
        try:
            from pinecone import Pinecone as PineconeClient
            from app.core.config.settings import get_settings

            settings = get_settings()
            if not settings.pinecone_api_key:
                logger.warning("embedding_worker.pinecone_not_configured")
                return

            pc    = PineconeClient(api_key=settings.pinecone_api_key.get_secret_value())
            index = pc.Index(settings.pinecone_index_name)
            await index.upsert(
                vectors=[
                    {
                        "id":       task.chunk_id,
                        "values":   vector,
                        "metadata": {
                            "document_id":   task.document_id,
                            "text_snippet":  task.text[:200],
                            **task.vector_metadata,
                        },
                    }
                ],
                namespace=task.namespace,
                async_req=True,
            )
            logger.debug(
                "embedding_worker.vector_upserted",
                chunk_id=task.chunk_id,
                namespace=task.namespace,
            )
        except Exception as exc:
            logger.error("embedding_worker.pinecone_upsert_failed", error=str(exc))
            raise


def _embedding_cache_key(model: str, text: str) -> str:
    text_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
    return f"pa:v1:embedding:{model}:{text_hash}"


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)
