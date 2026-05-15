"""
LangGraph workflow lifecycle hooks for observability.

WorkflowHooks is a container of lightweight async callables that
WorkflowRunner registers on graph events.  Each hook is try/except
wrapped — hook failures never propagate to the workflow.

Hook signatures
---------------
on_graph_start(case_id, inputs)
on_graph_end(case_id, outputs, error, elapsed_ms)
on_node_start(case_id, node_name, state)
on_node_end(case_id, node_name, patch, elapsed_ms)
on_interrupt(case_id, node_name, interrupt_type, payload)
on_retry(case_id, node_name, attempt, error)
on_failure(case_id, node_name, error_type, error_msg)

The default implementation (DefaultWorkflowHooks) emits structured
structlog events and Prometheus counters for every hook.

Usage:
    hooks = DefaultWorkflowHooks()

    # WorkflowRunner calls hooks around graph.ainvoke():
    await hooks.on_graph_start(case_id, inputs)
    try:
        result = await graph.ainvoke(state, config)
        await hooks.on_graph_end(case_id, result, None, elapsed_ms)
    except Exception as exc:
        await hooks.on_graph_end(case_id, {}, str(exc), elapsed_ms)
        raise
"""

from __future__ import annotations

import time
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class WorkflowHooks:
    """
    Base class for workflow lifecycle hooks.

    All methods are no-ops by default so subclasses can override selectively.
    All methods swallow exceptions to ensure hooks never break the workflow.
    """

    async def on_graph_start(self, case_id: str, inputs: dict[str, Any]) -> None:
        pass

    async def on_graph_end(
        self,
        case_id: str,
        outputs: dict[str, Any],
        error: str | None,
        elapsed_ms: float,
    ) -> None:
        pass

    async def on_node_start(
        self,
        case_id: str,
        node_name: str,
        state: dict[str, Any],
    ) -> None:
        pass

    async def on_node_end(
        self,
        case_id: str,
        node_name: str,
        patch: dict[str, Any],
        elapsed_ms: float,
    ) -> None:
        pass

    async def on_interrupt(
        self,
        case_id: str,
        node_name: str,
        interrupt_type: str,
        payload: dict[str, Any],
    ) -> None:
        pass

    async def on_retry(
        self,
        case_id: str,
        node_name: str,
        attempt: int,
        error: str,
    ) -> None:
        pass

    async def on_failure(
        self,
        case_id: str,
        node_name: str,
        error_type: str,
        error_msg: str,
    ) -> None:
        pass


class DefaultWorkflowHooks(WorkflowHooks):
    """
    Production hook implementation: structlog + Prometheus for every event.
    """

    async def on_graph_start(self, case_id: str, inputs: dict[str, Any]) -> None:
        try:
            logger.info(
                "workflow.graph_start",
                case_id=case_id,
                input_keys=list(inputs.keys()),
            )
            _inc_counter("workflow_runs_total", {"outcome": "started"})
        except Exception:
            pass

    async def on_graph_end(
        self,
        case_id: str,
        outputs: dict[str, Any],
        error: str | None,
        elapsed_ms: float,
    ) -> None:
        try:
            outcome = "error" if error else "success"
            logger.info(
                "workflow.graph_end",
                case_id=case_id,
                outcome=outcome,
                elapsed_ms=round(elapsed_ms, 1),
                error=error,
            )
            _inc_counter("workflow_runs_total", {"outcome": outcome})
            _observe_histogram(
                "workflow_duration_ms",
                elapsed_ms,
                {"outcome": outcome},
            )
        except Exception:
            pass

    async def on_node_start(
        self,
        case_id: str,
        node_name: str,
        state: dict[str, Any],
    ) -> None:
        try:
            logger.debug(
                "workflow.node_start",
                case_id=case_id,
                node=node_name,
                phase=state.get("workflow_phase", "unknown"),
            )
        except Exception:
            pass

    async def on_node_end(
        self,
        case_id: str,
        node_name: str,
        patch: dict[str, Any],
        elapsed_ms: float,
    ) -> None:
        try:
            logger.debug(
                "workflow.node_end",
                case_id=case_id,
                node=node_name,
                patch_keys=list(patch.keys()) if patch else [],
                elapsed_ms=round(elapsed_ms, 1),
            )
        except Exception:
            pass

    async def on_interrupt(
        self,
        case_id: str,
        node_name: str,
        interrupt_type: str,
        payload: dict[str, Any],
    ) -> None:
        try:
            logger.info(
                "workflow.node_interrupt",
                case_id=case_id,
                node=node_name,
                interrupt_type=interrupt_type,
                payload_keys=list(payload.keys()) if payload else [],
            )
            _inc_counter("workflow_interrupts_total", {"node": node_name, "type": interrupt_type})
        except Exception:
            pass

    async def on_retry(
        self,
        case_id: str,
        node_name: str,
        attempt: int,
        error: str,
    ) -> None:
        try:
            logger.warning(
                "workflow.node_retry",
                case_id=case_id,
                node=node_name,
                attempt=attempt,
                error=error,
            )
            _inc_counter("workflow_retries_total", {"node": node_name, "attempt": str(attempt)})
        except Exception:
            pass

    async def on_failure(
        self,
        case_id: str,
        node_name: str,
        error_type: str,
        error_msg: str,
    ) -> None:
        try:
            logger.error(
                "workflow.node_failure",
                case_id=case_id,
                node=node_name,
                error_type=error_type,
                error=error_msg,
            )
            _inc_counter("workflow_failures_total", {"node": node_name, "error_type": error_type})
        except Exception:
            pass


class CompositeWorkflowHooks(WorkflowHooks):
    """Fan-out to multiple hook implementations."""

    def __init__(self, *hooks: WorkflowHooks) -> None:
        self._hooks = list(hooks)

    async def on_graph_start(self, case_id: str, inputs: dict[str, Any]) -> None:
        for h in self._hooks:
            try:
                await h.on_graph_start(case_id, inputs)
            except Exception:
                pass

    async def on_graph_end(
        self,
        case_id: str,
        outputs: dict[str, Any],
        error: str | None,
        elapsed_ms: float,
    ) -> None:
        for h in self._hooks:
            try:
                await h.on_graph_end(case_id, outputs, error, elapsed_ms)
            except Exception:
                pass

    async def on_node_start(
        self,
        case_id: str,
        node_name: str,
        state: dict[str, Any],
    ) -> None:
        for h in self._hooks:
            try:
                await h.on_node_start(case_id, node_name, state)
            except Exception:
                pass

    async def on_node_end(
        self,
        case_id: str,
        node_name: str,
        patch: dict[str, Any],
        elapsed_ms: float,
    ) -> None:
        for h in self._hooks:
            try:
                await h.on_node_end(case_id, node_name, patch, elapsed_ms)
            except Exception:
                pass

    async def on_interrupt(
        self,
        case_id: str,
        node_name: str,
        interrupt_type: str,
        payload: dict[str, Any],
    ) -> None:
        for h in self._hooks:
            try:
                await h.on_interrupt(case_id, node_name, interrupt_type, payload)
            except Exception:
                pass

    async def on_retry(
        self,
        case_id: str,
        node_name: str,
        attempt: int,
        error: str,
    ) -> None:
        for h in self._hooks:
            try:
                await h.on_retry(case_id, node_name, attempt, error)
            except Exception:
                pass

    async def on_failure(
        self,
        case_id: str,
        node_name: str,
        error_type: str,
        error_msg: str,
    ) -> None:
        for h in self._hooks:
            try:
                await h.on_failure(case_id, node_name, error_type, error_msg)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Prometheus helpers (lazy imports)
# ---------------------------------------------------------------------------

def _inc_counter(metric: str, labels: dict) -> None:
    try:
        from app.monitoring.metrics import WORKFLOW_NODE_DURATION_MS  # noqa: F401
        # Use a generic approach: each metric resolved by name
        import app.monitoring.metrics as m
        counter = getattr(m, metric.upper(), None)
        if counter is not None:
            counter.labels(**labels).inc()
    except Exception:
        pass


def _observe_histogram(metric: str, value: float, labels: dict) -> None:
    try:
        import app.monitoring.metrics as m
        histogram = getattr(m, metric.upper(), None)
        if histogram is not None:
            histogram.labels(**labels).observe(value)
    except Exception:
        pass
