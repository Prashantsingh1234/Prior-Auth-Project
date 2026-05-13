"""
Evaluation ORM model.

Stores criterion-level AI evaluations and human review outcomes.
Each row represents one policy criterion evaluated against patient evidence.

AI evaluation example:
  criterion_name:   "Intensive insulin therapy requirement"
  criterion_status: PASS
  evidence:         "Patient takes insulin 4 times daily per prescription dated 2024-01-10"
  confidence_score: 0.96

The evidence_sources field cites exactly which document/chunk the
evidence came from, enabling full explainability and audit.
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
from app.models.enums import CriterionStatus, EvaluationType

if TYPE_CHECKING:
    from app.models.pa_case import PACase


class Evaluation(BaseModel):
    """
    Single criterion evaluation — the core AI explainability unit.

    Every AI recommendation must be backed by one or more Evaluation
    records explaining WHY a criterion passed or failed.
    Reviewers see these evaluations in their dashboard.
    """

    __tablename__ = "evaluations"

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
    # Evaluation Context
    # ----------------------------------------------------------
    evaluation_type: Mapped[EvaluationType] = mapped_column(
        SAEnum(EvaluationType),
        nullable=False,
        index=True,
    )
    # Name of the policy criterion being evaluated
    criterion_name: Mapped[str] = mapped_column(
        String(500), nullable=False, index=True
    )
    # The full policy criterion text (for audit — policy may change over time)
    criterion_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Which policy version this criterion comes from
    policy_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    policy_version: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # ----------------------------------------------------------
    # Evaluation Result (the explainable AI output)
    # ----------------------------------------------------------
    criterion_status: Mapped[CriterionStatus] = mapped_column(
        SAEnum(CriterionStatus),
        nullable=False,
        index=True,
    )
    # The specific patient evidence supporting this evaluation
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Structured citation list: [{document_id, page, text_snippet, chunk_id}, ...]
    evidence_sources: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list,
        comment="Grounded citations — each source must be a retrieved policy chunk or document",
    )
    # The AI's reasoning chain explaining why evidence → status
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    # AI confidence for this specific criterion (0.0–1.0)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ----------------------------------------------------------
    # LLM Provenance
    # ----------------------------------------------------------
    llm_model_used: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="e.g. gpt-4o, claude-3-5-sonnet"
    )
    llm_prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    llm_completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    llm_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Raw LLM output before parsing (for debugging)
    llm_raw_output: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ----------------------------------------------------------
    # Human Review Overlay
    # ----------------------------------------------------------
    # If a reviewer disagrees with the AI evaluation, they set this
    reviewer_override_status: Mapped[CriterionStatus | None] = mapped_column(
        SAEnum(CriterionStatus), nullable=True
    )
    reviewer_override_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewer_id: Mapped[str | None] = mapped_column(CHAR(36), nullable=True)

    # ----------------------------------------------------------
    # Extended Metadata
    # ----------------------------------------------------------
    evaluation_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )

    # ----------------------------------------------------------
    # Relationship
    # ----------------------------------------------------------
    case: Mapped["PACase"] = relationship(
        "PACase", back_populates="evaluations", lazy="raise"
    )

    # ----------------------------------------------------------
    # Indexes
    # ----------------------------------------------------------
    __table_args__ = (
        Index("ix_evaluations_case_id", "case_id"),
        Index("ix_evaluations_type", "evaluation_type"),
        Index("ix_evaluations_criterion", "criterion_name"),
        Index("ix_evaluations_status", "criterion_status"),
        Index("ix_evaluations_case_type", "case_id", "evaluation_type"),
    )

    def __repr__(self) -> str:
        return (
            f"<Evaluation id={self.id} "
            f"criterion={self.criterion_name!r} "
            f"status={self.criterion_status}>"
        )
