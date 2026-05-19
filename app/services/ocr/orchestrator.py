"""
OCR Orchestrator — intelligent fallback routing between providers.

Decision flow:
    1. Check provider availability
    2. Run primary provider (Azure)
    3. Evaluate result quality against all fallback conditions
    4. If fallback triggered → run PaddleOCR
    5. Merge: use best page-level result (higher confidence wins)
    6. Emit structured audit event + Prometheus metrics

Fallback conditions checked in priority order:
    RATE_LIMIT / TIMEOUT         → immediate fallback (don't score)
    AZURE_EXCEPTION              → immediate fallback
    UNSUPPORTED_LAYOUT           → immediate fallback
    PARTIAL_EXTRACTION           → score-based fallback
    CORRUPTED_OUTPUT             → heuristic check
    LOW_CONFIDENCE               → per-page + overall threshold
    MALFORMED_OUTPUT             → empty / non-text detection

Merge strategy:
    Per-page winner = provider with higher confidence.
    Full-text is rebuilt from winning pages.
    All tables from both providers are merged (dedup by page+index).
"""

from __future__ import annotations

import time
from typing import Any

import structlog

from app.services.ocr.base import (
    BaseOCRProvider,
    FallbackReason,
    OCRPageResult,
    OCRProvider,
    OCRProviderError,
    OCRResult,
)
from app.services.ocr.azure_provider import AzureOCRProvider
from app.services.ocr.paddle_provider import PaddleOCRProvider
from app.services.ocr.tesseract_provider import TesseractOCRProvider

logger = structlog.get_logger(__name__)

# Per-page confidence below which the page is sent to fallback
_PAGE_CONFIDENCE_THRESHOLD = 0.70

# If more than this fraction of pages are below threshold → full fallback
_PAGE_FALLBACK_RATIO = 0.30

# If overall confidence is below this → full fallback
_OVERALL_CONFIDENCE_THRESHOLD = 0.75

# If extracted text is shorter than expected (chars per page) → partial extraction
_MIN_CHARS_PER_PAGE = 50


class OCROrchestrator:
    """
    Routes OCR requests between Azure (primary) and PaddleOCR (fallback).

    Usage:
        orchestrator = OCROrchestrator.from_settings()
        result = await orchestrator.process(content_bytes, "application/pdf")
    """

    def __init__(
        self,
        primary: BaseOCRProvider,
        fallback: BaseOCRProvider,
        second_fallback: BaseOCRProvider | None = None,
        low_confidence_threshold: float = _OVERALL_CONFIDENCE_THRESHOLD,
        page_confidence_threshold: float = _PAGE_CONFIDENCE_THRESHOLD,
        page_fallback_ratio: float = _PAGE_FALLBACK_RATIO,
        min_chars_per_page: int = _MIN_CHARS_PER_PAGE,
    ) -> None:
        self._primary         = primary
        self._fallback        = fallback
        self._second_fallback = second_fallback
        self._low_conf        = low_confidence_threshold
        self._page_conf       = page_confidence_threshold
        self._page_ratio      = page_fallback_ratio
        self._min_chars       = min_chars_per_page
        self._log = structlog.get_logger(self.__class__.__name__)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def process(
        self,
        content: bytes,
        mime_type: str,
        page_count: int | None = None,
        document_hash: str = "",
    ) -> OCRResult:
        """
        Process a document through the OCR pipeline with automatic fallback.

        Returns the best available OCRResult, merged across providers if needed.
        """
        start = time.monotonic()

        # --- Step 1: Try primary provider ---
        primary_result: OCRResult | None = None
        primary_error:  OCRProviderError | None = None

        try:
            primary_result = await self._primary.extract(content, mime_type, page_count)
            self._emit_metrics(primary_result, "primary")
        except OCRProviderError as err:
            primary_error = err
            self._log.warning(
                "ocr_orchestrator.primary_failed",
                provider=err.provider,
                reason=err.reason,
                error=str(err),
                is_retryable=err.is_retryable,
            )
            self._emit_failure_metric(self._primary.provider_name, err.reason)

        # --- Step 2: Evaluate whether fallback is needed ---
        fallback_reason = self._evaluate_for_fallback(primary_result, primary_error)

        if fallback_reason is None:
            # Primary result is good — return it directly
            assert primary_result is not None
            primary_result.document_hash = document_hash
            elapsed = (time.monotonic() - start) * 1000
            primary_result.processing_time_ms = elapsed
            self._log.info(
                "ocr_orchestrator.primary_accepted",
                confidence=primary_result.overall_confidence,
                pages=primary_result.total_pages,
            )
            return primary_result

        # --- Step 3: Run fallback provider ---
        self._log.info(
            "ocr_orchestrator.fallback_triggered",
            reason=fallback_reason,
            primary_confidence=primary_result.overall_confidence if primary_result else None,
        )
        self._emit_fallback_metric(fallback_reason)

        try:
            fallback_result = await self._fallback.extract(content, mime_type, page_count)
            self._emit_metrics(fallback_result, "fallback")
        except OCRProviderError as fallback_err:
            self._log.warning(
                "ocr_orchestrator.fallback_failed",
                provider=fallback_err.provider,
                error=str(fallback_err),
            )
            self._emit_failure_metric(self._fallback.provider_name, fallback_err.reason)

            # Try second fallback (Tesseract) if configured
            if self._second_fallback is not None:
                self._log.info("ocr_orchestrator.second_fallback_triggered")
                try:
                    fallback_result = await self._second_fallback.extract(content, mime_type, page_count)
                    self._emit_metrics(fallback_result, "second_fallback")
                except OCRProviderError as second_err:
                    self._log.error(
                        "ocr_orchestrator.all_providers_failed",
                        error=str(second_err),
                    )
                    if primary_result is not None:
                        primary_result.warnings.append(
                            f"All OCR fallbacks failed; using primary result despite low confidence"
                        )
                        primary_result.fallback_triggered = True
                        primary_result.fallback_reason = fallback_reason
                        primary_result.document_hash = document_hash
                        return primary_result
                    raise OCRProviderError(
                        OCRProvider.PADDLE,
                        FallbackReason.CORRUPTED_OUTPUT,
                        "All OCR providers (Azure, PaddleOCR, Tesseract) failed",
                        second_err,
                    ) from second_err
            else:
                if primary_result is not None:
                    primary_result.warnings.append(
                        f"Fallback OCR also failed ({fallback_err.reason}); "
                        "using primary result despite low confidence"
                    )
                    primary_result.fallback_triggered = True
                    primary_result.fallback_reason = fallback_reason
                    primary_result.document_hash = document_hash
                    return primary_result

                raise OCRProviderError(
                    OCRProvider.PADDLE,
                    FallbackReason.CORRUPTED_OUTPUT,
                    "Both primary and fallback OCR providers failed",
                    fallback_err,
                ) from fallback_err

        # --- Step 4: Merge results ---
        if primary_result is not None:
            merged = self._merge(primary_result, fallback_result, fallback_reason)
        else:
            merged = fallback_result
            merged.fallback_triggered = True
            merged.fallback_reason = fallback_reason
            for page in merged.pages:
                page.used_fallback = True
                page.fallback_reason = fallback_reason

        merged.document_hash = document_hash
        merged.processing_time_ms = (time.monotonic() - start) * 1000

        self._log.info(
            "ocr_orchestrator.merge_complete",
            final_confidence=merged.overall_confidence,
            fallback_pages=len(merged.fallback_pages),
            total_pages=merged.total_pages,
        )
        return merged

    # ------------------------------------------------------------------
    # Fallback evaluation
    # ------------------------------------------------------------------

    def _evaluate_for_fallback(
        self,
        result: OCRResult | None,
        error: OCRProviderError | None,
    ) -> FallbackReason | None:
        """
        Return the fallback reason if fallback should be triggered, else None.
        """
        # Immediate fallback on any provider error
        if error is not None:
            return error.reason

        assert result is not None

        # Corrupted output heuristic
        if self._primary._is_output_corrupted(result):
            return FallbackReason.CORRUPTED_OUTPUT

        # Partial extraction: too few chars per page
        if result.total_pages > 0:
            avg_chars = len(result.full_text) / result.total_pages
            if avg_chars < self._min_chars:
                return FallbackReason.PARTIAL_EXTRACTION

        # Overall confidence below threshold
        if result.overall_confidence < self._low_conf:
            return FallbackReason.LOW_CONFIDENCE

        # Per-page confidence: if too many pages are low-confidence
        low_pages = [p for p in result.pages if p.confidence < self._page_conf]
        if result.total_pages > 0:
            ratio = len(low_pages) / result.total_pages
            if ratio >= self._page_ratio:
                return FallbackReason.LOW_CONFIDENCE

        # Malformed output: pages are not empty but full_text is suspiciously short
        if result.total_pages > 0 and len(result.full_text.strip()) < 20:
            return FallbackReason.MALFORMED_OUTPUT

        return None  # primary result is acceptable

    # ------------------------------------------------------------------
    # Merge strategy
    # ------------------------------------------------------------------

    def _merge(
        self,
        primary: OCRResult,
        fallback: OCRResult,
        fallback_reason: FallbackReason,
    ) -> OCRResult:
        """
        Merge primary and fallback results, selecting the better page per-page.

        Selection rule: higher confidence wins for each page.
        Tables: union of both providers (primary first, fallback fills gaps).
        """
        # Build a page map for the fallback provider
        fallback_pages: dict[int, OCRPageResult] = {
            p.page_number: p for p in fallback.pages
        }

        merged_pages: list[OCRPageResult] = []

        for primary_page in primary.pages:
            fb_page = fallback_pages.get(primary_page.page_number)

            if fb_page and fb_page.confidence > primary_page.confidence:
                # Fallback page wins — mark it
                winning = fb_page.model_copy(
                    update={
                        "used_fallback": True,
                        "fallback_reason": fallback_reason,
                        # Preserve any tables the primary found that fallback missed
                        "tables": primary_page.tables or fb_page.tables,
                        "key_values": primary_page.key_values or fb_page.key_values,
                    }
                )
            else:
                winning = primary_page

            merged_pages.append(winning)

        # Add any fallback pages that primary missed (e.g. primary had 0 results on page N)
        primary_page_nums = {p.page_number for p in primary.pages}
        for fb_page in fallback.pages:
            if fb_page.page_number not in primary_page_nums:
                merged_pages.append(
                    fb_page.model_copy(
                        update={"used_fallback": True, "fallback_reason": fallback_reason}
                    )
                )

        merged_pages.sort(key=lambda p: p.page_number)

        full_text   = "\n\n".join(p.text for p in merged_pages if p.text.strip())
        overall_conf = (
            sum(p.confidence for p in merged_pages) / len(merged_pages)
            if merged_pages else 0.0
        )
        fallback_page_nums = [p.page_number for p in merged_pages if p.used_fallback]
        all_tables = [t for p in merged_pages for t in p.tables]
        all_kvs    = [kv for p in merged_pages for kv in p.key_values]

        return OCRResult(
            pages=merged_pages,
            full_text=full_text,
            overall_confidence=round(overall_conf, 4),
            provider_used=OCRProvider.AZURE,  # primary was at least partially used
            fallback_triggered=True,
            fallback_pages=fallback_page_nums,
            fallback_reason=fallback_reason,
            total_pages=len(merged_pages),
            all_tables=all_tables,
            all_key_values=all_kvs,
            warnings=[
                f"OCR fallback triggered (reason: {fallback_reason}); "
                f"{len(fallback_page_nums)} page(s) served by PaddleOCR"
            ],
        )

    # ------------------------------------------------------------------
    # Metrics helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _emit_metrics(result: OCRResult, role: str) -> None:
        try:
            from app.monitoring.metrics import OCR_CONFIDENCE, OCR_REQUESTS_TOTAL

            OCR_CONFIDENCE.labels(
                provider=result.provider_used.value
            ).observe(result.overall_confidence)

            OCR_REQUESTS_TOTAL.labels(
                provider=result.provider_used.value,
                outcome="success" if role == "primary" else "fallback",
            ).inc()
        except Exception:
            pass  # metrics must never break OCR

    @staticmethod
    def _emit_failure_metric(provider: OCRProvider, reason: FallbackReason) -> None:
        try:
            from app.monitoring.metrics import OCR_REQUESTS_TOTAL

            OCR_REQUESTS_TOTAL.labels(
                provider=provider.value,
                outcome="failure",
            ).inc()
        except Exception:
            pass

    @staticmethod
    def _emit_fallback_metric(reason: FallbackReason) -> None:
        try:
            from app.monitoring.metrics import OCR_FALLBACK_TOTAL

            OCR_FALLBACK_TOTAL.labels(
                reason=reason.value,
                from_provider=OCRProvider.AZURE.value,
                to_provider=OCRProvider.PADDLE.value,
            ).inc()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_settings(cls) -> "OCROrchestrator":
        from app.core.config.settings import get_settings

        s = get_settings()
        primary         = AzureOCRProvider.from_settings()
        fallback        = PaddleOCRProvider()
        second_fallback = TesseractOCRProvider()
        return cls(
            primary=primary,
            fallback=fallback,
            second_fallback=second_fallback,
            low_confidence_threshold=s.azure_ocr_confidence_threshold,
        )
