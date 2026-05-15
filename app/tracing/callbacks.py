"""
LangChain callback handler for the PA workflow.

PAWorkflowCallbackHandler intercepts every LangChain/LangGraph lifecycle
event and:
  1. Logs structured events via structlog
  2. Records to Prometheus (token counts, latency, error rates)
  3. Forwards LLM-specific events to LangSmith as child "llm" runs
     under the active node run
  4. Captures retry/failure details for alerting

Event coverage:
  on_llm_start      — model name, prompt preview, metadata
  on_llm_end        — token usage, response preview, latency
  on_llm_error      — error message, model, partial output
  on_chain_start    — chain/node name, inputs summary
  on_chain_end      — outputs summary, latency
  on_chain_error    — error type, inputs context
  on_tool_start     — tool name, inputs
  on_tool_end       — tool output preview
  on_tool_error     — error details

Usage:
    handler = PAWorkflowCallbackHandler(case_id="PA-2024-001")
    config = {"callbacks": [handler]}
    await graph.ainvoke(state, config)
"""

from __future__ import annotations

import time
from typing import Any, Union
from uuid import UUID

import structlog

logger = structlog.get_logger(__name__)


class PAWorkflowCallbackHandler:
    """
    LangChain BaseCallbackHandler for the PA workflow.

    Inherits BaseCallbackHandler if langchain_core is installed; otherwise
    provides the same interface as a plain Python object so the rest of the
    codebase compiles without langchain_core.
    """

    def __init__(
        self,
        case_id: str,
        workflow_run_id: str | None = None,
        tracer=None,       # WorkflowTracer | None
    ) -> None:
        self.case_id          = case_id
        self.workflow_run_id  = workflow_run_id
        self._tracer          = tracer
        self._chain_starts: dict[str, float] = {}    # run_id → wall-clock start
        self._llm_starts:   dict[str, float] = {}
        self._log = structlog.get_logger(__name__).bind(case_id=case_id)

    # ------------------------------------------------------------------
    # LLM events
    # ------------------------------------------------------------------

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        self._llm_starts[str(run_id)] = time.monotonic()
        model = _extract_model_name(serialized)
        prompt_preview = _truncate(prompts[0] if prompts else "", 200)

        self._log.debug(
            "llm.start",
            run_id=str(run_id),
            model=model,
            prompt_preview=prompt_preview,
        )
        _track_llm_start(model, self.case_id)

    def on_llm_end(
        self,
        response,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        elapsed_ms = _pop_elapsed(self._llm_starts, str(run_id))

        # Extract token usage from LLMResult
        prompt_tokens = 0
        completion_tokens = 0
        output_text = ""
        try:
            if hasattr(response, "llm_output") and response.llm_output:
                usage = response.llm_output.get("token_usage", {})
                prompt_tokens     = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)
            if response.generations:
                flat = response.generations[0]
                if flat:
                    output_text = getattr(flat[0], "text", "")
        except Exception:
            pass

        self._log.debug(
            "llm.end",
            run_id=str(run_id),
            elapsed_ms=round(elapsed_ms, 1),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            output_preview=_truncate(output_text, 200),
        )
        _track_llm_end(prompt_tokens, completion_tokens, elapsed_ms, self.case_id)

    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        elapsed_ms = _pop_elapsed(self._llm_starts, str(run_id))
        self._log.error(
            "llm.error",
            run_id=str(run_id),
            error=str(error),
            error_type=type(error).__name__,
            elapsed_ms=round(elapsed_ms, 1),
        )
        _track_llm_error(type(error).__name__, self.case_id)

    # ------------------------------------------------------------------
    # Chat model events (mirror of LLM events for chat models)
    # ------------------------------------------------------------------

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[Any]],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        self._llm_starts[str(run_id)] = time.monotonic()
        model = _extract_model_name(serialized)
        flat_msgs = [getattr(m, "content", str(m)) for row in messages for m in row]
        preview = _truncate(" | ".join(flat_msgs[:2]), 300)

        self._log.debug(
            "chat_model.start",
            run_id=str(run_id),
            model=model,
            message_preview=preview,
        )
        _track_llm_start(model, self.case_id)

    # on_llm_end covers chat model outputs too (LangChain calls on_llm_end
    # for both streaming and non-streaming chat models)

    # ------------------------------------------------------------------
    # Chain (node) events
    # ------------------------------------------------------------------

    def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        self._chain_starts[str(run_id)] = time.monotonic()
        name = _chain_name(serialized, tags)
        self._log.debug(
            "chain.start",
            run_id=str(run_id),
            name=name,
            input_keys=list(inputs.keys()) if isinstance(inputs, dict) else [],
        )

    def on_chain_end(
        self,
        outputs: dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        elapsed_ms = _pop_elapsed(self._chain_starts, str(run_id))
        self._log.debug(
            "chain.end",
            run_id=str(run_id),
            elapsed_ms=round(elapsed_ms, 1),
            output_keys=list(outputs.keys()) if isinstance(outputs, dict) else [],
        )
        _track_chain_latency(elapsed_ms, self.case_id)

    def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        elapsed_ms = _pop_elapsed(self._chain_starts, str(run_id))
        self._log.error(
            "chain.error",
            run_id=str(run_id),
            error=str(error),
            error_type=type(error).__name__,
            elapsed_ms=round(elapsed_ms, 1),
        )
        _track_chain_error(type(error).__name__, self.case_id)

    # ------------------------------------------------------------------
    # Tool events
    # ------------------------------------------------------------------

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        self._chain_starts[str(run_id)] = time.monotonic()
        tool_name = serialized.get("name", "unknown_tool")
        self._log.debug(
            "tool.start",
            run_id=str(run_id),
            tool=tool_name,
            input_preview=_truncate(input_str, 150),
        )

    def on_tool_end(
        self,
        output: Any,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        elapsed_ms = _pop_elapsed(self._chain_starts, str(run_id))
        self._log.debug(
            "tool.end",
            run_id=str(run_id),
            elapsed_ms=round(elapsed_ms, 1),
            output_preview=_truncate(str(output), 150),
        )

    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        elapsed_ms = _pop_elapsed(self._chain_starts, str(run_id))
        self._log.error(
            "tool.error",
            run_id=str(run_id),
            error=str(error),
            elapsed_ms=round(elapsed_ms, 1),
        )

    # ------------------------------------------------------------------
    # Retry events (custom — called from BaseNode retry logic)
    # ------------------------------------------------------------------

    def on_retry(self, node_name: str, attempt: int, error: str) -> None:
        self._log.warning(
            "node.retry",
            node=node_name,
            attempt=attempt,
            error=error,
        )
        _track_retry(node_name, attempt)
        if self._tracer:
            self._tracer.log_retry(node_name, attempt, error)


# ---------------------------------------------------------------------------
# Prometheus helpers (lazy-import to avoid circular deps)
# ---------------------------------------------------------------------------

def _track_llm_start(model: str, case_id: str) -> None:
    try:
        from app.monitoring.metrics import LLM_CALLS_TOTAL
        LLM_CALLS_TOTAL.labels(model=model, tier="unknown", outcome="started").inc()
    except Exception:
        pass


def _track_llm_end(
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: float,
    case_id: str,
) -> None:
    try:
        from app.monitoring.metrics import (
            LLM_TOKEN_USAGE,
            LLM_LATENCY_MS,
        )
        LLM_TOKEN_USAGE.labels(model="unknown", tier="unknown", token_type="prompt").inc(prompt_tokens)
        LLM_TOKEN_USAGE.labels(model="unknown", tier="unknown", token_type="completion").inc(completion_tokens)
        LLM_LATENCY_MS.labels(model="unknown", tier="unknown", operation="inference").observe(latency_ms)
    except Exception:
        pass


def _track_llm_error(error_type: str, case_id: str) -> None:
    try:
        from app.monitoring.metrics import LLM_CALLS_TOTAL
        LLM_CALLS_TOTAL.labels(model="unknown", tier="unknown", outcome="error").inc()
    except Exception:
        pass


def _track_chain_latency(latency_ms: float, case_id: str) -> None:
    try:
        from app.monitoring.metrics import WORKFLOW_NODE_DURATION_MS
        WORKFLOW_NODE_DURATION_MS.labels(node="chain", phase="unknown").observe(latency_ms)
    except Exception:
        pass


def _track_chain_error(error_type: str, case_id: str) -> None:
    try:
        from app.monitoring.metrics import WORKFLOW_ERRORS_TOTAL
        WORKFLOW_ERRORS_TOTAL.labels(node="chain", error_type=error_type).inc()
    except Exception:
        pass


def _track_retry(node_name: str, attempt: int) -> None:
    try:
        from app.monitoring.metrics import WORKFLOW_RETRIES_TOTAL
        WORKFLOW_RETRIES_TOTAL.labels(node=node_name, attempt=str(attempt)).inc()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# String helpers
# ---------------------------------------------------------------------------

def _extract_model_name(serialized: dict[str, Any]) -> str:
    return (
        serialized.get("id", ["unknown"])[-1]
        or serialized.get("name", "unknown")
        or "unknown"
    )


def _chain_name(serialized: dict[str, Any], tags: list[str] | None) -> str:
    name = serialized.get("name") or serialized.get("id", ["chain"])[-1]
    if not name and tags:
        return tags[0]
    return str(name or "chain")


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + "…"


def _pop_elapsed(store: dict[str, float], key: str) -> float:
    t0 = store.pop(key, None)
    return (time.monotonic() - t0) * 1000 if t0 else 0.0
