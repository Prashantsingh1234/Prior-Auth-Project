"""
app.tracing — LangSmith + observability integration for the PA workflow.

Public API
----------
configure_langsmith()           Set LANGCHAIN_* env vars, verify connectivity
get_langsmith_config()          Return the cached LangSmithConfig
LangSmithConfig                 Dataclass: enabled, api_key, project, endpoint

WorkflowTracer                  Per-request LangSmith RunTree manager
  .for_case(case_id)            Class-method factory
  .start_workflow(inputs, ...)  Open top-level chain run → returns run_id
  .end_workflow(outputs, error) Close top-level run
  .start_node(name, state, ...) Open child node run → returns node_run_id
  .end_node(name, patch, error) Close node run → returns elapsed_ms
  .log_interrupt(...)           Attach interrupt metadata to active node run
  .log_retry(...)               Attach retry metadata to active node run
  .log_token_usage(...)         Attach token counts to active node run
  .trace_node(name, state)      Async context manager (start + end)

PAWorkflowCallbackHandler       LangChain-compatible callback handler
  on_llm_start / on_llm_end     LLM lifecycle events
  on_chat_model_start           Chat model events
  on_chain_start / on_chain_end Chain (node) events
  on_tool_start / on_tool_end   Tool events
  on_retry                      Custom retry hook (called from BaseNode)

trace_node                      @trace_node() decorator for execute() methods
trace_llm_call                  @trace_llm_call() decorator for LLM helpers

LangSmithTracingMiddleware      Starlette middleware (HTTP header propagation)
get_request_run_id()            Read active run-id from contextvar
set_request_run_id(run_id)      Write run-id into contextvar

WorkflowHooks                   Abstract base for lifecycle hooks
DefaultWorkflowHooks            structlog + Prometheus implementation
CompositeWorkflowHooks          Fan-out to multiple hook sets
"""

from app.tracing.callbacks import PAWorkflowCallbackHandler
from app.tracing.config import (
    LangSmithConfig,
    configure_langsmith,
    get_langsmith_config,
)
from app.tracing.decorators import trace_llm_call, trace_node
from app.tracing.middleware import (
    LangSmithTracingMiddleware,
    get_request_run_id,
    set_request_run_id,
)
from app.tracing.tracer import WorkflowTracer
from app.tracing.workflow_hooks import (
    CompositeWorkflowHooks,
    DefaultWorkflowHooks,
    WorkflowHooks,
)

__all__ = [
    # Config
    "LangSmithConfig",
    "configure_langsmith",
    "get_langsmith_config",
    # Tracer
    "WorkflowTracer",
    # Callback handler
    "PAWorkflowCallbackHandler",
    # Decorators
    "trace_node",
    "trace_llm_call",
    # Middleware
    "LangSmithTracingMiddleware",
    "get_request_run_id",
    "set_request_run_id",
    # Hooks
    "WorkflowHooks",
    "DefaultWorkflowHooks",
    "CompositeWorkflowHooks",
]
