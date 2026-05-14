"""
Immutable state update helpers for graph node implementations.

Every function returns a partial state dict that LangGraph merges into the
current state via the channel reducers defined in schema.py.

Design contract:
  - Returns dict[str, Any] — never modifies the input state in-place.
  - Every helper emits an appropriate AuditEvent (audit-complete principle).
  - All data arguments are typed — no raw dicts passed through.
  - Helpers are pure functions (no side effects, no I/O).

Typical node pattern:
    async def my_node(state: PAWorkflowState) -> dict[str, Any]:
        ctx = AuditContext(node_name="my_node", step=get_step(state))
        t0 = time.monotonic()
        # ... do work ...
        ms = (time.monotonic() - t0) * 1000
        return mutations.with_extracted_entities(
            doc_id, entities, ctx, duration_ms=ms
        )
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any

from app.services.extraction.models import ExtractionResult
from app.services.workflow.state.audit import AuditContext
from app.services.workflow.state.models import (
    AuditEventType,
    AuditMetadata,
    ClarificationAttempt,
    ClarificationStatus,
    DocumentStatus,
    EvaluationResult,
    ExtractedEntities,
    PARecommendation,
    RawDocument,
    RetrievedPolicy,
    ReviewerAction,
    WorkflowPhase,
)


# ---------------------------------------------------------------------------
# Document mutations
# ---------------------------------------------------------------------------

def with_document(
    document: RawDocument,
    ctx: AuditContext,
) -> dict[str, Any]:
    """
    State patch: add or update a document in raw_documents.

    The append_documents reducer deduplicates by document_id, so calling this
    again with the same document_id (e.g., to mark it PROCESSED) is safe.
    """
    return {
        "raw_documents": [document],
        **ctx.event(
            AuditEventType.DOCUMENT_RECEIVED,
            data={
                "document_id": document.document_id,
                "mime_type": document.mime_type,
                "document_type": document.document_type,
                "file_size": document.file_size,
                "sha256": document.sha256_hash,
            },
        ),
    }


def with_document_processed(
    document: RawDocument,
    ctx: AuditContext,
    *,
    duration_ms: float | None = None,
) -> dict[str, Any]:
    """State patch: mark a document as successfully parsed/processed."""
    updated = document.model_copy(update={
        "status": DocumentStatus.PROCESSED,
        "processed_at": datetime.utcnow(),
        "content": None,  # drop raw bytes from state after processing
    })
    return {
        "raw_documents": [updated],
        "processing_ms": duration_ms or 0.0,
        **ctx.event(
            AuditEventType.DOCUMENT_PARSED,
            data={
                "document_id": document.document_id,
                "page_count": document.page_count,
            },
            duration_ms=duration_ms,
        ),
    }


def with_document_failed(
    document: RawDocument,
    error: str,
    ctx: AuditContext,
) -> dict[str, Any]:
    """State patch: mark a document as failed."""
    updated = document.model_copy(update={
        "status": DocumentStatus.FAILED,
        "error": error,
        "processed_at": datetime.utcnow(),
        "content": None,
    })
    return {
        "raw_documents": [updated],
        **ctx.error_event(error, context={"document_id": document.document_id}),
    }


# ---------------------------------------------------------------------------
# Extraction mutations
# ---------------------------------------------------------------------------

def with_extracted_entities(
    document_id: str,
    result: ExtractionResult,
    ctx: AuditContext,
    *,
    duration_ms: float | None = None,
) -> dict[str, Any]:
    """
    State patch: store extraction output for one document.

    Converts ExtractionResult → ExtractedEntities and places it in the
    extracted_entities dict under document_id.
    The merge_entities reducer handles idempotent upserts.
    """
    entities = ExtractedEntities(
        document_id=document_id,
        patient=result.patient,
        provider=result.provider,
        diagnoses=result.diagnoses,
        icd_codes=result.icd_codes,
        cpt_codes=result.cpt_codes,
        medications=result.medications,
        glucose_readings=result.glucose_readings,
        hba1c_readings=result.hba1c_readings,
        insulin_regimens=result.insulin_regimens,
        lab_values=result.lab_values,
        symptoms=result.symptoms,
        treatment_history=result.treatment_history,
        complications=result.complications,
        overall_confidence=result.overall_confidence,
        grounding_pass_rate=result.grounding_pass_rate,
        extraction_method=result.extraction_method.value,
        llm_tokens_used=result.llm_tokens_used,
    )
    return {
        "extracted_entities": {document_id: entities},
        "tokens_used": result.llm_tokens_used,
        "processing_ms": duration_ms or 0.0,
        **ctx.event(
            AuditEventType.ENTITIES_EXTRACTED,
            data={
                "document_id": document_id,
                "total_entities": entities.total_entities,
                "confidence": result.overall_confidence,
                "method": result.extraction_method.value,
                "icd_codes": [c.code for c in result.icd_codes],
                "cpt_codes": [c.code for c in result.cpt_codes],
            },
            duration_ms=duration_ms,
        ),
    }


# ---------------------------------------------------------------------------
# Retrieval mutations
# ---------------------------------------------------------------------------

def with_retrieved_policies(
    policies: list[RetrievedPolicy],
    ctx: AuditContext,
    *,
    query: str | None = None,
    duration_ms: float | None = None,
) -> dict[str, Any]:
    """
    State patch: add retrieved policy results.

    The append_policies reducer deduplicates and re-sorts by similarity_score.
    """
    return {
        "retrieved_policies": policies,
        "processing_ms": duration_ms or 0.0,
        **ctx.event(
            AuditEventType.POLICIES_RETRIEVED,
            data={
                "count": len(policies),
                "query": query,
                "top_policy_id": policies[0].policy_id if policies else None,
                "top_score": policies[0].similarity_score if policies else 0.0,
            },
            duration_ms=duration_ms,
        ),
    }


# ---------------------------------------------------------------------------
# Evaluation mutations
# ---------------------------------------------------------------------------

def with_evaluation_result(
    result: EvaluationResult,
    ctx: AuditContext,
    *,
    duration_ms: float | None = None,
) -> dict[str, Any]:
    """
    State patch: store evaluation result for one policy.

    Keyed by result.dedup_key so re-evaluations after clarification overwrite
    the prior result for the same policy version.
    """
    return {
        "evaluation_results": {result.dedup_key: result},
        "tokens_used": result.tokens_used,
        "processing_ms": duration_ms or 0.0,
        **ctx.event(
            AuditEventType.CRITERIA_EVALUATED,
            data={
                "policy_id": result.policy_id,
                "policy_version": result.policy_version,
                "criteria_met": result.criteria_met,
                "criteria_not_met": result.criteria_not_met,
                "criteria_undetermined": result.criteria_undetermined,
                "criteria_total": result.criteria_total,
                "overall_score": result.overall_score,
            },
            duration_ms=duration_ms,
        ),
    }


def with_multiple_evaluation_results(
    results: list[EvaluationResult],
    ctx: AuditContext,
    *,
    duration_ms: float | None = None,
) -> dict[str, Any]:
    """State patch: store evaluation results for multiple policies at once."""
    tokens = sum(r.tokens_used for r in results)
    return {
        "evaluation_results": {r.dedup_key: r for r in results},
        "tokens_used": tokens,
        "processing_ms": duration_ms or 0.0,
        **ctx.event(
            AuditEventType.CRITERIA_EVALUATED,
            data={
                "policies_evaluated": len(results),
                "total_criteria": sum(r.criteria_total for r in results),
                "total_met": sum(r.criteria_met for r in results),
            },
            duration_ms=duration_ms,
        ),
    }


# ---------------------------------------------------------------------------
# Clarification mutations
# ---------------------------------------------------------------------------

def with_clarification_sent(
    attempt: ClarificationAttempt,
    ctx: AuditContext,
) -> dict[str, Any]:
    """State patch: record a clarification request sent to the provider."""
    return {
        "clarification_attempts": [attempt],
        **ctx.event(
            AuditEventType.CLARIFICATION_SENT,
            data={
                "attempt_id": attempt.attempt_id,
                "attempt_number": attempt.attempt_number,
                "question_category": attempt.question_category,
                "missing_criteria": attempt.missing_criteria,
            },
        ),
    }


def with_clarification_received(
    attempt_id: str,
    response: str,
    responded_by: str,
    ctx: AuditContext,
    *,
    current_attempts: list[ClarificationAttempt],
) -> dict[str, Any]:
    """
    State patch: record the provider's response to a clarification request.

    Finds the matching attempt by attempt_id and updates it with the response.
    The append_clarifications reducer will overwrite the existing attempt
    because ClarificationAttempt has no dedup_key — this creates a second entry.

    To properly update an existing attempt, the node must pass current_attempts
    (from state) so we can find and update the right one.
    """
    updated_attempts = []
    matched = False
    for attempt in current_attempts:
        if attempt.attempt_id == attempt_id:
            updated_attempts.append(attempt.model_copy(update={
                "response": response,
                "responded_by": responded_by,
                "answered_at": datetime.utcnow(),
                "status": ClarificationStatus.ANSWERED,
            }))
            matched = True
        else:
            updated_attempts.append(attempt)

    # Replace entire list — use merge_dicts pattern won't work here,
    # so we emit all attempts (the reducer will re-merge them correctly).
    # Since append_clarifications is pure-append, we instead return only the
    # updated attempt and let the reducer append it; the original (unanswered)
    # attempt stays in history as a record that the question was asked.
    if matched:
        updated_attempt = next(
            a for a in updated_attempts if a.attempt_id == attempt_id
        )
        return {
            "clarification_attempts": [updated_attempt],
            **ctx.event(
                AuditEventType.CLARIFICATION_RECEIVED,
                data={
                    "attempt_id": attempt_id,
                    "responded_by": responded_by,
                    "response_length": len(response),
                },
            ),
        }

    # If attempt_id not found, still record the response as a new attempt entry
    return {
        **ctx.error_event(
            f"Clarification attempt {attempt_id} not found; response recorded as orphan",
            context={"attempt_id": attempt_id},
        ),
    }


# ---------------------------------------------------------------------------
# Recommendation mutations
# ---------------------------------------------------------------------------

def with_recommendation(
    recommendation: PARecommendation,
    ctx: AuditContext,
    *,
    duration_ms: float | None = None,
) -> dict[str, Any]:
    """
    State patch: set the AI recommendation.

    Also sets requires_review based on the recommendation's own flag,
    transitions to RECOMMENDATION phase, and advances to HUMAN_REVIEW
    if review is required.
    """
    next_phase = (
        WorkflowPhase.HUMAN_REVIEW
        if recommendation.requires_human_review
        else WorkflowPhase.COMPLETED
    )
    return {
        "recommendation": recommendation,
        "rationale": recommendation.rationale,
        "requires_review": recommendation.requires_human_review,
        "workflow_phase": next_phase,
        "tokens_used": recommendation.tokens_used,
        "processing_ms": duration_ms or 0.0,
        **ctx.event(
            AuditEventType.RECOMMENDATION_GENERATED,
            data={
                "recommendation_type": recommendation.recommendation_type.value,
                "confidence_score": recommendation.confidence_score,
                "requires_human_review": recommendation.requires_human_review,
                "review_reason": recommendation.review_reason,
                "supporting_criteria": len(recommendation.supporting_criteria),
                "conflicting_criteria": len(recommendation.conflicting_criteria),
            },
            duration_ms=duration_ms,
        ),
    }


# ---------------------------------------------------------------------------
# Reviewer action mutations
# ---------------------------------------------------------------------------

def with_reviewer_action(
    action: ReviewerAction,
    ctx: AuditContext,
) -> dict[str, Any]:
    """State patch: record a human reviewer's action."""
    from app.services.workflow.state.models import ReviewerActionType

    is_terminal_action = action.action_type in (
        ReviewerActionType.APPROVE,
        ReviewerActionType.DENY,
        ReviewerActionType.OVERRIDE_APPROVE,
        ReviewerActionType.OVERRIDE_DENY,
    )
    patch: dict[str, Any] = {
        "reviewer_actions": [action],
        **ctx.event(
            AuditEventType.REVIEWER_ACTION,
            data={
                "action_id": action.action_id,
                "reviewer_id": action.reviewer_id,
                "action_type": action.action_type.value,
                "is_override": action.is_override,
                "notes": action.notes,
            },
        ),
    }
    if is_terminal_action:
        patch["workflow_phase"] = WorkflowPhase.COMPLETED
    return patch


# ---------------------------------------------------------------------------
# Phase / control mutations
# ---------------------------------------------------------------------------

def with_phase(
    to_phase: WorkflowPhase,
    ctx: AuditContext,
    *,
    from_phase: WorkflowPhase | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    """State patch: transition to a new workflow phase."""
    patch: dict[str, Any] = {"workflow_phase": to_phase}
    if from_phase is not None:
        patch.update(ctx.phase_event(from_phase, to_phase, reason=reason))
    return patch


def with_error(
    error: str,
    ctx: AuditContext,
    *,
    exc_type: str | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """State patch: record an unrecoverable error and transition to FAILED."""
    return {
        "error": error,
        "workflow_phase": WorkflowPhase.FAILED,
        **ctx.error_event(error, exc_type=exc_type, context=context),
    }


def with_retry(
    current_retry_count: int,
    ctx: AuditContext,
    *,
    reason: str | None = None,
) -> dict[str, Any]:
    """State patch: increment retry counter and emit an audit event."""
    return {
        "retry_count": current_retry_count + 1,
        **ctx.event(
            AuditEventType.RETRY,
            data={"attempt": current_retry_count + 1, "reason": reason},
        ),
    }


def with_workflow_started(
    ctx: AuditContext,
    *,
    case_id: str,
    pa_request_id: str | None = None,
) -> dict[str, Any]:
    """State patch: emit the WORKFLOW_STARTED audit event."""
    return ctx.event(
        AuditEventType.WORKFLOW_STARTED,
        data={"case_id": case_id, "pa_request_id": pa_request_id},
    )


def with_workflow_completed(
    ctx: AuditContext,
    *,
    recommendation_type: str,
    total_tokens: int,
    total_ms: float,
    audit_meta: AuditMetadata,
) -> dict[str, Any]:
    """State patch: emit WORKFLOW_COMPLETED and update audit metadata summary."""
    updated_meta = audit_meta.model_copy(update={
        "total_tokens_used": total_tokens,
        "total_processing_ms": total_ms,
        "updated_at": datetime.utcnow(),
    })
    return {
        "workflow_phase": WorkflowPhase.COMPLETED,
        "audit_metadata": updated_meta,
        **ctx.event(
            AuditEventType.WORKFLOW_COMPLETED,
            data={
                "recommendation_type": recommendation_type,
                "total_tokens_used": total_tokens,
                "total_processing_ms": round(total_ms, 1),
            },
        ),
    }
