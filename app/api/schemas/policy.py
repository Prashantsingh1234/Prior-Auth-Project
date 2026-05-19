"""API schemas for policy management."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import PolicyEmbeddingStatus, PolicyProcessingStatus


class PolicyCreateResponse(BaseModel):
    policy_id: str


class PolicyListItem(BaseModel):
    id: str
    policy_key: str
    policy_name: str
    policy_version: str
    policy_type: str | None = None
    effective_date: date | None = None
    upload_date: datetime
    total_chunks: int
    processing_status: PolicyProcessingStatus
    embedding_status: PolicyEmbeddingStatus
    pinecone_namespace: str
    original_filename: str
    last_processed_at: datetime | None = None
    last_error: str | None = None

    @classmethod
    def from_orm_row(cls, p) -> "PolicyListItem":
        return cls(
            id=str(p.id),
            policy_key=p.policy_key,
            policy_name=p.policy_name,
            policy_version=p.policy_version,
            policy_type=p.policy_type,
            effective_date=p.effective_date,
            upload_date=p.created_at,
            total_chunks=p.total_chunks,
            processing_status=p.processing_status,
            embedding_status=p.embedding_status,
            pinecone_namespace=p.pinecone_namespace,
            original_filename=p.original_filename,
            last_processed_at=p.last_processed_at,
            last_error=p.last_error,
        )


class PolicyListResponse(BaseModel):
    items: list[PolicyListItem]
    total: int


class PolicyProcessResponse(BaseModel):
    policy_id: str
    status: PolicyProcessingStatus
    total_chunks: int = 0
    warnings: list[str] = Field(default_factory=list)


class PolicyChunkItem(BaseModel):
    id: str
    chunk_index: int
    chunk_length: int
    chunk_overlap: int
    preview: str
    cpt_codes: list[str] = Field(default_factory=list)
    icd_codes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_orm_row(cls, c) -> "PolicyChunkItem":
        text = c.chunk_text or ""
        preview = text[:400].strip()
        if len(text) > 400:
            preview = preview + "…"
        return cls(
            id=str(c.id),
            chunk_index=c.chunk_index,
            chunk_length=c.chunk_length,
            chunk_overlap=c.chunk_overlap,
            preview=preview,
            cpt_codes=list(c.cpt_codes or []),
            icd_codes=list(c.icd_codes or []),
            metadata=dict(c.chunk_metadata or {}),
        )


class PolicyChunkListResponse(BaseModel):
    items: list[PolicyChunkItem]
    total: int

