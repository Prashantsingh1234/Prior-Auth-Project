"""
PolicyDocument + PolicyChunk ORM models.

These tables back the Admin "Policy Management" workflow:
upload -> extract -> chunk -> embed -> store in Pinecone -> audit/manage.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Enum as SAEnum,
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
from app.models.enums import PolicyEmbeddingStatus, PolicyProcessingStatus


class PolicyDocument(BaseModel):
    """A payer policy document that has been ingested and indexed for retrieval."""

    __tablename__ = "policy_documents"

    policy_key: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        unique=True,
        index=True,
        comment="Stable policy identifier (slug-like). Used for Pinecone vector IDs.",
    )
    policy_name: Mapped[str] = mapped_column(String(500), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(50), nullable=False, default="v1")

    policy_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # File metadata
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    # Extraction output (full text) - stored to support reprocessing and transparency
    extracted_text: Mapped[str | None] = mapped_column(LONGTEXT, nullable=True)
    extraction_warnings: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    # Processing / indexing state
    processing_status: Mapped[PolicyProcessingStatus] = mapped_column(
        SAEnum(PolicyProcessingStatus),
        nullable=False,
        default=PolicyProcessingStatus.UPLOADED,
        index=True,
    )
    embedding_status: Mapped[PolicyEmbeddingStatus] = mapped_column(
        SAEnum(PolicyEmbeddingStatus),
        nullable=False,
        default=PolicyEmbeddingStatus.NONE,
        index=True,
    )
    pinecone_namespace: Mapped[str] = mapped_column(String(100), nullable=False)
    total_chunks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    chunks: Mapped[list["PolicyChunk"]] = relationship(
        "PolicyChunk",
        back_populates="policy",
        lazy="raise",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        UniqueConstraint("policy_key", name="uq_policy_documents_policy_key"),
        Index("ix_policy_documents_status", "processing_status"),
        Index("ix_policy_documents_embedding", "embedding_status"),
        Index("ix_policy_documents_deleted_at", "deleted_at"),
    )


class PolicyChunk(BaseModel):
    """A semantic chunk extracted from a PolicyDocument and indexed in Pinecone."""

    __tablename__ = "policy_chunks"

    policy_document_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("policy_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(LONGTEXT, nullable=False)
    chunk_length: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_overlap: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    cpt_codes: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    icd_codes: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    chunk_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True, name="metadata")

    pinecone_vector_id: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    chunk_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    policy: Mapped["PolicyDocument"] = relationship(
        "PolicyDocument", back_populates="chunks", lazy="raise"
    )

    __table_args__ = (
        Index("ix_policy_chunks_policy_index", "policy_document_id", "chunk_index"),
        Index("ix_policy_chunks_deleted_at", "deleted_at"),
    )

