"""
app.monitoring — Prometheus metrics and observability.

Public API
----------
Metrics:
  METRICS                     PAMetrics singleton (attribute-style access)
  setup_metrics(app)          Register instrumentator and expose /metrics

Middleware:
  RequestMetricsMiddleware    Business-context HTTP metrics middleware

Exporters:
  record_decision(rec)        Track AI recommendation; refresh rate gauges
  record_clarification_event  Track clarification frequency
  record_queue_depth(q, n)    Set queue backlog gauge
  record_system_error()       Increment active system error gauge
  clear_system_error()        Decrement active system error gauge
  run_metric_collection_loop  Background async task for derived gauges
"""

from app.monitoring.metrics import METRICS, setup_metrics
from app.monitoring.middleware import RequestMetricsMiddleware
from app.monitoring.exporters import (
    clear_system_error,
    record_clarification_event,
    record_decision,
    record_queue_depth,
    record_system_error,
    run_metric_collection_loop,
)

__all__ = [
    # Metrics
    "METRICS",
    "setup_metrics",
    # Middleware
    "RequestMetricsMiddleware",
    # Exporters
    "record_decision",
    "record_clarification_event",
    "record_queue_depth",
    "record_system_error",
    "clear_system_error",
    "run_metric_collection_loop",
]
