"""
Policy ingestion pipeline package.

Primary entry point:
    from app.services.ingestion import IngestionPipeline, PolicyIngestionRequest

    pipeline = IngestionPipeline.from_clients(
        pinecone_client=get_pinecone_client(),
        embedding_service=EmbeddingService.from_settings(),
    )
    result = await pipeline.ingest(request, pdf_bytes)
"""

from app.services.ingestion.chunker import PolicyChunker
from app.services.ingestion.dedup import DuplicateDetector
from app.services.ingestion.extractor import MetadataExtractor
from app.services.ingestion.models import (
    BatchValidationResult,
    ChunkingResult,
    CriterionType,
    DuplicateCheckResult,
    ExtractedMetadata,
    IngestionResult,
    IngestionStatus,
    ParsedDocument,
    ParsedPage,
    PolicyCriterion,
    PolicyIngestionRequest,
    ValidationResult,
)
from app.services.ingestion.pdf_parser import PDFParser, PDFParseError
from app.services.ingestion.pipeline import IngestionPipeline
from app.services.ingestion.validator import ChunkValidator

__all__ = [
    # Pipeline
    "IngestionPipeline",
    # Stage services
    "PDFParser",
    "PDFParseError",
    "PolicyChunker",
    "MetadataExtractor",
    "ChunkValidator",
    "DuplicateDetector",
    # Models
    "PolicyIngestionRequest",
    "ParsedPage",
    "ParsedDocument",
    "PolicyCriterion",
    "ChunkingResult",
    "ExtractedMetadata",
    "ValidationResult",
    "BatchValidationResult",
    "DuplicateCheckResult",
    "IngestionResult",
    "IngestionStatus",
    "CriterionType",
]
