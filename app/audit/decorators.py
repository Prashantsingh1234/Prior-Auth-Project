"""
Service-layer audit decorators.

Wrap any async (or sync) function to automatically emit an audit record
on entry and exit.  The decorator family covers the 9 auditable domains:

    @audit_ocr          — document OCR processing functions
    @audit_extraction   — entity extraction functions
    @audit_retrieval    — policy retrieval functions
    @audit_llm_call     — LLM inference functions
    @audit_decision     — decision engine functions
    @audit_action       — generic catch-all for any domain

All decorators:
  - Are async-compatible (wrap both sync and async functions)
  - Read the current AuditContext from contextvars automatically
  - Emit on SUCCESS and on EXCEPTION
  - Never raise from within audit code (errors are logged, not propagated)
  - Preserve the original function's signature via functools.wraps

Usage:

    @audit_ocr(document_id_arg="document_id")
    async def run_ocr(document_id: str, ...) -> OcrResult:
        ...

    @audit_llm_call(operation="reasoning", tier="medium")
    async def evaluate_policy(policy, state, ...) -> ReasoningResult:
        ...

    @audit_action(
        category=AuditCategory.CLARIFICATION,
        action="clarification.question.generated",
    )
    async def generate_question(...) -> ClarificationRequest:
        ...
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import time
from typing import Any, Callable, TypeVar

import structlog

from app.audit.events import (
    error_event,
    extraction_event,
    llm_call_event,
    ocr_event,
    retrieval_event,
)
from app.audit.models import AuditCategory, AuditRecord, AuditSeverity
from app.audit.writer import emit

logger = structlog.get_logger(__name__)
F = TypeVar("F", bound=Callable[..., Any])


# ---------------------------------------------------------------------------
# Generic internal helpers
# ---------------------------------------------------------------------------

def _call_emit(record: AuditRecord) -> None:
    """Safe emit that never raises."""
    try:
        emit(record)
    except Exception as exc:
        logger.error("audit.decorator.emit_failed", error=str(exc))


def _is_async(func: Callable) -> bool:
    return asyncio.iscoroutinefunction(func)


def _get_arg(args: tuple, kwargs: dict, func: Callable, name: str, default: Any = None) -> Any:
    """Extract a named argument from *args or **kwargs using the function signature."""
    try:
        sig = inspect.signature(func)
        params = list(sig.parameters.keys())
        if name in kwargs:
            return kwargs[name]
        if name in params:
            idx = params.index(name)
            if idx < len(args):
                return args[idx]
    except (ValueError, TypeError):
        pass
    return default


# ---------------------------------------------------------------------------
# OCR decorator
# ---------------------------------------------------------------------------

def audit_ocr(
    document_id_arg: str = "document_id",
    provider_arg: str = "provider",
) -> Callable[[F], F]:
    """
    Audit a document OCR function.

    The decorated function must return an object with `.confidence` and
    `.page_count` attributes (or a dict with those keys).
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            t0 = time.perf_counter()
            doc_id = _get_arg(args, kwargs, func, document_id_arg, "unknown")
            provider = _get_arg(args, kwargs, func, provider_arg, "unknown")
            error: str | None = None
            result = None
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as exc:
                error = str(exc)
                raise
            finally:
                elapsed = (time.perf_counter() - t0) * 1000
                conf = getattr(result, "confidence", 0.0) if result else 0.0
                pages = getattr(result, "page_count", 0) if result else 0
                if isinstance(result, dict):
                    conf = result.get("confidence", 0.0)
                    pages = result.get("page_count", 0)
                _call_emit(ocr_event(
                    document_id=str(doc_id),
                    provider=str(provider),
                    confidence=float(conf),
                    page_count=int(pages),
                    duration_ms=elapsed,
                    error=error,
                ))

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            t0 = time.perf_counter()
            doc_id = _get_arg(args, kwargs, func, document_id_arg, "unknown")
            provider = _get_arg(args, kwargs, func, provider_arg, "unknown")
            error: str | None = None
            result = None
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as exc:
                error = str(exc)
                raise
            finally:
                elapsed = (time.perf_counter() - t0) * 1000
                conf = getattr(result, "confidence", 0.0) if result else 0.0
                pages = getattr(result, "page_count", 0) if result else 0
                _call_emit(ocr_event(
                    document_id=str(doc_id),
                    provider=str(provider),
                    confidence=float(conf),
                    page_count=int(pages),
                    duration_ms=elapsed,
                    error=error,
                ))

        return async_wrapper if _is_async(func) else sync_wrapper  # type: ignore
    return decorator


# ---------------------------------------------------------------------------
# Extraction decorator
# ---------------------------------------------------------------------------

def audit_extraction(
    document_id_arg: str = "document_id",
    model: str = "unknown",
) -> Callable[[F], F]:
    """Audit a medical entity extraction function."""
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            t0 = time.perf_counter()
            doc_id = _get_arg(args, kwargs, func, document_id_arg, "unknown")
            error: str | None = None
            result = None
            try:
                result = await func(*args, **kwargs) if _is_async(func) else func(*args, **kwargs)
                return result
            except Exception as exc:
                error = str(exc)
                raise
            finally:
                elapsed = (time.perf_counter() - t0) * 1000
                conf = 0.0
                tokens = 0
                entity_counts: dict[str, int] = {}
                if result is not None:
                    conf = float(getattr(result, "overall_confidence", 0.0))
                    tokens = int(getattr(result, "llm_tokens_used", 0))
                    # Build entity count breakdown from known attributes
                    for attr in ("diagnoses", "medications", "lab_values",
                                 "icd_codes", "cpt_codes", "symptoms",
                                 "hba1c_readings", "treatment_history"):
                        val = getattr(result, attr, [])
                        if val:
                            entity_counts[attr] = len(val)
                _call_emit(extraction_event(
                    document_id=str(doc_id),
                    entity_counts=entity_counts,
                    overall_confidence=conf,
                    grounding_pass_rate=float(getattr(result, "grounding_pass_rate", 0.0)) if result else 0.0,
                    model=model,
                    tokens_used=tokens,
                    duration_ms=elapsed,
                    error=error,
                ))
        return wrapper  # type: ignore
    return decorator


# ---------------------------------------------------------------------------
# Retrieval decorator
# ---------------------------------------------------------------------------

def audit_retrieval(
    query_arg: str = "query",
    strategy: str = "hybrid",
) -> Callable[[F], F]:
    """Audit a policy retrieval function."""
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            t0 = time.perf_counter()
            query = _get_arg(args, kwargs, func, query_arg, "")
            error: str | None = None
            result = None
            try:
                result = await func(*args, **kwargs) if _is_async(func) else func(*args, **kwargs)
                return result
            except Exception as exc:
                error = str(exc)
                raise
            finally:
                elapsed = (time.perf_counter() - t0) * 1000
                policies = 0
                chunks = 0
                top_score = 0.0
                if result is not None:
                    policies = len(getattr(result, "policies", getattr(result, "retrieved_policies", [])))
                    chunks = int(getattr(result, "chunks_returned", 0))
                    all_policies = getattr(result, "policies", [])
                    if all_policies:
                        top_score = float(getattr(all_policies[0], "similarity_score", 0.0))
                _call_emit(retrieval_event(
                    query=str(query)[:500],
                    policies_found=policies,
                    chunks_returned=chunks,
                    top_score=top_score,
                    strategy=strategy,
                    duration_ms=elapsed,
                    error=error,
                ))
        return wrapper  # type: ignore
    return decorator


# ---------------------------------------------------------------------------
# LLM call decorator
# ---------------------------------------------------------------------------

def audit_llm_call(
    operation: str,
    tier: str = "unknown",
    policy_id_arg: str | None = None,
) -> Callable[[F], F]:
    """
    Audit an LLM inference function.

    The decorated function should return a ReasoningResult or similar object
    with `.total_tokens`, `.succeeded`, `.final_tier`, `.escalations_count`.
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            t0 = time.perf_counter()
            pol_id = _get_arg(args, kwargs, func, policy_id_arg, None) if policy_id_arg else None
            error: str | None = None
            result = None
            try:
                result = await func(*args, **kwargs) if _is_async(func) else func(*args, **kwargs)
                return result
            except Exception as exc:
                error = str(exc)
                raise
            finally:
                elapsed = (time.perf_counter() - t0) * 1000
                outcome = "error"
                prompt_tokens = 0
                completion_tokens = 0
                confidence = None
                escalation_count = 0
                actual_tier = tier
                if result is not None:
                    outcome = "success" if getattr(result, "succeeded", False) else "failed"
                    if getattr(result, "requires_human_escalation", False):
                        outcome = "escalated"
                    prompt_tokens = int(getattr(result, "total_prompt_tokens", 0))
                    completion_tokens = int(getattr(result, "total_completion_tokens", 0))
                    escalation_count = int(getattr(result, "escalations_count", 0))
                    final_tier = getattr(result, "final_tier", None)
                    if final_tier:
                        actual_tier = final_tier.value if hasattr(final_tier, "value") else str(final_tier)
                    output = getattr(result, "output", None)
                    if output:
                        confidence = float(getattr(output, "overall_confidence", 0.0))
                _call_emit(llm_call_event(
                    model="",
                    tier=actual_tier,
                    operation=operation,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    duration_ms=elapsed,
                    outcome="error" if error else outcome,
                    confidence=confidence,
                    escalation_count=escalation_count,
                    policy_id=str(pol_id) if pol_id else None,
                    error=error,
                ))
        return wrapper  # type: ignore
    return decorator


# ---------------------------------------------------------------------------
# Generic action decorator
# ---------------------------------------------------------------------------

def audit_action(
    category: AuditCategory,
    action: str,
    severity: AuditSeverity = AuditSeverity.INFO,
    case_id_arg: str | None = None,
    capture_error: bool = True,
) -> Callable[[F], F]:
    """
    Generic audit decorator for any domain.

    Emits a minimal AuditRecord with category, action, duration, and
    error details.  Use domain-specific decorators (audit_ocr, etc.) for
    richer structured event_data.
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            from app.audit.context import get_audit_context
            t0 = time.perf_counter()
            case_id = _get_arg(args, kwargs, func, case_id_arg, None) if case_id_arg else None
            error: str | None = None
            exc_obj: BaseException | None = None
            try:
                result = await func(*args, **kwargs) if _is_async(func) else func(*args, **kwargs)
                return result
            except Exception as exc:
                error = str(exc)
                exc_obj = exc
                raise
            finally:
                elapsed = (time.perf_counter() - t0) * 1000
                ctx = get_audit_context()
                if case_id:
                    ctx = ctx.with_case(str(case_id))

                if error and capture_error:
                    _call_emit(error_event(
                        component=func.__module__ or "unknown",
                        error_type=type(exc_obj).__name__ if exc_obj else "Error",
                        error_message=error,
                        exc=exc_obj,
                        case_id=case_id,
                        severity=AuditSeverity.ERROR,
                    ))
                else:
                    from app.audit.models import AuditRecord
                    _call_emit(AuditRecord(
                        category=category,
                        action=action,
                        severity=severity,
                        audit_ctx=ctx,
                        case_id=case_id,
                        event_data={"duration_ms": round(elapsed, 2), "outcome": "success"},
                        log_data={"duration_ms": round(elapsed, 2), "outcome": "success"},
                        duration_ms=elapsed,
                    ))
        return wrapper  # type: ignore
    return decorator
