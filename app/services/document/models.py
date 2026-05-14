"""
Data models for the document ingestion pipeline.

These models represent the full lifecycle of a healthcare document from raw
bytes through normalization, OCR, layout parsing, and final structured output.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.services.ocr.base import (
    ExtractedTable,
    KeyValuePair,
    OCRProvider,
    OCRResult,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class DocumentType(str, Enum):
    """Physical format of the raw input."""
    SCANNED_PDF             = "SCANNED_PDF"
    NATIVE_PDF              = "NATIVE_PDF"    # Has embedded text — no OCR needed
    IMAGE_PNG               = "IMAGE_PNG"
    IMAGE_JPG               = "IMAGE_JPG"
    IMAGE_TIFF              = "IMAGE_TIFF"
    JSON_PAYLOAD            = "JSON_PAYLOAD"
    TEXT_NOTE               = "TEXT_NOTE"
    EMAIL                   = "EMAIL"
    UNKNOWN                 = "UNKNOWN"


class DocumentCategory(str, Enum):
    """Clinical / administrative category inferred from content."""
    PRESCRIPTION            = "PRESCRIPTION"
    LAB_REPORT              = "LAB_REPORT"
    MEDICAL_NECESSITY_CERT  = "MEDICAL_NECESSITY_CERT"
    INSURANCE_CARD          = "INSURANCE_CARD"
    REFERRAL                = "REFERRAL"
    CLINICAL_NOTE           = "CLINICAL_NOTE"
    RADIOLOGY_REPORT        = "RADIOLOGY_REPORT"
    OPERATIVE_REPORT        = "OPERATIVE_REPORT"
    POLICY_DOCUMENT         = "POLICY_DOCUMENT"
    GENERAL                 = "GENERAL"


class IngestionStatus(str, Enum):
    SUCCESS         = "SUCCESS"
    PARTIAL         = "PARTIAL"      # Processed with warnings
    DUPLICATE       = "DUPLICATE"
    FAILED          = "FAILED"
    UNSUPPORTED     = "UNSUPPORTED"  # File type not supported


class NormalizationMethod(str, Enum):
    NATIVE_TEXT     = "native_text"   # PDF with embedded text
    OCR_AZURE       = "ocr_azure"
    OCR_PADDLE      = "ocr_paddle"
    OCR_MERGED      = "ocr_merged"    # Both providers merged
    DIRECT_PARSE    = "direct_parse"  # JSON / TXT — no OCR
    EMAIL_EXTRACT   = "email_extract"


# ---------------------------------------------------------------------------
# Ingestion request
# ---------------------------------------------------------------------------

class DocumentIngestionRequest(BaseModel):
    """Caller-supplied context for a document being ingested."""
    document_id: str = Field(..., description="Unique identifier for this document")
    case_id: str | None = None
    patient_id: str | None = None
    filename: str = ""
    mime_type: str = ""
    expected_category: DocumentCategory | None = None
    source_system: str | None = None    # e.g. "fax", "portal_upload", "hl7"
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Normalized content models
# ---------------------------------------------------------------------------

class NormalizedPage(BaseModel):
    """Normalized content for a single page after OCR + layout analysis."""
    page_number: int
    text: str
    confidence: float = 1.0
    ocr_provider: OCRProvider = OCRProvider.NONE
    tables: list[ExtractedTable] = Field(default_factory=list)
    key_values: list[KeyValuePair] = Field(default_factory=list)
    section_headers: list[str] = Field(default_factory=list)
    used_fallback: bool = False


class StructuredSection(BaseModel):
    """A named section extracted from the document."""
    title: str
    content: str
    page_start: int
    page_end: int
    section_type: str = "general"     # "header", "body", "findings", "impression" …


class MedicalEntities(BaseModel):
    """
    Lightweight medical entities extracted during layout parsing.
    Full NLP extraction happens in the medical entity service (future step).
    """
    patient_name: str | None = None
    date_of_birth: str | None = None
    mrn: str | None = None
    ordering_provider: str | None = None
    facility: str | None = None
    diagnosis_codes: list[str] = Field(default_factory=list)
    procedure_codes: list[str] = Field(default_factory=list)
    medications: list[str] = Field(default_factory=list)
    dates: list[str] = Field(default_factory=list)
    lab_values: list[dict[str, str]] = Field(default_factory=list)


class NormalizedDocument(BaseModel):
    """
    Fully normalized and structured document output.

    This is the output of the document ingestion pipeline and the input
    to downstream services (medical entity extraction, retrieval, reasoning).
    """
    document_id: str
    document_type: DocumentType
    document_category: DocumentCategory
    normalization_method: NormalizationMethod

    # Content
    full_text: str
    pages: list[NormalizedPage]
    sections: list[StructuredSection] = Field(default_factory=list)
    all_tables: list[ExtractedTable] = Field(default_factory=list)
    all_key_values: list[KeyValuePair] = Field(default_factory=list)

    # Extracted entities (lightweight pass)
    entities: MedicalEntities = Field(default_factory=MedicalEntities)

    # Quality signals
    overall_confidence: float = 1.0
    total_pages: int
    document_hash: str
    ocr_used: bool = False
    fallback_triggered: bool = False
    fallback_pages: list[int] = Field(default_factory=list)

    # Metadata
    filename: str = ""
    mime_type: str = ""
    file_size_bytes: int = 0
    warnings: list[str] = Field(default_factory=list)

    @property
    def is_reliable(self) -> bool:
        return self.overall_confidence >= 0.80

    @property
    def has_tables(self) -> bool:
        return len(self.all_tables) > 0

    @property
    def has_key_values(self) -> bool:
        return len(self.all_key_values) > 0


# ---------------------------------------------------------------------------
# Pipeline result
# ---------------------------------------------------------------------------

class DocumentIngestionResult(BaseModel):
    """Final result returned to the caller after full pipeline execution."""
    document_id: str
    status: IngestionStatus
    document_hash: str
    document_type: DocumentType
    document_category: DocumentCategory
    normalization_method: NormalizationMethod
    total_pages: int
    overall_confidence: float
    ocr_provider_used: OCRProvider
    fallback_triggered: bool
    fallback_pages: list[int] = Field(default_factory=list)
    tables_extracted: int
    key_values_extracted: int
    sections_found: int
    processing_time_ms: float
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    normalized_document: NormalizedDocument | None = None
