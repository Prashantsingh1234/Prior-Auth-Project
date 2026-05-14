"""
Document ingestion pipeline package.

Primary entry point:
    from app.services.document import DocumentIngestionPipeline

    pipeline = DocumentIngestionPipeline.from_settings()
    result = await pipeline.ingest(request, file_bytes)
"""

from app.services.document.detector import DocumentDetector
from app.services.document.layout_parser import LayoutParser
from app.services.document.models import (
    DocumentCategory,
    DocumentIngestionRequest,
    DocumentIngestionResult,
    DocumentType,
    IngestionStatus,
    MedicalEntities,
    NormalizationMethod,
    NormalizedDocument,
    NormalizedPage,
    StructuredSection,
)
from app.services.document.normalizer import DocumentNormalizer
from app.services.document.pipeline import DocumentIngestionPipeline

__all__ = [
    # Pipeline
    "DocumentIngestionPipeline",
    # Services
    "DocumentDetector",
    "DocumentNormalizer",
    "LayoutParser",
    # Models
    "DocumentIngestionRequest",
    "DocumentIngestionResult",
    "NormalizedDocument",
    "NormalizedPage",
    "StructuredSection",
    "MedicalEntities",
    "DocumentType",
    "DocumentCategory",
    "IngestionStatus",
    "NormalizationMethod",
]
