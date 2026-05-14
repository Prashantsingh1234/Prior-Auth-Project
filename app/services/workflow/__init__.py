"""
LangGraph workflow package.

The workflow package orchestrates the full PA review lifecycle as a
directed graph where each node is an async Python function and state
flows through typed channels with defined reducers.

Subpackages:
  state/    — PAWorkflowState schema, models, reducers, mutations,
              audit utilities, and the AsyncRedisSaver checkpointer.

Future subpackages (built in subsequent steps):
  nodes/    — Individual graph node implementations
              (ingestion, extraction, retrieval, evaluation, etc.)
  graph.py  — StateGraph assembly, edge definitions, conditional routing
  runner.py — High-level async runner (invoke, stream, resume)
"""

from app.services.workflow.state import (
    AsyncRedisSaver,
    AuditContext,
    PAWorkflowState,
    WorkflowPhase,
    initial_state,
    mutations,
    state_summary,
)

__all__ = [
    "PAWorkflowState",
    "WorkflowPhase",
    "initial_state",
    "state_summary",
    "mutations",
    "AuditContext",
    "AsyncRedisSaver",
]
