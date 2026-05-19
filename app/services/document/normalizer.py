"""
Document normalization — converts diverse input formats into a unified
NormalizedDocument ready for layout parsing and downstream services.

Format handlers:
  NATIVE_PDF      → pdfplumber text extraction (no OCR)
  SCANNED_PDF     → OCR orchestrator
  IMAGE_*         → OCR orchestrator
  JSON_PAYLOAD    → direct parse → NormalizedDocument
  TEXT_NOTE       → direct decode → NormalizedDocument
  EMAIL           → extract body + attachments, recurse per attachment

Output always has:
  - full_text   (str)
  - pages       (list[NormalizedPage])
  - ocr_used    (bool)
  - overall_confidence (float)
"""

from __future__ import annotations

import email
import email.policy
import hashlib
import io
import json
import time

import structlog

from app.services.document.models import (
    DocumentCategory,
    DocumentType,
    MedicalEntities,
    NormalizationMethod,
    NormalizedDocument,
    NormalizedPage,
)
from app.services.ocr.base import OCRProvider, OCRResult
from app.services.ocr.orchestrator import OCROrchestrator

logger = structlog.get_logger(__name__)

# Minimum average characters per page before we warn about thin content
_MIN_CHARS_PER_PAGE = 50


class DocumentNormalizer:
    """
    Converts raw document bytes into a NormalizedDocument.

    Usage:
        normalizer = DocumentNormalizer(ocr_orchestrator)
        doc = await normalizer.normalize(content, doc_type, request)
    """

    def __init__(self, ocr_orchestrator: OCROrchestrator) -> None:
        self._ocr  = ocr_orchestrator
        self._log  = structlog.get_logger(self.__class__.__name__)

    # ------------------------------------------------------------------
    # Main dispatch
    # ------------------------------------------------------------------

    async def normalize(
        self,
        content: bytes,
        doc_type: DocumentType,
        document_id: str,
        filename: str = "",
        mime_type: str = "",
        category: DocumentCategory = DocumentCategory.GENERAL,
    ) -> NormalizedDocument:
        start = time.monotonic()
        doc_hash = hashlib.sha256(content).hexdigest()

        self._log.info(
            "normalizer.started",
            document_id=document_id,
            doc_type=doc_type,
            size_bytes=len(content),
        )

        if doc_type == DocumentType.NATIVE_PDF:
            doc = await self._normalize_native_pdf(
                content, document_id, doc_hash, filename, mime_type, category
            )
        elif doc_type in (
            DocumentType.SCANNED_PDF,
            DocumentType.IMAGE_PNG,
            DocumentType.IMAGE_JPG,
            DocumentType.IMAGE_TIFF,
        ):
            doc = await self._normalize_via_ocr(
                content, doc_type, document_id, doc_hash, filename, mime_type, category
            )
        elif doc_type == DocumentType.JSON_PAYLOAD:
            doc = self._normalize_json(
                content, document_id, doc_hash, filename, category
            )
        elif doc_type == DocumentType.TEXT_NOTE:
            doc = self._normalize_text(
                content, document_id, doc_hash, filename, category
            )
        elif doc_type == DocumentType.EMAIL:
            doc = await self._normalize_email(
                content, document_id, doc_hash, filename, category
            )
        else:
            doc = self._normalize_unknown(
                content, document_id, doc_hash, filename, category
            )

        elapsed = (time.monotonic() - start) * 1000
        self._log.info(
            "normalizer.complete",
            document_id=document_id,
            method=doc.normalization_method,
            pages=doc.total_pages,
            confidence=doc.overall_confidence,
            elapsed_ms=round(elapsed, 1),
        )
        return doc

    # ------------------------------------------------------------------
    # Native PDF (pdfplumber — no OCR)
    # ------------------------------------------------------------------

    async def _normalize_native_pdf(
        self,
        content: bytes,
        document_id: str,
        doc_hash: str,
        filename: str,
        mime_type: str,
        category: DocumentCategory,
    ) -> NormalizedDocument:
        import asyncio

        pages = await asyncio.to_thread(self._extract_native_pdf_sync, content)
        full_text = "\n\n".join(p.text for p in pages if p.text.strip())

        # pdfplumber returned nothing — try pypdf (handles more PDF flavors)
        if not full_text.strip():
            try:
                pypdf_pages = await self._extract_pypdf(content)
                pypdf_text = "\n\n".join(p.text for p in pypdf_pages if p.text.strip())
                if pypdf_text.strip():
                    self._log.info("normalizer.pypdf_fallback_used", document_id=document_id)
                    pages = pypdf_pages
                    full_text = pypdf_text
            except Exception as pypdf_err:
                self._log.warning(
                    "normalizer.pypdf_fallback_failed",
                    document_id=document_id,
                    error=str(pypdf_err),
                )

        return NormalizedDocument(
            document_id=document_id,
            document_type=DocumentType.NATIVE_PDF,
            document_category=category,
            normalization_method=NormalizationMethod.NATIVE_TEXT,
            full_text=full_text,
            pages=pages,
            overall_confidence=1.0,
            total_pages=len(pages),
            document_hash=doc_hash,
            ocr_used=False,
            filename=filename,
            mime_type=mime_type or "application/pdf",
            file_size_bytes=len(content),
        )

    def _extract_native_pdf_sync(self, content: bytes) -> list[NormalizedPage]:
        import pdfplumber

        pages: list[NormalizedPage] = []
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                raw_tables = page.extract_tables() or []
                from app.services.ocr.base import ExtractedTable
                tables = [
                    ExtractedTable.from_rows(
                        [[str(c) if c else "" for c in row] for row in t],
                        page_number=i,
                        table_index=t_idx,
                    )
                    for t_idx, t in enumerate(raw_tables)
                    if t
                ]
                pages.append(
                    NormalizedPage(
                        page_number=i,
                        text=text,
                        confidence=1.0,
                        ocr_provider=OCRProvider.NONE,
                        tables=tables,
                    )
                )
        return pages

    # ------------------------------------------------------------------
    # OCR path (scanned PDFs, images)
    # ------------------------------------------------------------------

    async def _normalize_via_ocr(
        self,
        content: bytes,
        doc_type: DocumentType,
        document_id: str,
        doc_hash: str,
        filename: str,
        mime_type: str,
        category: DocumentCategory,
    ) -> NormalizedDocument:
        ocr_warnings: list[str] = []
        ocr_result: OCRResult | None = None

        try:
            ocr_result = await self._ocr.process(
                content=content,
                mime_type=mime_type or self._infer_mime(doc_type),
                document_hash=doc_hash,
            )
        except Exception as ocr_err:
            self._log.warning(
                "normalizer.ocr_failed_using_pdfplumber_fallback",
                document_id=document_id,
                error=str(ocr_err),
            )
            ocr_warnings.append(f"OCR unavailable ({ocr_err}); using direct text extraction fallback")

        # If OCR produced a result, check if the text is non-empty
        if ocr_result is not None and ocr_result.full_text.strip():
            pages = [
                NormalizedPage(
                    page_number=p.page_number,
                    text=p.text,
                    confidence=p.confidence,
                    ocr_provider=p.provider,
                    tables=p.tables,
                    key_values=p.key_values,
                    used_fallback=p.used_fallback,
                )
                for p in ocr_result.pages
            ]
            return NormalizedDocument(
                document_id=document_id,
                document_type=doc_type,
                document_category=category,
                normalization_method=self._ocr_method(ocr_result),
                full_text=ocr_result.full_text,
                pages=pages,
                all_tables=ocr_result.all_tables,
                all_key_values=ocr_result.all_key_values,
                overall_confidence=ocr_result.overall_confidence,
                total_pages=ocr_result.total_pages,
                document_hash=doc_hash,
                ocr_used=True,
                fallback_triggered=ocr_result.fallback_triggered,
                fallback_pages=ocr_result.fallback_pages,
                filename=filename,
                mime_type=mime_type,
                file_size_bytes=len(content),
                warnings=list(ocr_result.warnings) + ocr_warnings,
            )

        # OCR failed or returned empty — try direct PDF text extraction as fallback
        if "pdf" in (mime_type or "").lower() or doc_type in (
            DocumentType.NATIVE_PDF, DocumentType.SCANNED_PDF
        ):
            try:
                self._log.info(
                    "normalizer.pdf_fallback_extraction",
                    document_id=document_id,
                )
                doc = await self._normalize_native_pdf(
                    content, document_id, doc_hash, filename, mime_type or "application/pdf", category
                )
                if doc.full_text.strip():
                    doc.warnings.extend(ocr_warnings)
                    doc.warnings.append("OCR unavailable; text extracted directly from PDF")
                    return doc
            except Exception as pdf_err:
                self._log.warning(
                    "normalizer.pdf_fallback_failed",
                    document_id=document_id,
                    error=str(pdf_err),
                )
                ocr_warnings.append(f"PDF direct extraction also failed: {pdf_err}")

            # Second direct-extraction attempt: pypdf
            try:
                pypdf_pages = await self._extract_pypdf(content)
                if pypdf_pages:
                    pypdf_text = "\n\n".join(p.text for p in pypdf_pages if p.text.strip())
                    if pypdf_text.strip():
                        ocr_warnings.append("OCR unavailable; text extracted via pypdf")
                        return NormalizedDocument(
                            document_id=document_id,
                            document_type=doc_type,
                            document_category=category,
                            normalization_method=NormalizationMethod.NATIVE_TEXT,
                            full_text=pypdf_text,
                            pages=pypdf_pages,
                            overall_confidence=0.85,
                            total_pages=len(pypdf_pages),
                            document_hash=doc_hash,
                            ocr_used=False,
                            filename=filename,
                            mime_type=mime_type or "application/pdf",
                            file_size_bytes=len(content),
                            warnings=ocr_warnings,
                        )
            except Exception as pypdf_err:
                self._log.warning(
                    "normalizer.pypdf_fallback_failed",
                    document_id=document_id,
                    error=str(pypdf_err),
                )
                ocr_warnings.append(f"pypdf extraction also failed: {pypdf_err}")

            # Last resort: PyMuPDF (fitz)
            try:
                pages = await self._extract_pymupdf(content)
                if pages:
                    full_text = "\n\n".join(p.text for p in pages if p.text.strip())
                    if full_text.strip():
                        ocr_warnings.append("OCR unavailable; text extracted via PyMuPDF")
                        return NormalizedDocument(
                            document_id=document_id,
                            document_type=doc_type,
                            document_category=category,
                            normalization_method=NormalizationMethod.NATIVE_TEXT,
                            full_text=full_text,
                            pages=pages,
                            overall_confidence=0.9,
                            total_pages=len(pages),
                            document_hash=doc_hash,
                            ocr_used=False,
                            filename=filename,
                            mime_type=mime_type or "application/pdf",
                            file_size_bytes=len(content),
                            warnings=ocr_warnings,
                        )
            except Exception as fitz_err:
                self._log.warning(
                    "normalizer.pymupdf_fallback_failed",
                    document_id=document_id,
                    error=str(fitz_err),
                )
                ocr_warnings.append(f"PyMuPDF extraction also failed: {fitz_err}")

        # All methods exhausted — return empty document with warnings rather than raising
        if ocr_result is not None:
            # Return the (empty) OCR result so the pipeline doesn't crash
            pages = [
                NormalizedPage(
                    page_number=p.page_number,
                    text=p.text,
                    confidence=p.confidence,
                    ocr_provider=p.provider,
                )
                for p in ocr_result.pages
            ]
            return NormalizedDocument(
                document_id=document_id,
                document_type=doc_type,
                document_category=category,
                normalization_method=self._ocr_method(ocr_result),
                full_text=ocr_result.full_text,
                pages=pages,
                overall_confidence=ocr_result.overall_confidence,
                total_pages=ocr_result.total_pages,
                document_hash=doc_hash,
                ocr_used=True,
                filename=filename,
                mime_type=mime_type,
                file_size_bytes=len(content),
                warnings=list(ocr_result.warnings) + ocr_warnings,
            )

        # No OCR result at all — propagate original error so pipeline records it
        raise RuntimeError(
            "OCR failed and no text-extraction fallback succeeded. "
            f"Warnings: {'; '.join(ocr_warnings)}"
        )

    async def _extract_pymupdf(self, content: bytes) -> list[NormalizedPage]:
        """Extract text with PyMuPDF — handles PDFs that pdfplumber struggles with."""
        import asyncio
        return await asyncio.to_thread(self._extract_pymupdf_sync, content)

    @staticmethod
    def _extract_pymupdf_sync(content: bytes) -> list[NormalizedPage]:
        try:
            import fitz  # type: ignore[import-untyped]  # PyMuPDF (pymupdf package)
        except ImportError as exc:
            raise RuntimeError("PyMuPDF not installed") from exc

        pages: list[NormalizedPage] = []
        with fitz.open(stream=content, filetype="pdf") as doc:  # type: ignore[attr-defined]
            for i, page in enumerate(doc, start=1):
                text = page.get_text("text") or ""
                pages.append(
                    NormalizedPage(
                        page_number=i,
                        text=text,
                        confidence=0.9,
                        ocr_provider=OCRProvider.NONE,
                    )
                )
        return pages

    async def _extract_pypdf(self, content: bytes) -> list[NormalizedPage]:
        """Extract text with pypdf — pure-Python, handles PDF flavors pdfplumber misses."""
        import asyncio
        return await asyncio.to_thread(self._extract_pypdf_sync, content)

    @staticmethod
    def _extract_pypdf_sync(content: bytes) -> list[NormalizedPage]:
        try:
            from pypdf import PdfReader  # type: ignore[import-untyped]
        except ImportError as exc:
            raise RuntimeError("pypdf not installed") from exc
        import io

        reader = PdfReader(io.BytesIO(content))
        pages: list[NormalizedPage] = []
        for i, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            pages.append(
                NormalizedPage(
                    page_number=i,
                    text=text,
                    confidence=0.85 if text.strip() else 0.0,
                    ocr_provider=OCRProvider.NONE,
                )
            )
        return pages

    # ------------------------------------------------------------------
    # JSON
    # ------------------------------------------------------------------

    def _normalize_json(
        self,
        content: bytes,
        document_id: str,
        doc_hash: str,
        filename: str,
        category: DocumentCategory,
    ) -> NormalizedDocument:
        try:
            data = json.loads(content.decode("utf-8"))
            full_text = json.dumps(data, indent=2)
        except Exception as err:
            self._log.warning("normalizer.json_parse_failed", error=str(err))
            full_text = content.decode("utf-8", errors="replace")

        page = NormalizedPage(
            page_number=1,
            text=full_text,
            confidence=1.0,
            ocr_provider=OCRProvider.NONE,
        )
        return NormalizedDocument(
            document_id=document_id,
            document_type=DocumentType.JSON_PAYLOAD,
            document_category=category,
            normalization_method=NormalizationMethod.DIRECT_PARSE,
            full_text=full_text,
            pages=[page],
            overall_confidence=1.0,
            total_pages=1,
            document_hash=doc_hash,
            filename=filename,
            mime_type="application/json",
            file_size_bytes=len(content),
        )

    # ------------------------------------------------------------------
    # Plain text
    # ------------------------------------------------------------------

    def _normalize_text(
        self,
        content: bytes,
        document_id: str,
        doc_hash: str,
        filename: str,
        category: DocumentCategory,
    ) -> NormalizedDocument:
        text = content.decode("utf-8", errors="replace")
        page = NormalizedPage(
            page_number=1,
            text=text,
            confidence=1.0,
            ocr_provider=OCRProvider.NONE,
        )
        return NormalizedDocument(
            document_id=document_id,
            document_type=DocumentType.TEXT_NOTE,
            document_category=category,
            normalization_method=NormalizationMethod.DIRECT_PARSE,
            full_text=text,
            pages=[page],
            overall_confidence=1.0,
            total_pages=1,
            document_hash=doc_hash,
            filename=filename,
            mime_type="text/plain",
            file_size_bytes=len(content),
        )

    # ------------------------------------------------------------------
    # Email (EML)
    # ------------------------------------------------------------------

    async def _normalize_email(
        self,
        content: bytes,
        document_id: str,
        doc_hash: str,
        filename: str,
        category: DocumentCategory,
    ) -> NormalizedDocument:
        msg = email.message_from_bytes(content, policy=email.policy.default)
        body_parts: list[str] = []

        if msg.is_multipart():
            for part in msg.walk():
                ct = part.get_content_type()
                if ct == "text/plain":
                    body_parts.append(part.get_payload(decode=True).decode("utf-8", errors="replace"))
        else:
            raw = msg.get_payload(decode=True)
            if raw:
                body_parts.append(raw.decode("utf-8", errors="replace"))

        full_text = "\n\n".join(body_parts)
        pages = [
            NormalizedPage(
                page_number=1,
                text=full_text,
                confidence=1.0,
                ocr_provider=OCRProvider.NONE,
            )
        ]
        return NormalizedDocument(
            document_id=document_id,
            document_type=DocumentType.EMAIL,
            document_category=category,
            normalization_method=NormalizationMethod.EMAIL_EXTRACT,
            full_text=full_text,
            pages=pages,
            overall_confidence=1.0,
            total_pages=1,
            document_hash=doc_hash,
            filename=filename,
            mime_type="message/rfc822",
            file_size_bytes=len(content),
        )

    # ------------------------------------------------------------------
    # Unknown / unsupported
    # ------------------------------------------------------------------

    def _normalize_unknown(
        self,
        content: bytes,
        document_id: str,
        doc_hash: str,
        filename: str,
        category: DocumentCategory,
    ) -> NormalizedDocument:
        self._log.warning("normalizer.unsupported_type", filename=filename)
        return NormalizedDocument(
            document_id=document_id,
            document_type=DocumentType.UNKNOWN,
            document_category=category,
            normalization_method=NormalizationMethod.DIRECT_PARSE,
            full_text="",
            pages=[],
            overall_confidence=0.0,
            total_pages=0,
            document_hash=doc_hash,
            filename=filename,
            file_size_bytes=len(content),
            warnings=["Document type not supported — no text extracted"],
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _infer_mime(doc_type: DocumentType) -> str:
        return {
            DocumentType.SCANNED_PDF: "application/pdf",
            DocumentType.IMAGE_PNG:   "image/png",
            DocumentType.IMAGE_JPG:   "image/jpeg",
            DocumentType.IMAGE_TIFF:  "image/tiff",
        }.get(doc_type, "application/octet-stream")

    @staticmethod
    def _ocr_method(result: OCRResult) -> NormalizationMethod:
        if result.fallback_triggered:
            return NormalizationMethod.OCR_MERGED
        if result.provider_used == OCRProvider.AZURE:
            return NormalizationMethod.OCR_AZURE
        return NormalizationMethod.OCR_PADDLE
