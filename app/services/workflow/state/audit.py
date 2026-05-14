"""
Audit trail utilities for the PA workflow.

Provides:
  - create_audit_event()  — factory that stamps every state transition
  - AuditContext          — dataclass threaded through node implementations
                            so they don't have to repeat node_name / step

Usage inside a graph node:
    async def extraction_node(state: PAWorkflowState, ctx: AuditContext):
        t0 = time.monotonic()
        result = await engine.extract(...)
        ms = (time.monotonic() - t0) * 1000

        return {
            **ctx.event(
                AuditEventType.ENTITIES_EXTRACTED,
                data={"document_id": doc_id, "entities": result.total_entities},
                duration_ms=ms,
            ),
            "extracted_entities": {doc_id: entities},
            "tokens_used": result.llm_tokens_used,
            "processing_ms": ms,
        }
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4

from app.services.workflow.state.models import AuditEvent, AuditEventType, WorkflowPhase


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_audit_event(
    event_type: AuditEventType,
    *,
    node_name: str,
    step: int = 0,
    data: dict[str, Any] | None = None,
    duration_ms: float | None = None,
    error: str | None = None,
) -> AuditEvent:
    """
    Construct a single AuditEvent ready to be appended to state["audit_events"].

    Args:
        event_type:  The category of event (see AuditEventType enum).
        node_name:   LangGraph node name that generated this event.
        step:        LangGraph internal step counter (from RunnableConfig).
        data:        Arbitrary structured context for the event.
        duration_ms: Wall-clock time the node took to produce this event.
        error:       Populated only on AuditEventType.ERROR events.

    Returns:
        AuditEvent with a unique event_id and a UTC timestamp.
    """
    return AuditEvent(
        event_id=str(uuid4()),
        event_type=event_type,
        node_name=node_name,
        step=step,
        timestamp=datetime.utcnow(),
        data=data or {},
        duration_ms=duration_ms,
        error=error,
    )


def create_phase_transition_event(
    from_phase: WorkflowPhase,
    to_phase: WorkflowPhase,
    *,
    node_name: str,
    step: int = 0,
    reason: str | None = None,
) -> AuditEvent:
    """Convenience wrapper for workflow phase transitions."""
    return create_audit_event(
        AuditEventType.PHASE_TRANSITION,
        node_name=node_name,
        step=step,
        data={
            "from_phase": from_phase.value,
            "to_phase": to_phase.value,
            "reason": reason,
        },
    )


def create_error_event(
    error: str,
    *,
    node_name: str,
    step: int = 0,
    exc_type: str | None = None,
    context: dict[str, Any] | None = None,
) -> AuditEvent:
    """Convenience wrapper for error events."""
    return create_audit_event(
        AuditEventType.ERROR,
        node_name=node_name,
        step=step,
        data={
            "exc_type": exc_type,
            **(context or {}),
        },
        error=error,
    )


# ---------------------------------------------------------------------------
# AuditContext — threaded through every node
# ---------------------------------------------------------------------------

@dataclass
class AuditContext:
    """
    Carries node identity and timing into graph node implementations.

    Pass this to every node so that:
      - node_name and step are never hard-coded in node bodies
      - timing is always consistent (uses self._t0 for duration)
      - the pattern for emitting audit events is uniform

    Typical usage:
        ctx = AuditContext(node_name="extraction_node", step=config["step"])
        ...
        return {
            **ctx.event(AuditEventType.ENTITIES_EXTRACTED, data={...}),
            "extracted_entities": {...},
        }
    """

    node_name: str
    step: int = 0
    _t0: float = field(default_factory=time.monotonic, repr=False)

    def elapsed_ms(self) -> float:
        """Wall-clock ms since this context was created."""
        return (time.monotonic() - self._t0) * 1000

    def event(
        self,
        event_type: AuditEventType,
        *,
        data: dict[str, Any] | None = None,
        duration_ms: float | None = None,
        error: str | None = None,
        measure_elapsed: bool = True,
    ) -> dict[str, list[AuditEvent]]:
        """
        Return a partial state dict `{"audit_events": [event]}`.

        Use with `**ctx.event(...)` inside a node return dict:

            return {
                **ctx.event(AuditEventType.ENTITIES_EXTRACTED, data={...}),
                "extracted_entities": {...},
                "processing_ms": ctx.elapsed_ms(),
            }

        Args:
            event_type:       The audit event category.
            data:             Contextual data for the event.
            duration_ms:      Explicit duration; defaults to elapsed since context creation.
            error:            Error message for ERROR events.
            measure_elapsed:  If True and duration_ms is None, auto-measures elapsed.
        """
        if duration_ms is None and measure_elapsed:
            duration_ms = self.elapsed_ms()

        return {
            "audit_events": [
                create_audit_event(
                    event_type,
                    node_name=self.node_name,
                    step=self.step,
                    data=data,
                    duration_ms=duration_ms,
                    error=error,
                )
            ]
        }

    def error_event(
        self,
        error: str,
        *,
        exc_type: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, list[AuditEvent]]:
        """Shortcut for emitting an ERROR audit event."""
        return self.event(
            AuditEventType.ERROR,
            data={"exc_type": exc_type, **(context or {})},
            error=error,
        )

    def phase_event(
        self,
        from_phase: WorkflowPhase,
        to_phase: WorkflowPhase,
        reason: str | None = None,
    ) -> dict[str, list[AuditEvent]]:
        """Shortcut for emitting a PHASE_TRANSITION event."""
        return {
            "audit_events": [
                create_phase_transition_event(
                    from_phase, to_phase,
                    node_name=self.node_name,
                    step=self.step,
                    reason=reason,
                )
            ]
        }


# ---------------------------------------------------------------------------
# Timing context manager
# ---------------------------------------------------------------------------

class NodeTimer:
    """
    Context manager that measures node execution time and produces an
    AuditEvent on exit.

    Usage:
        async with NodeTimer(ctx, AuditEventType.CRITERIA_EVALUATED) as t:
            result = await evaluate(...)
        # t.event is now populated — merge into return dict

        return {
            **t.as_state_patch(),
            "evaluation_results": {...},
        }
    """

    def __init__(
        self,
        ctx: AuditContext,
        event_type: AuditEventType,
        data: dict[str, Any] | None = None,
    ) -> None:
        self._ctx = ctx
        self._event_type = event_type
        self._data = data or {}
        self._t0 = 0.0
        self._duration_ms = 0.0
        self.event: AuditEvent | None = None

    def __enter__(self) -> "NodeTimer":
        self._t0 = time.monotonic()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self._duration_ms = (time.monotonic() - self._t0) * 1000
        error = str(exc_val) if exc_val else None
        self.event = create_audit_event(
            self._event_type,
            node_name=self._ctx.node_name,
            step=self._ctx.step,
            data=self._data,
            duration_ms=self._duration_ms,
            error=error,
        )

    async def __aenter__(self) -> "NodeTimer":
        return self.__enter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        self.__exit__(exc_type, exc_val, exc_tb)

    def as_state_patch(self) -> dict[str, Any]:
        """Return `{"audit_events": [event], "processing_ms": duration_ms}`."""
        if self.event is None:
            return {}
        return {
            "audit_events": [self.event],
            "processing_ms": self._duration_ms,
        }
