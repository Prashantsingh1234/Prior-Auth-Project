"""Azure OpenAI embedding helper (async).

Used as the primary embedding backend when AZURE_OPENAI_EMBEDDING_DEPLOYMENT is configured.
Falls back to OpenAIEmbeddingService when only a direct OpenAI key is available.
"""

from __future__ import annotations

from openai import AsyncAzureOpenAI

from app.core.config.settings import get_settings
from app.services.vector.embeddings import EmbeddingResult


class AzureOpenAIEmbeddingService:
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.azure_openai_api_key:
            raise RuntimeError("Azure OpenAI not configured (AZURE_OPENAI_API_KEY missing)")
        if not settings.azure_openai_endpoint:
            raise RuntimeError("Azure OpenAI not configured (AZURE_OPENAI_ENDPOINT missing)")
        if not settings.azure_openai_embedding_deployment:
            raise RuntimeError(
                "Azure OpenAI embedding deployment not configured "
                "(AZURE_OPENAI_EMBEDDING_DEPLOYMENT missing)"
            )
        self._client = AsyncAzureOpenAI(
            api_key=settings.azure_openai_api_key.get_secret_value(),
            azure_endpoint=settings.azure_openai_endpoint,
            api_version=settings.azure_openai_api_version,
        )
        self._deployment = settings.azure_openai_embedding_deployment

    async def embed_texts(self, texts: list[str], *, batch_size: int = 64) -> EmbeddingResult:
        vectors: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = [t if len(t) <= 12000 else t[:12000] for t in texts[i : i + batch_size]]
            resp = await self._client.embeddings.create(model=self._deployment, input=batch)
            vectors.extend([d.embedding for d in resp.data])
        return EmbeddingResult(vectors=vectors)
