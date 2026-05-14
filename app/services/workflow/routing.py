"""
Conditional edge routing functions for the PA LangGraph workflow.

Each function receives the current state and returns a string that names
the next node.  LangGraph's add_conditional_edges() maps these strings to
actual node names.

Routing table summary
─────────────────────
Source node          Possible targets
────────────────────────────────────────────────────────────────────
ingestion_node    → extraction_node  | audit_node
extraction_node   → retrieval_node   | audit_node
retrieval_node    → reasoning_node   | decision_node | audit_node
reasoning_node    → clarification_node | human_review_node | audit_node
clarification_node→ retrieval_node   | human_review_node
human_review_node → decision_node    | clarification_node | reasoning_node
decision_node     → audit_node  (unconditional)
audit_node        → END         (unconditional)
"""

from __future__ import annotations

import structlog

from app.services.workflow.state.models import (
    ClarificationStatus,
    DocumentStatus,
    ReviewerActionType,
    WorkflowPhase,
)
from app.services.workflow.state.schema import (
    PAWorkflowState,
    clarification_exhausted,
)

logger = structlog.get_logger(__name__)

# Sentinel string constants — must match node names used in graph.add_node()
_INGESTION       = "ingestion_node"
_EXTRACTION      = "extraction_node"
_RETRIEVAL       = "retrieval_node"
_REASONING       = "reasoning_node"
_CLARIFICATION   = "clarification_node"
_HUMAN_REVIEW    = "human_review_node"
_DECISION        = "decision_node"
_AUDIT           = "audit_node"


# ---------------------------------------------------------------------------
# After ingestion
# ---------------------------------------------------------------------------

def route_after_ingestion(state: PAWorkflowState) -> str:
    """
    Route after the ingestion node.

    → extraction_node  if at least one document was successfully parsed
    → audit_node       if all documents failed or a hard error occurred
    """
    if state.get("error"):
        logger.warning("routing.ingestion→audit (error)", case_id=state.get("case_id"))
        return _AUDIT

    processed = [
        d for d in state.get("raw_documents", [])
        if d.status == DocumentStatus.PROCESSED
    ]
    if not processed:
        logger.warning("routing.ingestion→audit (no docs)", case_id=state.get("case_id"))
        return _AUDIT

    return _EXTRACTION


# ---------------------------------------------------------------------------
# After extraction
# ---------------------------------------------------------------------------

def route_after_extraction(state: PAWorkflowState) -> str:
    """
    Route after the extraction node.

    → retrieval_node  if at least one document yielded extracted entities
    → audit_node      on error or empty extraction
    """
    if state.get("error"):
        return _AUDIT

    if not state.get("extracted_entities"):
        logger.warning("routing.extraction→audit (no entities)", case_id=state.get("case_id"))
        return _AUDIT

    return _RETRIEVAL


# ---------------------------------------------------------------------------
# After retrieval
# ---------------------------------------------------------------------------

def route_after_retrieval(state: PAWorkflowState) -> str:
    """
    Route after the retrieval node.

    → reasoning_node  if policy criteria were retrieved
    → decision_node   if no policies found (auto-deny / pend)
    → audit_node      on hard error
    """
    if state.get("error"):
        return _AUDIT

    if not state.get("retrieved_policies"):
        logger.warning(
            "routing.retrieval→decision (no policies)",
            case_id=state.get("case_id"),
        )
        return _DECISION

    return _REASONING


# ---------------------------------------------------------------------------
# After reasoning
# ---------------------------------------------------------------------------

def route_after_reasoning(state: PAWorkflowState) -> str:
    """
    Route after the reasoning node.

    → clarification_node   if undetermined criteria exist AND clarification
                           not exhausted (pending attempt created by reasoning)
    → human_review_node    if criteria evaluated and human review needed
    → audit_node           on hard error
    """
    if state.get("error"):
        return _AUDIT

    # Reasoning node sets phase=CLARIFICATION when it creates a pending attempt
    if state.get("workflow_phase") == WorkflowPhase.CLARIFICATION:
        # Confirm there is actually a pending clarification
        attempts = state.get("clarification_attempts", [])
        has_pending = any(a.status == ClarificationStatus.PENDING for a in attempts)
        if has_pending:
            return _CLARIFICATION

    return _HUMAN_REVIEW


# ---------------------------------------------------------------------------
# After clarification
# ---------------------------------------------------------------------------

def route_after_clarification(state: PAWorkflowState) -> str:
    """
    Route after the clarification node.

    → retrieval_node   if the clarification was answered (re-run retrieval
                       with enriched clinical context)
    → human_review_node if clarification timed out or was skipped
    """
    if state.get("error"):
        return _AUDIT

    # Phase was set by the clarification node
    phase = state.get("workflow_phase")
    if phase == WorkflowPhase.RETRIEVAL:
        return _RETRIEVAL

    # Timeout or skipped → proceed to human review
    return _HUMAN_REVIEW


# ---------------------------------------------------------------------------
# After human review
# ---------------------------------------------------------------------------

def route_after_human_review(state: PAWorkflowState) -> str:
    """
    Route after the human review node.

    → decision_node       if the reviewer made a final determination
    → clarification_node  if the reviewer requested clarification
    → reasoning_node      if the reviewer returned the case for rework
    → audit_node          on hard error
    """
    if state.get("error"):
        return _AUDIT

    reviewer_actions = state.get("reviewer_actions", [])
    if not reviewer_actions:
        # Still waiting — should not happen (NodeInterrupt should have fired)
        return _HUMAN_REVIEW

    latest_action = reviewer_actions[-1]
    action_type = latest_action.action_type

    if action_type == ReviewerActionType.REQUEST_CLARIFICATION:
        if not clarification_exhausted(state):
            # Reviewer wants clarification — but reasoning_node needs to generate the question
            # Route back to reasoning for one more pass
            return _REASONING
        # Clarification exhausted — proceed to decision with current info
        return _DECISION

    if action_type == ReviewerActionType.RETURN_FOR_REWORK:
        return _REASONING

    # Approve, Deny, Pend, Override, Escalate → decision
    return _DECISION


# ---------------------------------------------------------------------------
# Routing map (used by graph.py for add_conditional_edges)
# ---------------------------------------------------------------------------

ROUTING_MAP: dict[str, tuple] = {
    _INGESTION:    (route_after_ingestion,    {_EXTRACTION: _EXTRACTION, _AUDIT: _AUDIT}),
    _EXTRACTION:   (route_after_extraction,   {_RETRIEVAL: _RETRIEVAL, _AUDIT: _AUDIT}),
    _RETRIEVAL:    (route_after_retrieval,    {_REASONING: _REASONING, _DECISION: _DECISION, _AUDIT: _AUDIT}),
    _REASONING:    (route_after_reasoning,    {_CLARIFICATION: _CLARIFICATION, _HUMAN_REVIEW: _HUMAN_REVIEW, _AUDIT: _AUDIT}),
    _CLARIFICATION:(route_after_clarification,{_RETRIEVAL: _RETRIEVAL, _HUMAN_REVIEW: _HUMAN_REVIEW, _AUDIT: _AUDIT}),
    _HUMAN_REVIEW: (route_after_human_review, {_DECISION: _DECISION, _REASONING: _REASONING, _CLARIFICATION: _CLARIFICATION, _HUMAN_REVIEW: _HUMAN_REVIEW, _AUDIT: _AUDIT}),
}
