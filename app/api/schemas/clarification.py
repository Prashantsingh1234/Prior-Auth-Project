"""
Clarification loop request/response schemas.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.api.schemas.common import BaseSchema


class ClarificationRespondRequest(BaseSchema):
    """Body for POST /clarification/{case_id}/respond."""

    model_config = BaseSchema.model_config.copy()
    model_config["extra"] = "forbid"

    clarification_id: str = Field(
        description="UUID of the clarification request being answered",
    )
    response: str = Field(
        min_length=5,
        max_length=10_000,
        description="Provider's response to the clarification question",
    )


class ClarificationResponseBody(BaseSchema):
    """Response for a clarification submission."""

    clarification_id: str
    case_id: str
    case_number: str
    status: str
    answered_at: datetime
    message: str = "Clarification response recorded. Case will be re-evaluated."
