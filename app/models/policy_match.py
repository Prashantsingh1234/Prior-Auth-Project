"""
PolicyMatch ORM model.

Records the result of a Pinecone hybrid retrieval query against the
policy vector index. Stores which policy was retrieved, the chunks
returned, retrieval scores, and metadata for audit purposes.

One case may have multiple policy matches (e.g., one per CPT code or
when the retriever returns candidates from multiple policies).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import Float, ForeignKey, Index, JSON, String, Text
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base.model import BaseModel

if TYPE_CHECKING:
    from app.models.pa_case import PACase


class PolicyMatch(BaseModel):
    """
    A policy retrieved from Pinecone for a specific PA case.

    Stores the retrieved chunks verbatim so the reasoning engine
    can cite evidence directly from the stored record without
    re-querying Pinecone (cache-first reasoning).
    """

    __tablename__ = "policy_matches"

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
    # Policy Identity
    # ----------------------------------------------------------
    policy_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="Policy internal identifier"
    )
    policy_name: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="Human-readable policy name"
    )
    policy_version: Mapped[str] = mapped_column(
        String(20), nullable=False, default="v1",
        comment="Policy version for cache key and audit tracking",
    )
    pinecone_namespace: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="Pinecone namespace used for retrieval"
    )

    # ----------------------------------------------------------
    # Matching Codes
    # ----------------------------------------------------------
    # Which CPT / ICD codes in the query matched this policy
    matched_cpt_codes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    matched_icd_codes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    # ----------------------------------------------------------
    # Retrieval Results
    # ----------------------------------------------------------
    # Top-level relevance score from Pinecone (hybrid: sparse + dense)
    retrieval_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Number of chunks returned
    chunk_count: Mapped[int] = mapped_column(nullable=False, default=0)
    # Retrieved chunks stored verbatim: [{text, score, metadata}, ...]
    retrieved_chunks: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list,
        comment="List of retrieved policy criterion chunks with scores and metadata",
    )
    # Raw Pinecone query metadata (model used, latency, etc.)
    retrieval_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )

    # ----------------------------------------------------------
    # Reranking
    # ----------------------------------------------------------
    rerank_score: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="Score after cross-encoder reranking"
    )
    is_primary_policy: Mapped[bool] = mapped_column(
        nullable=False, default=True,
        comment="True if this is the primary policy used for reasoning",
    )

    # ----------------------------------------------------------
    # Relationship
    # ----------------------------------------------------------
    case: Mapped["PACase"] = relationship(
        "PACase", back_populates="policy_matches", lazy="raise"
    )

    # ----------------------------------------------------------
    # Indexes
    # ----------------------------------------------------------
    __table_args__ = (
        Index("ix_policy_matches_case_id", "case_id"),
        Index("ix_policy_matches_policy_name", "policy_name"),
        Index("ix_policy_matches_version", "policy_version"),
        Index("ix_policy_matches_primary", "case_id", "is_primary_policy"),
    )

    def __repr__(self) -> str:
        return (
            f"<PolicyMatch id={self.id} "
            f"policy={self.policy_name} v={self.policy_version} "
            f"score={self.retrieval_score}>"
        )
