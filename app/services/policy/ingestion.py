"""Policy ingestion orchestration (extract -> chunk -> embed -> Pinecone)."""

from __future__ import annotations

import structlog

from app.core.config.settings import get_settings
from app.services.document import DocumentIngestionPipeline
from app.services.document.models import DocumentCategory, DocumentIngestionRequest
from app.services.policy.chunking import PolicySemanticChunker
from app.services.policy.metadata import PolicyChunkMetadata, extract_codes, sha256_text
from app.services.vector.pinecone_indexer import PineconePolicyIndexer

logger = structlog.get_logger(__name__)


def _build_embedder():
    """
    Return the best available embedding service.

    Priority:
      1. Azure OpenAI (if AZURE_OPENAI_EMBEDDING_DEPLOYMENT is set) — preferred
         because it uses real credentials from the Azure subscription.
      2. Direct OpenAI (if OPENAI_API_KEY is set and not the placeholder value).
    """
    settings = get_settings()

    if (
        settings.azure_openai_api_key
        and settings.azure_openai_endpoint
        and settings.azure_openai_embedding_deployment
    ):
        from app.services.vector.azure_embeddings import AzureOpenAIEmbeddingService
        logger.info("policy.embedder.using_azure_openai")
        return AzureOpenAIEmbeddingService()

    from app.services.vector.embeddings import OpenAIEmbeddingService
    logger.info("policy.embedder.using_openai")
    return OpenAIEmbeddingService()


class PolicyIngestionService:
    def __init__(self) -> None:
        self._pipeline = DocumentIngestionPipeline.from_settings()
        self._chunker = PolicySemanticChunker()
        self._embedder = _build_embedder()
        self._indexer = PineconePolicyIndexer()

    async def extract_text(
        self,
        *,
        policy_document_id: str,
        filename: str,
        mime_type: str,
        content: bytes,
    ) -> tuple[str, list[str]]:
        req = DocumentIngestionRequest(
            document_id=policy_document_id,
            filename=filename,
            mime_type=mime_type,
            expected_category=DocumentCategory.POLICY_DOCUMENT,
        )
        result = await self._pipeline.ingest(req, content)
        warnings = list(result.warnings or [])
        normalized = result.normalized_document
        text = normalized.full_text if normalized else ""
        return (text.strip(), warnings)

    async def process_and_index(
        self,
        *,
        policy_key: str,
        policy_name: str,
        policy_version: str,
        policy_type: str | None,
        effective_date,
        namespace: str,
        text: str,
    ) -> tuple[int, list[dict], list[str]]:
        """
        Returns:
          total_chunks, chunk_rows_for_db, warnings
        """
        warnings: list[str] = []
        chunks = self._chunker.chunk(text)
        if not chunks:
            return (0, [], ["No extractable policy text to chunk"])

        ids: list[str] = []
        embed_texts: list[str] = []
        pinecone_meta: list[dict] = []
        chunk_rows: list[dict] = []

        for c in chunks:
            cpt, icd = extract_codes(c.text)
            chunk_hash = sha256_text(c.text)
            vector_id = f"{policy_key}:{c.index}"
            chunk_id = vector_id
            meta = PolicyChunkMetadata(
                policy_name=policy_name,
                policy_version=policy_version,
                policy_type=policy_type,
                effective_date=effective_date,
                namespace=namespace,
                chunk_index=c.index,
                chunk_id=chunk_id,
                cpt_codes=cpt,
                icd_codes=icd,
            )
            ids.append(vector_id)
            embed_texts.append(c.text)
            pinecone_meta.append(meta.to_pinecone_dict())
            chunk_rows.append(
                {
                    "chunk_index": c.index,
                    "chunk_text": c.text,
                    "chunk_length": c.length,
                    "chunk_overlap": c.overlap,
                    "cpt_codes": cpt,
                    "icd_codes": icd,
                    "chunk_metadata": meta.to_pinecone_dict(),
                    "pinecone_vector_id": vector_id,
                    "chunk_hash": chunk_hash,
                }
            )

        vectors = (await self._embedder.embed_texts(embed_texts)).vectors
        await self._indexer.upsert(
            namespace=namespace,
            ids=ids,
            vectors=vectors,
            metadatas=pinecone_meta,
        )

        return (len(chunk_rows), chunk_rows, warnings)


def build_policy_key(name_or_filename: str, version: str | None = None) -> str:
    """
    Deterministic-ish slug used as a stable policy identifier.

    Policy keys are used in vector IDs, so keep them URL/ID friendly.
    """
    import re

    base = (name_or_filename or "").strip().lower()
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    base = re.sub(r"-{2,}", "-", base)
    if not base:
        base = "policy"
    if version:
        v = re.sub(r"[^a-z0-9.]+", "-", version.strip().lower()).strip("-")
        if v:
            base = f"{base}-v{v}"
    return base[:120]


def default_namespace() -> str:
    return get_settings().pinecone_namespace
