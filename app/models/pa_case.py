"""
PACase ORM model — the central entity of the platform.

Every prior authorization request is a PACase. All other entities
(documents, evaluations, clarifications, decisions) link back to a PACase.

Status transitions:
  SUBMITTED → PROCESSING → PENDING_CLARIFICATION → UNDER_REVIEW → APPROVED/DENIED/PENDED
                         ↘ UNDER_REVIEW ↗
                         → ESCALATED → APPROVED/DENIED/PENDED
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
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
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base.model import BaseModel
from app.models.enums import CasePriority, CaseStatus, ServiceType

if TYPE_CHECKING:
    from app.models.clarification import Clarification
    from app.models.decision import Decision
    from app.models.document import UploadedDocument
    from app.models.entity import ExtractedEntity
    from app.models.evaluation import Evaluation
    from app.models.patient import Patient
    from app.models.policy_match import PolicyMatch
    from app.models.provider import Provider
    from app.models.reviewer_action import ReviewerAction


class PACase(BaseModel):
    """
    Prior authorization case — the core domain entity.

    Tracks the full lifecycle of a PA request from initial submission
    through AI evaluation, clarification, human review, and final decision.
    clarification_count must never exceed 3 (enforced in the service layer).
    """

    __tablename__ = "pa_cases"

    # ----------------------------------------------------------
    # Case Identity
    # ----------------------------------------------------------
    case_number: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="Human-readable case ID, e.g. PA-20240101-A1B2",
    )

    # ----------------------------------------------------------
    # Foreign Keys
    # ----------------------------------------------------------
    patient_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("patients.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    provider_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("providers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    # UUID of the reviewer assigned from the users table (no FK — avoids circular dep)
    assigned_reviewer_id: Mapped[str | None] = mapped_column(
        CHAR(36), nullable=True, index=True
    )

    # ----------------------------------------------------------
    # Clinical Details
    # ----------------------------------------------------------
    status: Mapped[CaseStatus] = mapped_column(
        SAEnum(CaseStatus),
        nullable=False,
        default=CaseStatus.SUBMITTED,
        index=True,
    )
    priority: Mapped[CasePriority] = mapped_column(
        SAEnum(CasePriority),
        nullable=False,
        default=CasePriority.ROUTINE,
        index=True,
    )
    service_type: Mapped[ServiceType | None] = mapped_column(
        SAEnum(ServiceType), nullable=True
    )

    # Extracted CPT and ICD codes stored as JSON arrays for fast filtering
    cpt_codes: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list,
        comment="List of CPT procedure codes",
    )
    icd_codes: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list,
        comment="List of ICD-10 diagnosis codes",
    )

    requested_service_description: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    clinical_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ----------------------------------------------------------
    # AI Recommendation (set after reasoning node completes)
    # ----------------------------------------------------------
    ai_recommendation: Mapped[str | None] = mapped_column(
        String(10), nullable=True,
        comment="APPROVE | DENY | PEND — AI advisory output only",
    )
    ai_confidence_score: Mapped[float | None] = mapped_column(
        nullable=True,
        comment="Overall AI confidence (0.0–1.0)",
    )
    ai_reasoning_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ----------------------------------------------------------
    # Clarification Tracking
    # ----------------------------------------------------------
    clarification_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="Number of clarification loops completed (max 3)",
    )

    # ----------------------------------------------------------
    # Lifecycle Timestamps
    # ----------------------------------------------------------
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    processing_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    review_assigned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    # ----------------------------------------------------------
    # Extended Metadata
    # ----------------------------------------------------------
    external_reference_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True,
        comment="Reference ID from external system (EHR, fax system, etc.)",
    )
    source_channel: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        comment="Submission channel: api | portal | fax | hl7",
    )
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "case_metadata", JSON, nullable=True,
        comment="Arbitrary additional metadata",
    )

    # ----------------------------------------------------------
    # Relationships
    # ----------------------------------------------------------
    patient: Mapped["Patient"] = relationship(
        "Patient", back_populates="pa_cases", lazy="raise"
    )
    provider: Mapped["Provider"] = relationship(
        "Provider", back_populates="pa_cases", lazy="raise"
    )
    documents: Mapped[list["UploadedDocument"]] = relationship(
        "UploadedDocument", back_populates="case", lazy="raise",
        cascade="all, delete-orphan",
    )
    entities: Mapped[list["ExtractedEntity"]] = relationship(
        "ExtractedEntity", back_populates="case", lazy="raise",
        cascade="all, delete-orphan",
    )
    policy_matches: Mapped[list["PolicyMatch"]] = relationship(
        "PolicyMatch", back_populates="case", lazy="raise",
        cascade="all, delete-orphan",
    )
    evaluations: Mapped[list["Evaluation"]] = relationship(
        "Evaluation", back_populates="case", lazy="raise",
        cascade="all, delete-orphan",
    )
    clarifications: Mapped[list["Clarification"]] = relationship(
        "Clarification", back_populates="case", lazy="raise",
        cascade="all, delete-orphan",
        order_by="Clarification.attempt_number",
    )
    reviewer_actions: Mapped[list["ReviewerAction"]] = relationship(
        "ReviewerAction", back_populates="case", lazy="raise",
        cascade="all, delete-orphan",
    )
    decision: Mapped["Decision | None"] = relationship(
        "Decision", back_populates="case", lazy="raise",
        uselist=False, cascade="all, delete-orphan",
    )

    # ----------------------------------------------------------
    # Indexes & Constraints
    # ----------------------------------------------------------
    __table_args__ = (
        UniqueConstraint("case_number", name="uq_pa_cases_case_number"),
        Index("ix_pa_cases_status", "status"),
        Index("ix_pa_cases_priority", "priority"),
        Index("ix_pa_cases_patient_id", "patient_id"),
        Index("ix_pa_cases_provider_id", "provider_id"),
        Index("ix_pa_cases_reviewer_id", "assigned_reviewer_id"),
        Index("ix_pa_cases_decided_at", "decided_at"),
        Index("ix_pa_cases_submitted_at", "submitted_at"),
        Index("ix_pa_cases_deleted_at", "deleted_at"),
        # Composite index for queue queries (status + priority)
        Index("ix_pa_cases_status_priority", "status", "priority"),
    )

    @property
    def is_decided(self) -> bool:
        return self.status in (CaseStatus.APPROVED, CaseStatus.DENIED, CaseStatus.PENDED)

    @property
    def can_be_clarified(self) -> bool:
        return (
            self.status == CaseStatus.PENDING_CLARIFICATION
            and self.clarification_count < 3
        )

    def __repr__(self) -> str:
        return f"<PACase id={self.id} case_number={self.case_number} status={self.status}>"
