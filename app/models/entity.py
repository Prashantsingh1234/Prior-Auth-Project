"""
ExtractedEntity ORM model.

Stores individual medical entities extracted from documents via OCR + LLM.
Each row represents one atomic extracted fact: a CPT code, a glucose reading,
a medication name, an ICD code, etc.

The entity_value JSON column accommodates varying shapes per entity type:
  CPT_CODE:         {"code": "95249", "description": "..."}
  GLUCOSE_READING:  {"value": 320, "unit": "mg/dL", "date": "2024-01-15"}
  MEDICATION:       {"name": "Metformin", "dose": "500mg", "frequency": "BID"}
  LAB_VALUE:        {"test": "HbA1c", "value": 9.2, "unit": "%"}
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base.model import BaseModel
from app.models.enums import EntityType, ExtractionMethod

if TYPE_CHECKING:
    from app.models.document import UploadedDocument
    from app.models.pa_case import PACase


class ExtractedEntity(BaseModel):
    """
    A single medical entity extracted from a document or case context.

    Multiple entities of the same type can exist per case (e.g., multiple
    lab values, multiple medications). The confidence_score reflects
    the LLM's certainty about the extraction.
    """

    __tablename__ = "extracted_entities"

    # ----------------------------------------------------------
    # Foreign Keys
    # ----------------------------------------------------------
    case_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("pa_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[str | None] = mapped_column(
        CHAR(36),
        ForeignKey("uploaded_documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Source document — NULL if entity was inferred from case context",
    )

    # ----------------------------------------------------------
    # Entity Classification
    # ----------------------------------------------------------
    entity_type: Mapped[EntityType] = mapped_column(
        SAEnum(EntityType),
        nullable=False,
        index=True,
    )
    entity_key: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Machine-readable key, e.g. 'icd_code', 'medication_name', 'hba1c'",
    )
    # Flexible JSON value — shape varies by entity_type (see module docstring)
    entity_value: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    # Human-readable string for display and logging
    display_value: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # ----------------------------------------------------------
    # Extraction Provenance
    # ----------------------------------------------------------
    extraction_method: Mapped[ExtractionMethod] = mapped_column(
        SAEnum(ExtractionMethod),
        nullable=False,
        default=ExtractionMethod.LLM,
    )
    confidence_score: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="Extraction confidence (0.0–1.0)"
    )
    # The verbatim text span the entity was extracted from
    source_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Page number within the source document (1-indexed)
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Character offset within extracted_text for highlighting
    source_start_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_end_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ----------------------------------------------------------
    # Validation
    # ----------------------------------------------------------
    # Whether this entity has been confirmed by a human reviewer
    is_verified: Mapped[bool] = mapped_column(
        nullable=False, default=False
    )
    is_corrected: Mapped[bool] = mapped_column(
        nullable=False, default=False,
        comment="True if a reviewer modified the AI-extracted value",
    )
    # Original AI-extracted value before reviewer correction
    original_value: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # ----------------------------------------------------------
    # Relationships
    # ----------------------------------------------------------
    case: Mapped["PACase"] = relationship(
        "PACase", back_populates="entities", lazy="raise"
    )
    document: Mapped["UploadedDocument | None"] = relationship(
        "UploadedDocument", back_populates="entities", lazy="raise"
    )

    # ----------------------------------------------------------
    # Indexes
    # ----------------------------------------------------------
    __table_args__ = (
        Index("ix_entities_case_id", "case_id"),
        Index("ix_entities_document_id", "document_id"),
        Index("ix_entities_type", "entity_type"),
        Index("ix_entities_key", "entity_key"),
        Index("ix_entities_case_type", "case_id", "entity_type"),
    )

    def __repr__(self) -> str:
        return (
            f"<ExtractedEntity id={self.id} "
            f"type={self.entity_type} key={self.entity_key}>"
        )
