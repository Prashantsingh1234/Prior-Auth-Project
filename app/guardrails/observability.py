"""
Guardrail Prometheus metrics and security observability.

All metrics use the ``guardrail_`` prefix.

Key dashboards:
  - Violation rate by type and severity (track injection/jailbreak trends)
  - Block rate by node (high block rate = either attack or false positive)
  - Escalation queue depth (unresolved security incidents)
  - PII detection frequency (HIPAA compliance signal)
  - Tool execution latency and error rates
"""

from __future__ import annotations

try:
    from prometheus_client import Counter, Histogram, Gauge

    GUARDRAIL_VIOLATIONS_TOTAL = Counter(
        "guardrail_violations_total",
        "Number of guardrail violations detected",
        ["node", "violation_type", "severity"],
    )

    GUARDRAIL_BLOCKS_TOTAL = Counter(
        "guardrail_blocks_total",
        "Number of requests blocked by guardrails",
        ["node"],
    )

    GUARDRAIL_ESCALATIONS_TOTAL = Counter(
        "guardrail_escalations_total",
        "Number of escalation events created",
        ["target", "auto_blocked"],
    )

    GUARDRAIL_RESOLUTIONS_TOTAL = Counter(
        "guardrail_resolutions_total",
        "Number of escalation events resolved",
    )

    GUARDRAIL_PII_DETECTIONS_TOTAL = Counter(
        "guardrail_pii_detections_total",
        "Number of PHI/PII entities detected",
        ["entity_type", "stage"],
    )

    GUARDRAIL_PROCESSING_MS = Histogram(
        "guardrail_processing_ms",
        "Guardrail pipeline processing latency in milliseconds",
        ["node", "stage"],
        buckets=[1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500],
    )

    GUARDRAIL_OPEN_ESCALATIONS = Gauge(
        "guardrail_open_escalations",
        "Number of unresolved escalation events",
        ["target"],
    )

    TOOL_EXECUTIONS_TOTAL = Counter(
        "guardrail_tool_executions_total",
        "Number of secure tool executions",
        ["tool", "success"],
    )

    TOOL_EXECUTION_DURATION_MS = Histogram(
        "guardrail_tool_execution_ms",
        "Tool execution latency in milliseconds",
        ["tool"],
        buckets=[10, 50, 100, 250, 500, 1000, 2500, 5000, 10000],
    )

    SCHEMA_VIOLATIONS_TOTAL = Counter(
        "guardrail_schema_violations_total",
        "Number of schema validation violations",
        ["node", "severity"],
    )

    INJECTION_ATTEMPTS_TOTAL = Counter(
        "guardrail_injection_attempts_total",
        "Number of prompt injection / jailbreak attempts detected",
        ["type", "severity"],
    )

    _METRICS_AVAILABLE = True

except ImportError:

    class _NoOp:
        def labels(self, **kwargs):
            return self
        def inc(self, *args):
            pass
        def observe(self, *args):
            pass
        def set(self, *args):
            pass

    _noop = _NoOp()

    GUARDRAIL_VIOLATIONS_TOTAL   = _noop
    GUARDRAIL_BLOCKS_TOTAL       = _noop
    GUARDRAIL_ESCALATIONS_TOTAL  = _noop
    GUARDRAIL_RESOLUTIONS_TOTAL  = _noop
    GUARDRAIL_PII_DETECTIONS_TOTAL = _noop
    GUARDRAIL_PROCESSING_MS      = _noop
    GUARDRAIL_OPEN_ESCALATIONS   = _noop
    TOOL_EXECUTIONS_TOTAL        = _noop
    TOOL_EXECUTION_DURATION_MS   = _noop
    SCHEMA_VIOLATIONS_TOTAL      = _noop
    INJECTION_ATTEMPTS_TOTAL     = _noop

    _METRICS_AVAILABLE = False
