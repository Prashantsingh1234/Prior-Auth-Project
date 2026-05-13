"""
PDF parsing stage of the policy ingestion pipeline.

Extraction strategy:
  1. Attempt pdfplumber (vectorized text) — fastest, preserves layout
  2. If text yield is poor (< 80 chars / page on average), fall back to OCR
  3. OCR backend priority: Azure Document Intelligence → PaddleOCR → error

ParsedDocument carries per-page text, table data, OCR flags, and the SHA-256
of the raw PDF bytes (used for duplicate detection in later stages).
"""

from __future__ import annotations

import hashlib
import io
import structlog
from typing import TYPE_CHECKING

from app.services.ingestion.models import ParsedDocument, ParsedPage

if TYPE_CHECKING:
    pass

logger = structlog.get_logger(__name__)

# Threshold below which a page is considered text-poor (likely scanned)
_MIN_CHARS_PER_PAGE = 80

# Maximum characters stored per page (caps memory usage for very dense pages)
_MAX_PAGE_CHARS = 50_000


class PDFParseError(Exception):
    """Raised when a PDF cannot be parsed by any available backend."""


class PDFParser:
    """
    Parses a policy PDF into a ParsedDocument.

    Usage:
        parser = PDFParser(ocr_enabled=True)
        doc = await parser.parse(pdf_bytes)

    OCR backends are lazy-imported so the service can start without them
    if OCR is disabled (ocr_enabled=False).
    """

    def __init__(self, ocr_enabled: bool = True) -> None:
        self._ocr_enabled = ocr_enabled
        self._log = structlog.get_logger(self.__class__.__name__)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def parse(self, pdf_bytes: bytes) -> ParsedDocument:
        """
        Parse raw PDF bytes into a structured ParsedDocument.

        Steps:
          1. Hash the bytes (always, even before parsing)
          2. Extract text with pdfplumber
          3. If is_text_poor and OCR enabled, re-extract with OCR
        """
        document_hash = self._compute_hash(pdf_bytes)
        self._log.info("pdf_parser.started", hash=document_hash[:16])

        pages = await self._extract_with_pdfplumber(pdf_bytes)
        doc = self._build_document(pages, document_hash)

        if doc.is_text_poor and self._ocr_enabled:
            self._log.info(
                "pdf_parser.ocr_fallback",
                reason="text_poor",
                avg_chars=doc.avg_chars_per_page,
                hash=document_hash[:16],
            )
            pages = await self._extract_with_ocr(pdf_bytes)
            doc = self._build_document(pages, document_hash, ocr_used=True)

        self._log.info(
            "pdf_parser.complete",
            hash=document_hash[:16],
            pages=doc.total_pages,
            used_ocr=bool(doc.used_ocr_pages),
            avg_chars=round(doc.avg_chars_per_page, 1),
        )
        return doc

    # ------------------------------------------------------------------
    # pdfplumber extraction
    # ------------------------------------------------------------------

    async def _extract_with_pdfplumber(self, pdf_bytes: bytes) -> list[ParsedPage]:
        """Extract text and tables from all pages using pdfplumber."""
        import asyncio

        return await asyncio.to_thread(self._pdfplumber_sync, pdf_bytes)

    def _pdfplumber_sync(self, pdf_bytes: bytes) -> list[ParsedPage]:
        try:
            import pdfplumber
        except ImportError as exc:
            raise PDFParseError("pdfplumber is not installed") from exc

        pages: list[ParsedPage] = []
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                raw_text = page.extract_text() or ""
                raw_text = raw_text[:_MAX_PAGE_CHARS]

                tables = self._extract_tables(page)

                pages.append(
                    ParsedPage(
                        page_number=i,
                        text=raw_text,
                        char_count=len(raw_text),
                        used_ocr=False,
                        tables=tables,
                    )
                )
        return pages

    @staticmethod
    def _extract_tables(page: object) -> list[list[list[str]]]:
        """Extract structured tables from a pdfplumber page object."""
        try:
            raw_tables = page.extract_tables()  # type: ignore[attr-defined]
            if not raw_tables:
                return []
            cleaned: list[list[list[str]]] = []
            for table in raw_tables:
                cleaned_table = [
                    [str(cell) if cell is not None else "" for cell in row]
                    for row in table
                ]
                cleaned.append(cleaned_table)
            return cleaned
        except Exception:
            return []

    # ------------------------------------------------------------------
    # OCR extraction
    # ------------------------------------------------------------------

    async def _extract_with_ocr(self, pdf_bytes: bytes) -> list[ParsedPage]:
        """
        Attempt OCR backends in priority order:
          1. Azure Document Intelligence (higher accuracy, handles complex layouts)
          2. PaddleOCR (local fallback)
        """
        try:
            return await self._extract_with_azure(pdf_bytes)
        except Exception as azure_err:
            self._log.warning(
                "pdf_parser.azure_ocr_failed",
                error=str(azure_err),
            )

        try:
            return await self._extract_with_paddle(pdf_bytes)
        except Exception as paddle_err:
            self._log.error(
                "pdf_parser.all_ocr_backends_failed",
                error=str(paddle_err),
            )
            raise PDFParseError(
                "All OCR backends failed — cannot extract text from scanned PDF"
            ) from paddle_err

    async def _extract_with_azure(self, pdf_bytes: bytes) -> list[ParsedPage]:
        """Extract text using Azure Document Intelligence."""
        import asyncio

        return await asyncio.to_thread(self._azure_ocr_sync, pdf_bytes)

    def _azure_ocr_sync(self, pdf_bytes: bytes) -> list[ParsedPage]:
        from azure.ai.documentintelligence import DocumentIntelligenceClient
        from azure.core.credentials import AzureKeyCredential

        from app.core.config import get_settings

        settings = get_settings()
        endpoint = getattr(settings, "azure_document_intelligence_endpoint", None)
        key = getattr(settings, "azure_document_intelligence_key", None)
        if not endpoint or not key:
            raise RuntimeError("Azure Document Intelligence credentials not configured")

        client = DocumentIntelligenceClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(key),
        )

        poller = client.begin_analyze_document(
            "prebuilt-read",
            analyze_request={"base64Source": pdf_bytes},
            content_type="application/json",
        )
        result = poller.result()

        pages: list[ParsedPage] = []
        for azure_page in result.pages or []:
            page_num = azure_page.page_number or len(pages) + 1
            lines = [line.content for line in (azure_page.lines or [])]
            text = "\n".join(lines)[:_MAX_PAGE_CHARS]
            pages.append(
                ParsedPage(
                    page_number=page_num,
                    text=text,
                    char_count=len(text),
                    used_ocr=True,
                )
            )
        return pages

    async def _extract_with_paddle(self, pdf_bytes: bytes) -> list[ParsedPage]:
        """Extract text using PaddleOCR (local, CPU-based)."""
        import asyncio

        return await asyncio.to_thread(self._paddle_ocr_sync, pdf_bytes)

    def _paddle_ocr_sync(self, pdf_bytes: bytes) -> list[ParsedPage]:
        try:
            from paddleocr import PaddleOCR
            import pypdf
        except ImportError as exc:
            raise PDFParseError(f"OCR dependency not installed: {exc}") from exc

        ocr_engine = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)

        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        pages: list[ParsedPage] = []

        for i, _ in enumerate(reader.pages, start=1):
            try:
                result = ocr_engine.ocr(pdf_bytes, page_num=i)
                lines: list[str] = []
                if result and result[0]:
                    for line in result[0]:
                        if line and len(line) >= 2 and line[1]:
                            lines.append(line[1][0])
                text = "\n".join(lines)[:_MAX_PAGE_CHARS]
            except Exception as err:
                self._log.warning(
                    "pdf_parser.paddle_page_failed",
                    page=i,
                    error=str(err),
                )
                text = ""

            pages.append(
                ParsedPage(
                    page_number=i,
                    text=text,
                    char_count=len(text),
                    used_ocr=True,
                )
            )
        return pages

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_hash(pdf_bytes: bytes) -> str:
        return hashlib.sha256(pdf_bytes).hexdigest()

    @staticmethod
    def _build_document(
        pages: list[ParsedPage],
        document_hash: str,
        ocr_used: bool = False,
    ) -> ParsedDocument:
        if ocr_used:
            for page in pages:
                object.__setattr__(page, "used_ocr", True)

        used_ocr_pages = [p.page_number for p in pages if p.used_ocr]
        full_text = "\n\n".join(p.text for p in pages if p.text.strip())

        return ParsedDocument(
            pages=pages,
            full_text=full_text,
            total_pages=len(pages),
            used_ocr_pages=used_ocr_pages,
            document_hash=document_hash,
        )
