"""
Review action request/response schemas.

All review actions follow the same response pattern:
- Return updated case summary + confirmation message
"""

from __future__ import annotations

from pydantic import Field, field_validator

from app.api.schemas.common import BaseSchema


class ApproveRequest(BaseSchema):
    """Body for POST /review/{case_id}/approve."""

    model_config = BaseSchema.model_config.copy()
    model_config["extra"] = "forbid"

    rationale: str = Field(
        default="",
        max_length=5000,
        description="Clinical rationale for approval",
    )
    override_reason: str | None = Field(
        default=None,
        max_length=2000,
        description="Reason for overriding AI recommendation (required if AI recommended DENY)",
    )


class DenyRequest(BaseSchema):
    """Body for POST /review/{case_id}/deny."""

    model_config = BaseSchema.model_config.copy()
    model_config["extra"] = "forbid"

    rationale: str = Field(
        min_length=10,
        max_length=5000,
        description="Clinical rationale for denial (included in member letter)",
    )
    override_reason: str | None = Field(
        default=None,
        max_length=2000,
        description="Reason for overriding AI recommendation (required if AI recommended APPROVE)",
    )
    denial_reason_code: str | None = Field(
        default=None,
        max_length=20,
        description="Standard denial reason code (e.g. N-MED-001)",
    )


class PendRequest(BaseSchema):
    """Body for POST /review/{case_id}/pend."""

    model_config = BaseSchema.model_config.copy()
    model_config["extra"] = "forbid"

    rationale: str = Field(
        min_length=10,
        max_length=5000,
        description="Reason for pending (what additional information is needed)",
    )
    pending_reason: str = Field(
        min_length=5,
        max_length=1000,
        description="Short summary of the pending reason (used in provider notification)",
    )


class EscalateRequest(BaseSchema):
    """Body for POST /review/{case_id}/escalate."""

    model_config = BaseSchema.model_config.copy()
    model_config["extra"] = "forbid"

    reason: str = Field(
        min_length=10,
        max_length=3000,
        description="Reason for escalation to senior reviewer",
    )
    escalate_to: str | None = Field(
        default=None,
        max_length=36,
        description="Optional UUID of the target reviewer; system assigns if omitted",
    )


class AddNoteRequest(BaseSchema):
    """Body for POST /review/{case_id}/notes."""

    model_config = BaseSchema.model_config.copy()
    model_config["extra"] = "forbid"

    note: str = Field(
        min_length=1,
        max_length=10_000,
        description="Free-text note added to the case audit trail",
    )


class AssignRequest(BaseSchema):
    """Body for POST /review/{case_id}/assign."""

    model_config = BaseSchema.model_config.copy()
    model_config["extra"] = "forbid"

    reviewer_id: str = Field(
        description="UUID of the reviewer to assign",
    )


class ReviewActionResponse(BaseSchema):
    """Standard response for all review action endpoints."""

    case_id: str
    case_number: str
    new_status: str
    action_type: str
    message: str
    decided_at: str | None = None
