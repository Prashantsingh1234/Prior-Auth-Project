"""Prometheus metrics stubs.

Real metrics are only registered when the prometheus_client package is available
and a Prometheus endpoint is configured.  In all other environments these
objects silently no-op so that the rest of the application never raises due
to missing instrumentation.
"""

from __future__ import annotations


class _NoOpLabels:
    """Returned by .labels() — every operation is a no-op."""

    def observe(self, value: float) -> None:  # noqa: ARG002
        pass

    def inc(self, amount: float = 1) -> None:  # noqa: ARG002
        pass

    def set(self, value: float) -> None:  # noqa: ARG002
        pass


class _NoOpMetric:
    """A no-op Prometheus metric that accepts any label set."""

    def labels(self, **_kwargs) -> _NoOpLabels:
        return _NoOpLabels()


def _try_prometheus():
    """Attempt to load real Prometheus metrics; fall back to no-ops on failure."""
    try:
        from prometheus_client import Counter, Histogram, Gauge  # noqa: F401

        ocr_requests_total = Counter(
            "ocr_requests_total",
            "Total OCR requests",
            ["provider", "outcome"],
        )
        ocr_confidence = Histogram(
            "ocr_confidence",
            "OCR confidence score distribution",
            ["provider"],
            buckets=[0.1, 0.2, 0.4, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0],
        )
        ocr_fallback_total = Counter(
            "ocr_fallback_total",
            "Total OCR fallback events",
            ["reason", "from_provider", "to_provider"],
        )
        document_ingestion_total = Counter(
            "document_ingestion_total",
            "Total document ingestion runs",
            ["document_type", "status"],
        )
        document_ingestion_seconds = Histogram(
            "document_ingestion_seconds",
            "Document ingestion latency",
            ["document_type"],
        )
        return (
            ocr_requests_total,
            ocr_confidence,
            ocr_fallback_total,
            document_ingestion_total,
            document_ingestion_seconds,
        )
    except Exception:
        stub = _NoOpMetric()
        return stub, stub, stub, stub, stub


(
    OCR_REQUESTS_TOTAL,
    OCR_CONFIDENCE,
    OCR_FALLBACK_TOTAL,
    DOCUMENT_INGESTION_TOTAL,
    DOCUMENT_INGESTION_SECONDS,
) = _try_prometheus()
