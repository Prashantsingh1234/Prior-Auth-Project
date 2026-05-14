"""
WorkflowRunner — high-level async interface for the PA review workflow.

Wraps the compiled LangGraph graph with ergonomic methods for:
  - run()                     Start a new workflow from raw documents
  - resume_clarification()    Provide an answer to a pending clarification
  - resume_review()           Submit a human reviewer's action
  - get_state()               Read the current workflow state
  - get_history()             List all checkpoints for a case
  - stream()                  Stream node-by-node updates
  - get_mermaid_diagram()     Get graph visualization

Thread-safety:
  Each WorkflowRunner instance holds a single compiled graph.
  Multiple concurrent cases are isolated by their thread_id (case_id).
  The AsyncRedisSaver uses a Redis connection pool so concurrent awaits
  are safe.

Interrupt lifecycle:
  When a node raises NodeInterrupt, ainvoke() returns an InterruptResult
  that the API layer surfaces to the caller.  The caller then calls
  resume_clarification() or resume_review() which:
    1. Calls graph.aupdate_state() to inject the answer into the checkpoint.
    2. Calls graph.ainvoke() again (with None input) to resume from the
       saved checkpoint.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncIterator

import structlog

from app.services.workflow.state.models import (
    ClarificationAttempt,
    ClarificationStatus,
    RawDocument,
    ReviewerAction,
    WorkflowPhase,
)
from app.services.workflow.state.schema import (
    PAWorkflowState,
    initial_state,
    state_summary,
)

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------

@dataclass
class WorkflowResult:
    """
    Returned by run() or resume_*() when the workflow runs to completion
    (or pauses at an interrupt point).
    """
    case_id:          str
    is_complete:      bool                   # True = terminal state reached
    is_interrupted:   bool                   # True = NodeInterrupt raised
    interrupt_type:   str | None             # "clarification_required" | "human_review_required"
    interrupt_payload: dict[str, Any] | None  # Payload from NodeInterrupt
    phase:            WorkflowPhase
    recommendation:   Any | None             # PARecommendation or None
    state:            PAWorkflowState | None = None
    error:            str | None = None
    elapsed_ms:       float = 0.0


@dataclass
class WorkflowHistoryEntry:
    """One checkpoint in the workflow history."""
    checkpoint_id: str
    step:          int
    phase:         str
    timestamp:     str
    metadata:      dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

class WorkflowRunner:
    """
    High-level async runner for the PA review LangGraph workflow.

    Usage:
        runner = WorkflowRunner.from_settings()

        # Start a new case
        result = await runner.run(
            case_id="PA-2024-001",
            documents=[RawDocument(...)],
            pa_request_id="REQ-001",
        )

        # If result.is_interrupted and interrupt_type == "clarification_required":
        result = await runner.resume_clarification(
            case_id="PA-2024-001",
            attempt_id=result.interrupt_payload["attempt_id"],
            response="Patient has been on metformin for 6 months.",
        )

        # If result.is_interrupted and interrupt_type == "human_review_required":
        result = await runner.resume_review(
            case_id="PA-2024-001",
            action=ReviewerAction(
                reviewer_id="dr-smith",
                action_type=ReviewerActionType.APPROVE,
                notes="Criteria clearly met.",
            ),
        )
    """

    def __init__(self, compiled_graph) -> None:
        self._graph = compiled_graph
        self._log   = structlog.get_logger(self.__class__.__name__)

    # ------------------------------------------------------------------
    # Start a new workflow
    # ------------------------------------------------------------------

    async def run(
        self,
        case_id: str,
        documents: list[RawDocument],
        *,
        pa_request_id: str | None = None,
        member_id: str | None = None,
        payer_id: str | None = None,
        service_type: str | None = None,
        requesting_npi: str | None = None,
        max_clarification_attempts: int = 3,
        workflow_version: str = "1.0",
        langsmith_run_id: str | None = None,
    ) -> WorkflowResult:
        """
        Start a new PA review workflow for a case.

        Args:
            case_id:    Unique identifier for this PA case.
            documents:  List of RawDocument objects (with content or content_text).
            pa_request_id: Upstream PA request identifier.

        Returns:
            WorkflowResult — either complete (with recommendation) or
            interrupted (waiting for clarification / human review).
        """
        t0 = time.monotonic()

        state = initial_state(
            case_id=case_id,
            pa_request_id=pa_request_id,
            member_id=member_id,
            payer_id=payer_id,
            service_type=service_type,
            requesting_npi=requesting_npi,
            max_clarification_attempts=max_clarification_attempts,
            workflow_version=workflow_version,
            langsmith_run_id=langsmith_run_id,
        )
        # Inject documents into the initial state
        state = {**state, "raw_documents": documents}

        config = self._config(case_id)

        self._log.info(
            "runner.workflow_started",
            case_id=case_id,
            doc_count=len(documents),
        )

        return await self._invoke(state, config, t0)

    # ------------------------------------------------------------------
    # Resume after clarification
    # ------------------------------------------------------------------

    async def resume_clarification(
        self,
        case_id: str,
        attempt_id: str,
        response: str,
        responded_by: str = "provider",
    ) -> WorkflowResult:
        """
        Inject a clarification answer and resume the paused workflow.

        Steps:
          1. Read current checkpoint to find the pending attempt.
          2. Update state: mark attempt ANSWERED.
          3. Resume graph execution (ainvoke with None).
        """
        t0     = time.monotonic()
        config = self._config(case_id)

        # Get current state from checkpoint
        checkpoint_tuple = await self._graph.checkpointer.aget_tuple(config)
        if not checkpoint_tuple:
            raise ValueError(f"No checkpoint found for case_id={case_id}")

        current_state: PAWorkflowState = checkpoint_tuple.checkpoint["channel_values"]
        attempts = list(current_state.get("clarification_attempts", []))

        # Find and update the matching attempt
        updated_attempts = []
        for attempt in attempts:
            if attempt.attempt_id == attempt_id:
                updated_attempts.append(attempt.model_copy(update={
                    "response":      response,
                    "responded_by":  responded_by,
                    "answered_at":   datetime.utcnow(),
                    "status":        ClarificationStatus.ANSWERED,
                }))
            else:
                updated_attempts.append(attempt)

        # Inject the updated attempts into the checkpoint
        await self._graph.aupdate_state(
            config,
            {"clarification_attempts": updated_attempts},
        )

        self._log.info(
            "runner.clarification_injected",
            case_id=case_id,
            attempt_id=attempt_id,
            response_len=len(response),
        )

        return await self._invoke(None, config, t0)

    # ------------------------------------------------------------------
    # Resume after human review
    # ------------------------------------------------------------------

    async def resume_review(
        self,
        case_id: str,
        action: ReviewerAction,
    ) -> WorkflowResult:
        """
        Inject a reviewer's action and resume the paused workflow.

        Steps:
          1. Append the ReviewerAction to reviewer_actions in the checkpoint.
          2. Resume graph execution.
        """
        t0     = time.monotonic()
        config = self._config(case_id)

        await self._graph.aupdate_state(
            config,
            {"reviewer_actions": [action]},
        )

        self._log.info(
            "runner.review_injected",
            case_id=case_id,
            reviewer_id=action.reviewer_id,
            action_type=action.action_type.value,
        )

        return await self._invoke(None, config, t0)

    # ------------------------------------------------------------------
    # Mark a clarification as timed out
    # ------------------------------------------------------------------

    async def timeout_clarification(
        self,
        case_id: str,
        attempt_id: str,
    ) -> WorkflowResult:
        """Mark a pending clarification as timed out and resume."""
        t0     = time.monotonic()
        config = self._config(case_id)

        checkpoint_tuple = await self._graph.checkpointer.aget_tuple(config)
        if not checkpoint_tuple:
            raise ValueError(f"No checkpoint found for case_id={case_id}")

        current_state: PAWorkflowState = checkpoint_tuple.checkpoint["channel_values"]
        attempts = [
            (a.model_copy(update={"status": ClarificationStatus.TIMEOUT})
             if a.attempt_id == attempt_id else a)
            for a in current_state.get("clarification_attempts", [])
        ]

        await self._graph.aupdate_state(config, {"clarification_attempts": attempts})
        return await self._invoke(None, config, t0)

    # ------------------------------------------------------------------
    # State inspection
    # ------------------------------------------------------------------

    async def get_state(self, case_id: str) -> PAWorkflowState | None:
        """Return the current state for a case from its latest checkpoint."""
        config = self._config(case_id)
        tup = await self._graph.checkpointer.aget_tuple(config)
        if not tup:
            return None
        return tup.checkpoint.get("channel_values")

    async def get_summary(self, case_id: str) -> dict[str, Any] | None:
        """Return a lightweight state summary dict."""
        state = await self.get_state(case_id)
        return state_summary(state) if state else None

    async def get_history(self, case_id: str, limit: int = 20) -> list[WorkflowHistoryEntry]:
        """Return the checkpoint history for a case in reverse-chronological order."""
        config = self._config(case_id)
        history: list[WorkflowHistoryEntry] = []
        async for tup in self._graph.checkpointer.alist(config, limit=limit):
            meta = tup.metadata or {}
            cv   = tup.checkpoint.get("channel_values", {})
            history.append(WorkflowHistoryEntry(
                checkpoint_id=tup.checkpoint.get("id", ""),
                step=meta.get("step", -1),
                phase=str(cv.get("workflow_phase", "unknown")),
                timestamp=tup.checkpoint.get("ts", ""),
                metadata={
                    "source": meta.get("source"),
                    "writes": list(meta.get("writes", {}).keys()) if meta.get("writes") else [],
                },
            ))
        return history

    # ------------------------------------------------------------------
    # Streaming
    # ------------------------------------------------------------------

    async def stream(
        self,
        case_id: str,
        documents: list[RawDocument],
        *,
        pa_request_id: str | None = None,
        stream_mode: str = "values",
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Stream workflow progress as node-by-node state snapshots.

        stream_mode options:
          "values"   → yields the full state after each node
          "updates"  → yields only the state delta from each node
        Yields dicts with "phase", "node", "state_patch" keys.
        """
        state = initial_state(case_id=case_id, pa_request_id=pa_request_id)
        state = {**state, "raw_documents": documents}
        config = self._config(case_id)

        async for event in self._graph.astream(state, config, stream_mode=stream_mode):
            yield event

    # ------------------------------------------------------------------
    # Visualization
    # ------------------------------------------------------------------

    def get_mermaid_diagram(self) -> str:
        """Return the workflow graph as a Mermaid diagram string."""
        from app.services.workflow.graph import get_mermaid_diagram
        return get_mermaid_diagram()

    def get_ascii_diagram(self) -> str:
        """Return the workflow graph as ASCII art."""
        from app.services.workflow.graph import get_ascii_diagram
        return get_ascii_diagram()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _invoke(
        self,
        state: PAWorkflowState | None,
        config: dict,
        t0: float,
    ) -> WorkflowResult:
        """Call graph.ainvoke(), catch interrupts, and wrap the result."""
        case_id = config["configurable"]["thread_id"]

        try:
            final_state: PAWorkflowState = await self._graph.ainvoke(state, config)
            elapsed_ms = (time.monotonic() - t0) * 1000

            recommendation = final_state.get("recommendation")
            phase          = final_state.get("workflow_phase", WorkflowPhase.FAILED)
            is_complete    = phase in (WorkflowPhase.COMPLETED, WorkflowPhase.FAILED)
            error          = final_state.get("error")

            self._log.info(
                "runner.invocation_complete",
                case_id=case_id,
                phase=phase,
                is_complete=is_complete,
                elapsed_ms=round(elapsed_ms, 1),
            )

            return WorkflowResult(
                case_id=case_id,
                is_complete=is_complete,
                is_interrupted=False,
                interrupt_type=None,
                interrupt_payload=None,
                phase=phase,
                recommendation=recommendation,
                state=final_state,
                error=error,
                elapsed_ms=elapsed_ms,
            )

        except Exception as exc:
            elapsed_ms = (time.monotonic() - t0) * 1000

            # LangGraph surfaces NodeInterrupt as a GraphInterrupt exception
            # (depending on version it may be wrapped differently)
            interrupt_payload = self._extract_interrupt(exc)
            if interrupt_payload is not None:
                interrupt_type = interrupt_payload.get("type", "unknown")
                self._log.info(
                    "runner.workflow_interrupted",
                    case_id=case_id,
                    interrupt_type=interrupt_type,
                    elapsed_ms=round(elapsed_ms, 1),
                )
                # Read back the phase from the latest checkpoint
                saved_state = await self.get_state(case_id)
                phase = (saved_state or {}).get("workflow_phase", WorkflowPhase.CLARIFICATION)
                return WorkflowResult(
                    case_id=case_id,
                    is_complete=False,
                    is_interrupted=True,
                    interrupt_type=interrupt_type,
                    interrupt_payload=interrupt_payload,
                    phase=phase,
                    recommendation=(saved_state or {}).get("recommendation"),
                    state=saved_state,
                    elapsed_ms=elapsed_ms,
                )

            # Genuine error
            self._log.error(
                "runner.invocation_failed",
                case_id=case_id,
                error=str(exc),
                exc_info=True,
            )
            raise

    @staticmethod
    def _extract_interrupt(exc: Exception) -> dict[str, Any] | None:
        """
        Extract the interrupt payload from a LangGraph NodeInterrupt exception.

        LangGraph wraps NodeInterrupt in different ways depending on version:
          - 0.1.x: exception IS the NodeInterrupt, exc.value = payload
          - 0.2.x+: may be wrapped in GraphInterrupt
        """
        # Direct NodeInterrupt
        if hasattr(exc, "value") and isinstance(exc.value, dict):
            return exc.value

        # GraphInterrupt wrapper (0.2.x)
        if hasattr(exc, "interrupts"):
            interrupts = exc.interrupts
            if interrupts:
                first = interrupts[0]
                if hasattr(first, "value"):
                    return first.value

        # Check if it's a tuple/list of interrupts
        if isinstance(getattr(exc, "args", None), (list, tuple)) and exc.args:
            payload = exc.args[0]
            if isinstance(payload, dict) and "type" in payload:
                return payload

        return None

    @staticmethod
    def _config(case_id: str) -> dict:
        """Build a LangGraph RunnableConfig for the given case."""
        return {"configurable": {"thread_id": case_id}}

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_settings(cls) -> "WorkflowRunner":
        """
        Create a WorkflowRunner from application settings.

        Builds and compiles the graph with a Redis-backed checkpointer.
        """
        from app.services.workflow.graph import compile_graph
        compiled = compile_graph()
        return cls(compiled)

    @classmethod
    def with_memory_checkpointer(cls) -> "WorkflowRunner":
        """
        Create a WorkflowRunner with an in-memory checkpointer.

        For testing only — state is lost on process restart.
        """
        from langgraph.checkpoint.memory import MemorySaver
        from app.services.workflow.graph import build_graph
        compiled = build_graph().compile(checkpointer=MemorySaver())
        return cls(compiled)
