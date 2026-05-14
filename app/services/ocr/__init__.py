"""
OCR service package — provider abstraction + fallback orchestration.

Primary entry point:
    from app.services.ocr import OCROrchestrator

    orchestrator = OCROrchestrator.from_settings()
    result = await orchestrator.process(pdf_bytes, "application/pdf")

Provider abstraction:
    from app.services.ocr import AzureOCRProvider, PaddleOCRProvider, BaseOCRProvider
"""

from app.services.ocr.azure_provider import AzureOCRProvider
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
from app.services.ocr.orchestrator import OCROrchestrator
from app.services.ocr.paddle_provider import PaddleOCRProvider

__all__ = [
    # Orchestrator
    "OCROrchestrator",
    # Providers
    "BaseOCRProvider",
    "AzureOCRProvider",
    "PaddleOCRProvider",
    # Models
    "OCRResult",
    "OCRPageResult",
    "OCRProvider",
    "FallbackReason",
    "OCRProviderError",
    "ExtractedTable",
    "ExtractedCell",
    "KeyValuePair",
    "BoundingBox",
]
