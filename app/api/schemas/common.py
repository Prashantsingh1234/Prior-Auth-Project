"""
Shared Pydantic response schemas.

These base schemas enforce a consistent API envelope across all endpoints:

  Success:  { "success": true,  "data": {...},  "meta": {...} }
  Error:    { "success": false, "error": {...} }

Using a consistent envelope means clients always know where to find data
and front-end error handling code is uniform.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class BaseSchema(BaseModel):
    """Base schema with strict mode and ORM compatibility."""

    model_config = ConfigDict(
        # Populate from ORM model attributes (SQLAlchemy)
        from_attributes=True,
        # Reject extra fields to prevent accidental data leakage
        extra="forbid",
        # Use enum values in JSON, not enum names
        use_enum_values=True,
        # Serialize datetime as ISO 8601 strings
        json_encoders={datetime: lambda dt: dt.isoformat()},
    )


class SuccessResponse(BaseModel, Generic[T]):
    """
    Standard success response envelope.

    Usage:
        return SuccessResponse(data=MySchema(...), meta={"count": 1})
    """

    success: bool = Field(default=True)
    data: T
    meta: dict[str, Any] = Field(default_factory=dict)


class ErrorDetail(BaseModel):
    """Structured error information."""
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = None


class ErrorResponse(BaseModel):
    """Standard error response envelope."""
    success: bool = Field(default=False)
    error: ErrorDetail


class PaginationMeta(BaseModel):
    """Pagination metadata included in list responses."""
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total_items: int = Field(ge=0)
    total_pages: int = Field(ge=0)
    has_next: bool
    has_previous: bool

    @classmethod
    def build(cls, page: int, page_size: int, total_items: int) -> "PaginationMeta":
        total_pages = (total_items + page_size - 1) // page_size if total_items > 0 else 0
        return cls(
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1,
        )


class UUIDSchema(BaseSchema):
    """Schema for resources identified by UUID."""
    id: UUID


class TimestampedSchema(UUIDSchema):
    """Schema for resources with audit timestamps."""
    created_at: datetime
    updated_at: datetime


# ----------------------------------------------------------
# Health Check Schemas
# ----------------------------------------------------------

class ServiceHealthStatus(BaseModel):
    """Health status for a single downstream dependency."""
    status: str = Field(description="healthy | degraded | unhealthy")
    latency_ms: float | None = Field(default=None, description="Round-trip latency in ms")
    message: str | None = Field(default=None, description="Additional context")


class HealthResponse(BaseModel):
    """
    Comprehensive health check response.
    Shows overall application health and per-service status.
    """
    status: str = Field(description="healthy | degraded | unhealthy")
    version: str
    environment: str
    uptime_seconds: float
    services: dict[str, ServiceHealthStatus]
    timestamp: str = Field(description="ISO 8601 UTC timestamp")
