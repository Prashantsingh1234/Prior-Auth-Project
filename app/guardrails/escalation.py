"""
Violation escalation workflows.

EscalationEngine handles the lifecycle of security incidents:
  1. Evaluate violations against escalation policy
  2. Create an EscalationEvent record
  3. Notify the appropriate escalation target (reviewer / admin / security)
  4. Store in-memory (with optional DB persistence hook)
  5. Provide resolution interface

Escalation targets:
  reviewer      — PA human reviewer queue (standard MEDIUM violations)
  admin         — Platform admin (HIGH violations, policy bypass attempts)
  security_team — CRITICAL violations (injection, jailbreak, data exfiltration)

The engine is evaluator-aware: repeated violations from a specific model
trigger automatic model downgrade via the EvaluationService.
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import structlog

from app.guardrails.models import (
    EscalationEvent,
    GuardrailResult,
    GuardrailViolation,
    ViolationSeverity,
    ViolationType,
)

logger = structlog.get_logger(__name__)


@dataclass
class EscalationRecord:
    """In-memory escalation record (persisted via audit hooks)."""
    event:        EscalationEvent
    resolved:     bool = False
    resolved_by:  str | None = None
    resolved_at:  datetime | None = None
    notes:        str = ""


class EscalationEngine:
    """
    Central violation escalation coordinator.

    Thread-safe: uses asyncio.Lock for the shared registry.
    One instance per application (use get_escalation_engine()).
    """

    def __init__(self) -> None:
        self._lock            = asyncio.Lock()
        self._records: dict[str, EscalationRecord] = {}
        # Per-case violation counts (for combined escalation triggering)
        self._case_violation_counts: dict[str, int] = defaultdict(int)
        # Per-model violation counts (for evaluator-aware downgrade)
        self._model_violation_counts: dict[str, int] = defaultdict(int)
        self._log = structlog.get_logger(__name__)

    # ------------------------------------------------------------------
    # Escalation creation
    # ------------------------------------------------------------------

    async def process_result(
        self,
        result: GuardrailResult,
        model_id: str | None = None,
        user_id: str | None = None,
    ) -> EscalationEvent | None:
        """
        Process a GuardrailResult and create an escalation if warranted.

        Returns the EscalationEvent if one was created, else None.
        """
        if not result.violations and not result.blocked:
            return None

        target   = _determine_target(result.violations)
        reason   = _build_reason(result)
        auto_blocked = result.blocked

        event = EscalationEvent(
            case_id=result.case_id,
            violations=result.violations,
            escalated_to=target,
            reason=reason,
            auto_blocked=auto_blocked,
        )

        async with self._lock:
            self._records[event.escalation_id] = EscalationRecord(event=event)

            if result.case_id:
                self._case_violation_counts[result.case_id] += len(result.violations)

            if model_id:
                self._model_violation_counts[model_id] += len(result.violations)

        # Emit notifications (non-blocking; failures are logged not raised)
        asyncio.ensure_future(
            self._notify(event, user_id=user_id, model_id=model_id)
        )

        # Evaluator-aware: if model accumulates too many violations, request downgrade
        if model_id and self._model_violation_counts.get(model_id, 0) >= 5:
            asyncio.ensure_future(self._request_model_downgrade(model_id))

        self._log.warning(
            "guardrail.escalated",
            escalation_id=event.escalation_id,
            target=target,
            case_id=result.case_id,
            violation_count=len(result.violations),
            auto_blocked=auto_blocked,
        )

        return event

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    async def resolve(
        self,
        escalation_id: str,
        resolved_by: str,
        notes: str = "",
    ) -> bool:
        """Mark an escalation as resolved.  Returns True if found."""
        async with self._lock:
            record = self._records.get(escalation_id)
            if record is None:
                return False
            record.resolved    = True
            record.resolved_by = resolved_by
            record.resolved_at = datetime.now(timezone.utc)
            record.notes       = notes
            record.event.resolved    = True
            record.event.resolved_by = resolved_by
            record.event.resolved_at = record.resolved_at

        self._log.info(
            "guardrail.escalation_resolved",
            escalation_id=escalation_id,
            resolved_by=resolved_by,
        )
        _emit_prometheus_resolution()
        return True

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    async def get_open_escalations(
        self,
        case_id: str | None = None,
        target: str | None = None,
    ) -> list[EscalationEvent]:
        """Return all unresolved escalation events, optionally filtered."""
        async with self._lock:
            records = [
                r for r in self._records.values()
                if not r.resolved
                and (case_id is None or r.event.case_id == case_id)
                and (target is None or r.event.escalated_to == target)
            ]
        return [r.event for r in records]

    async def get_case_violation_count(self, case_id: str) -> int:
        async with self._lock:
            return self._case_violation_counts.get(case_id, 0)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _notify(
        self,
        event: EscalationEvent,
        user_id: str | None,
        model_id: str | None,
    ) -> None:
        """Send escalation notification to the appropriate target."""
        try:
            _log_escalation_notification(event, user_id=user_id, model_id=model_id)
            _emit_prometheus_escalation(event)
            await _emit_audit_event(event)
        except Exception as exc:
            self._log.error("guardrail.escalation_notify_failed", error=str(exc))

    async def _request_model_downgrade(self, model_id: str) -> None:
        """Request evaluator-driven model downgrade for a high-violation model."""
        try:
            from app.evaluation.routing.router import get_router
            router = get_router()
            if hasattr(router, "flag_model_for_review"):
                await router.flag_model_for_review(
                    model_id=model_id,
                    reason="Repeated guardrail violations",
                )
                self._log.warning(
                    "guardrail.model_flagged_for_review",
                    model_id=model_id,
                    violation_count=self._model_violation_counts[model_id],
                )
        except Exception as exc:
            self._log.debug("guardrail.model_downgrade_skip", error=str(exc))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _determine_target(violations: list[GuardrailViolation]) -> str:
    """Route to the right escalation team based on violation severity."""
    if not violations:
        return "reviewer"

    max_sev = max(v.severity for v in violations, key=lambda s: s.numeric)
    types   = {v.violation_type for v in violations}

    # Security-team triggers
    if max_sev >= ViolationSeverity.CRITICAL:
        return "security_team"
    if ViolationType.PROMPT_INJECTION in types or ViolationType.JAILBREAK in types:
        return "security_team"
    if ViolationType.RETRIEVAL_POISONING in types:
        return "security_team"

    # Admin triggers
    if max_sev >= ViolationSeverity.HIGH:
        return "admin"
    if ViolationType.PII_LEAKAGE in types:
        return "admin"

    return "reviewer"


def _build_reason(result: GuardrailResult) -> str:
    types = ", ".join(v.violation_type.value for v in result.violations[:3])
    suffix = f" (+{len(result.violations)-3} more)" if len(result.violations) > 3 else ""
    blocked_note = " [AUTO-BLOCKED]" if result.blocked else ""
    return f"Guardrail violations: {types}{suffix}{blocked_note}"


def _log_escalation_notification(
    event: EscalationEvent,
    user_id: str | None,
    model_id: str | None,
) -> None:
    logger.warning(
        "guardrail.escalation_notification",
        escalation_id=event.escalation_id,
        escalated_to=event.escalated_to,
        case_id=event.case_id,
        auto_blocked=event.auto_blocked,
        violation_types=[v.violation_type.value for v in event.violations],
        user_id=user_id,
        model_id=model_id,
    )


async def _emit_audit_event(event: EscalationEvent) -> None:
    """Forward escalation to the audit writer."""
    try:
        from app.guardrails.audit import emit_escalation_audit
        await emit_escalation_audit(event)
    except Exception:
        pass


def _emit_prometheus_escalation(event: EscalationEvent) -> None:
    try:
        from app.guardrails.observability import GUARDRAIL_ESCALATIONS_TOTAL
        GUARDRAIL_ESCALATIONS_TOTAL.labels(
            target=event.escalated_to,
            auto_blocked=str(event.auto_blocked),
        ).inc()
    except Exception:
        pass


def _emit_prometheus_resolution() -> None:
    try:
        from app.guardrails.observability import GUARDRAIL_RESOLUTIONS_TOTAL
        GUARDRAIL_RESOLUTIONS_TOTAL.inc()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_engine: EscalationEngine | None = None


def get_escalation_engine() -> EscalationEngine:
    global _engine
    if _engine is None:
        _engine = EscalationEngine()
    return _engine
