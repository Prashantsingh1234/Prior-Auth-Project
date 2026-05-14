"""
PaddleOCR fallback provider.

Handles all document types that Azure fails on:
- Scanned PDFs with poor layout
- Images (PNG, JPG, TIFF)
- Documents rejected by Azure's format validator
- Low-confidence Azure outputs

PDF → PaddleOCR:
  PaddleOCR accepts raw PDF bytes with page_num parameter.

Image → PaddleOCR:
  Images are passed as numpy arrays via PIL.

Confidence scoring:
  PaddleOCR returns per-word (text, confidence) tuples.
  We aggregate to page-level confidence as a weighted average.
"""

from __future__ import annotations

import asyncio
import io
import time
from typing import Any

import structlog

from app.services.ocr.base import (
    BaseOCRProvider,
    ExtractedTable,
    FallbackReason,
    OCRPageResult,
    OCRProvider,
    OCRProviderError,
    OCRResult,
)

logger = structlog.get_logger(__name__)

_PADDLE_CONFIDENCE_THRESHOLD = 0.70

# MIME types PaddleOCR can handle via numpy array path
_IMAGE_MIMES = {"image/png", "image/jpeg", "image/jpg", "image/tiff", "image/bmp"}
_PDF_MIMES   = {"application/pdf"}


class PaddleOCRProvider(BaseOCRProvider):
    """
    PaddleOCR-based OCR provider for fallback and image processing.

    Usage:
        provider = PaddleOCRProvider()
        result = await provider.extract(image_bytes, "image/png")
    """

    def __init__(
        self,
        lang: str = "en",
        use_angle_cls: bool = True,
        use_gpu: bool = False,
    ) -> None:
        self._lang          = lang
        self._use_angle_cls = use_angle_cls
        self._use_gpu       = use_gpu
        self._engine: Any | None = None
        self._log = structlog.get_logger(self.__class__.__name__)

    @property
    def provider_name(self) -> OCRProvider:
        return OCRProvider.PADDLE

    @property
    def confidence_threshold(self) -> float:
        return _PADDLE_CONFIDENCE_THRESHOLD

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
            "paddle_ocr.started",
            mime_type=mime_type,
            content_size=len(content),
        )

        try:
            if mime_type in _PDF_MIMES:
                pages = await asyncio.to_thread(
                    self._extract_pdf_sync, content, page_count
                )
            elif mime_type in _IMAGE_MIMES:
                pages = await asyncio.to_thread(
                    self._extract_image_sync, content, mime_type
                )
            else:
                # Attempt as image — let PaddleOCR decide
                pages = await asyncio.to_thread(
                    self._extract_image_sync, content, mime_type
                )
        except OCRProviderError:
            raise
        except Exception as err:
            raise OCRProviderError(
                provider=OCRProvider.PADDLE,
                reason=FallbackReason.AZURE_EXCEPTION,  # generic provider error
                message=f"PaddleOCR failed: {err}",
                original_error=err,
            ) from err

        elapsed_ms = (time.monotonic() - start) * 1000
        result = OCRResult.from_pages(pages, OCRProvider.PADDLE, elapsed_ms)

        self._log.info(
            "paddle_ocr.complete",
            pages=result.total_pages,
            confidence=result.overall_confidence,
            elapsed_ms=round(elapsed_ms, 1),
        )
        return result

    async def is_available(self) -> bool:
        try:
            import paddleocr  # noqa: F401
            return True
        except ImportError:
            return False

    # ------------------------------------------------------------------
    # Sync extraction helpers
    # ------------------------------------------------------------------

    def _extract_pdf_sync(
        self,
        content: bytes,
        page_count: int | None,
    ) -> list[OCRPageResult]:
        import pypdf

        engine = self._get_engine()
        reader = pypdf.PdfReader(io.BytesIO(content))
        total  = len(reader.pages)
        pages: list[OCRPageResult] = []

        for page_num in range(1, total + 1):
            try:
                raw_result = engine.ocr(content, page_num=page_num)
                page = self._parse_result(raw_result, page_num)
            except Exception as err:
                self._log.warning(
                    "paddle_ocr.page_failed",
                    page=page_num,
                    error=str(err),
                )
                page = OCRPageResult(
                    page_number=page_num,
                    text="",
                    confidence=0.0,
                    provider=OCRProvider.PADDLE,
                )
            pages.append(page)

        return pages

    def _extract_image_sync(
        self,
        content: bytes,
        mime_type: str,
    ) -> list[OCRPageResult]:
        import numpy as np
        from PIL import Image

        engine = self._get_engine()

        try:
            img = Image.open(io.BytesIO(content)).convert("RGB")
            img_array = np.array(img)
        except Exception as err:
            raise OCRProviderError(
                OCRProvider.PADDLE,
                FallbackReason.CORRUPTED_OUTPUT,
                f"Cannot decode image: {err}",
                err,
            ) from err

        raw_result = engine.ocr(img_array)
        return [self._parse_result(raw_result, page_number=1)]

    def _parse_result(
        self,
        raw_result: Any,
        page_number: int,
    ) -> OCRPageResult:
        """Convert PaddleOCR raw output to OCRPageResult."""
        if not raw_result or not raw_result[0]:
            return OCRPageResult(
                page_number=page_number,
                text="",
                confidence=0.0,
                provider=OCRProvider.PADDLE,
            )

        lines: list[str] = []
        confidences: list[float] = []

        for detection in raw_result[0]:
            if not detection or len(detection) < 2:
                continue
            text_conf = detection[1]
            if not text_conf:
                continue
            text = text_conf[0] if isinstance(text_conf, (list, tuple)) else str(text_conf)
            conf = text_conf[1] if isinstance(text_conf, (list, tuple)) and len(text_conf) > 1 else 0.8

            if text and str(text).strip():
                lines.append(str(text).strip())
                confidences.append(float(conf))

        text = "\n".join(lines)
        confidence = sum(confidences) / len(confidences) if confidences else 0.0

        return OCRPageResult(
            page_number=page_number,
            text=text,
            confidence=round(confidence, 4),
            provider=OCRProvider.PADDLE,
            word_count=sum(len(l.split()) for l in lines),
            char_count=len(text),
        )

    # ------------------------------------------------------------------
    # Engine lifecycle
    # ------------------------------------------------------------------

    def _get_engine(self) -> Any:
        if self._engine is None:
            try:
                from paddleocr import PaddleOCR
            except ImportError as err:
                raise OCRProviderError(
                    OCRProvider.PADDLE,
                    FallbackReason.AZURE_EXCEPTION,
                    "paddleocr not installed",
                    err,
                ) from err
            self._engine = PaddleOCR(
                use_angle_cls=self._use_angle_cls,
                lang=self._lang,
                use_gpu=self._use_gpu,
                show_log=False,
            )
        return self._engine
