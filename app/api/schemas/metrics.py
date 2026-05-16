"""
Business metrics response schemas.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.api.schemas.common import BaseSchema


class QueueMetricsSchema(BaseSchema):
    total_active: int
    under_review: int
    pending_clarification: int
    submitted_unprocessed: int
    escalated: int


class DecisionRateSchema(BaseSchema):
    approved: int
    denied: int
    pended: int
    total_decided: int
    approval_rate: float = Field(description="0.0–1.0")
    denial_rate: float   = Field(description="0.0–1.0")
    pend_rate: float     = Field(description="0.0–1.0")


class AIPerformanceSchema(BaseSchema):
    average_confidence: float | None
    high_confidence_count: int   = Field(description="Confidence >= 0.85")
    medium_confidence_count: int = Field(description="0.65 <= confidence < 0.85")
    low_confidence_count: int    = Field(description="Confidence < 0.65")
    ai_override_count: int       = Field(description="Reviewer overrode AI recommendation")


class PriorityBreakdownSchema(BaseSchema):
    routine: int
    urgent: int
    emergent: int


class BusinessMetricsResponse(BaseSchema):
    """
    Aggregated business metrics for the reviewer dashboard and monitoring.
    Updated in near-real-time by querying the operational database.
    """

    generated_at: datetime

    queue: QueueMetricsSchema
    decisions: DecisionRateSchema
    ai_performance: AIPerformanceSchema
    priority_breakdown: PriorityBreakdownSchema

    clarification_rate: float = Field(
        description="Fraction of cases that required at least one clarification (0.0–1.0)"
    )
    average_turnaround_hours: float | None = Field(
        default=None,
        description="Average hours from submission to decision (decided cases only)",
    )

    # Prometheus integration passthrough (raw text endpoint is /metrics)
    prometheus_url: str | None = Field(
        default=None,
        description="URL to the Prometheus metrics endpoint for raw metric scraping",
    )
