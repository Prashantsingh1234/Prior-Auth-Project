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
- Extended columns (audit_category … content_hash) added for structured audit system
"""

from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    Float,
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
    # Structured Audit System — Extended Columns
    # Added to support the compliance-grade AuditRecord fields
    # from app.audit.models.  All nullable so existing rows are
    # unaffected; new inserts populate them via DatabaseAuditStorage.
    # ----------------------------------------------------------

    # Fine-grained category from the audit system (e.g. "ocr", "llm_call")
    audit_category: Mapped[str | None] = mapped_column(
        String(50), nullable=True, index=True,
        comment="AuditCategory value from the structured audit system",
    )
    # Severity level: debug / info / warning / error / critical
    audit_severity: Mapped[str | None] = mapped_column(
        String(20), nullable=True,
        comment="AuditSeverity value",
    )
    # Exact timestamp of the event (may differ from created_at by queue latency)
    occurred_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True,
        comment="Wall-clock time the event occurred, before queue delay",
    )
    # Processing duration in milliseconds
    duration_ms: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="End-to-end duration of the audited operation in ms",
    )
    # Session identifier for cross-request user journey tracing
    session_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True,
        comment="Session ID from auth layer",
    )
    # Domain-specific foreign keys (denormalized for query performance)
    document_id: Mapped[str | None] = mapped_column(
        CHAR(36), nullable=True, index=True,
        comment="UUID of the source document (OCR / extraction events)",
    )
    policy_id: Mapped[str | None] = mapped_column(
        CHAR(36), nullable=True, index=True,
        comment="UUID of the evaluated policy (retrieval / LLM events)",
    )
    attempt_id: Mapped[str | None] = mapped_column(
        CHAR(36), nullable=True,
        comment="UUID of a ClarificationAttempt (clarification events)",
    )
    # Full structured payload — stored as JSON, never logged (may contain PII)
    event_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True,
        comment="Full event payload (PII present — DB only, not in logs)",
    )
    # Error classification fields
    error_type: Mapped[str | None] = mapped_column(
        String(120), nullable=True,
        comment="Exception class name for error events",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Human-readable error message",
    )
    # SHA-256 prefix of error message for grouping without storing full text
    error_hash: Mapped[str | None] = mapped_column(
        String(16), nullable=True,
        comment="First 16 hex chars of SHA-256(error_message) for grouping",
    )
    # Tamper-evidence hash over key immutable fields
    content_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
        comment="SHA-256 of core record fields; used to detect tampering",
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
        # Compliance queries: "all LLM calls in the last 30 days"
        Index("ix_audit_category_occurred", "audit_category", "occurred_at"),
        # Error aggregation: "group errors by hash"
        Index("ix_audit_error_hash", "error_hash"),
        # Document-level trace: "all events for document D"
        Index("ix_audit_document_id", "document_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog id={self.id} "
            f"action={self.action} "
            f"entity={self.entity_type}:{self.entity_id}>"
        )
