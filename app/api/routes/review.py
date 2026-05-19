"""
Human reviewer workflow endpoints.

POST /review/{case_id}/approve   — Approve authorization
POST /review/{case_id}/deny      — Deny authorization
POST /review/{case_id}/pend      — Pend for additional information
POST /review/{case_id}/escalate  — Escalate to senior reviewer
POST /review/{case_id}/notes     — Add a case note
POST /review/{case_id}/assign    — Assign a reviewer (admin only)
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, status
from fastapi.responses import ORJSONResponse

from app.api.dependencies.common import require_role
from app.core.security.jwt import TokenPayload
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
)
from app.db.repositories.pa_case import PACaseRepository
from app.models.enums import (
    CaseStatus,
    DecisionOutcome,
    DecisionSource,
    ReviewerActionType,
)

logger = structlog.get_logger(__name__)
router = APIRouter()

ReviewerRequired = require_role("reviewer", "admin")


def _decision_source(
    case_ai_recommendation: str | None,
    action_outcome: DecisionOutcome,
) -> DecisionSource:
    if case_ai_recommendation and case_ai_recommendation == action_outcome.value:
        return DecisionSource.AI_RECOMMENDATION
    return DecisionSource.REVIEWER_OVERRIDE


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


async def _transition_status(
    session: DbSession,
    case_id: str,
    new_status: CaseStatus,
    actor_id: str,
) -> None:
    case_repo = PACaseRepository(session)
    await case_repo.transition_status(case_id, new_status, actor_id=actor_id)


def _build_response(case, action_type: str, message: str) -> ReviewActionResponse:
    return ReviewActionResponse(
        case_id=str(case.id),
        case_number=case.case_number,
        new_status=str(case.status),
        action_type=action_type,
        message=message,
        decided_at=case.decided_at.isoformat() if case.decided_at else None,
    )


# ----------------------------------------------------------
# POST /review/{case_id}/approve
# ----------------------------------------------------------

@router.post(
    "/review/{case_id}/approve",
    response_model=SuccessResponse[ReviewActionResponse],
    summary="Approve prior authorization",
    tags=["Review"],
)
async def approve_case(
    case_id: str,
    body: ApproveRequest,
    session: DbSession,
    current_user: TokenPayload = Depends(ReviewerRequired),
    _rate_limit = rate_limit("review"),
) -> ORJSONResponse:
    case_repo = PACaseRepository(session)
    case = await case_repo.get_by_id(case_id)
    if not case:
        raise CaseNotFoundError(details={"case_id": case_id})

    if case.status in {CaseStatus.APPROVED, CaseStatus.DENIED, CaseStatus.CANCELLED}:
        raise CaseAlreadyDecidedError(details={"case_id": case_id, "current_status": str(case.status)})

    source = _decision_source(case.ai_recommendation, DecisionOutcome.APPROVE)
    await _create_decision(
        session, case_id=case_id, outcome=DecisionOutcome.APPROVE, source=source,
        rationale=body.rationale or "Approved by clinical reviewer",
        override_reason=body.override_reason, decided_by_id=current_user.sub,
    )
    await _transition_status(session, case_id, CaseStatus.APPROVED, current_user.sub)
    updated = await case_repo.get_by_id(case_id)

    action_type = ReviewerActionType.OVERRIDE_APPROVED if source == DecisionSource.REVIEWER_OVERRIDE else ReviewerActionType.APPROVED
    logger.info("review.approved", case_id=case_id, reviewer_id=current_user.sub, source=str(source))

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
    tags=["Review"],
)
async def deny_case(
    case_id: str,
    body: DenyRequest,
    session: DbSession,
    current_user: TokenPayload = Depends(ReviewerRequired),
    _rate_limit = rate_limit("review"),
) -> ORJSONResponse:
    case_repo = PACaseRepository(session)
    case = await case_repo.get_by_id(case_id)
    if not case:
        raise CaseNotFoundError(details={"case_id": case_id})

    if case.status in {CaseStatus.APPROVED, CaseStatus.DENIED, CaseStatus.CANCELLED}:
        raise CaseAlreadyDecidedError(details={"case_id": case_id, "current_status": str(case.status)})

    source = _decision_source(case.ai_recommendation, DecisionOutcome.DENY)
    await _create_decision(
        session, case_id=case_id, outcome=DecisionOutcome.DENY, source=source,
        rationale=body.rationale, override_reason=body.override_reason,
        decided_by_id=current_user.sub, denial_reason_code=body.denial_reason_code,
    )
    await _transition_status(session, case_id, CaseStatus.DENIED, current_user.sub)
    updated = await case_repo.get_by_id(case_id)

    action_type = ReviewerActionType.OVERRIDE_DENIED if source == DecisionSource.REVIEWER_OVERRIDE else ReviewerActionType.DENIED
    logger.info("review.denied", case_id=case_id, reviewer_id=current_user.sub, source=str(source))

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
    current_user: TokenPayload = Depends(ReviewerRequired),
    _rate_limit = rate_limit("review"),
) -> ORJSONResponse:
    case_repo = PACaseRepository(session)
    case = await case_repo.get_by_id(case_id)
    if not case:
        raise CaseNotFoundError(details={"case_id": case_id})

    if case.status in {CaseStatus.APPROVED, CaseStatus.DENIED, CaseStatus.CANCELLED}:
        raise CaseAlreadyDecidedError(details={"case_id": case_id})

    await _create_decision(
        session, case_id=case_id, outcome=DecisionOutcome.PEND,
        source=DecisionSource.REVIEWER_OVERRIDE, rationale=body.rationale,
        override_reason=None, decided_by_id=current_user.sub,
    )
    await _transition_status(session, case_id, CaseStatus.PENDED, current_user.sub)
    updated = await case_repo.get_by_id(case_id)

    logger.info("review.pended", case_id=case_id, reviewer_id=current_user.sub)

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
    current_user: TokenPayload = Depends(ReviewerRequired),
    _rate_limit = rate_limit("review"),
) -> ORJSONResponse:
    case_repo = PACaseRepository(session)
    case = await case_repo.get_by_id(case_id)
    if not case:
        raise CaseNotFoundError(details={"case_id": case_id})

    if case.status in {CaseStatus.APPROVED, CaseStatus.DENIED, CaseStatus.CANCELLED}:
        raise CaseAlreadyDecidedError(details={"case_id": case_id})

    await _transition_status(session, case_id, CaseStatus.ESCALATED, current_user.sub)
    if body.escalate_to:
        await case_repo.assign_reviewer(case_id, body.escalate_to)

    updated = await case_repo.get_by_id(case_id)
    logger.info("review.escalated", case_id=case_id, reviewer_id=current_user.sub, escalate_to=body.escalate_to)

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
    current_user: TokenPayload = Depends(ReviewerRequired),
) -> ORJSONResponse:
    case_repo = PACaseRepository(session)
    case = await case_repo.get_by_id(case_id)
    if not case:
        raise CaseNotFoundError(details={"case_id": case_id})

    logger.info("review.note_added", case_id=case_id, reviewer_id=current_user.sub, note_length=len(body.note))

    return ORJSONResponse(
        status_code=status.HTTP_201_CREATED,
        content=SuccessResponse(
            data=_build_response(case, "ADDED_NOTE", "Note added to case")
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
    current_user: TokenPayload = Depends(require_role("admin")),
) -> ORJSONResponse:
    case_repo = PACaseRepository(session)
    case = await case_repo.get_by_id(case_id)
    if not case:
        raise CaseNotFoundError(details={"case_id": case_id})

    await case_repo.assign_reviewer(case_id, body.reviewer_id)
    updated = await case_repo.get_by_id(case_id)

    logger.info("review.assigned", case_id=case_id, reviewer_id=body.reviewer_id, assigned_by=current_user.sub)

    return ORJSONResponse(
        content=SuccessResponse(
            data=_build_response(updated, "ASSIGNED", f"Case assigned to reviewer {body.reviewer_id}")
        ).model_dump(mode="json"),
    )
