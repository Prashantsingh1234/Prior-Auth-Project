"""
Tesseract OCR provider — local fallback when Azure and PaddleOCR are unavailable.

Uses pytesseract + pdf2image to:
  1. Convert each PDF page to a PIL image (via poppler's pdftoppm)
  2. Run tesseract on each image to extract text

This provider never raises OCRProviderError for missing config — it only
requires tesseract and poppler to be installed on the host.
"""

from __future__ import annotations

import asyncio
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

logger = structlog.get_logger(__name__)

_IMAGE_MIMES = {"image/png", "image/jpeg", "image/jpg", "image/tiff", "image/bmp"}
_PDF_MIMES = {"application/pdf"}


class TesseractOCRProvider(BaseOCRProvider):
    """
    Local Tesseract OCR provider — requires tesseract + poppler installed.

    Used as the last-resort fallback when Azure and PaddleOCR are unavailable.
    """

    def __init__(self, lang: str = "eng", dpi: int = 300) -> None:
        self._lang = lang
        self._dpi = dpi
        self._log = structlog.get_logger(self.__class__.__name__)

    @property
    def provider_name(self) -> OCRProvider:
        return OCRProvider.TESSERACT

    @property
    def confidence_threshold(self) -> float:
        return 0.60

    async def extract(
        self,
        content: bytes,
        mime_type: str,
        page_count: int | None = None,
    ) -> OCRResult:
        start = time.monotonic()
        self._log.info("tesseract_ocr.started", mime_type=mime_type, size=len(content))

        try:
            if mime_type in _PDF_MIMES or mime_type == "application/octet-stream":
                pages = await asyncio.to_thread(self._extract_pdf_sync, content)
            else:
                pages = await asyncio.to_thread(self._extract_image_sync, content)
        except OCRProviderError:
            raise
        except Exception as err:
            raise OCRProviderError(
                provider=OCRProvider.TESSERACT,
                reason=FallbackReason.AZURE_EXCEPTION,
                message=f"Tesseract OCR failed: {err}",
                original_error=err,
            ) from err

        elapsed_ms = (time.monotonic() - start) * 1000
        result = OCRResult.from_pages(pages, OCRProvider.TESSERACT, elapsed_ms)
        self._log.info(
            "tesseract_ocr.complete",
            pages=result.total_pages,
            confidence=result.overall_confidence,
            chars=len(result.full_text),
            elapsed_ms=round(elapsed_ms, 1),
        )
        return result

    async def is_available(self) -> bool:
        try:
            import pytesseract  # noqa: F401
            from pdf2image import convert_from_bytes  # noqa: F401
            return True
        except ImportError:
            return False

    # ------------------------------------------------------------------
    # Sync helpers
    # ------------------------------------------------------------------

    def _extract_pdf_sync(self, content: bytes) -> list[OCRPageResult]:
        try:
            from pdf2image import convert_from_bytes
        except ImportError as err:
            raise OCRProviderError(
                OCRProvider.TESSERACT,
                FallbackReason.AZURE_EXCEPTION,
                "pdf2image not installed — cannot convert PDF for Tesseract",
                err,
            ) from err

        try:
            images = convert_from_bytes(content, dpi=self._dpi)
        except Exception as err:
            raise OCRProviderError(
                OCRProvider.TESSERACT,
                FallbackReason.CORRUPTED_OUTPUT,
                f"pdf2image conversion failed: {err}",
                err,
            ) from err

        pages: list[OCRPageResult] = []
        for i, img in enumerate(images, start=1):
            page = self._ocr_image(img, page_number=i)
            pages.append(page)
        return pages

    def _extract_image_sync(self, content: bytes) -> list[OCRPageResult]:
        try:
            from PIL import Image  # type: ignore[import-untyped]
            import io
            img = Image.open(io.BytesIO(content)).convert("RGB")
        except Exception as err:
            raise OCRProviderError(
                OCRProvider.TESSERACT,
                FallbackReason.CORRUPTED_OUTPUT,
                f"Cannot open image: {err}",
                err,
            ) from err
        return [self._ocr_image(img, page_number=1)]

    def _ocr_image(self, img: Any, page_number: int) -> OCRPageResult:
        try:
            import pytesseract  # type: ignore[import-untyped]
        except ImportError as err:
            raise OCRProviderError(
                OCRProvider.TESSERACT,
                FallbackReason.AZURE_EXCEPTION,
                "pytesseract not installed",
                err,
            ) from err

        try:
            text: str = pytesseract.image_to_string(img, lang=self._lang) or ""
            text = text.strip()
        except Exception as err:
            self._log.warning("tesseract_ocr.page_failed", page=page_number, error=str(err))
            text = ""

        confidence = 0.75 if text else 0.0
        return OCRPageResult(
            page_number=page_number,
            text=text,
            confidence=confidence,
            provider=OCRProvider.TESSERACT,
            word_count=len(text.split()) if text else 0,
            char_count=len(text),
        )
