"""
LangGraph typed state schema for the PA Review workflow.

PAWorkflowState is the single source of truth passed between every graph node.
Each field is typed and annotated with a reducer that governs how node outputs
are merged into the current state.

Design principles:
  1. Typed — every channel has an explicit Python type.
  2. Reducer-controlled — mutable channels use Annotated[T, reducer_fn].
     Channels without a reducer are last-write-wins (LangGraph default).
  3. Serializable — all types are JSON-safe (Pydantic models + primitives).
  4. Audit-complete — every state mutation must emit at least one AuditEvent.
  5. Optional fields default to None so initial_state() never raises
     EmptyChannelError.

Reducer summary
───────────────
Channel                   Reducer              Behaviour
raw_documents             append_documents     Upsert by document_id
extracted_entities        merge_entities       Dict merge, doc-id keyed
retrieved_policies        append_policies      Upsert + sort by score
evaluation_results        merge_evaluations    Dict merge, policy-key keyed
clarification_attempts    append_clarifications Pure append
reviewer_actions          append_reviewer_actions Pure append
audit_events              append_audit_events  Pure append (immutable log)
tokens_used               operator.add         Running sum
processing_ms             operator.add         Running sum
"""

from __future__ import annotations

import operator
from datetime import datetime
from typing import Annotated, Any

from typing_extensions import TypedDict

from app.services.workflow.state.models import (
    AuditEvent,
    AuditMetadata,
    ClarificationAttempt,
    ExtractedEntities,
    EvaluationResult,
    PARecommendation,
    RawDocument,
    RetrievedPolicy,
    ReviewerAction,
    WorkflowPhase,
)
from app.services.workflow.state.reducers import (
    append_audit_events,
    append_clarifications,
    append_documents,
    append_policies,
    append_reviewer_actions,
    merge_entities,
    merge_evaluations,
)


class PAWorkflowState(TypedDict, total=False):
    """
    Complete shared state for a single PA review workflow instance.

    total=False: all keys are optional so that nodes can return partial
    updates without specifying every channel.  LangGraph merges partials
    via the configured reducers; missing keys leave the current value unchanged.

    ┌─────────────────────────────────────────────────────────┐
    │  IDENTITY          │  Who / what is being reviewed       │
    │  DOCUMENTS         │  Raw input material                 │
    │  EXTRACTION        │  Structured medical entities        │
    │  RETRIEVAL         │  Matching policy criteria           │
    │  EVALUATION        │  Criteria met / not met             │
    │  CLARIFICATION     │  Back-and-forth with submitter      │
    │  DECISION          │  AI recommendation + rationale      │
    │  REVIEW            │  Human reviewer actions             │
    │  AUDIT             │  Append-only event log + metadata   │
    │  CONTROL           │  Phase, error, retry signals        │
    └─────────────────────────────────────────────────────────┘
    """

    # ------------------------------------------------------------------
    # IDENTITY
    # ------------------------------------------------------------------
    case_id:          str           # PA case identifier — immutable after creation
    pa_request_id:    str | None    # Upstream request identifier (from API layer)
    member_id:        str | None    # Insurance member ID
    payer_id:         str | None    # Insurance company identifier
    service_type:     str | None    # Clinical service being authorized
    requesting_npi:   str | None    # Provider NPI submitting the request

    # ------------------------------------------------------------------
    # DOCUMENTS  (reducer: upsert by document_id)
    # ------------------------------------------------------------------
    raw_documents: Annotated[list[RawDocument], append_documents]

    # ------------------------------------------------------------------
    # EXTRACTION  (reducer: dict merge keyed by document_id)
    # ------------------------------------------------------------------
    extracted_entities: Annotated[dict[str, ExtractedEntities], merge_entities]

    # ------------------------------------------------------------------
    # RETRIEVAL  (reducer: upsert by policy_id+version, sort by score)
    # ------------------------------------------------------------------
    retrieved_policies: Annotated[list[RetrievedPolicy], append_policies]

    # ------------------------------------------------------------------
    # EVALUATION  (reducer: dict merge keyed by policy dedup_key)
    # ------------------------------------------------------------------
    evaluation_results: Annotated[dict[str, EvaluationResult], merge_evaluations]

    # ------------------------------------------------------------------
    # CLARIFICATION  (reducer: pure append)
    # ------------------------------------------------------------------
    clarification_attempts:     Annotated[list[ClarificationAttempt], append_clarifications]
    max_clarification_attempts: int     # Configurable ceiling (default 3)

    # ------------------------------------------------------------------
    # DECISION  (last-write-wins — set once by the recommendation node)
    # ------------------------------------------------------------------
    recommendation: PARecommendation | None
    rationale:      list[str]           # Ordered reasoning steps

    # ------------------------------------------------------------------
    # HUMAN REVIEW  (reducer: pure append — every action is permanent)
    # ------------------------------------------------------------------
    reviewer_actions: Annotated[list[ReviewerAction], append_reviewer_actions]

    # ------------------------------------------------------------------
    # AUDIT  (reducers: append-only event log + running totals)
    # ------------------------------------------------------------------
    audit_events:    Annotated[list[AuditEvent], append_audit_events]
    audit_metadata:  AuditMetadata          # Workflow-level metadata (last-write-wins)
    tokens_used:     Annotated[int,   operator.add]  # Cumulative LLM tokens
    processing_ms:   Annotated[float, operator.add]  # Cumulative wall-clock ms

    # ------------------------------------------------------------------
    # CONTROL FLOW  (last-write-wins)
    # ------------------------------------------------------------------
    workflow_phase:    WorkflowPhase
    error:             str | None       # Set by any node on unrecoverable failure
    retry_count:       int              # Incremented by retry logic nodes
    requires_review:   bool             # True when AI confidence < threshold


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def initial_state(
    case_id: str,
    *,
    pa_request_id: str | None = None,
    member_id: str | None = None,
    payer_id: str | None = None,
    service_type: str | None = None,
    requesting_npi: str | None = None,
    max_clarification_attempts: int = 3,
    workflow_version: str = "1.0",
    langsmith_run_id: str | None = None,
) -> PAWorkflowState:
    """
    Create a fully initialised empty state for a new PA case.

    All accumulator channels start empty/zero.
    All optional single-value channels start as None.

    Usage:
        state = initial_state(case_id="PA-2024-00001")
        graph.invoke(state, config={"configurable": {"thread_id": case_id}})
    """
    return PAWorkflowState(
        # Identity
        case_id=case_id,
        pa_request_id=pa_request_id,
        member_id=member_id,
        payer_id=payer_id,
        service_type=service_type,
        requesting_npi=requesting_npi,
        # Documents
        raw_documents=[],
        # Extraction
        extracted_entities={},
        # Retrieval
        retrieved_policies=[],
        # Evaluation
        evaluation_results={},
        # Clarification
        clarification_attempts=[],
        max_clarification_attempts=max_clarification_attempts,
        # Decision
        recommendation=None,
        rationale=[],
        # Review
        reviewer_actions=[],
        # Audit
        audit_events=[],
        audit_metadata=AuditMetadata(
            workflow_version=workflow_version,
            langsmith_run_id=langsmith_run_id,
        ),
        tokens_used=0,
        processing_ms=0.0,
        # Control
        workflow_phase=WorkflowPhase.INGESTION,
        error=None,
        retry_count=0,
        requires_review=False,
    )


# ---------------------------------------------------------------------------
# State inspection helpers
# ---------------------------------------------------------------------------

def current_clarification_count(state: PAWorkflowState) -> int:
    """Number of clarification rounds attempted so far."""
    return len(state.get("clarification_attempts", []))


def clarification_exhausted(state: PAWorkflowState) -> bool:
    """True when the case has reached its clarification limit."""
    return current_clarification_count(state) >= state.get(
        "max_clarification_attempts", 3
    )


def has_recommendation(state: PAWorkflowState) -> bool:
    return state.get("recommendation") is not None


def is_terminal(state: PAWorkflowState) -> bool:
    """True when the workflow has reached a terminal phase (completed or failed)."""
    return state.get("workflow_phase") in (
        WorkflowPhase.COMPLETED,
        WorkflowPhase.FAILED,
    )


def latest_reviewer_action(state: PAWorkflowState) -> ReviewerAction | None:
    actions = state.get("reviewer_actions", [])
    return actions[-1] if actions else None


def total_documents(state: PAWorkflowState) -> int:
    return len(state.get("raw_documents", []))


def all_documents_processed(state: PAWorkflowState) -> bool:
    from app.services.workflow.state.models import DocumentStatus
    docs = state.get("raw_documents", [])
    return bool(docs) and all(d.status == DocumentStatus.PROCESSED for d in docs)


def get_best_policy(state: PAWorkflowState) -> RetrievedPolicy | None:
    """Return the highest-scoring retrieved policy."""
    policies = state.get("retrieved_policies", [])
    return policies[0] if policies else None   # already sorted by score


def combined_icd_codes(state: PAWorkflowState) -> list[str]:
    """Collect all unique ICD codes extracted across all documents."""
    codes: set[str] = set()
    for entities in state.get("extracted_entities", {}).values():
        for code in entities.icd_codes:
            codes.add(code.code)
    return sorted(codes)


def combined_cpt_codes(state: PAWorkflowState) -> list[str]:
    """Collect all unique CPT codes extracted across all documents."""
    codes: set[str] = set()
    for entities in state.get("extracted_entities", {}).values():
        for code in entities.cpt_codes:
            codes.add(code.code)
    return sorted(codes)


def state_summary(state: PAWorkflowState) -> dict[str, Any]:
    """Return a lightweight summary dict suitable for logging."""
    return {
        "case_id":            state.get("case_id"),
        "phase":              state.get("workflow_phase"),
        "documents":          total_documents(state),
        "extracted_docs":     len(state.get("extracted_entities", {})),
        "policies_retrieved": len(state.get("retrieved_policies", [])),
        "criteria_evaluated": len(state.get("evaluation_results", {})),
        "clarifications":     current_clarification_count(state),
        "has_recommendation": has_recommendation(state),
        "reviewer_actions":   len(state.get("reviewer_actions", [])),
        "audit_events":       len(state.get("audit_events", [])),
        "tokens_used":        state.get("tokens_used", 0),
        "processing_ms":      state.get("processing_ms", 0.0),
        "error":              state.get("error"),
    }
