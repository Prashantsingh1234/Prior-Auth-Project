"""
Metric ORM model.

Persists business KPI snapshots to the database for historical reporting
and analytics dashboards. This complements Prometheus (which is ephemeral)
with durable, queryable business metrics.

Examples:
- Daily approval rate per reviewer
- Weekly case volume by service type
- Average time-to-decision by priority
- Clarification rate by provider
- AI override rate trend

These metrics are computed by background jobs and stored here
for multi-week trend analysis that Prometheus's retention window
(15 days by default) doesn't support.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    Float,
    Index,
    JSON,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base.model import Base, UUIDMixin, TimestampMixin
from app.models.enums import MetricType


class Metric(UUIDMixin, TimestampMixin, Base):
    """
    Business KPI snapshot — append-only, time-series style.

    Each row is a single metric observation at a point in time.
    Labels support multi-dimensional slicing (e.g., by reviewer, service type).
    """

    __tablename__ = "metrics"

    # ----------------------------------------------------------
    # Metric Identity
    # ----------------------------------------------------------
    metric_name: Mapped[str] = mapped_column(
        String(200), nullable=False, index=True,
        comment="e.g. pa.approval_rate, pa.avg_review_time_seconds",
    )
    metric_type: Mapped[MetricType] = mapped_column(
        SAEnum(MetricType), nullable=False
    )

    # ----------------------------------------------------------
    # Dimensions / Labels
    # ----------------------------------------------------------
    # Key-value dimension labels for slicing: {"reviewer_id": "uuid", "priority": "URGENT"}
    labels: Mapped[dict[str, str] | None] = mapped_column(
        JSON, nullable=True,
        comment="Dimension labels for multi-dimensional slicing",
    )

    # ----------------------------------------------------------
    # Value
    # ----------------------------------------------------------
    value: Mapped[float] = mapped_column(
        Float, nullable=False, comment="The metric value"
    )
    unit: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="e.g. percent, seconds, count"
    )

    # ----------------------------------------------------------
    # Time Window
    # ----------------------------------------------------------
    # The time this metric observation represents (may differ from created_at)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True,
        comment="The time period this metric represents",
    )
    # For aggregated metrics: the window they cover
    window_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    window_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Granularity: hourly | daily | weekly | monthly
    granularity: Mapped[str | None] = mapped_column(
        String(20), nullable=True, index=True
    )

    # ----------------------------------------------------------
    # Extended Metadata
    # ----------------------------------------------------------
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metric_metadata", JSON, nullable=True
    )

    # ----------------------------------------------------------
    # Indexes
    # ----------------------------------------------------------
    __table_args__ = (
        Index("ix_metrics_name", "metric_name"),
        Index("ix_metrics_recorded_at", "recorded_at"),
        Index("ix_metrics_granularity", "granularity"),
        Index("ix_metrics_name_time", "metric_name", "recorded_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<Metric id={self.id} "
            f"name={self.metric_name} "
            f"value={self.value} "
            f"at={self.recorded_at}>"
        )
