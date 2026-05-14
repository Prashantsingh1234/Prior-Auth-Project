"""
Main document ingestion pipeline orchestrator.

Stage order:
  1. Validation      — file size, non-empty, sane mime type
  2. Detection       — magic bytes → DocumentType
  3. Dedup           — SHA-256 hash check (optional, caller-supplied check fn)
  4. Normalization   — text extraction / OCR / JSON parse
  5. Layout parsing  — sections, category, entities, tables
  6. Audit log       — structured event with all quality signals
  7. Result          — DocumentIngestionResult

All stages are async.  Layout parsing and dedup are synchronous but fast.
Non-critical failures (layout errors, entity extraction) produce warnings
rather than hard failures.
"""

from __future__ import annotations

import hashlib
import time
from typing import Awaitable, Callable

import structlog

from app.services.document.detector import DocumentDetector
from app.services.document.layout_parser import LayoutParser
from app.services.document.models import (
    DocumentCategory,
    DocumentIngestionRequest,
    DocumentIngestionResult,
    DocumentType,
    IngestionStatus,
    NormalizedDocument,
)
from app.services.document.normalizer import DocumentNormalizer
from app.services.ocr.base import OCRProvider
from app.services.ocr.orchestrator import OCROrchestrator

logger = structlog.get_logger(__name__)

# Maximum file size: 100 MB
_MAX_FILE_SIZE = 100 * 1024 * 1024

# Duplicate check callable type: (document_hash: str) -> bool
DuplicateCheckFn = Callable[[str], Awaitable[bool]]


class DocumentIngestionPipeline:
    """
    End-to-end healthcare document ingestion pipeline.

    Usage:
        pipeline = DocumentIngestionPipeline.from_settings()
        result = await pipeline.ingest(request, file_bytes)

    The pipeline is stateless across calls — safe to reuse concurrently.
    """

    def __init__(
        self,
        detector:   DocumentDetector,
        normalizer: DocumentNormalizer,
        layout:     LayoutParser,
    ) -> None:
        self._detector   = detector
        self._normalizer = normalizer
        self._layout     = layout
        self._log        = structlog.get_logger(self.__class__.__name__)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_settings(cls) -> "DocumentIngestionPipeline":
        orchestrator = OCROrchestrator.from_settings()
        return cls(
            detector=DocumentDetector(),
            normalizer=DocumentNormalizer(orchestrator),
            layout=LayoutParser(),
        )

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def ingest(
        self,
        request: DocumentIngestionRequest,
        content: bytes,
        duplicate_check: DuplicateCheckFn | None = None,
    ) -> DocumentIngestionResult:
        """
        Ingest a healthcare document end-to-end.

        Args:
            request:         Caller-supplied document metadata
            content:         Raw file bytes
            duplicate_check: Optional async callable — receives document_hash,
                             returns True if already ingested.

        Returns:
            DocumentIngestionResult describing the outcome of every stage.
        """
        start = time.monotonic()
        warnings: list[str] = []
        errors:   list[str] = []

        self._log.info(
            "pipeline.started",
            document_id=request.document_id,
            filename=request.filename,
            size_bytes=len(content),
        )

        # ----------------------------------------------------------
        # Stage 1: Validation
        # ----------------------------------------------------------
        validation_error = self._validate(content, request.filename)
        if validation_error:
            return self._failed_result(
                request, content, errors=[validation_error],
                status=IngestionStatus.UNSUPPORTED,
            )

        # ----------------------------------------------------------
        # Stage 2: File type detection
        # ----------------------------------------------------------
        doc_type = self._detector.detect(
            content,
            mime_hint=request.mime_type,
            filename=request.filename,
        )
        if not self._detector.is_supported(doc_type):
            return self._failed_result(
                request, content,
                errors=[f"Unsupported document type: {doc_type}"],
                status=IngestionStatus.UNSUPPORTED,
                doc_type=doc_type,
            )

        effective_mime = request.mime_type or self._detector.get_mime_type(doc_type)

        # ----------------------------------------------------------
        # Stage 3: Duplicate detection
        # ----------------------------------------------------------
        doc_hash = hashlib.sha256(content).hexdigest()
        if duplicate_check is not None:
            try:
                is_dup = await duplicate_check(doc_hash)
                if is_dup:
                    self._log.info(
                        "pipeline.duplicate",
                        document_id=request.document_id,
                        hash=doc_hash[:16],
                    )
                    self._emit_ingestion_metric(doc_type, "duplicate")
                    return DocumentIngestionResult(
                        document_id=request.document_id,
                        status=IngestionStatus.DUPLICATE,
                        document_hash=doc_hash,
                        document_type=doc_type,
                        document_category=DocumentCategory.GENERAL,
                        normalization_method=__import__(
                            "app.services.document.models", fromlist=["NormalizationMethod"]
                        ).NormalizationMethod.DIRECT_PARSE,
                        total_pages=0,
                        overall_confidence=0.0,
                        ocr_provider_used=OCRProvider.NONE,
                        fallback_triggered=False,
                        tables_extracted=0,
                        key_values_extracted=0,
                        sections_found=0,
                        processing_time_ms=(time.monotonic() - start) * 1000,
                    )
            except Exception as err:
                warnings.append(f"Duplicate check failed (non-fatal): {err}")

        # ----------------------------------------------------------
        # Stage 4: Normalization (OCR / text extraction)
        # ----------------------------------------------------------
        try:
            category = request.expected_category or DocumentCategory.GENERAL
            normalized: NormalizedDocument = await self._normalizer.normalize(
                content=content,
                doc_type=doc_type,
                document_id=request.document_id,
                filename=request.filename,
                mime_type=effective_mime,
                category=category,
            )
            warnings.extend(normalized.warnings)
        except Exception as err:
            self._log.error(
                "pipeline.normalization_failed",
                document_id=request.document_id,
                error=str(err),
            )
            self._emit_ingestion_metric(doc_type, "failed")
            return self._failed_result(
                request, content,
                errors=[f"Normalization failed: {err}"],
                doc_type=doc_type,
            )

        if not normalized.full_text.strip():
            warnings.append("Document produced no extractable text")

        # ----------------------------------------------------------
        # Stage 5: Layout parsing
        # ----------------------------------------------------------
        try:
            normalized = self._layout.parse(normalized)
        except Exception as err:
            warnings.append(f"Layout parsing failed (non-fatal): {err}")
            self._log.warning(
                "pipeline.layout_parse_failed",
                document_id=request.document_id,
                error=str(err),
            )

        # ----------------------------------------------------------
        # Stage 6: Audit log
        # ----------------------------------------------------------
        elapsed_ms = (time.monotonic() - start) * 1000
        self._audit_log(request, normalized, elapsed_ms)

        # ----------------------------------------------------------
        # Stage 7: Assemble result
        # ----------------------------------------------------------
        status = (
            IngestionStatus.PARTIAL if warnings
            else IngestionStatus.SUCCESS
        )
        self._emit_ingestion_metric(doc_type, status.value.lower())

        from app.monitoring.metrics import DOCUMENT_INGESTION_SECONDS
        try:
            DOCUMENT_INGESTION_SECONDS.labels(
                document_type=doc_type.value
            ).observe(elapsed_ms / 1000)
        except Exception:
            pass

        self._log.info(
            "pipeline.complete",
            document_id=request.document_id,
            status=status,
            category=normalized.document_category,
            pages=normalized.total_pages,
            confidence=normalized.overall_confidence,
            elapsed_ms=round(elapsed_ms, 1),
        )

        return DocumentIngestionResult(
            document_id=request.document_id,
            status=status,
            document_hash=doc_hash,
            document_type=normalized.document_type,
            document_category=normalized.document_category,
            normalization_method=normalized.normalization_method,
            total_pages=normalized.total_pages,
            overall_confidence=normalized.overall_confidence,
            ocr_provider_used=normalized.pages[0].ocr_provider if normalized.pages else OCRProvider.NONE,
            fallback_triggered=normalized.fallback_triggered,
            fallback_pages=normalized.fallback_pages,
            tables_extracted=len(normalized.all_tables),
            key_values_extracted=len(normalized.all_key_values),
            sections_found=len(normalized.sections),
            processing_time_ms=elapsed_ms,
            warnings=warnings,
            errors=errors,
            normalized_document=normalized,
        )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate(self, content: bytes, filename: str) -> str | None:
        if not content:
            return "Empty file — no content to process"
        if len(content) > _MAX_FILE_SIZE:
            return (
                f"File too large ({len(content) / 1024 / 1024:.1f} MB); "
                f"maximum is {_MAX_FILE_SIZE // 1024 // 1024} MB"
            )
        return None

    # ------------------------------------------------------------------
    # Audit logging
    # ------------------------------------------------------------------

    def _audit_log(
        self,
        request: DocumentIngestionRequest,
        doc: NormalizedDocument,
        elapsed_ms: float,
    ) -> None:
        self._log.info(
            "pipeline.audit",
            document_id=request.document_id,
            case_id=request.case_id,
            patient_id=request.patient_id,
            filename=request.filename,
            document_type=doc.document_type.value,
            document_category=doc.document_category.value,
            normalization_method=doc.normalization_method.value,
            total_pages=doc.total_pages,
            overall_confidence=doc.overall_confidence,
            ocr_used=doc.ocr_used,
            fallback_triggered=doc.fallback_triggered,
            fallback_pages=doc.fallback_pages,
            tables_extracted=len(doc.all_tables),
            key_values_extracted=len(doc.all_key_values),
            sections_found=len(doc.sections),
            icd_codes=doc.entities.diagnosis_codes,
            cpt_codes=doc.entities.procedure_codes,
            source_system=request.source_system,
            elapsed_ms=round(elapsed_ms, 1),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _failed_result(
        self,
        request: DocumentIngestionRequest,
        content: bytes,
        errors: list[str],
        status: IngestionStatus = IngestionStatus.FAILED,
        doc_type: DocumentType = DocumentType.UNKNOWN,
    ) -> DocumentIngestionResult:
        from app.services.document.models import NormalizationMethod

        self._emit_ingestion_metric(doc_type, "failed")
        return DocumentIngestionResult(
            document_id=request.document_id,
            status=status,
            document_hash=hashlib.sha256(content).hexdigest() if content else "",
            document_type=doc_type,
            document_category=DocumentCategory.GENERAL,
            normalization_method=NormalizationMethod.DIRECT_PARSE,
            total_pages=0,
            overall_confidence=0.0,
            ocr_provider_used=OCRProvider.NONE,
            fallback_triggered=False,
            tables_extracted=0,
            key_values_extracted=0,
            sections_found=0,
            processing_time_ms=0.0,
            errors=errors,
        )

    @staticmethod
    def _emit_ingestion_metric(doc_type: DocumentType, status: str) -> None:
        try:
            from app.monitoring.metrics import DOCUMENT_INGESTION_TOTAL

            DOCUMENT_INGESTION_TOTAL.labels(
                document_type=doc_type.value,
                status=status,
            ).inc()
        except Exception:
            pass
