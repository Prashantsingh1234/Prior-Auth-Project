"""
Guardrail audit logging.

Every guardrail check and escalation emits a structured audit record via
structlog (always) and the async AuditWriter (when available).

Audit records are HIPAA-compliant:
  - PHI is never logged in plain text (sanitized before audit emission)
  - All records include: timestamp, case_id, node, violation types, severity
  - Escalation records include: target, auto_blocked, resolution status
  - Records are append-only (immutable after creation)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog

from app.guardrails.models import EscalationEvent, GuardrailResult, GuardrailViolation

logger = structlog.get_logger(__name__)


async def emit_check_audit(
    result: GuardrailResult,
    user_id: str | None = None,
    model_id: str | None = None,
) -> None:
    """
    Emit an audit record for a completed guardrail check.

    Always emits to structlog.  Also writes to the AuditWriter if available.
    """
    log_data: dict[str, Any] = {
        "event":          "guardrail.check",
        "result_id":      result.result_id,
        "case_id":        result.case_id,
        "node_name":      result.node_name,
        "stage":          result.stage.value,
        "passed":         result.passed,
        "blocked":        result.blocked,
        "escalated":      result.escalated,
        "processing_ms":  result.processing_ms,
        "violation_count": len(result.violations),
        "violation_types": [v.violation_type.value for v in result.violations],
        "max_severity":   result.max_severity.value if result.max_severity else None,
        "user_id":        user_id,
        "model_id":       model_id,
        "timestamp":      datetime.now(timezone.utc).isoformat(),
    }

    if result.violations:
        logger.warning("guardrail.check_audit", **log_data)
    else:
        logger.debug("guardrail.check_audit", **log_data)

    await _write_to_audit_db(
        event_type="GUARDRAIL_CHECK",
        actor_id=user_id,
        case_id=result.case_id,
        event_data={
            "result_id":       result.result_id,
            "stage":           result.stage.value,
            "blocked":         result.blocked,
            "violation_types": [v.violation_type.value for v in result.violations],
            "violation_count": len(result.violations),
            "model_id":        model_id,
        },
        severity="HIGH" if result.blocked else ("MEDIUM" if result.violations else "LOW"),
    )


async def emit_escalation_audit(event: EscalationEvent) -> None:
    """Emit an audit record for a guardrail escalation event."""
    log_data: dict[str, Any] = {
        "event":           "guardrail.escalation",
        "escalation_id":   event.escalation_id,
        "case_id":         event.case_id,
        "escalated_to":    event.escalated_to,
        "auto_blocked":    event.auto_blocked,
        "violation_types": [v.violation_type.value for v in event.violations],
        "violation_count": len(event.violations),
        "reason":          event.reason,
        "timestamp":       event.created_at.isoformat(),
    }

    logger.warning("guardrail.escalation_audit", **log_data)

    await _write_to_audit_db(
        event_type="GUARDRAIL_ESCALATION",
        actor_id=None,
        case_id=event.case_id,
        event_data={
            "escalation_id":   event.escalation_id,
            "escalated_to":    event.escalated_to,
            "auto_blocked":    event.auto_blocked,
            "violation_types": [v.violation_type.value for v in event.violations],
        },
        severity="CRITICAL" if event.auto_blocked else "HIGH",
    )


async def emit_resolution_audit(
    escalation_id: str,
    resolved_by: str,
    notes: str,
    case_id: str | None = None,
) -> None:
    """Emit an audit record when a guardrail escalation is resolved."""
    logger.info(
        "guardrail.resolution_audit",
        escalation_id=escalation_id,
        resolved_by=resolved_by,
        case_id=case_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    await _write_to_audit_db(
        event_type="GUARDRAIL_ESCALATION_RESOLVED",
        actor_id=resolved_by,
        case_id=case_id,
        event_data={
            "escalation_id": escalation_id,
            "notes":         notes[:500],
        },
        severity="LOW",
    )


async def emit_pii_detection_audit(
    entity_type: str,
    entity_count: int,
    stage: str,
    case_id: str | None = None,
    node_name: str | None = None,
) -> None:
    """Emit HIPAA-compliant audit for PHI detection (no raw PHI values)."""
    logger.warning(
        "guardrail.pii_detection_audit",
        entity_type=entity_type,
        entity_count=entity_count,
        stage=stage,
        case_id=case_id,
        node_name=node_name,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    await _write_to_audit_db(
        event_type="PHI_DETECTED",
        actor_id=None,
        case_id=case_id,
        event_data={
            "entity_type":  entity_type,
            "entity_count": entity_count,
            "stage":        stage,
            "node_name":    node_name,
        },
        severity="HIGH",
    )


# ---------------------------------------------------------------------------
# DB writer helper
# ---------------------------------------------------------------------------

async def _write_to_audit_db(
    event_type: str,
    actor_id: str | None,
    case_id: str | None,
    event_data: dict[str, Any],
    severity: str = "MEDIUM",
) -> None:
    """Write guardrail audit record to the AuditWriter queue (non-blocking)."""
    try:
        from app.audit.writer import get_audit_writer
        from app.audit.events import make_system_event

        writer = get_audit_writer()
        record = make_system_event(
            event_type=event_type,
            actor_id=actor_id,
            case_id=case_id,
            event_data=event_data,
            audit_category="guardrail",
            audit_severity=severity,
        )
        await writer.emit(record)
    except Exception as exc:
        logger.debug("guardrail.audit_db_write_failed", error=str(exc))
