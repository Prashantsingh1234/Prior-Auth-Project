"""
Main orchestrator for the policy ingestion pipeline.

Stage order:
  1. PDF parsing          → ParsedDocument
  2. Duplicate detection  → DuplicateCheckResult (short-circuit if duplicate)
  3. Metadata extraction  → ExtractedMetadata  (merged into request)
  4. Criterion chunking   → ChunkingResult
  5. Chunk validation     → BatchValidationResult
  6. Embedding + upload   → vectors upserted to Pinecone
  7. Result assembly      → IngestionResult

All stages are async.  Failures in non-critical stages (extraction, validation)
produce warnings rather than hard failures — the pipeline never partially
uploads without returning a result the caller can inspect.
"""

from __future__ import annotations

import structlog
from typing import IO

from app.services.ingestion.chunker import PolicyChunker
from app.services.ingestion.dedup import DuplicateDetector
from app.services.ingestion.extractor import MetadataExtractor
from app.services.ingestion.models import (
    IngestionResult,
    IngestionStatus,
    PolicyIngestionRequest,
)
from app.services.ingestion.pdf_parser import PDFParser
from app.services.ingestion.validator import ChunkValidator
from app.services.vector.embeddings import EmbeddingService
from app.services.vector.indexer import PolicyIndexer
from app.services.vector.pinecone_client import PineconeClient
from app.services.vector.schemas import PolicyChunkMetadata
from app.services.vector.upsert import VectorUpsertService

logger = structlog.get_logger(__name__)


class IngestionPipeline:
    """
    End-to-end policy ingestion pipeline.

    Usage:
        pipeline = IngestionPipeline.from_clients(
            pinecone_client=get_pinecone_client(),
            embedding_service=EmbeddingService.from_settings(),
        )
        result = await pipeline.ingest(request, pdf_bytes)

    The pipeline is stateless across calls — safe to reuse.
    """

    def __init__(
        self,
        pdf_parser: PDFParser,
        chunker: PolicyChunker,
        extractor: MetadataExtractor,
        validator: ChunkValidator,
        dedup: DuplicateDetector,
        indexer: PolicyIndexer,
    ) -> None:
        self._parser    = pdf_parser
        self._chunker   = chunker
        self._extractor = extractor
        self._validator = validator
        self._dedup     = dedup
        self._indexer   = indexer
        self._log       = structlog.get_logger(self.__class__.__name__)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_clients(
        cls,
        pinecone_client: PineconeClient,
        embedding_service: EmbeddingService,
        ocr_enabled: bool = True,
    ) -> "IngestionPipeline":
        upsert_service = VectorUpsertService(pinecone_client)
        indexer        = PolicyIndexer(embedding_service, upsert_service)
        return cls(
            pdf_parser=PDFParser(ocr_enabled=ocr_enabled),
            chunker=PolicyChunker(),
            extractor=MetadataExtractor(),
            validator=ChunkValidator(),
            dedup=DuplicateDetector(pinecone_client),
            indexer=indexer,
        )

    # ------------------------------------------------------------------
    # Main entry points
    # ------------------------------------------------------------------

    async def ingest(
        self,
        request: PolicyIngestionRequest,
        pdf_bytes: bytes,
        namespace: str | None = None,
        allow_reindex: bool = False,
    ) -> IngestionResult:
        """
        Ingest a policy PDF end-to-end.

        Args:
            request:        Caller-supplied metadata + policy_id
            pdf_bytes:      Raw PDF bytes
            namespace:      Pinecone namespace override (defaults to request.namespace)
            allow_reindex:  If True, replace existing vectors when a version
                            conflict is detected.  If False, return DUPLICATE.

        Returns:
            IngestionResult describing the outcome of each stage.
        """
        ns = namespace or request.namespace
        warnings: list[str] = []
        errors:   list[str] = []

        self._log.info(
            "pipeline.started",
            policy_id=request.policy_id,
            namespace=ns,
        )

        # ----------------------------------------------------------
        # Stage 1: PDF parsing
        # ----------------------------------------------------------
        try:
            parsed_doc = await self._parser.parse(pdf_bytes)
        except Exception as err:
            self._log.error(
                "pipeline.pdf_parse_failed",
                policy_id=request.policy_id,
                error=str(err),
            )
            return IngestionResult(
                policy_id=request.policy_id,
                status=IngestionStatus.FAILED,
                document_hash="",
                total_pages=0,
                total_chunks_indexed=0,
                valid_chunks=0,
                invalid_chunks=0,
                used_ocr=False,
                strategy_used="none",
                extracted_cpt_codes=[],
                extracted_icd_codes=[],
                effective_date=None,
                policy_version=None,
                errors=[f"PDF parsing failed: {err}"],
            )

        # ----------------------------------------------------------
        # Stage 2: Duplicate detection
        # ----------------------------------------------------------
        dedup_result = await self._dedup.check(
            document_hash=parsed_doc.document_hash,
            policy_id=request.policy_id,
            namespace=ns,
        )
        if dedup_result.is_duplicate:
            self._log.info(
                "pipeline.duplicate_detected",
                policy_id=request.policy_id,
                existing_policy_id=dedup_result.existing_policy_id,
            )
            return IngestionResult(
                policy_id=request.policy_id,
                status=IngestionStatus.DUPLICATE,
                document_hash=parsed_doc.document_hash,
                total_pages=parsed_doc.total_pages,
                total_chunks_indexed=0,
                valid_chunks=0,
                invalid_chunks=0,
                used_ocr=bool(parsed_doc.used_ocr_pages),
                strategy_used="none",
                extracted_cpt_codes=[],
                extracted_icd_codes=[],
                effective_date=request.effective_date,
                policy_version=request.policy_version,
                metadata={
                    "existing_policy_id": dedup_result.existing_policy_id,
                    "existing_version": dedup_result.existing_version,
                },
            )

        # Check for version conflict (same policy_id, different content)
        conflict, existing_hash = await self._dedup.check_version_conflict(
            policy_id=request.policy_id,
            document_hash=parsed_doc.document_hash,
            namespace=ns,
        )
        if conflict and not allow_reindex:
            warnings.append(
                f"Version conflict: policy_id '{request.policy_id}' already exists "
                f"with different content. Pass allow_reindex=True to replace."
            )

        # ----------------------------------------------------------
        # Stage 3: Metadata extraction
        # ----------------------------------------------------------
        extracted = self._extractor.extract(parsed_doc.full_text)
        enriched_request = MetadataExtractor.merge(request, extracted)

        # ----------------------------------------------------------
        # Stage 4: Criterion-aware chunking
        # ----------------------------------------------------------
        chunking_result = self._chunker.chunk(parsed_doc)
        if not chunking_result.criteria:
            errors.append("Chunking produced zero criteria — document may be empty")
            return IngestionResult(
                policy_id=request.policy_id,
                status=IngestionStatus.FAILED,
                document_hash=parsed_doc.document_hash,
                total_pages=parsed_doc.total_pages,
                total_chunks_indexed=0,
                valid_chunks=0,
                invalid_chunks=0,
                used_ocr=bool(parsed_doc.used_ocr_pages),
                strategy_used=chunking_result.strategy_used,
                extracted_cpt_codes=enriched_request.cpt_codes,
                extracted_icd_codes=enriched_request.icd_codes,
                effective_date=enriched_request.effective_date,
                policy_version=enriched_request.policy_version,
                errors=errors,
            )

        warnings.extend(chunking_result.warnings)

        # ----------------------------------------------------------
        # Stage 5: Chunk validation
        # ----------------------------------------------------------
        validation = self._validator.validate_batch(chunking_result.criteria)
        if validation.warnings:
            for vr in validation.results:
                warnings.extend(vr.warnings)

        if not validation.valid_criteria:
            errors.append("All chunks failed validation — nothing to index")
            return IngestionResult(
                policy_id=request.policy_id,
                status=IngestionStatus.FAILED,
                document_hash=parsed_doc.document_hash,
                total_pages=parsed_doc.total_pages,
                total_chunks_indexed=0,
                valid_chunks=0,
                invalid_chunks=len(validation.invalid_criteria),
                used_ocr=bool(parsed_doc.used_ocr_pages),
                strategy_used=chunking_result.strategy_used,
                extracted_cpt_codes=enriched_request.cpt_codes,
                extracted_icd_codes=enriched_request.icd_codes,
                effective_date=enriched_request.effective_date,
                policy_version=enriched_request.policy_version,
                errors=errors,
            )

        # ----------------------------------------------------------
        # Stage 6: Build enriched text → embed → upsert to Pinecone
        # ----------------------------------------------------------
        base_metadata = PolicyChunkMetadata(
            policy_id=enriched_request.policy_id,
            policy_name=enriched_request.policy_name,
            payer_name=enriched_request.payer_name,
            service_type=enriched_request.service_type,
            policy_version=enriched_request.policy_version,
            effective_date=enriched_request.effective_date,
            expiration_date=enriched_request.expiration_date,
            cpt_codes=enriched_request.cpt_codes,
            icd_codes=enriched_request.icd_codes,
            document_hash=parsed_doc.document_hash,
            chunk_index=0,         # overwritten per-chunk by PolicyIndexer
            total_chunks=0,        # overwritten by PolicyIndexer
            chunk_text="",         # overwritten by PolicyIndexer
        )

        # Build the full enriched text corpus for the indexer
        enriched_texts = [c.enriched_text for c in validation.valid_criteria]
        full_enriched_text = "\n\n".join(enriched_texts)

        if conflict and allow_reindex:
            reindex_result = await self._indexer.reindex_policy(
                policy_text=full_enriched_text,
                metadata=base_metadata,
                namespace=ns,
            )
            chunks_indexed = reindex_result.get("upserted", 0)
        else:
            chunks_indexed = await self._indexer.index_policy(
                policy_text=full_enriched_text,
                metadata=base_metadata,
                namespace=ns,
            )

        # ----------------------------------------------------------
        # Stage 7: Assemble result
        # ----------------------------------------------------------
        invalid_count = len(validation.invalid_criteria)
        status = (
            IngestionStatus.PARTIAL if invalid_count > 0
            else IngestionStatus.SUCCESS
        )

        self._log.info(
            "pipeline.complete",
            policy_id=request.policy_id,
            status=status,
            chunks_indexed=chunks_indexed,
            invalid_chunks=invalid_count,
            used_ocr=bool(parsed_doc.used_ocr_pages),
        )

        return IngestionResult(
            policy_id=request.policy_id,
            status=status,
            document_hash=parsed_doc.document_hash,
            total_pages=parsed_doc.total_pages,
            total_chunks_indexed=chunks_indexed,
            valid_chunks=len(validation.valid_criteria),
            invalid_chunks=invalid_count,
            used_ocr=bool(parsed_doc.used_ocr_pages),
            strategy_used=chunking_result.strategy_used,
            extracted_cpt_codes=enriched_request.cpt_codes,
            extracted_icd_codes=enriched_request.icd_codes,
            effective_date=enriched_request.effective_date,
            policy_version=enriched_request.policy_version,
            warnings=warnings,
            errors=errors,
            metadata={
                "sections_found": chunking_result.sections_found,
                "payer_name": enriched_request.payer_name,
                "service_type": enriched_request.service_type,
                "revision_history": extracted.revision_history,
            },
        )

    async def ingest_file(
        self,
        request: PolicyIngestionRequest,
        file_obj: IO[bytes],
        namespace: str | None = None,
        allow_reindex: bool = False,
    ) -> IngestionResult:
        """Convenience wrapper accepting a file-like object."""
        return await self.ingest(
            request=request,
            pdf_bytes=file_obj.read(),
            namespace=namespace,
            allow_reindex=allow_reindex,
        )
