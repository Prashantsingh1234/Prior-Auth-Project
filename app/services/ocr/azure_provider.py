"""
Azure AI Document Intelligence OCR provider.

Uses the `prebuilt-read` model for general document text extraction and
`prebuilt-document` for structured key-value pair extraction.

Features:
- Full text extraction with word-level confidence scores
- Structured table extraction (cell-by-cell with confidence)
- Key-value pair extraction (forms, prescriptions)
- Per-page confidence aggregation
- Timeout and rate-limit handling → maps to OCRProviderError
- Async via asyncio.to_thread (SDK is synchronous)
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import structlog

from app.services.ocr.base import (
    BaseOCRProvider,
    BoundingBox,
    ExtractedCell,
    ExtractedTable,
    FallbackReason,
    KeyValuePair,
    OCRPageResult,
    OCRProvider,
    OCRProviderError,
    OCRResult,
)

logger = structlog.get_logger(__name__)

# Minimum model: prebuilt-read (text only)
# Full model:    prebuilt-document (text + key-value + layout)
_MODEL_READ     = "prebuilt-read"
_MODEL_DOCUMENT = "prebuilt-document"

# Azure confidence threshold below which we flag for fallback
_AZURE_CONFIDENCE_THRESHOLD = 0.80


class AzureOCRProvider(BaseOCRProvider):
    """
    Azure Document Intelligence OCR provider.

    Instantiation is cheap — the SDK client is created lazily on first use.

    Usage:
        provider = AzureOCRProvider(endpoint, key, timeout=30)
        result = await provider.extract(pdf_bytes, "application/pdf")
    """

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        model: str = _MODEL_READ,
        timeout: int = 30,
    ) -> None:
        self._endpoint  = endpoint
        self._api_key   = api_key
        self._model     = model
        self._timeout   = timeout
        self._client: Any | None = None
        self._log = structlog.get_logger(self.__class__.__name__)

    @property
    def provider_name(self) -> OCRProvider:
        return OCRProvider.AZURE

    @property
    def confidence_threshold(self) -> float:
        return _AZURE_CONFIDENCE_THRESHOLD

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def extract(
        self,
        content: bytes,
        mime_type: str,
        page_count: int | None = None,
    ) -> OCRResult:
        start = time.monotonic()
        self._log.info(
            "azure_ocr.started",
            content_size=len(content),
            mime_type=mime_type,
            model=self._model,
        )

        try:
            raw = await asyncio.to_thread(
                self._extract_sync, content, mime_type
            )
        except OCRProviderError:
            raise
        except Exception as err:
            reason = self._classify_error(err)
            raise OCRProviderError(
                provider=OCRProvider.AZURE,
                reason=reason,
                message=str(err),
                original_error=err,
                is_retryable=reason in (FallbackReason.TIMEOUT, FallbackReason.RATE_LIMIT),
            ) from err

        elapsed_ms = (time.monotonic() - start) * 1000
        pages = self._build_pages(raw)
        result = OCRResult.from_pages(pages, OCRProvider.AZURE, elapsed_ms)

        self._log.info(
            "azure_ocr.complete",
            pages=result.total_pages,
            confidence=result.overall_confidence,
            elapsed_ms=round(elapsed_ms, 1),
        )
        return result

    async def is_available(self) -> bool:
        try:
            client = self._get_client()
            await asyncio.to_thread(lambda: client)  # lightweight thread check
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Sync extraction (wrapped in to_thread)
    # ------------------------------------------------------------------

    def _extract_sync(self, content: bytes, mime_type: str) -> Any:
        from azure.ai.documentintelligence import DocumentIntelligenceClient
        from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
        from azure.core.credentials import AzureKeyCredential
        from azure.core.exceptions import (
            HttpResponseError,
            ServiceRequestTimeoutError,
        )

        client = self._get_client()

        try:
            poller = client.begin_analyze_document(
                self._model,
                analyze_request=AnalyzeDocumentRequest(
                    bytes_source=content
                ),
                content_type="application/json",
                timeout=self._timeout,
            )
            return poller.result()
        except ServiceRequestTimeoutError as err:
            raise OCRProviderError(
                OCRProvider.AZURE,
                FallbackReason.TIMEOUT,
                f"Azure request timed out after {self._timeout}s",
                err,
                is_retryable=True,
            ) from err
        except HttpResponseError as err:
            if err.status_code == 429:
                raise OCRProviderError(
                    OCRProvider.AZURE,
                    FallbackReason.RATE_LIMIT,
                    "Azure rate limit exceeded",
                    err,
                    is_retryable=True,
                ) from err
            if err.status_code in (400, 415):
                raise OCRProviderError(
                    OCRProvider.AZURE,
                    FallbackReason.UNSUPPORTED_LAYOUT,
                    f"Azure rejected document: {err.message}",
                    err,
                ) from err
            raise OCRProviderError(
                OCRProvider.AZURE,
                FallbackReason.AZURE_EXCEPTION,
                str(err),
                err,
            ) from err

    # ------------------------------------------------------------------
    # Result parsing
    # ------------------------------------------------------------------

    def _build_pages(self, result: Any) -> list[OCRPageResult]:
        pages: list[OCRPageResult] = []

        for azure_page in result.pages or []:
            page_num = azure_page.page_number or (len(pages) + 1)

            # Extract lines → text
            lines = [line.content for line in (azure_page.lines or [])]
            text = "\n".join(lines)

            # Word-level confidence
            words = azure_page.words or []
            word_confs = [w.confidence for w in words if w.confidence is not None]
            page_confidence = (
                sum(word_confs) / len(word_confs) if word_confs else 0.0
            )

            tables = self._extract_tables(result, page_num)
            kvs    = self._extract_key_values(result, page_num)

            pages.append(
                OCRPageResult(
                    page_number=page_num,
                    text=text,
                    confidence=round(page_confidence, 4),
                    provider=OCRProvider.AZURE,
                    tables=tables,
                    key_values=kvs,
                    word_count=len(words),
                    char_count=len(text),
                )
            )

        return pages

    @staticmethod
    def _extract_tables(result: Any, page_num: int) -> list[ExtractedTable]:
        tables: list[ExtractedTable] = []
        for t_idx, table in enumerate(result.tables or []):
            # Filter cells that belong to this page
            page_cells = [
                c for c in (table.cells or [])
                if any(
                    (r.page_number == page_num)
                    for r in (c.bounding_regions or [])
                )
            ]
            if not page_cells:
                continue

            rows_grid: dict[int, dict[int, str]] = {}
            cells_out: list[ExtractedCell] = []
            for cell in page_cells:
                rows_grid.setdefault(cell.row_index, {})[cell.column_index] = (
                    cell.content or ""
                )
                cells_out.append(
                    ExtractedCell(
                        row=cell.row_index,
                        column=cell.column_index,
                        text=cell.content or "",
                    )
                )

            if not rows_grid:
                continue

            max_row = max(rows_grid.keys()) + 1
            max_col = max(
                max(cols.keys()) for cols in rows_grid.values()
            ) + 1
            rows = [
                [rows_grid.get(r, {}).get(c, "") for c in range(max_col)]
                for r in range(max_row)
            ]
            tables.append(
                ExtractedTable(
                    page_number=page_num,
                    table_index=t_idx,
                    rows=rows,
                    column_headers=rows[0] if rows else [],
                    row_count=max_row,
                    column_count=max_col,
                    cells=cells_out,
                )
            )
        return tables

    @staticmethod
    def _extract_key_values(result: Any, page_num: int) -> list[KeyValuePair]:
        kvs: list[KeyValuePair] = []
        for kv_pair in getattr(result, "key_value_pairs", None) or []:
            key_obj = kv_pair.key
            val_obj = kv_pair.value
            if not key_obj:
                continue

            on_page = any(
                r.page_number == page_num
                for r in (key_obj.bounding_regions or [])
            )
            if not on_page:
                continue

            kvs.append(
                KeyValuePair(
                    key=key_obj.content or "",
                    value=val_obj.content if val_obj else "",
                    confidence=kv_pair.confidence or 1.0,
                    page_number=page_num,
                )
            )
        return kvs

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_client(self) -> Any:
        if self._client is None:
            from azure.ai.documentintelligence import DocumentIntelligenceClient
            from azure.core.credentials import AzureKeyCredential

            self._client = DocumentIntelligenceClient(
                endpoint=self._endpoint,
                credential=AzureKeyCredential(self._api_key),
            )
        return self._client

    @staticmethod
    def _classify_error(err: Exception) -> FallbackReason:
        msg = str(err).lower()
        if "timeout" in msg or "timed out" in msg:
            return FallbackReason.TIMEOUT
        if "429" in msg or "rate" in msg or "throttle" in msg:
            return FallbackReason.RATE_LIMIT
        if "unsupported" in msg or "invalid" in msg or "format" in msg:
            return FallbackReason.UNSUPPORTED_LAYOUT
        return FallbackReason.AZURE_EXCEPTION

    @classmethod
    def from_settings(cls) -> "AzureOCRProvider":
        from app.core.config.settings import get_settings

        s = get_settings()
        if not s.azure_document_intelligence_endpoint or not s.azure_document_intelligence_key:
            raise RuntimeError("Azure Document Intelligence credentials not configured")
        return cls(
            endpoint=s.azure_document_intelligence_endpoint,
            api_key=s.azure_document_intelligence_key.get_secret_value(),
            timeout=s.azure_ocr_timeout,
        )
