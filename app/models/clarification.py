"""
Clarification ORM model.

Tracks the closed-loop clarification process when the AI detects
insufficient evidence to evaluate a criterion.

The system supports a maximum of 3 clarification attempts per case.
After 3 failed attempts, the case is automatically escalated.

Loop lifecycle:
  AI identifies missing criteria
  → generates questions
  → case status → PENDING_CLARIFICATION
  → provider submits answers
  → status → PROCESSING (re-evaluation)
  → repeat up to 3 times
  → after 3rd failure → ESCALATED
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
    Text,
)
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base.model import BaseModel
from app.models.enums import ClarificationStatus

if TYPE_CHECKING:
    from app.models.pa_case import PACase


class Clarification(BaseModel):
    """
    A single clarification request-response cycle for a PA case.

    attempt_number tracks which loop this is (1, 2, or 3).
    The missing_criteria field lists the criterion names that need more evidence.
    The questions field contains the AI-generated questions sent to the provider.
    The answers field is populated when the provider responds.
    """

    __tablename__ = "clarifications"

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
    # Loop Tracking
    # ----------------------------------------------------------
    attempt_number: Mapped[int] = mapped_column(
        Integer, nullable=False,
        comment="Which clarification attempt this is (1–3)",
    )
    status: Mapped[ClarificationStatus] = mapped_column(
        SAEnum(ClarificationStatus),
        nullable=False,
        default=ClarificationStatus.PENDING,
        index=True,
    )

    # ----------------------------------------------------------
    # Content
    # ----------------------------------------------------------
    # Criteria that have insufficient evidence — triggers this clarification
    missing_criteria: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list,
        comment="List of criterion names needing more evidence",
    )
    # AI-generated questions to send to the provider
    questions: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list,
        comment="List of {question, criterion, required} dicts",
    )
    # Provider's responses (populated when answered)
    answers: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON, nullable=True,
        comment="List of {question, answer, submitted_by} dicts",
    )
    # Context passed to the AI to generate questions
    clarification_context: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )
    # Summary of what was resolved after this clarification
    resolution_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ----------------------------------------------------------
    # Timestamps
    # ----------------------------------------------------------
    requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    answered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # SLA deadline for provider response
    response_deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    # ----------------------------------------------------------
    # Notification Tracking
    # ----------------------------------------------------------
    notification_sent: Mapped[bool] = mapped_column(nullable=False, default=False)
    notification_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_notification_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ----------------------------------------------------------
    # Relationship
    # ----------------------------------------------------------
    case: Mapped["PACase"] = relationship(
        "PACase", back_populates="clarifications", lazy="raise"
    )

    # ----------------------------------------------------------
    # Indexes
    # ----------------------------------------------------------
    __table_args__ = (
        Index("ix_clarifications_case_id", "case_id"),
        Index("ix_clarifications_status", "status"),
        Index("ix_clarifications_deadline", "response_deadline"),
        Index("ix_clarifications_case_attempt", "case_id", "attempt_number"),
    )

    @property
    def is_overdue(self) -> bool:
        """True if the response deadline has passed without an answer."""
        from datetime import UTC
        from datetime import datetime as dt
        if self.response_deadline is None or self.status != ClarificationStatus.PENDING:
            return False
        return dt.now(UTC) > self.response_deadline

    def __repr__(self) -> str:
        return (
            f"<Clarification id={self.id} "
            f"case_id={self.case_id} "
            f"attempt={self.attempt_number} "
            f"status={self.status}>"
        )
