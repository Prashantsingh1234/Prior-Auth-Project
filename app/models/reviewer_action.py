"""
ReviewerAction ORM model.

Immutable audit trail of every action taken by a human reviewer on a case.
Records are never updated — each action appends a new row.

This gives a complete timeline:
  09:00 - reviewer_A ASSIGNED to case
  09:15 - reviewer_A VIEWED case
  09:45 - reviewer_A REQUESTED_CLARIFICATION
  10:30 - reviewer_A VIEWED case (after clarification answered)
  11:00 - reviewer_A OVERRIDE_APPROVED (AI said DENY, reviewer approved)

The override_reason is mandatory when reviewer_decision differs from
ai_recommendation — enforced at the service layer.
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
from app.models.enums import DecisionOutcome, ReviewerActionType

if TYPE_CHECKING:
    from app.models.pa_case import PACase


class ReviewerAction(BaseModel):
    """
    Immutable record of a single reviewer action on a PA case.

    Every action — view, approve, deny, override, escalate — creates a new row.
    This design makes the complete review history fully auditable.
    """

    __tablename__ = "reviewer_actions"

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
    # Actor
    # ----------------------------------------------------------
    # UUID from the users table — no FK to avoid circular dependency
    reviewer_id: Mapped[str] = mapped_column(
        CHAR(36), nullable=False, index=True,
        comment="UUID of the reviewer who performed this action",
    )
    reviewer_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        comment="Snapshot of reviewer display name at time of action",
    )
    reviewer_role: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        comment="reviewer | admin | senior_reviewer",
    )

    # ----------------------------------------------------------
    # Action
    # ----------------------------------------------------------
    action_type: Mapped[ReviewerActionType] = mapped_column(
        SAEnum(ReviewerActionType),
        nullable=False,
        index=True,
    )
    previous_case_status: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    new_case_status: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )

    # ----------------------------------------------------------
    # Decision Detail (for APPROVED / DENIED / OVERRIDE_* actions)
    # ----------------------------------------------------------
    ai_recommendation: Mapped[DecisionOutcome | None] = mapped_column(
        SAEnum(DecisionOutcome), nullable=True,
        comment="What the AI recommended before this action",
    )
    reviewer_decision: Mapped[DecisionOutcome | None] = mapped_column(
        SAEnum(DecisionOutcome), nullable=True,
        comment="What the reviewer decided",
    )
    # Mandatory if reviewer_decision != ai_recommendation
    override_reason: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Clinical justification for overriding AI recommendation",
    )
    override_reason_code: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        comment="Coded override reason for analytics: CLINICAL_JUDGMENT | POLICY_EXCEPTION | ...",
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ----------------------------------------------------------
    # Performance Metrics
    # ----------------------------------------------------------
    # Time from case assignment to this action (seconds)
    time_to_action_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # AI confidence when the reviewer received this case
    ai_confidence_at_review: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ----------------------------------------------------------
    # Request Context (for security audit)
    # ----------------------------------------------------------
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    request_id: Mapped[str | None] = mapped_column(CHAR(36), nullable=True)

    # ----------------------------------------------------------
    # Extended Metadata
    # ----------------------------------------------------------
    action_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # ----------------------------------------------------------
    # Relationship
    # ----------------------------------------------------------
    case: Mapped["PACase"] = relationship(
        "PACase", back_populates="reviewer_actions", lazy="raise"
    )

    # ----------------------------------------------------------
    # Indexes
    # ----------------------------------------------------------
    __table_args__ = (
        Index("ix_reviewer_actions_case_id", "case_id"),
        Index("ix_reviewer_actions_reviewer_id", "reviewer_id"),
        Index("ix_reviewer_actions_action_type", "action_type"),
        Index("ix_reviewer_actions_created_at", "created_at"),
        # Analytics query: all overrides by reviewer
        Index("ix_reviewer_actions_reviewer_action", "reviewer_id", "action_type"),
    )

    @property
    def is_override(self) -> bool:
        """True if this action represents a reviewer overriding the AI."""
        return self.action_type in (
            ReviewerActionType.OVERRIDE_APPROVED,
            ReviewerActionType.OVERRIDE_DENIED,
        )

    def __repr__(self) -> str:
        return (
            f"<ReviewerAction id={self.id} "
            f"action={self.action_type} "
            f"reviewer={self.reviewer_id}>"
        )
