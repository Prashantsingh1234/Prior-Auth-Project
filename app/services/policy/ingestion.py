"""Policy ingestion orchestration (extract -> chunk -> embed -> Pinecone)."""

from __future__ import annotations

import structlog

from app.core.config.settings import get_settings
from app.services.policy.chunking import PolicySemanticChunker
from app.services.policy.metadata import PolicyChunkMetadata, extract_codes, sha256_text
from app.services.vector.pinecone_indexer import PineconePolicyIndexer

logger = structlog.get_logger(__name__)


async def _try_pypdf_extract(content: bytes) -> str:
    """Extract text from PDF bytes using pypdf — pure Python, no external deps."""
    import asyncio
    import io

    def _sync() -> str:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(content))
        parts: list[str] = []
        for page in reader.pages:
            t = page.extract_text() or ""
            if t.strip():
                parts.append(t.strip())
        return "\n\n".join(parts)

    return await asyncio.to_thread(_sync)


def _build_embedder():
    """
    Return the best available embedding service.

    Priority:
      1. Azure OpenAI (if AZURE_OPENAI_EMBEDDING_DEPLOYMENT is set) — preferred.
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

    openai_key = settings.openai_api_key
    if openai_key:
        raw = openai_key.get_secret_value()
        if raw and raw != "your-openai-api-key":
            from app.services.vector.embeddings import OpenAIEmbeddingService
            logger.info("policy.embedder.using_openai")
            return OpenAIEmbeddingService()

    # Development fallback: hash-based local embeddings (not semantically meaningful)
    from app.services.vector.local_embeddings import LocalEmbeddingService
    logger.warning(
        "policy.embedder.using_local_fallback",
        note="No cloud embedding provider configured — using hash-based local embeddings. "
             "Set AZURE_OPENAI_EMBEDDING_DEPLOYMENT or OPENAI_API_KEY for production.",
    )
    return LocalEmbeddingService()


class PolicyIngestionService:
    """Orchestrates the full policy processing pipeline.

    Init is intentionally cheap — heavy resources (OCR pipeline, embedder)
    are created lazily on first use so construction never fails at startup.
    """

    def __init__(self) -> None:
        self._chunker = PolicySemanticChunker()
        self._pipeline = None   # lazy
        self._embedder = None   # lazy
        self._indexer = None    # lazy

    # ------------------------------------------------------------------
    # Lazy accessors
    # ------------------------------------------------------------------

    def _get_pipeline(self):
        if self._pipeline is None:
            from app.services.document import DocumentIngestionPipeline
            self._pipeline = DocumentIngestionPipeline.from_settings()
        return self._pipeline

    def _get_embedder(self):
        if self._embedder is None:
            self._embedder = _build_embedder()
        return self._embedder

    def _get_indexer(self):
        if self._indexer is None:
            self._indexer = PineconePolicyIndexer()
        return self._indexer

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def extract_text(
        self,
        *,
        policy_document_id: str,
        filename: str,
        mime_type: str,
        content: bytes,
    ) -> tuple[str, list[str]]:
        warnings: list[str] = []

        # Fast path: try pypdf first for PDF files.
        # pypdf is pure-Python and handles many PDF encoding variants that pdfplumber misses.
        is_pdf = "pdf" in (mime_type or "").lower() or filename.lower().endswith(".pdf")
        if is_pdf:
            try:
                pdf_text = await _try_pypdf_extract(content)
                if pdf_text.strip():
                    logger.info(
                        "policy.extraction.pypdf_success",
                        policy_id=policy_document_id,
                        chars=len(pdf_text),
                    )
                    return (pdf_text, warnings)
            except Exception as pypdf_err:
                warnings.append(f"pypdf extraction skipped: {pypdf_err}")
                logger.warning(
                    "policy.extraction.pypdf_failed",
                    policy_id=policy_document_id,
                    error=str(pypdf_err),
                )

        # Full pipeline: Azure DI → PaddleOCR → Tesseract → pdfplumber → PyMuPDF
        from app.services.document.models import DocumentCategory, DocumentIngestionRequest
        req = DocumentIngestionRequest(
            document_id=policy_document_id,
            filename=filename,
            mime_type=mime_type,
            expected_category=DocumentCategory.POLICY_DOCUMENT,
        )
        pipeline = self._get_pipeline()
        result = await pipeline.ingest(req, content)
        warnings.extend(result.warnings or [])
        normalized = result.normalized_document
        text = normalized.full_text if normalized else ""
        return (text.strip(), warnings)

    async def process_and_index(
        self,
        *,
        policy_id: str,
        policy_key: str,
        policy_name: str,
        policy_version: str,
        policy_type: str | None,
        effective_date,
        namespace: str,
        text: str,
    ) -> tuple[int, list[dict], list[str]]:
        """
        Chunk, embed, and upsert into Pinecone.

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
            meta = PolicyChunkMetadata(
                policy_id=policy_id,
                policy_name=policy_name,
                policy_version=policy_version,
                policy_type=policy_type,
                effective_date=effective_date,
                namespace=namespace,
                chunk_index=c.index,
                chunk_id=vector_id,
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

        logger.info(
            "policy.ingestion.embedding",
            policy_id=policy_id,
            total_chunks=len(chunks),
        )
        embedder = self._get_embedder()
        try:
            vectors = (await embedder.embed_texts(embed_texts)).vectors
        except RuntimeError as embed_exc:
            err_str = str(embed_exc)
            if "not found" in err_str.lower() or "deploymentnotfound" in err_str.lower():
                # Primary provider's deployment doesn't exist — fall through to local embeddings
                from app.services.vector.local_embeddings import LocalEmbeddingService
                self._embedder = LocalEmbeddingService()
                warnings.append(
                    f"Cloud embedding unavailable ({err_str[:200]}). "
                    "Using hash-based local embeddings. Set up Azure OpenAI deployment for production."
                )
                vectors = (await self._embedder.embed_texts(embed_texts)).vectors
            else:
                raise

        logger.info(
            "policy.ingestion.upserting_to_pinecone",
            policy_id=policy_id,
            namespace=namespace,
            vector_count=len(ids),
        )
        indexer = self._get_indexer()
        await indexer.upsert(
            namespace=namespace,
            ids=ids,
            vectors=vectors,
            metadatas=pinecone_meta,
        )

        logger.info(
            "policy.ingestion.complete",
            policy_id=policy_id,
            total_chunks=len(chunk_rows),
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
