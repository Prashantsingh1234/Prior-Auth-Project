"""
Abstract OCR provider interface and shared data models.

All OCR providers (Azure, PaddleOCR, future engines) implement BaseOCRProvider.
This decouples orchestration logic from any specific SDK.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class OCRProvider(str, Enum):
    AZURE     = "azure"
    PADDLE    = "paddle"
    TESSERACT = "tesseract"
    NONE      = "none"      # Native text extraction — no OCR needed


class FallbackReason(str, Enum):
    AZURE_EXCEPTION       = "azure_exception"
    LOW_CONFIDENCE        = "low_confidence"
    TIMEOUT               = "timeout"
    RATE_LIMIT            = "rate_limit"
    MALFORMED_OUTPUT      = "malformed_output"
    PARTIAL_EXTRACTION    = "partial_extraction"
    UNSUPPORTED_LAYOUT    = "unsupported_layout"
    CORRUPTED_OUTPUT      = "corrupted_output"


# ---------------------------------------------------------------------------
# Shared result models
# ---------------------------------------------------------------------------

class BoundingBox(BaseModel):
    x: float
    y: float
    width: float
    height: float
    page: int = 1


class ExtractedCell(BaseModel):
    row: int
    column: int
    text: str
    confidence: float = 1.0
    bounding_box: BoundingBox | None = None


class ExtractedTable(BaseModel):
    """Structured table extracted from a document page."""
    page_number: int
    table_index: int
    rows: list[list[str]]          # rows[row_idx][col_idx] = cell text
    column_headers: list[str] = Field(default_factory=list)
    row_count: int
    column_count: int
    confidence: float = 1.0
    cells: list[ExtractedCell] = Field(default_factory=list)

    @classmethod
    def from_rows(
        cls,
        rows: list[list[str]],
        page_number: int,
        table_index: int = 0,
        confidence: float = 1.0,
    ) -> "ExtractedTable":
        headers = rows[0] if rows else []
        return cls(
            page_number=page_number,
            table_index=table_index,
            rows=rows,
            column_headers=headers,
            row_count=len(rows),
            column_count=max((len(r) for r in rows), default=0),
            confidence=confidence,
        )


class KeyValuePair(BaseModel):
    key: str
    value: str
    confidence: float = 1.0
    page_number: int = 1


class OCRPageResult(BaseModel):
    """OCR extraction result for a single page."""
    page_number: int
    text: str
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    provider: OCRProvider
    tables: list[ExtractedTable] = Field(default_factory=list)
    key_values: list[KeyValuePair] = Field(default_factory=list)
    word_count: int = 0
    char_count: int = 0
    used_fallback: bool = False
    fallback_reason: FallbackReason | None = None
    processing_time_ms: float = 0.0
    raw_provider_response: dict[str, Any] | None = None   # stored for debugging

    @property
    def is_high_confidence(self) -> bool:
        return self.confidence >= 0.85

    @property
    def is_low_confidence(self) -> bool:
        return self.confidence < 0.70

    @property
    def is_empty(self) -> bool:
        return len(self.text.strip()) < 10


class OCRResult(BaseModel):
    """Complete OCR extraction result for a document."""
    pages: list[OCRPageResult]
    full_text: str
    overall_confidence: float = Field(0.0, ge=0.0, le=1.0)
    provider_used: OCRProvider
    fallback_triggered: bool = False
    fallback_pages: list[int] = Field(default_factory=list)
    fallback_reason: FallbackReason | None = None
    total_pages: int
    processing_time_ms: float = 0.0
    document_hash: str = ""
    warnings: list[str] = Field(default_factory=list)
    all_tables: list[ExtractedTable] = Field(default_factory=list)
    all_key_values: list[KeyValuePair] = Field(default_factory=list)

    @property
    def is_reliable(self) -> bool:
        return self.overall_confidence >= 0.80

    @property
    def has_tables(self) -> bool:
        return len(self.all_tables) > 0

    @classmethod
    def from_pages(
        cls,
        pages: list[OCRPageResult],
        provider: OCRProvider,
        processing_time_ms: float = 0.0,
        document_hash: str = "",
    ) -> "OCRResult":
        full_text = "\n\n".join(p.text for p in pages if p.text.strip())
        overall_conf = (
            sum(p.confidence for p in pages) / len(pages) if pages else 0.0
        )
        fallback_pages = [p.page_number for p in pages if p.used_fallback]
        all_tables = [t for p in pages for t in p.tables]
        all_kvs   = [kv for p in pages for kv in p.key_values]

        return cls(
            pages=pages,
            full_text=full_text,
            overall_confidence=round(overall_conf, 4),
            provider_used=provider,
            fallback_triggered=bool(fallback_pages),
            fallback_pages=fallback_pages,
            total_pages=len(pages),
            processing_time_ms=processing_time_ms,
            document_hash=document_hash,
            all_tables=all_tables,
            all_key_values=all_kvs,
        )


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class OCRProviderError(Exception):
    """Raised by an OCR provider when extraction fails."""

    def __init__(
        self,
        provider: OCRProvider,
        reason: FallbackReason,
        message: str = "",
        original_error: Exception | None = None,
        is_retryable: bool = False,
    ) -> None:
        self.provider = provider
        self.reason = reason
        self.original_error = original_error
        self.is_retryable = is_retryable
        super().__init__(message or f"{provider} OCR failed: {reason}")


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class BaseOCRProvider(ABC):
    """
    Contract all OCR providers must satisfy.

    Implementations: AzureOCRProvider, PaddleOCRProvider.
    Future providers (Textract, Google Document AI) add a new subclass only.
    """

    @property
    @abstractmethod
    def provider_name(self) -> OCRProvider:
        """Identifies this provider in metrics and logs."""

    @property
    @abstractmethod
    def confidence_threshold(self) -> float:
        """Minimum acceptable average confidence score (0–1)."""

    @abstractmethod
    async def extract(
        self,
        content: bytes,
        mime_type: str,
        page_count: int | None = None,
    ) -> OCRResult:
        """
        Extract text and structure from document bytes.

        Args:
            content:    Raw document bytes (PDF, PNG, JPG, TIFF …)
            mime_type:  MIME type string (e.g. "application/pdf")
            page_count: Known page count hint (may be None)

        Returns:
            OCRResult with per-page text, tables, key-values, confidence.

        Raises:
            OCRProviderError on any failure (timeout, rate-limit, parse error …)
        """

    @abstractmethod
    async def is_available(self) -> bool:
        """Return True if the provider can currently accept requests."""

    def _is_output_corrupted(self, result: OCRResult) -> bool:
        """
        Heuristic check for known corruption patterns:
        - Majority of pages are empty
        - Average confidence well below threshold
        - Full text is garbled (high ratio of non-ASCII characters)
        """
        if not result.pages:
            return True
        empty_pages = sum(1 for p in result.pages if p.is_empty)
        if empty_pages / len(result.pages) > 0.5:
            return True
        if result.overall_confidence < 0.3:
            return True
        non_ascii = sum(1 for c in result.full_text if ord(c) > 127)
        if result.full_text and non_ascii / len(result.full_text) > 0.4:
            return True
        return False
