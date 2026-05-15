"""
Async audit context management via Python contextvars.

Provides thread-safe (async-safe) propagation of AuditContext through
the entire async call stack without explicit parameter passing.

Pattern:
  1. AuditMiddleware sets the context on every incoming HTTP request.
  2. Any service layer function can call get_audit_context() to get the
     current context and attach it to audit records.
  3. Background tasks that are spawned mid-request inherit the context
     automatically (Python propagates ContextVar values into task copies).

Usage:
    # In middleware (once per request):
    token = set_audit_context(AuditContext(request_id=..., user_id=...))
    try:
        await call_next(request)
    finally:
        reset_audit_context(token)

    # In any service layer:
    ctx = get_audit_context()
    record = build_api_request_record(ctx, ...)
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Any

from app.audit.models import AuditActorType, AuditContext

# Module-level ContextVar — one per application process, shared across all
# async tasks but isolated between concurrent requests.
_AUDIT_CTX_VAR: ContextVar[AuditContext | None] = ContextVar(
    "audit_context", default=None
)

# Empty sentinel to avoid None checks in service code
_EMPTY_CONTEXT = AuditContext()


def set_audit_context(ctx: AuditContext) -> Token:
    """
    Set the audit context for the current async task.

    Returns a Token that MUST be passed to reset_audit_context() after
    the request completes (in a finally block), to prevent context leakage.
    """
    return _AUDIT_CTX_VAR.set(ctx)


def reset_audit_context(token: Token) -> None:
    """Reset the context variable to the state before set_audit_context()."""
    _AUDIT_CTX_VAR.reset(token)


def get_audit_context() -> AuditContext:
    """
    Return the current audit context, or an empty context if not set.

    Never returns None — callers can always attach the result to records
    without None checks.
    """
    return _AUDIT_CTX_VAR.get() or _EMPTY_CONTEXT


def get_raw_audit_context() -> AuditContext | None:
    """Return None if no context is set (useful for presence checks)."""
    return _AUDIT_CTX_VAR.get()


def update_case_id(case_id: str) -> None:
    """
    Update the case_id in the current audit context.

    Called by workflow nodes once a case_id is known (it may not be
    available at request start — e.g., on case creation endpoints).
    """
    current = _AUDIT_CTX_VAR.get()
    if current is not None:
        _AUDIT_CTX_VAR.set(current.with_case(case_id))


def build_context_from_request(
    *,
    request_id: str | None,
    trace_id: str | None,
    user_id: str | None,
    session_id: str | None,
    actor_ip: str | None,
    actor_user_agent: str | None,
    actor_type: AuditActorType = AuditActorType.USER,
    actor_name: str | None = None,
) -> AuditContext:
    """
    Convenience constructor for building an AuditContext from HTTP request
    metadata extracted by RequestTracingMiddleware.
    """
    return AuditContext(
        request_id=request_id,
        trace_id=trace_id,
        session_id=session_id,
        user_id=user_id,
        actor_type=actor_type,
        actor_name=actor_name,
        actor_ip=actor_ip,
        actor_user_agent=actor_user_agent,
    )


def build_system_context(
    *,
    component: str,
    case_id: str | None = None,
) -> AuditContext:
    """
    Build an audit context for background system events (no HTTP request).

    Used by worker processes, scheduled jobs, and internal services.
    """
    return AuditContext(
        actor_type=AuditActorType.SYSTEM,
        actor_name=component,
        case_id=case_id,
    )
