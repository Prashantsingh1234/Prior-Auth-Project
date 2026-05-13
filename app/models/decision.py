"""
Decision ORM model.

The final, immutable prior authorization decision for a case.
One case has exactly one Decision record (enforced by unique constraint on case_id).

The decision captures:
- What the AI recommended
- What the final decision is (may differ if reviewer overrode AI)
- Who made the final decision
- Clinical codes and denial reasons (for CMS/HIPAA compliance)
- Effective date and expiration date (for approvals)

CRITICAL: This record is immutable once created. Amendments require
a new PA case to be submitted.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Date,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base.model import BaseModel
from app.models.enums import DecisionOutcome, DecisionSource

if TYPE_CHECKING:
    from app.models.pa_case import PACase


class Decision(BaseModel):
    """
    Final prior authorization decision — one per case.

    Created when a reviewer approves, denies, or pends a case.
    The decision_source distinguishes AI-assisted from reviewer-overridden decisions.
    """

    __tablename__ = "decisions"

    # ----------------------------------------------------------
    # Foreign Key (unique — one decision per case)
    # ----------------------------------------------------------
    case_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("pa_cases.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,   # enforced as UniqueConstraint below as well
        comment="One-to-one with pa_cases",
    )

    # ----------------------------------------------------------
    # Decision Outcome
    # ----------------------------------------------------------
    final_decision: Mapped[DecisionOutcome] = mapped_column(
        SAEnum(DecisionOutcome),
        nullable=False,
        index=True,
        comment="The binding final decision: APPROVE | DENY | PEND",
    )
    decision_source: Mapped[DecisionSource] = mapped_column(
        SAEnum(DecisionSource),
        nullable=False,
        comment="AI_RECOMMENDATION or REVIEWER_OVERRIDE",
    )

    # ----------------------------------------------------------
    # AI Recommendation (preserved for analytics)
    # ----------------------------------------------------------
    ai_recommendation: Mapped[DecisionOutcome | None] = mapped_column(
        SAEnum(DecisionOutcome), nullable=True
    )
    ai_confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_reasoning_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ----------------------------------------------------------
    # Reviewer (who made the final call)
    # ----------------------------------------------------------
    reviewer_id: Mapped[str | None] = mapped_column(CHAR(36), nullable=True)
    reviewer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    # ----------------------------------------------------------
    # Denial Details (required if final_decision == DENY)
    # ----------------------------------------------------------
    denial_reason_code: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        comment="Standardized denial reason code (NCQA / CMS standard)",
    )
    denial_reason_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    denial_letter_text: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Full denial letter text for member communication",
    )

    # ----------------------------------------------------------
    # Approval Details (required if final_decision == APPROVE)
    # ----------------------------------------------------------
    approval_conditions: Mapped[list[str] | None] = mapped_column(
        JSON, nullable=True,
        comment="Conditions or limitations attached to the approval",
    )
    approved_service_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_units: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="Approved quantity or units"
    )
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiration_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    # Calendar days after denial for member to file an appeal
    appeal_deadline_days: Mapped[int | None] = mapped_column(nullable=True, default=60)

    # ----------------------------------------------------------
    # Compliance & Regulatory
    # ----------------------------------------------------------
    # CMS-required turnaround time compliance tracking
    turnaround_time_hours: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Hours from submission to decision (regulatory SLA tracking)",
    )
    is_expedited: Mapped[bool] = mapped_column(
        nullable=False, default=False,
        comment="True for emergent/urgent cases requiring expedited review",
    )
    regulatory_deadline_met: Mapped[bool | None] = mapped_column(nullable=True)

    # ----------------------------------------------------------
    # Extended Metadata
    # ----------------------------------------------------------
    decision_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # ----------------------------------------------------------
    # Relationship
    # ----------------------------------------------------------
    case: Mapped["PACase"] = relationship(
        "PACase", back_populates="decision", lazy="raise"
    )

    # ----------------------------------------------------------
    # Indexes & Constraints
    # ----------------------------------------------------------
    __table_args__ = (
        UniqueConstraint("case_id", name="uq_decisions_case_id"),
        Index("ix_decisions_final_decision", "final_decision"),
        Index("ix_decisions_source", "decision_source"),
        Index("ix_decisions_decided_at", "decided_at"),
        Index("ix_decisions_expiration", "expiration_date"),
        Index("ix_decisions_reviewer_id", "reviewer_id"),
    )

    @property
    def is_override(self) -> bool:
        return self.decision_source == DecisionSource.REVIEWER_OVERRIDE

    @property
    def ai_agreed(self) -> bool | None:
        """Whether the AI recommendation matched the final decision."""
        if self.ai_recommendation is None:
            return None
        return self.ai_recommendation == self.final_decision

    def __repr__(self) -> str:
        return (
            f"<Decision id={self.id} "
            f"case_id={self.case_id} "
            f"decision={self.final_decision} "
            f"source={self.decision_source}>"
        )
