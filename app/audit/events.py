"""
Audit event factory functions for all 9 healthcare audit domains.

Each factory:
  - Accepts domain-specific arguments
  - Pulls the current AuditContext from contextvars
  - Builds event_data (full fidelity for DB)
  - Builds log_data (PII-masked for log sinks)
  - Computes content_hash for tamper evidence
  - Returns a ready-to-emit AuditRecord

PII handling:
  - Patient names, DOBs, member_ids → masked in log_data
  - Full values stored in event_data (DB, encrypted at rest)
  - LLM prompts → first 200 chars in log_data; full in event_data
  - Stack traces → SHA-256 hash in log_data; full message in event_data
  - IP addresses → kept (operational requirement, not PHI)
"""

from __future__ import annotations

import hashlib
import traceback
from datetime import UTC, datetime
from typing import Any

from app.audit.context import get_audit_context
from app.audit.models import (
    AuditActorType,
    AuditCategory,
    AuditContext,
    AuditRecord,
    AuditSeverity,
    hash_sensitive,
    mask_member_id,
)


# ---------------------------------------------------------------------------
# 1. API REQUEST
# ---------------------------------------------------------------------------

def api_request_event(
    *,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    query_params: dict[str, str] | None = None,
    response_size_bytes: int | None = None,
    error_message: str | None = None,
) -> AuditRecord:
    """Audit one completed HTTP request."""
    ctx = get_audit_context()
    severity = (
        AuditSeverity.ERROR if status_code >= 500
        else AuditSeverity.WARNING if status_code >= 400
        else AuditSeverity.INFO
    )
    # Hash query params — may contain search terms with PHI
    params_hash = hash_sensitive(str(sorted((query_params or {}).items()))) if query_params else None

    event_data: dict[str, Any] = {
        "method": method,
        "path": path,
        "status_code": status_code,
        "duration_ms": round(duration_ms, 2),
        "response_size_bytes": response_size_bytes,
        "query_params": query_params or {},
        "error_message": error_message,
    }
    log_data: dict[str, Any] = {
        "method": method,
        "path": path,
        "status_code": status_code,
        "duration_ms": round(duration_ms, 2),
        "response_size_bytes": response_size_bytes,
        "query_params_hash": params_hash,   # Never log raw params (may contain PHI)
    }

    return AuditRecord(
        category=AuditCategory.API_REQUEST,
        action=f"http.{method.lower()}",
        severity=severity,
        audit_ctx=ctx,
        event_data=event_data,
        log_data=log_data,
        duration_ms=duration_ms,
        error_message=error_message,
        error_type="http_error" if status_code >= 400 else None,
    )


# ---------------------------------------------------------------------------
# 2. OCR ACTION
# ---------------------------------------------------------------------------

def ocr_event(
    *,
    document_id: str,
    provider: str,
    confidence: float,
    page_count: int,
    duration_ms: float,
    document_type: str = "unknown",
    fallback_used: bool = False,
    fallback_reason: str | None = None,
    error: str | None = None,
) -> AuditRecord:
    """Audit an OCR processing action on a document."""
    ctx = get_audit_context()
    severity = AuditSeverity.WARNING if fallback_used else AuditSeverity.INFO
    if error:
        severity = AuditSeverity.ERROR

    event_data: dict[str, Any] = {
        "document_id": document_id,
        "provider": provider,
        "confidence": round(confidence, 4),
        "page_count": page_count,
        "document_type": document_type,
        "fallback_used": fallback_used,
        "fallback_reason": fallback_reason,
        "error": error,
    }
    log_data: dict[str, Any] = {
        "document_id": document_id,
        "provider": provider,
        "confidence": round(confidence, 4),
        "page_count": page_count,
        "document_type": document_type,
        "fallback_used": fallback_used,
    }

    return AuditRecord(
        category=AuditCategory.OCR,
        action="document.ocr.processed" if not error else "document.ocr.failed",
        severity=severity,
        audit_ctx=ctx,
        document_id=document_id,
        event_data=event_data,
        log_data=log_data,
        duration_ms=duration_ms,
        error_type="ocr_failure" if error else None,
        error_message=error,
    )


# ---------------------------------------------------------------------------
# 3. EXTRACTION OUTPUT
# ---------------------------------------------------------------------------

def extraction_event(
    *,
    document_id: str,
    entity_counts: dict[str, int],
    overall_confidence: float,
    grounding_pass_rate: float,
    model: str,
    tokens_used: int,
    duration_ms: float,
    patient_name: str | None = None,
    member_id: str | None = None,
    error: str | None = None,
) -> AuditRecord:
    """Audit medical entity extraction from a document."""
    ctx = get_audit_context()
    total_entities = sum(entity_counts.values())

    event_data: dict[str, Any] = {
        "document_id": document_id,
        "entity_counts": entity_counts,
        "total_entities": total_entities,
        "overall_confidence": round(overall_confidence, 4),
        "grounding_pass_rate": round(grounding_pass_rate, 4),
        "model": model,
        "tokens_used": tokens_used,
        # Full PII stored in DB (encrypted at rest)
        "patient_name": patient_name,
        "member_id": member_id,
        "error": error,
    }
    log_data: dict[str, Any] = {
        "document_id": document_id,
        "entity_counts": entity_counts,
        "total_entities": total_entities,
        "overall_confidence": round(overall_confidence, 4),
        "grounding_pass_rate": round(grounding_pass_rate, 4),
        "model": model,
        "tokens_used": tokens_used,
        # PII masked in logs
        "patient_name": "[MASKED]" if patient_name else None,
        "member_id": mask_member_id(member_id),
    }

    return AuditRecord(
        category=AuditCategory.EXTRACTION,
        action="document.extraction.completed" if not error else "document.extraction.failed",
        severity=AuditSeverity.ERROR if error else AuditSeverity.INFO,
        audit_ctx=ctx,
        document_id=document_id,
        event_data=event_data,
        log_data=log_data,
        duration_ms=duration_ms,
        error_type="extraction_failure" if error else None,
        error_message=error,
    )


# ---------------------------------------------------------------------------
# 4. RETRIEVAL RESULTS
# ---------------------------------------------------------------------------

def retrieval_event(
    *,
    query: str,
    policies_found: int,
    chunks_returned: int,
    top_score: float,
    strategy: str,
    duration_ms: float,
    cpt_codes: list[str] | None = None,
    icd_codes: list[str] | None = None,
    reranked: bool = False,
    error: str | None = None,
) -> AuditRecord:
    """Audit a policy retrieval operation from the vector store."""
    ctx = get_audit_context()
    query_hash = hash_sensitive(query)

    event_data: dict[str, Any] = {
        "query": query[:500],     # Truncate very long queries in DB
        "query_hash": query_hash,
        "policies_found": policies_found,
        "chunks_returned": chunks_returned,
        "top_score": round(top_score, 4),
        "strategy": strategy,
        "cpt_codes": cpt_codes or [],
        "icd_codes": icd_codes or [],
        "reranked": reranked,
        "error": error,
    }
    log_data: dict[str, Any] = {
        "query_hash": query_hash,   # Never log raw query (may contain PHI)
        "policies_found": policies_found,
        "chunks_returned": chunks_returned,
        "top_score": round(top_score, 4),
        "strategy": strategy,
        "cpt_codes": cpt_codes or [],
        "icd_codes": icd_codes or [],
        "reranked": reranked,
    }

    return AuditRecord(
        category=AuditCategory.RETRIEVAL,
        action="policy.retrieval.completed" if not error else "policy.retrieval.failed",
        severity=AuditSeverity.ERROR if error else AuditSeverity.INFO,
        audit_ctx=ctx,
        event_data=event_data,
        log_data=log_data,
        duration_ms=duration_ms,
        error_type="retrieval_failure" if error else None,
        error_message=error,
    )


# ---------------------------------------------------------------------------
# 5. LLM PROMPT + RESPONSE
# ---------------------------------------------------------------------------

def llm_call_event(
    *,
    model: str,
    tier: str,
    operation: str,
    prompt_tokens: int,
    completion_tokens: int,
    duration_ms: float,
    outcome: str,                    # "success" | "guardrail_fail" | "escalated" | "error"
    confidence: float | None = None,
    escalation_count: int = 0,
    prompt_preview: str | None = None,  # First 200 chars of prompt (may contain PHI)
    policy_id: str | None = None,
    violations: list[str] | None = None,
    error: str | None = None,
) -> AuditRecord:
    """Audit an LLM API call (reasoning, extraction, clarification generation)."""
    ctx = get_audit_context()
    severity = AuditSeverity.ERROR if error else (
        AuditSeverity.WARNING if outcome != "success" else AuditSeverity.INFO
    )
    total_tokens = prompt_tokens + completion_tokens

    event_data: dict[str, Any] = {
        "model": model,
        "tier": tier,
        "operation": operation,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "outcome": outcome,
        "confidence": confidence,
        "escalation_count": escalation_count,
        "prompt_preview": prompt_preview,   # Full preview in DB
        "violations": violations or [],
        "error": error,
    }
    log_data: dict[str, Any] = {
        "model": model,
        "tier": tier,
        "operation": operation,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "outcome": outcome,
        "confidence": confidence,
        "escalation_count": escalation_count,
        # Only first 100 chars in logs — prompt may contain PHI
        "prompt_preview": (prompt_preview or "")[:100] if prompt_preview else None,
        "violation_count": len(violations or []),
    }

    return AuditRecord(
        category=AuditCategory.LLM_CALL,
        action=f"llm.{operation}.{outcome}",
        severity=severity,
        audit_ctx=ctx,
        policy_id=policy_id,
        event_data=event_data,
        log_data=log_data,
        duration_ms=duration_ms,
        error_type="llm_error" if error else None,
        error_message=error,
    )


# ---------------------------------------------------------------------------
# 6. REVIEWER ACTION
# ---------------------------------------------------------------------------

def reviewer_action_event(
    *,
    reviewer_id: str,
    reviewer_name: str | None,
    action_type: str,
    case_id: str,
    ai_verdict: str | None = None,
    final_verdict: str | None = None,
    override_reason: str | None = None,
    clinical_notes: str | None = None,
    duration_seconds: float | None = None,
    is_override: bool = False,
) -> AuditRecord:
    """Audit a human reviewer action on a PA case."""
    ctx = get_audit_context()
    severity = AuditSeverity.INFO

    # Capture full override reason in DB; hash it for logs (may contain PHI context)
    override_reason_hash = hash_sensitive(override_reason) if override_reason else None

    event_data: dict[str, Any] = {
        "reviewer_id": reviewer_id,
        "reviewer_name": reviewer_name,
        "action_type": action_type,
        "ai_verdict": ai_verdict,
        "final_verdict": final_verdict,
        "override_reason": override_reason,   # Full text in DB
        "clinical_notes": clinical_notes,     # Full text in DB
        "duration_seconds": duration_seconds,
        "is_override": is_override,
    }
    log_data: dict[str, Any] = {
        "reviewer_id": reviewer_id,
        "action_type": action_type,
        "ai_verdict": ai_verdict,
        "final_verdict": final_verdict,
        "override_reason_hash": override_reason_hash,  # Hashed in logs
        "duration_seconds": duration_seconds,
        "is_override": is_override,
    }

    return AuditRecord(
        category=AuditCategory.REVIEWER_ACTION,
        action=f"reviewer.{action_type.lower()}",
        severity=severity,
        audit_ctx=ctx.with_case(case_id),
        case_id=case_id,
        event_data=event_data,
        log_data=log_data,
        duration_ms=duration_seconds * 1000 if duration_seconds else None,
    )


# ---------------------------------------------------------------------------
# 7. DECISION
# ---------------------------------------------------------------------------

def decision_event(
    *,
    case_id: str,
    verdict: str,
    rule_applied: str,
    confidence: float,
    requires_human_review: bool,
    review_reason: str | None,
    policies_evaluated: int,
    criteria_met: int,
    criteria_not_met: int,
    criteria_undetermined: int,
    is_override: bool = False,
    override_reviewer_id: str | None = None,
    model_used: str | None = None,
    tokens_used: int = 0,
) -> AuditRecord:
    """Audit a PA decision (AI-generated or reviewer override)."""
    ctx = get_audit_context()

    event_data: dict[str, Any] = {
        "case_id": case_id,
        "verdict": verdict,
        "rule_applied": rule_applied,
        "confidence": round(confidence, 4),
        "requires_human_review": requires_human_review,
        "review_reason": review_reason,
        "policies_evaluated": policies_evaluated,
        "criteria_met": criteria_met,
        "criteria_not_met": criteria_not_met,
        "criteria_undetermined": criteria_undetermined,
        "is_override": is_override,
        "override_reviewer_id": override_reviewer_id,
        "model_used": model_used,
        "tokens_used": tokens_used,
    }

    return AuditRecord(
        category=AuditCategory.DECISION,
        action="pa.decision.made" if not is_override else "pa.decision.override",
        severity=AuditSeverity.INFO,
        audit_ctx=ctx.with_case(case_id),
        case_id=case_id,
        event_data=event_data,
        log_data=dict(event_data),   # No PII in decision metadata
        new_state={"verdict": verdict, "confidence": confidence},
    )


# ---------------------------------------------------------------------------
# 8. CLARIFICATION
# ---------------------------------------------------------------------------

def clarification_event(
    *,
    case_id: str,
    attempt_id: str,
    attempt_number: int,
    event_type: str,              # "sent" | "answered" | "timeout" | "escalated"
    question_category: str,
    generated_by: str,            # "llm" | "template"
    response_quality: str | None = None,
    question: str | None = None,  # Full question (may contain clinical context)
    response: str | None = None,  # Provider response (may contain PHI)
) -> AuditRecord:
    """Audit a clarification loop event (sent, answered, timeout, escalated)."""
    ctx = get_audit_context()
    question_hash = hash_sensitive(question) if question else None
    response_hash = hash_sensitive(response) if response else None

    event_data: dict[str, Any] = {
        "attempt_id": attempt_id,
        "attempt_number": attempt_number,
        "event_type": event_type,
        "question_category": question_category,
        "generated_by": generated_by,
        "response_quality": response_quality,
        "question": question,     # Full text in DB (may contain clinical criteria)
        "response": response,     # Full text in DB (may contain PHI)
    }
    log_data: dict[str, Any] = {
        "attempt_id": attempt_id,
        "attempt_number": attempt_number,
        "event_type": event_type,
        "question_category": question_category,
        "generated_by": generated_by,
        "response_quality": response_quality,
        "question_hash": question_hash,    # Hashed in logs
        "response_hash": response_hash,    # Hashed in logs
    }

    return AuditRecord(
        category=AuditCategory.CLARIFICATION,
        action=f"clarification.{event_type}",
        severity=AuditSeverity.WARNING if event_type in ("timeout", "escalated") else AuditSeverity.INFO,
        audit_ctx=ctx.with_case(case_id),
        case_id=case_id,
        attempt_id=attempt_id,
        event_data=event_data,
        log_data=log_data,
    )


# ---------------------------------------------------------------------------
# 9. ERROR
# ---------------------------------------------------------------------------

def error_event(
    *,
    component: str,
    error_type: str,
    error_message: str,
    exc: BaseException | None = None,
    case_id: str | None = None,
    document_id: str | None = None,
    severity: AuditSeverity = AuditSeverity.ERROR,
    is_retriable: bool = False,
    metadata: dict[str, Any] | None = None,
) -> AuditRecord:
    """Audit a system error or exception in any component."""
    ctx = get_audit_context()
    stack_trace: str | None = None
    if exc is not None:
        import traceback as tb
        stack_trace = "".join(tb.format_exception(type(exc), exc, exc.__traceback__))
    stack_hash = hash_sensitive(stack_trace) if stack_trace else None

    event_data: dict[str, Any] = {
        "component": component,
        "error_type": error_type,
        "error_message": error_message,
        "stack_trace": stack_trace,        # Full trace in DB
        "is_retriable": is_retriable,
        **(metadata or {}),
    }
    log_data: dict[str, Any] = {
        "component": component,
        "error_type": error_type,
        "error_message": error_message[:300] if error_message else None,  # Truncate
        "stack_hash": stack_hash,           # Hashed in logs (stack may contain PHI)
        "is_retriable": is_retriable,
    }

    return AuditRecord(
        category=AuditCategory.ERROR,
        action=f"error.{component}.{error_type.lower()}",
        severity=severity,
        audit_ctx=ctx.with_case(case_id) if case_id else ctx,
        case_id=case_id,
        document_id=document_id,
        event_data=event_data,
        log_data=log_data,
        error_type=error_type,
        error_message=error_message,
        error_hash=stack_hash,
    )
