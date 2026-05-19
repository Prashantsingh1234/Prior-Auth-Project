"""OpenAI embedding helper (async)."""

from __future__ import annotations

from dataclasses import dataclass

from openai import AsyncOpenAI

from app.core.config.settings import get_settings


@dataclass(frozen=True)
class EmbeddingResult:
    vectors: list[list[float]]


class OpenAIEmbeddingService:
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.openai_api_key:
            raise RuntimeError("OpenAI not configured (OPENAI_API_KEY missing)")
        self._client = AsyncOpenAI(
            api_key=settings.openai_api_key.get_secret_value(),
            timeout=settings.openai_request_timeout,
        )
        self._model = getattr(settings, "openai_embedding_model", "text-embedding-3-small")

    async def embed_texts(self, texts: list[str], *, batch_size: int = 64) -> EmbeddingResult:
        vectors: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = [t if len(t) <= 12000 else t[:12000] for t in texts[i : i + batch_size]]
            resp = await self._client.embeddings.create(model=self._model, input=batch)
            vectors.extend([d.embedding for d in resp.data])
        return EmbeddingResult(vectors=vectors)

