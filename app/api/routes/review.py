"""
Human reviewer workflow endpoints.

POST /review/{case_id}/approve   — Approve authorization
POST /review/{case_id}/deny      — Deny authorization
POST /review/{case_id}/pend      — Pend for additional information
POST /review/{case_id}/escalate  — Escalate to senior reviewer
POST /review/{case_id}/notes     — Add a case note
POST /review/{case_id}/assign    — Assign a reviewer

All review actions:
  1. Validate case state (not terminal, not already processed)
  2. Create ReviewerAction audit record
  3. Create Decision record (for approve/deny/pend)
  4. Transition case status
  5. Emit notification (async, non-fatal)
  6. Return updated case summary

Role requirement: reviewer or admin
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import ORJSONResponse

from app.api.dependencies.common import CurrentUser, require_role
from app.api.dependencies.database import DbSession
from app.api.dependencies.rate_limiter import rate_limit
from app.api.schemas.common import SuccessResponse
from app.api.schemas.review import (
    AddNoteRequest,
    ApproveRequest,
    AssignRequest,
    DenyRequest,
    EscalateRequest,
    PendRequest,
    ReviewActionResponse,
)
from app.core.exceptions.base import (
    CaseAlreadyDecidedError,
    CaseNotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.db.repositories.pa_case import PACaseRepository
from app.models.enums import (
    CaseStatus,
    DecisionOutcome,
    DecisionSource,
    ReviewerActionType,
)
from app.monitoring.metrics import METRICS

logger = structlog.get_logger(__name__)

router = APIRouter()

# RBAC: both reviewers and admins can perform review actions
ReviewerRequired = require_role("reviewer", "admin")


def _decision_source(
    case_ai_recommendation: str | None,
    action_outcome: DecisionOutcome,
) -> DecisionSource:
    """Determine if reviewer is confirming or overriding the AI recommendation."""
    if case_ai_recommendation and case_ai_recommendation == action_outcome.value:
        return DecisionSource.AI_RECOMMENDATION
    return DecisionSource.REVIEWER_OVERRIDE


# ----------------------------------------------------------
# Shared: record reviewer action + transition status
# ----------------------------------------------------------

async def _record_action_and_transition(
    session: DbSession,
    case_id: str,
    reviewer_id: str,
    action_type: ReviewerActionType,
    new_status: CaseStatus,
    rationale: str | None = None,
) -> None:
    """
    Atomically:
    1. Record a ReviewerAction
    2. Transition the case status
    Both run in the same DB session/transaction.
    """
    from app.db.repositories.reviewer_action import ReviewerActionRepository
    action_repo = ReviewerActionRepository(session)
    case_repo   = PACaseRepository(session)

    await action_repo.create(
        case_id=case_id,
        reviewer_id=reviewer_id,
        action_type=action_type,
        rationale=rationale,
    )
    await case_repo.transition_status(case_id, new_status, actor_id=reviewer_id)


async def _create_decision(
    session: DbSession,
    case_id: str,
    outcome: DecisionOutcome,
    source: DecisionSource,
    rationale: str,
    override_reason: str | None,
    decided_by_id: str,
    denial_reason_code: str | None = None,
) -> None:
    """Persist a Decision record (one per case, immutable once created)."""
    from app.db.repositories.decision import DecisionRepository
    decision_repo = DecisionRepository(session)
    await decision_repo.create(
        case_id=case_id,
        final_decision=outcome,
        decision_source=source,
        rationale=rationale,
        override_reason=override_reason,
        decided_by_id=decided_by_id,
        denial_reason_code=denial_reason_code,
    )


def _build_response(case, action_type: str, message: str) -> ReviewActionResponse:
    return ReviewActionResponse(
        case_id=str(case.id),
        case_number=case.case_number,
        new_status=str(case.status),
        action_type=action_type,
        message=message,
        decided_at=case.decided_at.isoformat() if case.decided_at else None,
    )


async def _emit_notification(case_id: str, event_type: str, payload: dict) -> None:
    """Fire-and-forget notification publishing (non-fatal on failure)."""
    try:
        from app.queues.publisher import TaskPublisher
        from app.queues.models import NotificationTask
        publisher = TaskPublisher()
        await publisher.publish(
            NotificationTask(
                case_id=case_id,
                event=event_type,
                channels=["in_app", "email"],
                subject=f"PA Case Update: {event_type}",
                body=str(payload),
                template_vars=payload,
            )
        )
    except Exception as exc:
        logger.warning("review.notification_failed", case_id=case_id, event=event_type, error=str(exc))


# ----------------------------------------------------------
# POST /review/{case_id}/approve
# ----------------------------------------------------------

@router.post(
    "/review/{case_id}/approve",
    response_model=SuccessResponse[ReviewActionResponse],
    summary="Approve prior authorization",
    description=(
        "Clinically approved by a reviewer. If AI recommended DENY, "
        "an override_reason is strongly encouraged (enforced by best practice, not mandatory)."
    ),
    tags=["Review"],
    responses={
        200: {"description": "Case approved"},
        401: {"description": "Authentication required"},
        403: {"description": "Reviewer or admin role required"},
        404: {"description": "Case not found"},
        409: {"description": "Case already decided"},
        429: {"description": "Rate limit exceeded"},
    },
)
async def approve_case(
    case_id: str,
    body: ApproveRequest,
    session: DbSession,
    current_user: CurrentUser = ReviewerRequired,
    _rate_limit = rate_limit("review"),
) -> ORJSONResponse:
    case_repo = PACaseRepository(session)
    case = await case_repo.get_by_id(case_id)
    if not case:
        raise CaseNotFoundError(details={"case_id": case_id})

    terminal = {CaseStatus.APPROVED, CaseStatus.DENIED, CaseStatus.CANCELLED}
    if case.status in terminal:
        raise CaseAlreadyDecidedError(details={"case_id": case_id, "current_status": str(case.status)})

    source = _decision_source(case.ai_recommendation, DecisionOutcome.APPROVE)

    await _create_decision(
        session,
        case_id=case_id,
        outcome=DecisionOutcome.APPROVE,
        source=source,
        rationale=body.rationale or "Approved by clinical reviewer",
        override_reason=body.override_reason,
        decided_by_id=current_user.sub,
    )

    action_type = (
        ReviewerActionType.OVERRIDE_APPROVED
        if source == DecisionSource.REVIEWER_OVERRIDE
        else ReviewerActionType.APPROVED
    )
    await _record_action_and_transition(
        session, case_id, current_user.sub,
        action_type, CaseStatus.APPROVED, body.rationale,
    )

    updated = await case_repo.get_by_id(case_id)

    METRICS.review_decisions_total.labels(outcome="APPROVE", source=str(source)).inc()
    await _emit_notification(case_id, "CASE_APPROVED", {"case_number": case.case_number})

    logger.info(
        "review.approved",
        case_id=case_id,
        case_number=case.case_number,
        reviewer_id=current_user.sub,
        decision_source=str(source),
        had_override=body.override_reason is not None,
    )

    return ORJSONResponse(
        content=SuccessResponse(
            data=_build_response(updated, str(action_type), "Case approved successfully")
        ).model_dump(mode="json"),
    )


# ----------------------------------------------------------
# POST /review/{case_id}/deny
# ----------------------------------------------------------

@router.post(
    "/review/{case_id}/deny",
    response_model=SuccessResponse[ReviewActionResponse],
    summary="Deny prior authorization",
    description=(
        "Deny the PA request with a clinical rationale. "
        "The rationale is included in the member denial letter."
    ),
    tags=["Review"],
    responses={
        200: {"description": "Case denied"},
        401: {"description": "Authentication required"},
        403: {"description": "Reviewer or admin role required"},
        404: {"description": "Case not found"},
        409: {"description": "Case already decided"},
    },
)
async def deny_case(
    case_id: str,
    body: DenyRequest,
    session: DbSession,
    current_user: CurrentUser = ReviewerRequired,
    _rate_limit = rate_limit("review"),
) -> ORJSONResponse:
    case_repo = PACaseRepository(session)
    case = await case_repo.get_by_id(case_id)
    if not case:
        raise CaseNotFoundError(details={"case_id": case_id})

    terminal = {CaseStatus.APPROVED, CaseStatus.DENIED, CaseStatus.CANCELLED}
    if case.status in terminal:
        raise CaseAlreadyDecidedError(details={"case_id": case_id, "current_status": str(case.status)})

    source = _decision_source(case.ai_recommendation, DecisionOutcome.DENY)

    await _create_decision(
        session,
        case_id=case_id,
        outcome=DecisionOutcome.DENY,
        source=source,
        rationale=body.rationale,
        override_reason=body.override_reason,
        decided_by_id=current_user.sub,
        denial_reason_code=body.denial_reason_code,
    )

    action_type = (
        ReviewerActionType.OVERRIDE_DENIED
        if source == DecisionSource.REVIEWER_OVERRIDE
        else ReviewerActionType.DENIED
    )
    await _record_action_and_transition(
        session, case_id, current_user.sub,
        action_type, CaseStatus.DENIED, body.rationale,
    )

    updated = await case_repo.get_by_id(case_id)

    METRICS.review_decisions_total.labels(outcome="DENY", source=str(source)).inc()
    await _emit_notification(case_id, "CASE_DENIED", {
        "case_number": case.case_number,
        "rationale": body.rationale,
    })

    logger.info(
        "review.denied",
        case_id=case_id,
        case_number=case.case_number,
        reviewer_id=current_user.sub,
        denial_reason_code=body.denial_reason_code,
        decision_source=str(source),
    )

    return ORJSONResponse(
        content=SuccessResponse(
            data=_build_response(updated, str(action_type), "Case denied")
        ).model_dump(mode="json"),
    )


# ----------------------------------------------------------
# POST /review/{case_id}/pend
# ----------------------------------------------------------

@router.post(
    "/review/{case_id}/pend",
    response_model=SuccessResponse[ReviewActionResponse],
    summary="Pend case for additional information",
    tags=["Review"],
)
async def pend_case(
    case_id: str,
    body: PendRequest,
    session: DbSession,
    current_user: CurrentUser = ReviewerRequired,
    _rate_limit = rate_limit("review"),
) -> ORJSONResponse:
    case_repo = PACaseRepository(session)
    case = await case_repo.get_by_id(case_id)
    if not case:
        raise CaseNotFoundError(details={"case_id": case_id})

    if case.status in {CaseStatus.APPROVED, CaseStatus.DENIED, CaseStatus.CANCELLED}:
        raise CaseAlreadyDecidedError(details={"case_id": case_id})

    await _create_decision(
        session,
        case_id=case_id,
        outcome=DecisionOutcome.PEND,
        source=DecisionSource.REVIEWER_OVERRIDE,
        rationale=body.rationale,
        override_reason=None,
        decided_by_id=current_user.sub,
    )
    await _record_action_and_transition(
        session, case_id, current_user.sub,
        ReviewerActionType.PENDED, CaseStatus.PENDED, body.rationale,
    )

    updated = await case_repo.get_by_id(case_id)
    METRICS.review_decisions_total.labels(outcome="PEND", source="REVIEWER_OVERRIDE").inc()

    await _emit_notification(case_id, "CASE_PENDED", {
        "case_number": case.case_number,
        "pending_reason": body.pending_reason,
    })

    logger.info(
        "review.pended",
        case_id=case_id,
        reviewer_id=current_user.sub,
        pending_reason=body.pending_reason,
    )

    return ORJSONResponse(
        content=SuccessResponse(
            data=_build_response(updated, "PENDED", "Case pended — awaiting additional information")
        ).model_dump(mode="json"),
    )


# ----------------------------------------------------------
# POST /review/{case_id}/escalate
# ----------------------------------------------------------

@router.post(
    "/review/{case_id}/escalate",
    response_model=SuccessResponse[ReviewActionResponse],
    summary="Escalate to senior reviewer",
    tags=["Review"],
)
async def escalate_case(
    case_id: str,
    body: EscalateRequest,
    session: DbSession,
    current_user: CurrentUser = ReviewerRequired,
    _rate_limit = rate_limit("review"),
) -> ORJSONResponse:
    case_repo = PACaseRepository(session)
    case = await case_repo.get_by_id(case_id)
    if not case:
        raise CaseNotFoundError(details={"case_id": case_id})

    if case.status in {CaseStatus.APPROVED, CaseStatus.DENIED, CaseStatus.CANCELLED}:
        raise CaseAlreadyDecidedError(details={"case_id": case_id})

    await _record_action_and_transition(
        session, case_id, current_user.sub,
        ReviewerActionType.ESCALATED, CaseStatus.ESCALATED, body.reason,
    )

    # Reassign if escalate_to specified
    if body.escalate_to:
        await case_repo.assign_reviewer(case_id, body.escalate_to)

    updated = await case_repo.get_by_id(case_id)
    METRICS.review_escalations_total.labels(has_target=str(bool(body.escalate_to))).inc()

    await _emit_notification(case_id, "CASE_ESCALATED", {
        "case_number": case.case_number,
        "escalated_by": current_user.sub,
        "reason": body.reason,
    })

    logger.info(
        "review.escalated",
        case_id=case_id,
        reviewer_id=current_user.sub,
        escalate_to=body.escalate_to,
    )

    return ORJSONResponse(
        content=SuccessResponse(
            data=_build_response(updated, "ESCALATED", "Case escalated to senior reviewer")
        ).model_dump(mode="json"),
    )


# ----------------------------------------------------------
# POST /review/{case_id}/notes
# ----------------------------------------------------------

@router.post(
    "/review/{case_id}/notes",
    status_code=status.HTTP_201_CREATED,
    response_model=SuccessResponse[ReviewActionResponse],
    summary="Add a case note",
    tags=["Review"],
)
async def add_note(
    case_id: str,
    body: AddNoteRequest,
    session: DbSession,
    current_user: CurrentUser = ReviewerRequired,
) -> ORJSONResponse:
    case_repo = PACaseRepository(session)
    case = await case_repo.get_by_id(case_id)
    if not case:
        raise CaseNotFoundError(details={"case_id": case_id})

    from app.db.repositories.reviewer_action import ReviewerActionRepository
    action_repo = ReviewerActionRepository(session)
    await action_repo.create(
        case_id=case_id,
        reviewer_id=current_user.sub,
        action_type=ReviewerActionType.ADDED_NOTE,
        rationale=body.note,
    )

    logger.info("review.note_added", case_id=case_id, reviewer_id=current_user.sub)

    return ORJSONResponse(
        status_code=status.HTTP_201_CREATED,
        content=SuccessResponse(
            data=_build_response(case, "ADDED_NOTE", "Note added to case audit trail")
        ).model_dump(mode="json"),
    )


# ----------------------------------------------------------
# POST /review/{case_id}/assign
# ----------------------------------------------------------

@router.post(
    "/review/{case_id}/assign",
    response_model=SuccessResponse[ReviewActionResponse],
    summary="Assign a reviewer to a case",
    tags=["Review"],
)
async def assign_reviewer(
    case_id: str,
    body: AssignRequest,
    session: DbSession,
    current_user: CurrentUser = require_role("admin"),
) -> ORJSONResponse:
    """Admin-only: assign a specific reviewer to a case."""
    case_repo = PACaseRepository(session)
    case = await case_repo.get_by_id(case_id)
    if not case:
        raise CaseNotFoundError(details={"case_id": case_id})

    await case_repo.assign_reviewer(case_id, body.reviewer_id)

    from app.db.repositories.reviewer_action import ReviewerActionRepository
    action_repo = ReviewerActionRepository(session)
    await action_repo.create(
        case_id=case_id,
        reviewer_id=current_user.sub,
        action_type=ReviewerActionType.ASSIGNED,
        rationale=f"Assigned to reviewer {body.reviewer_id}",
    )

    updated = await case_repo.get_by_id(case_id)

    logger.info(
        "review.assigned",
        case_id=case_id,
        reviewer_id=body.reviewer_id,
        assigned_by=current_user.sub,
    )

    return ORJSONResponse(
        content=SuccessResponse(
            data=_build_response(updated, "ASSIGNED", f"Case assigned to reviewer {body.reviewer_id}")
        ).model_dump(mode="json"),
    )
