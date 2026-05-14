"""
PA Review LangGraph workflow package.

Complete prior authorization review workflow implemented as a directed
acyclic (with cycles) LangGraph StateGraph.

────────────────────────────────────────────────────────────────────────────
Quick start
────────────────────────────────────────────────────────────────────────────

    from app.services.workflow import WorkflowRunner
    from app.services.workflow.state import initial_state, RawDocument

    # 1. Create runner (builds + compiles graph from settings)
    runner = WorkflowRunner.from_settings()

    # 2. Start a new PA case
    result = await runner.run(
        case_id="PA-2024-00001",
        documents=[
            RawDocument(
                document_id="doc-001",
                mime_type="application/pdf",
                content=pdf_bytes,
            )
        ],
        pa_request_id="REQ-001",
        service_type="Continuous Glucose Monitor",
    )

    # 3. Handle interrupts
    if result.is_interrupted:
        if result.interrupt_type == "clarification_required":
            # Present result.interrupt_payload["question"] to provider
            # When answered:
            result = await runner.resume_clarification(
                case_id, attempt_id, response_text
            )
        elif result.interrupt_type == "human_review_required":
            # Present result.interrupt_payload to reviewer UI
            # When decided:
            from app.services.workflow.state import ReviewerAction, ReviewerActionType
            result = await runner.resume_review(
                case_id,
                ReviewerAction(
                    reviewer_id="dr-smith",
                    action_type=ReviewerActionType.APPROVE,
                    notes="Criteria clearly met.",
                ),
            )

    # 4. Final result
    if result.is_complete:
        print(result.recommendation.recommendation_type)

────────────────────────────────────────────────────────────────────────────
Package layout
────────────────────────────────────────────────────────────────────────────

    workflow/
    ├── state/          State schema, models, reducers, mutations, checkpoint
    ├── nodes/          Individual graph node implementations
    ├── routing.py      Conditional edge routing functions
    ├── graph.py        StateGraph assembly and compilation
    └── runner.py       WorkflowRunner high-level API
"""

from app.services.workflow.graph import (
    build_graph,
    compile_graph,
    get_ascii_diagram,
    get_mermaid_diagram,
    get_png_diagram,
)
from app.services.workflow.runner import WorkflowResult, WorkflowRunner
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
    # Primary interface
    "WorkflowRunner",
    "WorkflowResult",
    # State
    "PAWorkflowState",
    "WorkflowPhase",
    "initial_state",
    "state_summary",
    "mutations",
    "AuditContext",
    # Graph
    "build_graph",
    "compile_graph",
    "get_mermaid_diagram",
    "get_ascii_diagram",
    "get_png_diagram",
    # Checkpointer
    "AsyncRedisSaver",
]
