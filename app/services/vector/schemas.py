"""
Pydantic schemas for the Pinecone vector layer.

Every piece of data that moves into or out of Pinecone is typed here.
The schemas enforce the metadata contract at the Python layer so that
bad data is caught before it reaches the index.

Metadata stored per vector:
  - Policy identity  (policy_id, name, version, effective/expiry dates)
  - Medical codes    (cpt_codes, icd_codes) — lists, filterable
  - Document context (chunk_index, chunk_text preview, total_chunks)
  - Provenance       (payer_name, service_type, source_url, document_hash)

Vector ID convention:  {policy_id}_{chunk_index:04d}
  e.g.  aetna-cgx-pump-v3_0012
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Sparse vector (BM25 / keyword representation)
# ---------------------------------------------------------------------------

class SparseVector(BaseModel):
    """Sparse representation for hybrid Pinecone retrieval."""

    indices: list[int] = Field(..., description="Non-zero dimension indices")
    values: list[float] = Field(..., description="Corresponding weights")

    @field_validator("values")
    @classmethod
    def validate_lengths_match(cls, v: list[float], info) -> list[float]:
        indices = info.data.get("indices", [])
        if len(indices) != len(v):
            raise ValueError(
                f"indices length ({len(indices)}) must match values length ({len(v)})"
            )
        return v

    def scale(self, alpha: float) -> "SparseVector":
        """Return a copy with all values multiplied by alpha."""
        return SparseVector(indices=self.indices, values=[v * alpha for v in self.values])

    def to_pinecone_dict(self) -> dict[str, list]:
        return {"indices": self.indices, "values": self.values}


# ---------------------------------------------------------------------------
# Policy chunk metadata
# ---------------------------------------------------------------------------

class PolicyChunkMetadata(BaseModel):
    """
    Metadata attached to each Pinecone vector for a policy chunk.

    Pinecone metadata values must be str | int | float | bool | list[str].
    All datetime values are stored as ISO-8601 strings.
    """

    # Policy identity
    policy_id: str = Field(..., description="Unique policy identifier (slug-style)")
    policy_name: str = Field(..., description="Human-readable policy name")
    policy_version: str = Field(..., description="Policy version, e.g. '3.2.1'")

    # Validity window
    effective_date: str = Field(..., description="YYYY-MM-DD")
    expiration_date: str | None = Field(None, description="YYYY-MM-DD or null if open-ended")

    # Medical codes — stored as lists for $in metadata filtering
    cpt_codes: list[str] = Field(default_factory=list)
    icd_codes: list[str] = Field(default_factory=list)

    # Clinical context
    service_type: str | None = Field(None, description="e.g. 'DIAGNOSTIC', 'SURGICAL'")
    payer_name: str | None = Field(None, description="Insurance payer name")

    # Chunk context
    chunk_index: int = Field(..., ge=0, description="Zero-based chunk position in document")
    total_chunks: int = Field(..., ge=1)
    chunk_text: str = Field(..., description="First 1000 chars of chunk for display")

    # Provenance
    source_url: str | None = None
    document_hash: str = Field(..., description="SHA-256 of the source document")

    def to_pinecone_dict(self) -> dict[str, Any]:
        """
        Serialize to Pinecone-compatible metadata dict.

        Pinecone does not support nested dicts or None values — these are
        flattened / dropped here.
        """
        data: dict[str, Any] = {
            "policy_id": self.policy_id,
            "policy_name": self.policy_name,
            "policy_version": self.policy_version,
            "effective_date": self.effective_date,
            "cpt_codes": self.cpt_codes,
            "icd_codes": self.icd_codes,
            "chunk_index": self.chunk_index,
            "total_chunks": self.total_chunks,
            "chunk_text": self.chunk_text[:1000],
            "document_hash": self.document_hash,
        }
        # Omit None fields — Pinecone rejects null values in metadata
        if self.expiration_date:
            data["expiration_date"] = self.expiration_date
        if self.service_type:
            data["service_type"] = self.service_type
        if self.payer_name:
            data["payer_name"] = self.payer_name
        if self.source_url:
            data["source_url"] = self.source_url
        return data

    @classmethod
    def from_pinecone_dict(cls, data: dict[str, Any]) -> "PolicyChunkMetadata":
        """Reconstruct from Pinecone query result metadata."""
        return cls(
            policy_id=data["policy_id"],
            policy_name=data.get("policy_name", ""),
            policy_version=data.get("policy_version", "1.0.0"),
            effective_date=data.get("effective_date", "2024-01-01"),
            expiration_date=data.get("expiration_date"),
            cpt_codes=list(data.get("cpt_codes") or []),
            icd_codes=list(data.get("icd_codes") or []),
            service_type=data.get("service_type"),
            payer_name=data.get("payer_name"),
            chunk_index=int(data.get("chunk_index", 0)),
            total_chunks=int(data.get("total_chunks", 1)),
            chunk_text=data.get("chunk_text", ""),
            source_url=data.get("source_url"),
            document_hash=data.get("document_hash", ""),
        )


# ---------------------------------------------------------------------------
# Policy vector (ready for Pinecone upsert)
# ---------------------------------------------------------------------------

class PolicyVector(BaseModel):
    """A dense (+ optionally sparse) vector ready for Pinecone upsert."""

    id: str = Field(
        ...,
        description="Unique vector ID: {policy_id}_{chunk_index:04d}",
    )
    values: list[float] = Field(..., description="Dense embedding vector")
    sparse_values: SparseVector | None = Field(
        None,
        description="Sparse vector for hybrid search (BM25-style medical codes)",
    )
    metadata: PolicyChunkMetadata

    @classmethod
    def make_id(cls, policy_id: str, chunk_index: int) -> str:
        return f"{policy_id}_{chunk_index:04d}"

    def to_pinecone_dict(self) -> dict[str, Any]:
        """Serialize to the dict format Pinecone's upsert() expects."""
        record: dict[str, Any] = {
            "id": self.id,
            "values": self.values,
            "metadata": self.metadata.to_pinecone_dict(),
        }
        if self.sparse_values is not None:
            record["sparse_values"] = self.sparse_values.to_pinecone_dict()
        return record


# ---------------------------------------------------------------------------
# Query / retrieval results
# ---------------------------------------------------------------------------

class RetrievalMatch(BaseModel):
    """A single vector match returned from a Pinecone query."""

    vector_id: str
    score: float = Field(..., ge=0.0, description="Similarity score (cosine or hybrid)")
    metadata: PolicyChunkMetadata

    @property
    def is_high_confidence(self) -> bool:
        """True if the score meets the retrieval quality threshold."""
        return self.score >= 0.75


class QueryResult(BaseModel):
    """Structured output from a Pinecone query operation."""

    matches: list[RetrievalMatch]
    total_matches: int
    retrieval_type: str = Field(
        ...,
        description="'semantic' | 'hybrid'",
    )
    latency_ms: float
    namespace: str
    query_cpt_codes: list[str] = Field(default_factory=list)
    query_icd_codes: list[str] = Field(default_factory=list)

    @property
    def top_match(self) -> RetrievalMatch | None:
        return self.matches[0] if self.matches else None

    @property
    def unique_policy_ids(self) -> list[str]:
        """Deduplicated list of policy IDs in the result set."""
        seen: list[str] = []
        for m in self.matches:
            pid = m.metadata.policy_id
            if pid not in seen:
                seen.append(pid)
        return seen


# ---------------------------------------------------------------------------
# Index statistics
# ---------------------------------------------------------------------------

class IndexStats(BaseModel):
    """Summary statistics from Pinecone describe_index_stats()."""

    total_vector_count: int
    dimension: int
    index_fullness: float
    namespaces: dict[str, int] = Field(
        default_factory=dict,
        description="Namespace → vector count",
    )
