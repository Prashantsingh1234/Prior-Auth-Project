"""
Prometheus metrics for the async task queue system.

All metrics use the prefix ``pa_queue_`` to distinguish them from
application-domain metrics in app/monitoring/metrics.py.

Usage:
    from app.queues.metrics import QUEUE_METRICS
    QUEUE_METRICS.published.labels(queue="ocr", priority="5").inc()
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, Summary

# ---------------------------------------------------------------------------
# Publishing metrics
# ---------------------------------------------------------------------------

PUBLISHED_TOTAL = Counter(
    "pa_queue_published_total",
    "Total messages published to each queue",
    labelnames=["queue", "task_type"],
)

PUBLISH_ERRORS_TOTAL = Counter(
    "pa_queue_publish_errors_total",
    "Total publish failures by queue and error type",
    labelnames=["queue", "error_type"],
)

PUBLISH_LATENCY_SECONDS = Histogram(
    "pa_queue_publish_latency_seconds",
    "Time to publish a confirmed message to RabbitMQ",
    labelnames=["queue"],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
)

# ---------------------------------------------------------------------------
# Consumer / processing metrics
# ---------------------------------------------------------------------------

CONSUMED_TOTAL = Counter(
    "pa_queue_consumed_total",
    "Total messages consumed (before processing outcome)",
    labelnames=["queue", "task_type"],
)

PROCESSING_SUCCESS_TOTAL = Counter(
    "pa_queue_processing_success_total",
    "Messages processed successfully",
    labelnames=["queue", "task_type"],
)

PROCESSING_FAILURE_TOTAL = Counter(
    "pa_queue_processing_failure_total",
    "Messages that failed processing (including retries exhausted)",
    labelnames=["queue", "task_type", "error_type"],
)

PROCESSING_LATENCY_SECONDS = Histogram(
    "pa_queue_processing_latency_seconds",
    "End-to-end task processing time (from dequeue to ack/nack)",
    labelnames=["queue", "task_type"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0],
)

# ---------------------------------------------------------------------------
# Retry metrics
# ---------------------------------------------------------------------------

RETRY_TOTAL = Counter(
    "pa_queue_retry_total",
    "Total messages retried",
    labelnames=["queue", "task_type", "retry_number"],
)

DLQ_TOTAL = Counter(
    "pa_queue_dlq_total",
    "Total messages routed to dead-letter queues (retries exhausted)",
    labelnames=["queue", "task_type"],
)

# ---------------------------------------------------------------------------
# Queue depth gauges (polled by the monitoring exporter loop)
# ---------------------------------------------------------------------------

QUEUE_DEPTH = Gauge(
    "pa_queue_depth",
    "Approximate number of ready messages in each queue",
    labelnames=["queue"],
)

DLQ_DEPTH = Gauge(
    "pa_queue_dlq_depth",
    "Approximate number of messages in each dead-letter queue",
    labelnames=["queue"],
)

CONSUMER_COUNT = Gauge(
    "pa_queue_consumer_count",
    "Number of active consumers on each queue",
    labelnames=["queue"],
)

# ---------------------------------------------------------------------------
# Worker health
# ---------------------------------------------------------------------------

WORKER_ACTIVE = Gauge(
    "pa_queue_workers_active",
    "Number of currently running worker coroutines",
    labelnames=["worker_type"],
)

CONNECTION_RECONNECTS_TOTAL = Counter(
    "pa_queue_connection_reconnects_total",
    "Number of times the RabbitMQ connection was re-established",
)


# ---------------------------------------------------------------------------
# Convenience wrapper
# ---------------------------------------------------------------------------

class QueueMetrics:
    """Attribute-style access to all queue metrics."""

    published            = PUBLISHED_TOTAL
    publish_errors       = PUBLISH_ERRORS_TOTAL
    publish_latency      = PUBLISH_LATENCY_SECONDS
    consumed             = CONSUMED_TOTAL
    processing_success   = PROCESSING_SUCCESS_TOTAL
    processing_failure   = PROCESSING_FAILURE_TOTAL
    processing_latency   = PROCESSING_LATENCY_SECONDS
    retried              = RETRY_TOTAL
    dlq_routed           = DLQ_TOTAL
    queue_depth          = QUEUE_DEPTH
    dlq_depth            = DLQ_DEPTH
    consumer_count       = CONSUMER_COUNT
    workers_active       = WORKER_ACTIVE
    reconnects           = CONNECTION_RECONNECTS_TOTAL


QUEUE_METRICS = QueueMetrics()
