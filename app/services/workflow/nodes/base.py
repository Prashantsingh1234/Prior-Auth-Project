"""
Base node utilities for the PA LangGraph workflow.

Provides:
  - NodeInterrupt — cross-version compatible import
  - BaseNode      — abstract base with __call__ wiring, logging, error handling
  - with_retry    — tenacity decorator factory for LLM / API node methods
  - NodeContext   — thin dataclass threading case_id + step into helpers

All concrete node modules must define an async function or a callable instance
with signature:  async def node_fn(state: PAWorkflowState) -> dict[str, Any]

Example (function-style):
    from app.services.workflow.nodes.base import BaseNode, NodeContext

    class ExtractionNode(BaseNode):
        node_name = "extraction_node"

        async def execute(self, state, ctx) -> dict:
            ...
            return mutations.with_extracted_entities(...)

    extraction_node = ExtractionNode()   # callable passed to graph.add_node
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.services.workflow.state import mutations
from app.services.workflow.state.audit import AuditContext
from app.services.workflow.state.schema import PAWorkflowState

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Cross-version compatible NodeInterrupt
# ---------------------------------------------------------------------------

try:
    from langgraph.errors import NodeInterrupt  # langgraph 0.1.x – 0.2.x
except ImportError:
    try:
        from langgraph.types import NodeInterrupt  # some 0.2.x builds
    except ImportError:
        class NodeInterrupt(BaseException):  # type: ignore[no-redef]
            """
            Fallback definition.  Signals that a node requires external input
            before it can continue. LangGraph intercepts this and persists a
            checkpoint so execution can be resumed later.
            """

            def __init__(self, value: Any = None) -> None:
                self.value = value
                super().__init__(str(value))


# ---------------------------------------------------------------------------
# Retry decorator factory for LLM / external API calls
# ---------------------------------------------------------------------------

def with_retry(
    *,
    max_attempts: int = 3,
    min_wait: float = 2.0,
    max_wait: float = 30.0,
    retry_exceptions: tuple = (Exception,),
):
    """
    Return a tenacity retry decorator for async LLM node methods.

    Usage:
        @with_retry(max_attempts=3, retry_exceptions=(RateLimitError, APITimeoutError))
        async def _call_llm(self, prompt: str) -> dict:
            ...
    """
    return retry(
        retry=retry_if_exception_type(retry_exceptions),
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
        reraise=True,
    )


# ---------------------------------------------------------------------------
# Node context — binds case_id + step for log/audit helpers
# ---------------------------------------------------------------------------

@dataclass
class NodeContext:
    """
    Thin wrapper passed from __call__ into execute().

    Provides:
      - audit_ctx  : AuditContext for emitting structured audit events
      - log        : bound structlog logger with case_id pre-set
      - elapsed_ms : wall-clock ms since the node was invoked
    """

    node_name: str
    case_id: str
    step: int = 0
    _t0: float = field(default_factory=time.monotonic, repr=False)

    @property
    def audit_ctx(self) -> AuditContext:
        return AuditContext(node_name=self.node_name, step=self.step, _t0=self._t0)

    @property
    def log(self):
        return structlog.get_logger(self.node_name).bind(
            case_id=self.case_id, node=self.node_name
        )

    def elapsed_ms(self) -> float:
        return (time.monotonic() - self._t0) * 1000


# ---------------------------------------------------------------------------
# Abstract base node
# ---------------------------------------------------------------------------

class BaseNode(ABC):
    """
    Abstract base class for all PA workflow graph nodes.

    Subclasses must:
      1. Set `node_name` as a class variable.
      2. Implement `async execute(state, nctx) -> dict[str, Any]`.

    __call__ handles:
      - NodeContext creation
      - structured logging (start / complete / error)
      - top-level error capture → with_error state patch
      - NodeInterrupt pass-through (never caught)
    """

    node_name: str = "base_node"

    def __init__(self) -> None:
        self._log = structlog.get_logger(self.__class__.__name__)

    async def __call__(self, state: PAWorkflowState) -> dict[str, Any]:
        case_id = state.get("case_id", "unknown")
        step    = state.get("retry_count", 0)  # use retry_count as a proxy for step

        nctx = NodeContext(node_name=self.node_name, case_id=case_id, step=step)
        nctx.log.info(f"{self.node_name}.started")

        try:
            result = await self.execute(state, nctx)
            nctx.log.info(
                f"{self.node_name}.completed",
                elapsed_ms=round(nctx.elapsed_ms(), 1),
            )
            return result

        except NodeInterrupt:
            # Interrupts are NOT errors — pass them through so LangGraph can
            # persist the checkpoint and surface the interrupt payload to the caller.
            nctx.log.info(f"{self.node_name}.interrupted")
            raise

        except Exception as exc:
            nctx.log.error(
                f"{self.node_name}.error",
                error=str(exc),
                exc_type=type(exc).__name__,
                exc_info=True,
            )
            return mutations.with_error(
                str(exc), nctx.audit_ctx, exc_type=type(exc).__name__
            )

    @abstractmethod
    async def execute(
        self,
        state: PAWorkflowState,
        nctx: NodeContext,
    ) -> dict[str, Any]:
        """Node logic.  Return a partial state dict."""
        ...
