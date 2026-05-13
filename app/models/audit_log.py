"""
AuditLog ORM model.

Immutable, append-only audit trail for HIPAA compliance.
Every state change, AI inference, human action, and system event is logged here.

HIPAA § 164.312(b): "Implement hardware, software, and/or procedural mechanisms
that record and examine activity in information systems that contain or use ePHI."

Design principles:
- Rows are NEVER updated or deleted (append-only)
- Soft delete is intentionally DISABLED for this model
- previous_state and new_state capture full snapshots for forensic analysis
- actor_type distinguishes human users from system/AI actions
- request_id and trace_id link audit entries to HTTP request logs
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import (
    Enum as SAEnum,
    Index,
    JSON,
    String,
    Text,
)
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base.model import Base, UUIDMixin, TimestampMixin
from app.models.enums import ActorType, AuditAction, AuditEntityType


class AuditLog(UUIDMixin, TimestampMixin, Base):
    """
    Immutable HIPAA-compliant audit log entry.

    Does NOT inherit SoftDeleteMixin — audit records must never be deletable.
    Inherits only UUIDMixin and TimestampMixin from the base stack.
    """

    __tablename__ = "audit_logs"

    # ----------------------------------------------------------
    # What was affected
    # ----------------------------------------------------------
    entity_type: Mapped[AuditEntityType] = mapped_column(
        SAEnum(AuditEntityType),
        nullable=False,
        index=True,
        comment="Type of entity this log entry references",
    )
    entity_id: Mapped[str | None] = mapped_column(
        CHAR(36), nullable=True, index=True,
        comment="UUID of the affected entity",
    )

    # ----------------------------------------------------------
    # What happened
    # ----------------------------------------------------------
    action: Mapped[AuditAction] = mapped_column(
        SAEnum(AuditAction),
        nullable=False,
        index=True,
    )
    # Summary description for quick scanning
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # ----------------------------------------------------------
    # Who did it
    # ----------------------------------------------------------
    actor_type: Mapped[ActorType] = mapped_column(
        SAEnum(ActorType),
        nullable=False,
        index=True,
    )
    actor_id: Mapped[str | None] = mapped_column(
        CHAR(36), nullable=True, index=True,
        comment="UUID of user, service account, or AI model",
    )
    actor_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        comment="Display name snapshot at time of action",
    )
    actor_role: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # ----------------------------------------------------------
    # State Snapshots
    # ----------------------------------------------------------
    previous_state: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True,
        comment="Entity state BEFORE the action (for rollback analysis)",
    )
    new_state: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True,
        comment="Entity state AFTER the action",
    )
    # Specific fields that changed (for efficient diff display)
    changed_fields: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    # ----------------------------------------------------------
    # Request Context
    # ----------------------------------------------------------
    request_id: Mapped[str | None] = mapped_column(CHAR(36), nullable=True)
    trace_id: Mapped[str | None] = mapped_column(CHAR(36), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    api_endpoint: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # ----------------------------------------------------------
    # Case Context (denormalized for fast filtering)
    # ----------------------------------------------------------
    # Duplicates the case_id from the affected entity to enable
    # "show all audit events for case X" queries without JOINs
    case_id: Mapped[str | None] = mapped_column(CHAR(36), nullable=True, index=True)

    # ----------------------------------------------------------
    # Extended Metadata
    # ----------------------------------------------------------
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "audit_metadata", JSON, nullable=True
    )

    # ----------------------------------------------------------
    # Indexes
    # ----------------------------------------------------------
    __table_args__ = (
        Index("ix_audit_entity_type", "entity_type"),
        Index("ix_audit_entity_id", "entity_id"),
        Index("ix_audit_action", "action"),
        Index("ix_audit_actor_id", "actor_id"),
        Index("ix_audit_case_id", "case_id"),
        Index("ix_audit_created_at", "created_at"),
        Index("ix_audit_request_id", "request_id"),
        # Composite for "all events for entity X" query
        Index("ix_audit_entity_lookup", "entity_type", "entity_id", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog id={self.id} "
            f"action={self.action} "
            f"entity={self.entity_type}:{self.entity_id}>"
        )
