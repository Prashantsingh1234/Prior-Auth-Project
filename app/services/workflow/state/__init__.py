"""
LangGraph workflow state package.

Public surface:

    from app.services.workflow.state import (
        # State schema
        PAWorkflowState, initial_state,

        # Domain models
        WorkflowPhase, RawDocument, ExtractedEntities, RetrievedPolicy,
        PolicyChunk, CriterionEvaluation, EvaluationResult,
        ClarificationAttempt, PARecommendation, ReviewerAction,
        AuditEvent, AuditMetadata,

        # Enums
        DocumentStatus, ClarificationStatus, RecommendationType,
        ReviewerActionType, AuditEventType, CriterionMet,

        # Reducers (needed when building custom graphs)
        append_documents, merge_entities, append_policies,
        merge_evaluations, append_clarifications,
        append_reviewer_actions, append_audit_events,

        # Audit utilities
        AuditContext, NodeTimer, create_audit_event,
        create_phase_transition_event, create_error_event,

        # State mutations
        mutations,

        # Checkpointer
        AsyncRedisSaver,

        # Inspection helpers
        initial_state, state_summary, is_terminal,
        has_recommendation, clarification_exhausted,
        get_best_policy, combined_icd_codes, combined_cpt_codes,
    )
"""

from app.services.workflow.state.audit import (
    AuditContext,
    NodeTimer,
    create_audit_event,
    create_error_event,
    create_phase_transition_event,
)
from app.services.workflow.state.checkpoint import AsyncRedisSaver
from app.services.workflow.state.models import (
    AuditEvent,
    AuditEventType,
    AuditMetadata,
    ClarificationAttempt,
    ClarificationStatus,
    CriterionEvaluation,
    CriterionMet,
    DocumentStatus,
    EvaluationResult,
    ExtractedEntities,
    PARecommendation,
    PolicyChunk,
    RawDocument,
    RecommendationType,
    RetrievedPolicy,
    ReviewerAction,
    ReviewerActionType,
    WorkflowPhase,
)
from app.services.workflow.state.reducers import (
    append_audit_events,
    append_clarifications,
    append_documents,
    append_list,
    append_policies,
    append_reviewer_actions,
    merge_dicts,
    merge_entities,
    merge_evaluations,
)
from app.services.workflow.state.schema import (
    PAWorkflowState,
    all_documents_processed,
    clarification_exhausted,
    combined_cpt_codes,
    combined_icd_codes,
    current_clarification_count,
    get_best_policy,
    has_recommendation,
    initial_state,
    is_terminal,
    latest_reviewer_action,
    state_summary,
    total_documents,
)
from app.services.workflow.state import mutations

__all__ = [
    # Schema
    "PAWorkflowState",
    "initial_state",
    # Inspection helpers
    "state_summary",
    "is_terminal",
    "has_recommendation",
    "clarification_exhausted",
    "current_clarification_count",
    "all_documents_processed",
    "get_best_policy",
    "combined_icd_codes",
    "combined_cpt_codes",
    "total_documents",
    "latest_reviewer_action",
    # Models
    "WorkflowPhase",
    "RawDocument",
    "DocumentStatus",
    "ExtractedEntities",
    "RetrievedPolicy",
    "PolicyChunk",
    "CriterionEvaluation",
    "CriterionMet",
    "EvaluationResult",
    "ClarificationAttempt",
    "ClarificationStatus",
    "PARecommendation",
    "RecommendationType",
    "ReviewerAction",
    "ReviewerActionType",
    "AuditEvent",
    "AuditEventType",
    "AuditMetadata",
    # Reducers
    "append_documents",
    "merge_entities",
    "append_policies",
    "merge_evaluations",
    "append_clarifications",
    "append_reviewer_actions",
    "append_audit_events",
    "append_list",
    "merge_dicts",
    # Audit
    "AuditContext",
    "NodeTimer",
    "create_audit_event",
    "create_phase_transition_event",
    "create_error_event",
    # Mutations module
    "mutations",
    # Checkpointer
    "AsyncRedisSaver",
]
