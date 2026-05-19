"""Azure OpenAI embedding helper (async).

Prefers the dedicated embedding resource (AZURE_EMBEDDING_API_KEY /
AZURE_EMBEDDING_ENDPOINT) when configured, which lets the chat and
embedding workloads use separate Azure OpenAI resources and quota pools.
Falls back to the main AZURE_OPENAI_API_KEY / AZURE_OPENAI_ENDPOINT when
the dedicated resource is not configured.
"""

from __future__ import annotations

from openai import AsyncAzureOpenAI

from app.core.config.settings import get_settings
from app.services.vector.embeddings import EmbeddingResult


class AzureOpenAIEmbeddingService:
    def __init__(self) -> None:
        settings = get_settings()

        # Prefer dedicated embedding resource; fall back to main Azure OpenAI resource.
        api_key_secret = settings.azure_embedding_api_key or settings.azure_openai_api_key
        endpoint = settings.azure_embedding_endpoint or settings.azure_openai_endpoint
        api_version = settings.azure_embedding_api_version or settings.azure_openai_api_version

        if not api_key_secret:
            raise RuntimeError(
                "Azure OpenAI embedding not configured: "
                "set AZURE_EMBEDDING_API_KEY (dedicated) or AZURE_OPENAI_API_KEY"
            )
        if not endpoint:
            raise RuntimeError(
                "Azure OpenAI embedding not configured: "
                "set AZURE_EMBEDDING_ENDPOINT (dedicated) or AZURE_OPENAI_ENDPOINT"
            )
        if not settings.azure_openai_embedding_deployment:
            raise RuntimeError(
                "Azure OpenAI embedding deployment not configured "
                "(AZURE_OPENAI_EMBEDDING_DEPLOYMENT missing)"
            )

        self._client = AsyncAzureOpenAI(
            api_key=api_key_secret.get_secret_value(),
            azure_endpoint=endpoint,
            api_version=api_version,
        )
        self._deployment = settings.azure_openai_embedding_deployment

    async def embed_texts(self, texts: list[str], *, batch_size: int = 64) -> EmbeddingResult:
        vectors: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = [t if len(t) <= 12000 else t[:12000] for t in texts[i : i + batch_size]]
            try:
                resp = await self._client.embeddings.create(model=self._deployment, input=batch)
            except Exception as exc:
                err_str = str(exc)
                if "404" in err_str or "DeploymentNotFound" in err_str or "not found" in err_str.lower():
                    raise RuntimeError(
                        f"Azure OpenAI embedding deployment '{self._deployment}' not found. "
                        "Go to Azure AI Studio → Deployments and confirm the deployment exists, "
                        "then verify AZURE_OPENAI_EMBEDDING_DEPLOYMENT matches its name."
                    ) from exc
                raise
            vectors.extend([d.embedding for d in resp.data])
        return EmbeddingResult(vectors=vectors)
