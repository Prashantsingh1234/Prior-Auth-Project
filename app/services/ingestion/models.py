"""
Data models for the policy ingestion pipeline.

These models are internal to the ingestion layer — they carry enriched
state as the document flows through each pipeline stage. They are distinct
from the ORM models (app/models/) and the vector schemas (app/services/vector/).
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class CriterionType(str, Enum):
    """Semantic classification of a policy chunk."""
    COVERAGE_CRITERIA  = "COVERAGE_CRITERIA"   # Positive coverage conditions
    EXCLUSION          = "EXCLUSION"            # Services not covered
    LIMITATION         = "LIMITATION"           # Quantitative limits (units, frequency)
    DOCUMENTATION      = "DOCUMENTATION"        # Required supporting docs
    DEFINITION         = "DEFINITION"           # Clinical / payer definitions
    GENERAL            = "GENERAL"              # Background / uncategorized


class IngestionStatus(str, Enum):
    SUCCESS      = "SUCCESS"
    DUPLICATE    = "DUPLICATE"
    PARTIAL      = "PARTIAL"     # Some chunks failed validation
    FAILED       = "FAILED"


# ---------------------------------------------------------------------------
# Pipeline input
# ---------------------------------------------------------------------------

class PolicyIngestionRequest(BaseModel):
    """
    Caller-supplied metadata for a policy document being ingested.

    Fields left as None are filled in by the extraction stage.
    """
    policy_id: str = Field(
        ...,
        description="Unique slug: payer-service-vN (e.g. aetna-cgm-v3)"
    )
    policy_name: str = Field(..., description="Human-readable policy title")
    payer_name: str | None = None
    service_type: str | None = None
    namespace: str | None = None   # Pinecone namespace override

    # Pre-supplied codes (extractor fills in any that are missing)
    cpt_codes: list[str] = Field(default_factory=list)
    icd_codes: list[str] = Field(default_factory=list)

    # Pre-supplied dates (extractor fills in if absent)
    effective_date: str | None = None
    expiration_date: str | None = None
    policy_version: str | None = None

    @field_validator("policy_id")
    @classmethod
    def policy_id_slug(cls, v: str) -> str:
        if not v.replace("-", "").replace("_", "").replace(".", "").isalnum():
            raise ValueError(
                "policy_id must be a slug (letters, digits, hyphens, dots, underscores)"
            )
        return v.lower()


# ---------------------------------------------------------------------------
# PDF parsing
# ---------------------------------------------------------------------------

class ParsedPage(BaseModel):
    """Text and layout data extracted from one PDF page."""
    page_number: int = Field(..., ge=1)
    text: str
    char_count: int
    used_ocr: bool = False
    tables: list[list[list[str]]] = Field(
        default_factory=list,
        description="Structured table data extracted from the page",
    )


class ParsedDocument(BaseModel):
    """Full text + structure extracted from a PDF."""
    pages: list[ParsedPage]
    full_text: str
    total_pages: int
    used_ocr_pages: list[int] = Field(default_factory=list)
    document_hash: str = Field(..., description="SHA-256 of raw PDF bytes")

    @property
    def avg_chars_per_page(self) -> float:
        if not self.pages:
            return 0.0
        return sum(p.char_count for p in self.pages) / len(self.pages)

    @property
    def is_text_poor(self) -> bool:
        """True when the PDF appears scanned (< 80 chars/page on average)."""
        return self.avg_chars_per_page < 80


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

class PolicyCriterion(BaseModel):
    """
    A single policy criterion — the output unit of the chunking stage.

    One criterion = one Pinecone vector.
    Text must be self-contained: a reviewer reading just this chunk should
    understand the complete condition being stated.
    """
    chunk_index: int
    text: str = Field(..., min_length=20)
    criterion_type: CriterionType = CriterionType.GENERAL
    section_header: str | None = None   # Parent section heading for context
    list_marker: str | None = None      # Original bullet / number ("1.", "a.", "•")
    source_page: int = Field(1, ge=1)

    # Codes extracted from this specific chunk (may overlap with doc-level codes)
    cpt_codes: list[str] = Field(default_factory=list)
    icd_codes: list[str] = Field(default_factory=list)

    # Quality signals
    has_negation: bool = False          # Contains "not covered", "excluded", etc.
    confidence: float = Field(1.0, ge=0.0, le=1.0)

    @property
    def enriched_text(self) -> str:
        """
        Full text as it will be embedded: section header prepended for context.

        A retrieval query asking "Does insulin pump require A1C documentation?"
        matches better when the section header "Coverage Criteria" is part of
        the embedded text.
        """
        if self.section_header:
            return f"{self.section_header}\n{self.text}"
        return self.text


class ChunkingResult(BaseModel):
    """Output of the chunking stage."""
    criteria: list[PolicyCriterion]
    total_chunks: int
    strategy_used: str
    sections_found: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Metadata extraction
# ---------------------------------------------------------------------------

class ExtractedMetadata(BaseModel):
    """Metadata pulled from the document text by the extractor."""
    cpt_codes: list[str] = Field(default_factory=list)
    icd_codes: list[str] = Field(default_factory=list)
    policy_version: str | None = None
    effective_date: str | None = None
    expiration_date: str | None = None
    payer_name: str | None = None
    service_type: str | None = None
    revision_history: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class ValidationResult(BaseModel):
    """Outcome of validating a single PolicyCriterion."""
    chunk_index: int
    is_valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class BatchValidationResult(BaseModel):
    valid_criteria: list[PolicyCriterion]
    invalid_criteria: list[PolicyCriterion]
    results: list[ValidationResult]

    @property
    def pass_rate(self) -> float:
        total = len(self.results)
        if not total:
            return 0.0
        return len(self.valid_criteria) / total


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------

class DuplicateCheckResult(BaseModel):
    is_duplicate: bool
    existing_policy_id: str | None = None
    existing_version: str | None = None
    document_hash: str


# ---------------------------------------------------------------------------
# Pipeline result
# ---------------------------------------------------------------------------

class IngestionResult(BaseModel):
    """Final result returned to the caller after full pipeline execution."""
    policy_id: str
    status: IngestionStatus
    document_hash: str
    total_pages: int
    total_chunks_indexed: int
    valid_chunks: int
    invalid_chunks: int
    used_ocr: bool
    strategy_used: str
    extracted_cpt_codes: list[str]
    extracted_icd_codes: list[str]
    effective_date: str | None
    policy_version: str | None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
