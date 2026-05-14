"""
LangGraph state reducer functions.

Reducers control how a state channel is updated when multiple nodes or
parallel branches write to the same key.  LangGraph calls:

    new_value = reducer(current_value, node_returned_value)

Conventions used here:
  - All reducers handle None inputs gracefully (called on initial state)
  - append_* functions are pure-append or dedup-append (no removal)
  - merge_dicts is a shallow last-write-wins merge for dict channels
  - operator.add works for int/float accumulator channels

The reducers are referenced by schema.py via Annotated[T, reducer_fn].
"""

from __future__ import annotations

import operator  # noqa: F401  — re-exported for use in schema.py

from app.services.workflow.state.models import (
    AuditEvent,
    ClarificationAttempt,
    ExtractedEntities,
    EvaluationResult,
    RawDocument,
    RetrievedPolicy,
    ReviewerAction,
)


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

def append_list(
    current: list | None,
    update: list | None,
) -> list:
    """
    Pure-append reducer: concatenate current and update lists.

    Used for audit_events, clarification_attempts, reviewer_actions.
    Never deduplicates — order reflects causal sequence.
    """
    return (current or []) + (update or [])


def merge_dicts(
    current: dict | None,
    update: dict | None,
) -> dict:
    """
    Shallow last-write-wins dict merge.

    Used for extracted_entities and evaluation_results keyed by document/policy ID.
    Existing keys are overwritten by the update; novel keys are added.
    """
    merged = dict(current or {})
    merged.update(update or {})
    return merged


# ---------------------------------------------------------------------------
# Document channel
# ---------------------------------------------------------------------------

def append_documents(
    current: list[RawDocument] | None,
    update: list[RawDocument] | None,
) -> list[RawDocument]:
    """
    Dedup-append reducer for raw_documents.

    A document with the same document_id replaces the existing entry so that
    status updates (PENDING → PROCESSED) are reflected correctly.
    """
    current_map: dict[str, RawDocument] = {
        d.document_id: d for d in (current or [])
    }
    for doc in update or []:
        current_map[doc.document_id] = doc   # upsert by document_id
    return list(current_map.values())


# ---------------------------------------------------------------------------
# Entities channel  (dict[document_id, ExtractedEntities])
# ---------------------------------------------------------------------------

def merge_entities(
    current: dict[str, ExtractedEntities] | None,
    update: dict[str, ExtractedEntities] | None,
) -> dict[str, ExtractedEntities]:
    """
    Merge extraction results by document_id (last write wins per document).

    Thin wrapper around merge_dicts — kept separate for readability and
    potential future type-checking divergence.
    """
    return merge_dicts(current, update)


# ---------------------------------------------------------------------------
# Policy channel
# ---------------------------------------------------------------------------

def append_policies(
    current: list[RetrievedPolicy] | None,
    update: list[RetrievedPolicy] | None,
) -> list[RetrievedPolicy]:
    """
    Dedup-append reducer for retrieved_policies.

    Deduplication key: policy_id + '::' + policy_version.
    Later retrieval results replace earlier ones for the same policy version
    (e.g., a re-retrieval with a different query that yields higher confidence).
    """
    current_map: dict[str, RetrievedPolicy] = {
        p.dedup_key: p for p in (current or [])
    }
    for policy in update or []:
        current_map[policy.dedup_key] = policy  # upsert by dedup_key
    # Sort by similarity_score descending so the best match is always first
    return sorted(current_map.values(), key=lambda p: p.similarity_score, reverse=True)


# ---------------------------------------------------------------------------
# Evaluation channel  (dict[dedup_key, EvaluationResult])
# ---------------------------------------------------------------------------

def merge_evaluations(
    current: dict[str, EvaluationResult] | None,
    update: dict[str, EvaluationResult] | None,
) -> dict[str, EvaluationResult]:
    """
    Merge evaluation results by policy dedup_key (last write wins).

    Re-evaluations (e.g., after a clarification round) overwrite the prior result.
    """
    return merge_dicts(current, update)


# ---------------------------------------------------------------------------
# Clarification channel
# ---------------------------------------------------------------------------

def append_clarifications(
    current: list[ClarificationAttempt] | None,
    update: list[ClarificationAttempt] | None,
) -> list[ClarificationAttempt]:
    """
    Pure-append reducer for clarification_attempts.

    Each attempt is a distinct round; we never overwrite prior attempts.
    Answered attempts keep their original ask_at for audit purposes.
    """
    return append_list(current, update)


# ---------------------------------------------------------------------------
# Reviewer action channel
# ---------------------------------------------------------------------------

def append_reviewer_actions(
    current: list[ReviewerAction] | None,
    update: list[ReviewerAction] | None,
) -> list[ReviewerAction]:
    """
    Pure-append reducer for reviewer_actions.

    Every reviewer action is permanent — overrides, escalations, and approvals
    all accumulate to provide a complete decision history.
    """
    return append_list(current, update)


# ---------------------------------------------------------------------------
# Audit event channel
# ---------------------------------------------------------------------------

def append_audit_events(
    current: list[AuditEvent] | None,
    update: list[AuditEvent] | None,
) -> list[AuditEvent]:
    """
    Pure-append reducer for audit_events.

    Audit events are strictly append-only; once emitted they must never be
    mutated or removed.  The ordering reflects the causal graph execution order
    (LangGraph guarantees node execution order within a branch).
    """
    return append_list(current, update)
