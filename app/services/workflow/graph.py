"""
PA Review LangGraph workflow — graph assembly and compilation.

Topology (edges):

    START
      │
      ▼
  ingestion_node ──(error/no docs)──────────────────────────────────────────┐
      │ ok                                                                    │
      ▼                                                                       │
  extraction_node ──(error/empty)───────────────────────────────────────────┤
      │ ok                                                                    │
      ▼                                                                       │
  retrieval_node ──(no policies)──► decision_node ◄─── human_review_node ◄─┐│
      │ ok                              │                 │  ▲   │           ││
      ▼                                 │      override   │  │   │ rework    ││
  reasoning_node ──(clarify needed)──► clarification_node │  │   │           ││
      │ no clarification needed         │ answered         │  │   ▼           ││
      │ ◄───────────────────────────────┘                  │  reasoning_node  ││
      ▼                                                     │                  ││
  human_review_node ──(interrupt)──────────────────────────┘                  ││
                                                                               ││
      all paths ──────────────────────────────────────────────────────────────►▼│
                                                                              audit_node
                                                                                │
                                                                               END

Interrupt nodes (LangGraph pauses here and waits for external input):
  - clarification_node  (raises NodeInterrupt, waits for provider answer)
  - human_review_node   (raises NodeInterrupt, waits for reviewer action)

Checkpointing:
  - Every node completion is checkpointed by the AsyncRedisSaver.
  - The compiled graph accepts a config with {"configurable": {"thread_id": case_id}}.

Visualization:
  - graph.get_graph().draw_mermaid()  → Mermaid diagram string
  - graph.get_graph().draw_png()      → PNG bytes (requires Pillow + pygraphviz)
  - graph.get_graph().draw_ascii()    → ASCII art (no deps)
"""

from __future__ import annotations

from typing import Any

import structlog
from langgraph.graph import END, StateGraph

from app.services.workflow.nodes import (
    audit_node,
    clarification_node,
    decision_node,
    extraction_node,
    human_review_node,
    ingestion_node,
    reasoning_node,
    retrieval_node,
)
from app.services.workflow.routing import (
    ROUTING_MAP,
    _AUDIT,
    _CLARIFICATION,
    _DECISION,
    _EXTRACTION,
    _HUMAN_REVIEW,
    _INGESTION,
    _REASONING,
    _RETRIEVAL,
    route_after_clarification,
    route_after_extraction,
    route_after_human_review,
    route_after_ingestion,
    route_after_reasoning,
    route_after_retrieval,
)
from app.services.workflow.state.checkpoint import AsyncRedisSaver
from app.services.workflow.state.schema import PAWorkflowState

logger = structlog.get_logger(__name__)

_AUDIT_NODE     = "audit_node"
_END            = END


def build_graph() -> StateGraph:
    """
    Construct and return the uncompiled StateGraph.

    Call compile_graph() to get a runnable CompiledGraph.
    Keeping them separate makes the raw graph available for
    visualization without requiring a live Redis connection.
    """
    graph = StateGraph(PAWorkflowState)

    # ------------------------------------------------------------------
    # Register nodes
    # ------------------------------------------------------------------
    graph.add_node(_INGESTION,     ingestion_node)
    graph.add_node(_EXTRACTION,    extraction_node)
    graph.add_node(_RETRIEVAL,     retrieval_node)
    graph.add_node(_REASONING,     reasoning_node)
    graph.add_node(_CLARIFICATION, clarification_node)
    graph.add_node(_HUMAN_REVIEW,  human_review_node)
    graph.add_node(_DECISION,      decision_node)
    graph.add_node(_AUDIT,         audit_node)

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------
    graph.set_entry_point(_INGESTION)

    # ------------------------------------------------------------------
    # Conditional edges
    # ------------------------------------------------------------------
    graph.add_conditional_edges(
        _INGESTION,
        route_after_ingestion,
        {_EXTRACTION: _EXTRACTION, _AUDIT: _AUDIT},
    )
    graph.add_conditional_edges(
        _EXTRACTION,
        route_after_extraction,
        {_RETRIEVAL: _RETRIEVAL, _AUDIT: _AUDIT},
    )
    graph.add_conditional_edges(
        _RETRIEVAL,
        route_after_retrieval,
        {_REASONING: _REASONING, _DECISION: _DECISION, _AUDIT: _AUDIT},
    )
    graph.add_conditional_edges(
        _REASONING,
        route_after_reasoning,
        {_CLARIFICATION: _CLARIFICATION, _HUMAN_REVIEW: _HUMAN_REVIEW, _AUDIT: _AUDIT},
    )
    graph.add_conditional_edges(
        _CLARIFICATION,
        route_after_clarification,
        {_RETRIEVAL: _RETRIEVAL, _HUMAN_REVIEW: _HUMAN_REVIEW, _AUDIT: _AUDIT},
    )
    graph.add_conditional_edges(
        _HUMAN_REVIEW,
        route_after_human_review,
        {
            _DECISION:      _DECISION,
            _REASONING:     _REASONING,
            _CLARIFICATION: _CLARIFICATION,
            _HUMAN_REVIEW:  _HUMAN_REVIEW,
            _AUDIT:         _AUDIT,
        },
    )

    # ------------------------------------------------------------------
    # Unconditional edges
    # ------------------------------------------------------------------
    graph.add_edge(_DECISION, _AUDIT)
    graph.add_edge(_AUDIT,    _END)

    return graph


def compile_graph(
    checkpointer: AsyncRedisSaver | None = None,
    *,
    interrupt_before: list[str] | None = None,
    interrupt_after: list[str] | None = None,
    callbacks: list | None = None,
):
    """
    Compile the workflow graph with the given checkpointer.

    Args:
        checkpointer:      AsyncRedisSaver instance.  If None, a fresh one is
                           created from settings (requires Redis connection).
        interrupt_before:  Node names to interrupt BEFORE execution.
        interrupt_after:   Node names to interrupt AFTER execution.

    Returns:
        A compiled LangGraph CompiledGraph ready for ainvoke / astream.

    Note:
        clarification_node and human_review_node use NodeInterrupt internally,
        so they do NOT need to appear in interrupt_before/after.  Those lists
        are available for additional explicit interrupt points if needed.
    """
    if checkpointer is None:
        checkpointer = AsyncRedisSaver.from_settings()

    graph = build_graph()

    compile_kwargs: dict[str, Any] = {"checkpointer": checkpointer}
    if interrupt_before:
        compile_kwargs["interrupt_before"] = interrupt_before
    if interrupt_after:
        compile_kwargs["interrupt_after"] = interrupt_after

    compiled = graph.compile(**compile_kwargs)

    if callbacks:
        try:
            compiled = compiled.with_config({"callbacks": callbacks})
        except Exception as exc:
            logger.warning("workflow.graph_callbacks_failed", error=str(exc))

    logger.info(
        "workflow.graph_compiled",
        nodes=list(compiled.nodes.keys()) if hasattr(compiled, "nodes") else "unknown",
        has_checkpointer=True,
    )
    return compiled


# ---------------------------------------------------------------------------
# Graph visualization helpers
# ---------------------------------------------------------------------------

def get_mermaid_diagram() -> str:
    """
    Return the workflow graph as a Mermaid diagram string.

    Usage:
        diagram = get_mermaid_diagram()
        # paste into https://mermaid.live or a markdown code block
    """
    graph = build_graph()
    try:
        return graph.get_graph().draw_mermaid()
    except Exception:
        return _FALLBACK_MERMAID


def get_ascii_diagram() -> str:
    """Return the workflow graph as an ASCII art diagram."""
    graph = build_graph()
    try:
        return graph.get_graph().draw_ascii()
    except Exception:
        return "(ASCII diagram not available)"


def get_png_diagram() -> bytes | None:
    """
    Return the workflow graph as PNG bytes.

    Requires: pip install pygraphviz Pillow
    Returns None if the dependencies are not available.
    """
    graph = build_graph()
    try:
        return graph.get_graph().draw_png()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Fallback Mermaid diagram (in case LangGraph cannot render it)
# ---------------------------------------------------------------------------

_FALLBACK_MERMAID = """
flowchart TD
    START([START])
    ING[ingestion_node]
    EXT[extraction_node]
    RET[retrieval_node]
    RSN[reasoning_node]
    CLA[clarification_node\nNodeInterrupt]
    HRV[human_review_node\nNodeInterrupt]
    DEC[decision_node]
    AUD[audit_node]
    END_([END])

    START --> ING
    ING -->|ok| EXT
    ING -->|error| AUD
    EXT -->|ok| RET
    EXT -->|error| AUD
    RET -->|policies found| RSN
    RET -->|no policies| DEC
    RET -->|error| AUD
    RSN -->|needs clarification| CLA
    RSN -->|ready| HRV
    RSN -->|error| AUD
    CLA -->|answered| RET
    CLA -->|timeout| HRV
    HRV -->|decided| DEC
    HRV -->|rework| RSN
    HRV -->|clarify| RSN
    DEC --> AUD
    AUD --> END_

    classDef interrupt fill:#f9a825,color:#000
    class CLA,HRV interrupt
""".strip()
