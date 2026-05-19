"""
UploadedDocument ORM model.

Tracks every file submitted with a PA case: PDFs, images, lab reports,
prescriptions, EHR exports, etc. Records OCR processing status,
confidence scores, extracted text, and the raw OCR provider response.

The checksum field enables duplicate detection — if two uploads produce
the same SHA-256 hash, we avoid redundant OCR processing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import CHAR, LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base.model import BaseModel
from app.models.enums import DocumentType, OCRProvider, OCRStatus

if TYPE_CHECKING:
    from app.models.pa_case import PACase


class UploadedDocument(BaseModel):
    """
    A clinical document attached to a PA case.

    Tracks the full document ingestion pipeline:
    upload → preprocessing → OCR (Azure primary, PaddleOCR fallback)
    → text extraction → entity extraction

    processing_attempts counts total OCR retries across both providers.
    """

    __tablename__ = "uploaded_documents"

    # ----------------------------------------------------------
    # Foreign Key
    # ----------------------------------------------------------
    case_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("pa_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ----------------------------------------------------------
    # File Metadata
    # ----------------------------------------------------------
    document_type: Mapped[DocumentType] = mapped_column(
        SAEnum(DocumentType),
        nullable=False,
        default=DocumentType.OTHER,
    )
    original_filename: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="Original filename as uploaded by user"
    )
    stored_filename: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="Sanitized filename used in storage"
    )
    storage_path: Mapped[str] = mapped_column(
        String(1000), nullable=False, comment="Absolute path or object storage key"
    )
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # SHA-256 hash for dedup detection — computed before storage
    checksum_sha256: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True, comment="SHA-256 hex digest for dedup"
    )
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ----------------------------------------------------------
    # OCR Pipeline
    # ----------------------------------------------------------
    ocr_provider: Mapped[OCRProvider] = mapped_column(
        SAEnum(OCRProvider),
        nullable=False,
        default=OCRProvider.NONE,
        comment="Which OCR provider produced the final extracted_text",
    )
    ocr_status: Mapped[OCRStatus] = mapped_column(
        SAEnum(OCRStatus),
        nullable=False,
        default=OCRStatus.PENDING,
        index=True,
    )
    # Confidence from the OCR provider (0.0–1.0)
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Full extracted text (can be very large — LONGTEXT in MySQL)
    extracted_text: Mapped[str | None] = mapped_column(LONGTEXT, nullable=True)
    # Raw provider response stored for debugging/reprocessing
    ocr_raw_response: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True, comment="Raw OCR API response for debugging"
    )
    processing_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Last error message if OCR failed"
    )

    # ----------------------------------------------------------
    # Document Intelligence Extras
    # ----------------------------------------------------------
    # Tables detected in the document (by LayoutParser / Azure Tables)
    detected_tables: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON, nullable=True
    )
    # Key-value pairs extracted by Azure Form Recognizer
    detected_key_values: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )
    # Language detected in the document
    detected_language: Mapped[str | None] = mapped_column(
        String(10), nullable=True, comment="ISO 639-1 language code"
    )

    # ----------------------------------------------------------
    # Relationships
    # ----------------------------------------------------------
    case: Mapped["PACase"] = relationship(
        "PACase", back_populates="documents", lazy="raise"
    )

    # ----------------------------------------------------------
    # Indexes & Constraints
    # ----------------------------------------------------------
    __table_args__ = (
        Index("ix_documents_case_id", "case_id"),
        Index("ix_documents_ocr_status", "ocr_status"),
        Index("ix_documents_checksum", "checksum_sha256"),
        Index("ix_documents_deleted_at", "deleted_at"),
        # Allow fast lookup of all documents for a case by type
        Index("ix_documents_case_type", "case_id", "document_type"),
    )

    @property
    def is_ocr_complete(self) -> bool:
        return self.ocr_status in (OCRStatus.COMPLETED, OCRStatus.FALLBACK_USED)

    @property
    def needs_fallback(self) -> bool:
        """True if Azure OCR failed or returned low confidence → try PaddleOCR."""
        return (
            self.ocr_status == OCRStatus.FAILED
            or (
                self.ocr_confidence is not None
                and self.ocr_confidence < 0.80
                and self.ocr_provider == OCRProvider.AZURE
            )
        )

    def __repr__(self) -> str:
        return (
            f"<UploadedDocument id={self.id} "
            f"filename={self.original_filename} "
            f"ocr_status={self.ocr_status}>"
        )
