"""
WorkflowTracer — LangSmith RunTree management for the PA workflow.

Creates a two-level trace hierarchy in LangSmith:

  [chain] PA-Review-{case_id}          ← top-level workflow run
      └─ [chain] ingestion_node         ← one child per node
      └─ [chain] extraction_node
      └─ [chain] retrieval_node
      └─ [chain] reasoning_node
          └─ [llm]  gpt-4o / claude-*  ← LLM calls (via callback handler)
      └─ [chain] decision_node
      └─ [chain] audit_node

Each RunTree records:
  - inputs  (sanitised state fields, no PHI)
  - outputs (state patch keys, summary values)
  - latency (wall-clock ms)
  - error   (exception message + type)
  - metadata: case_id, node_name, phase, token_usage, retry_count, interrupt_type

Thread-safety:
  WorkflowTracer is per-request (created in WorkflowRunner.run()).
  The internal _runs dict is not shared across concurrent cases.
"""

from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncGenerator

import structlog

from app.tracing.config import get_langsmith_config

logger = structlog.get_logger(__name__)

# State fields safe to log as inputs (no PHI, no large blobs)
_SAFE_STATE_FIELDS = frozenset({
    "case_id", "pa_request_id", "payer_id", "service_type",
    "workflow_phase", "retry_count", "max_clarification_attempts",
})

# Output patch keys we summarise in LangSmith (avoids logging large embeddings)
_SUMMARY_OUTPUT_KEYS = frozenset({
    "workflow_phase", "error", "retry_count", "tokens_used", "processing_ms",
})


def _sanitise_state(state: dict) -> dict[str, Any]:
    """Return a subset of state fields safe to send to LangSmith."""
    return {k: v for k, v in state.items() if k in _SAFE_STATE_FIELDS}


def _summarise_patch(patch: dict) -> dict[str, Any]:
    """Summarise a node output patch for LangSmith (keys + scalar values only)."""
    summary: dict[str, Any] = {"changed_keys": list(patch.keys())}
    for k in _SUMMARY_OUTPUT_KEYS:
        if k in patch:
            v = patch[k]
            summary[k] = v.value if hasattr(v, "value") else v
    return summary


@dataclass
class NodeTrace:
    """Bookkeeping for a single in-flight node trace."""
    run_id:   str
    run_tree: Any        # langsmith.RunTree | None
    node_name: str
    started_at: float = field(default_factory=time.monotonic)


class WorkflowTracer:
    """
    Manages LangSmith RunTree objects for one workflow execution.

    One instance is created per WorkflowRunner.run() call.
    Passed into NodeContext so nodes can log their own child runs.
    """

    def __init__(self, case_id: str, parent_run_id: str | None = None) -> None:
        self._case_id       = case_id
        self._parent_run_id = parent_run_id
        self._workflow_run: Any = None     # langsmith.RunTree | None
        self._node_traces: dict[str, NodeTrace] = {}
        self._enabled = get_langsmith_config().is_active
        self._client: Any = None
        self._init_client()

    def _init_client(self) -> None:
        if not self._enabled:
            return
        try:
            import langsmith
            cfg = get_langsmith_config()
            self._client = langsmith.Client(
                api_key=cfg.api_key,
                api_url=cfg.endpoint,
            )
        except ImportError:
            self._enabled = False
            logger.debug("tracer.langsmith_not_installed")
        except Exception as exc:
            self._enabled = False
            logger.warning("tracer.init_failed", error=str(exc))

    # ------------------------------------------------------------------
    # Workflow-level run
    # ------------------------------------------------------------------

    def start_workflow(
        self,
        inputs: dict[str, Any],
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Open a top-level LangSmith "chain" run for the entire workflow.

        Returns a run_id string (UUID4) usable for cross-referencing.
        """
        run_id = str(uuid.uuid4())
        if not self._enabled:
            return run_id

        try:
            from langsmith.run_trees import RunTree

            extra: dict[str, Any] = {"metadata": {
                "case_id":    self._case_id,
                "component":  "pa_workflow",
                **(metadata or {}),
            }}
            rt = RunTree(
                name=f"PA-Review-{self._case_id}",
                run_type="chain",
                inputs=inputs,
                id=run_id,
                tags=tags or ["pa-workflow"],
                extra=extra,
                project_name=get_langsmith_config().project,
            )
            if self._parent_run_id:
                rt.parent_run_id = uuid.UUID(self._parent_run_id)
            rt.post()
            self._workflow_run = rt
        except Exception as exc:
            logger.debug("tracer.start_workflow_failed", error=str(exc))

        return run_id

    def end_workflow(
        self,
        outputs: dict[str, Any],
        error: str | None = None,
    ) -> None:
        """Close the top-level workflow run."""
        if not self._enabled or self._workflow_run is None:
            return
        try:
            if error:
                self._workflow_run.end(error=error)
            else:
                self._workflow_run.end(outputs=outputs)
            self._workflow_run.patch()
        except Exception as exc:
            logger.debug("tracer.end_workflow_failed", error=str(exc))

    # ------------------------------------------------------------------
    # Node-level runs
    # ------------------------------------------------------------------

    def start_node(
        self,
        node_name: str,
        state: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Open a child LangSmith run for a single node execution.

        Returns a node_run_id.
        """
        node_run_id = str(uuid.uuid4())
        if not self._enabled:
            self._node_traces[node_name] = NodeTrace(
                run_id=node_run_id,
                run_tree=None,
                node_name=node_name,
            )
            return node_run_id

        try:
            from langsmith.run_trees import RunTree

            inputs = _sanitise_state(state)
            extra: dict[str, Any] = {"metadata": {
                "case_id":   self._case_id,
                "node_name": node_name,
                **(metadata or {}),
            }}
            rt = RunTree(
                name=node_name,
                run_type="chain",
                inputs=inputs,
                id=node_run_id,
                tags=["pa-workflow", node_name],
                extra=extra,
                project_name=get_langsmith_config().project,
            )
            if self._workflow_run is not None:
                rt.parent_run_id = self._workflow_run.id
            rt.post()

            self._node_traces[node_name] = NodeTrace(
                run_id=node_run_id,
                run_tree=rt,
                node_name=node_name,
            )
        except Exception as exc:
            logger.debug("tracer.start_node_failed", node=node_name, error=str(exc))
            self._node_traces[node_name] = NodeTrace(
                run_id=node_run_id, run_tree=None, node_name=node_name
            )

        return node_run_id

    def end_node(
        self,
        node_name: str,
        patch: dict[str, Any],
        error: str | None = None,
    ) -> float:
        """
        Close the node run.  Returns elapsed_ms for the node.
        """
        trace = self._node_traces.pop(node_name, None)
        if trace is None:
            return 0.0

        elapsed_ms = (time.monotonic() - trace.started_at) * 1000

        if not self._enabled or trace.run_tree is None:
            return elapsed_ms

        try:
            outputs = _summarise_patch(patch)
            outputs["elapsed_ms"] = round(elapsed_ms, 1)
            if error:
                trace.run_tree.end(error=error)
            else:
                trace.run_tree.end(outputs=outputs)
            trace.run_tree.patch()
        except Exception as exc:
            logger.debug("tracer.end_node_failed", node=node_name, error=str(exc))

        return elapsed_ms

    # ------------------------------------------------------------------
    # Special events
    # ------------------------------------------------------------------

    def log_interrupt(
        self,
        node_name: str,
        interrupt_type: str,
        payload: dict[str, Any],
    ) -> None:
        """
        Record a NodeInterrupt as a LangSmith event on the node run.
        Interrupts are NOT errors — they pause execution for human input.
        """
        trace = self._node_traces.get(node_name)
        if not self._enabled or trace is None or trace.run_tree is None:
            return
        try:
            trace.run_tree.add_metadata({
                "interrupt": True,
                "interrupt_type": interrupt_type,
                "interrupt_payload_keys": list(payload.keys()),
            })
            trace.run_tree.patch()
        except Exception as exc:
            logger.debug("tracer.log_interrupt_failed", error=str(exc))

    def log_retry(
        self,
        node_name: str,
        attempt: int,
        error: str,
    ) -> None:
        """Record a retry event on an active node run."""
        trace = self._node_traces.get(node_name)
        if not self._enabled or trace is None or trace.run_tree is None:
            return
        try:
            trace.run_tree.add_metadata({
                f"retry_{attempt}_error": error,
                "retry_count": attempt,
            })
            trace.run_tree.patch()
        except Exception as exc:
            logger.debug("tracer.log_retry_failed", error=str(exc))

    def log_token_usage(
        self,
        node_name: str,
        prompt_tokens: int,
        completion_tokens: int,
        model: str = "",
    ) -> None:
        """Attach token usage to an active node run."""
        trace = self._node_traces.get(node_name)
        if not self._enabled or trace is None or trace.run_tree is None:
            return
        try:
            trace.run_tree.add_metadata({
                "tokens.prompt":     prompt_tokens,
                "tokens.completion": completion_tokens,
                "tokens.total":      prompt_tokens + completion_tokens,
                "model":             model,
            })
            trace.run_tree.patch()
        except Exception as exc:
            logger.debug("tracer.log_tokens_failed", error=str(exc))

    # ------------------------------------------------------------------
    # Context manager interface
    # ------------------------------------------------------------------

    @asynccontextmanager
    async def trace_node(
        self,
        node_name: str,
        state: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Async context manager: start a node run on entry, end it on exit.

        Usage in node execute():
            async with self._tracer.trace_node("extraction_node", state) as run_id:
                ...

        Captures exceptions and logs them as errors (does NOT suppress them).
        """
        run_id = self.start_node(node_name, state, metadata)
        error: str | None = None
        patch: dict[str, Any] = {}
        try:
            yield run_id
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            self.end_node(node_name, patch, error)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def for_case(
        cls,
        case_id: str,
        parent_run_id: str | None = None,
    ) -> "WorkflowTracer":
        return cls(case_id=case_id, parent_run_id=parent_run_id)
