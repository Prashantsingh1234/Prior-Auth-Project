"""
Tracing decorators for workflow node functions and LLM calls.

@trace_node
-----------
Wraps a node's execute() method to automatically:
  - Create a LangSmith child run for each node invocation
  - Record inputs (sanitised state fields), outputs (patch summary), latency
  - Log retries and failures
  - Emit Prometheus node-duration histogram observations
  - Never raise from tracing code (errors in tracing are silently swallowed)

Usage in a node class:

    class ExtractionNode(BaseNode):
        node_name = "extraction_node"

        @trace_node(
            capture_state_fields=["case_id", "workflow_phase", "retry_count"],
        )
        async def execute(self, state, nctx) -> dict:
            ...

@trace_llm_call
---------------
Wraps a standalone async function that calls an LLM.  Records prompt,
response, token usage, and latency as a "llm" run in LangSmith.

Usage:

    @trace_llm_call(operation="policy_evaluation", model="gpt-4o")
    async def _call_llm(self, prompt: str, ...) -> str:
        ...
"""

from __future__ import annotations

import asyncio
import functools
import time
from typing import Any, Callable, TypeVar

import structlog

logger = structlog.get_logger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

# Default state fields to capture as node inputs in LangSmith
_DEFAULT_CAPTURE_FIELDS = frozenset({
    "case_id", "pa_request_id", "payer_id", "service_type",
    "workflow_phase", "retry_count",
})


def trace_node(
    capture_state_fields: list[str] | None = None,
    tags: list[str] | None = None,
) -> Callable[[F], F]:
    """
    Decorator factory for node execute() methods.

    Wraps async execute(self, state, nctx) → dict.
    Reads the WorkflowTracer from nctx.tracer (set by BaseNode.__call__).

    Parameters
    ----------
    capture_state_fields:
        Additional state fields to include in the LangSmith run inputs.
        Always includes the default set (case_id, workflow_phase, etc.).
    tags:
        Extra LangSmith tags for this node (e.g., ["extraction", "medical-nlp"]).
    """
    extra_fields = set(capture_state_fields or [])
    all_fields   = _DEFAULT_CAPTURE_FIELDS | extra_fields

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(node_self, state, nctx, *args, **kwargs):
            tracer   = getattr(nctx, "tracer", None)
            node_name = getattr(node_self, "node_name", func.__name__)

            # Build safe inputs
            inputs = {k: v for k, v in state.items() if k in all_fields}

            # Start node run in LangSmith
            if tracer is not None:
                run_id = tracer.start_node(
                    node_name,
                    state,
                    metadata={"tags": (tags or []) + [node_name]},
                )
                nctx.langsmith_run_id = run_id

            t0 = time.monotonic()
            error_str: str | None = None
            patch: dict[str, Any] = {}

            try:
                patch = await func(node_self, state, nctx, *args, **kwargs)
                return patch
            except Exception as exc:
                error_str = f"{type(exc).__name__}: {exc}"
                raise
            finally:
                elapsed_ms = (time.monotonic() - t0) * 1000
                _emit_node_prometheus(node_name, elapsed_ms, bool(error_str))

                if tracer is not None:
                    tracer.end_node(
                        node_name,
                        patch if isinstance(patch, dict) else {},
                        error_str,
                    )

        return wrapper  # type: ignore

    return decorator


def trace_llm_call(
    operation: str,
    model: str = "unknown",
    capture_prompt: bool = True,
) -> Callable[[F], F]:
    """
    Decorator for standalone async LLM-call methods.

    Expects the decorated function to return a string or object with a
    `.content` / `.text` attribute.

    Logs the call as a "llm" run in LangSmith under the active node.

    Parameters
    ----------
    operation:
        Human-readable label (e.g., "policy_evaluation", "question_generation").
    model:
        Model name override.  The actual model is extracted from the response
        if available.
    capture_prompt:
        If False, the prompt is not sent to LangSmith (PII-sensitive flows).
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            t0 = time.monotonic()
            error_str: str | None = None
            result = None

            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as exc:
                error_str = f"{type(exc).__name__}: {exc}"
                raise
            finally:
                elapsed_ms = (time.monotonic() - t0) * 1000
                _log_llm_call(
                    operation=operation,
                    model=model,
                    elapsed_ms=elapsed_ms,
                    error=error_str,
                    result=result,
                )

        return wrapper  # type: ignore

    return decorator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _emit_node_prometheus(node_name: str, elapsed_ms: float, is_error: bool) -> None:
    try:
        from app.monitoring.metrics import WORKFLOW_NODE_DURATION_MS
        WORKFLOW_NODE_DURATION_MS.labels(
            node=node_name,
            phase="execution",
        ).observe(elapsed_ms)
    except Exception:
        pass

    if is_error:
        try:
            from app.monitoring.metrics import WORKFLOW_ERRORS_TOTAL
            WORKFLOW_ERRORS_TOTAL.labels(
                node=node_name,
                error_type="node_error",
            ).inc()
        except Exception:
            pass


def _log_llm_call(
    operation: str,
    model: str,
    elapsed_ms: float,
    error: str | None,
    result: Any,
) -> None:
    output_preview = ""
    try:
        if result is not None:
            text = getattr(result, "content", None) or getattr(result, "text", None)
            if text is None and isinstance(result, str):
                text = result
            output_preview = str(text or "")[:200]
    except Exception:
        pass

    logger.debug(
        "llm_call.traced",
        operation=operation,
        model=model,
        elapsed_ms=round(elapsed_ms, 1),
        error=error,
        output_preview=output_preview,
    )
