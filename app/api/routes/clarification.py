"""
Clarification loop endpoints.

POST /clarification/{case_id}/respond   — Submit provider response to clarification
GET  /clarification/{case_id}           — List clarifications for a case

Clarification flow:
  AI generates questions → case moves to PENDING_CLARIFICATION →
  Provider submits response → case re-enters evaluation pipeline →
  If still unresolved after 3 attempts → auto-escalate
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, status
from fastapi.responses import ORJSONResponse

from app.api.dependencies.common import CurrentUser
from app.api.dependencies.database import DbSession
from app.api.dependencies.rate_limiter import rate_limit
from app.api.schemas.clarification import (
    ClarificationRespondRequest,
    ClarificationResponseBody,
)
from app.api.schemas.common import SuccessResponse
from app.core.exceptions.base import (
    CaseNotFoundError,
    ClarificationLimitExceededError,
    PermissionDeniedError,
    ResourceConflictError,
    ResourceNotFoundError,
)
from app.db.repositories.clarification import ClarificationRepository
from app.db.repositories.pa_case import PACaseRepository
from app.models.enums import CaseStatus, ClarificationStatus
from app.monitoring.metrics import METRICS

logger = structlog.get_logger(__name__)

router = APIRouter()


# ----------------------------------------------------------
# POST /clarification/{case_id}/respond
# ----------------------------------------------------------

@router.post(
    "/clarification/{case_id}/respond",
    response_model=SuccessResponse[ClarificationResponseBody],
    summary="Submit a response to a clarification request",
    description=(
        "Provider submits the response to an outstanding clarification. "
        "Case is re-queued for AI re-evaluation with the new evidence."
    ),
    tags=["Clarification"],
    responses={
        200: {"description": "Response recorded; case re-queued for evaluation"},
        401: {"description": "Authentication required"},
        403: {"description": "Only the submitting provider can respond"},
        404: {"description": "Case or clarification not found"},
        409: {"description": "Clarification already answered or case not in correct state"},
        429: {"description": "Rate limit exceeded"},
    },
)
async def respond_to_clarification(
    case_id: str,
    body: ClarificationRespondRequest,
    session: DbSession,
    current_user: CurrentUser,
    _rate_limit = rate_limit("clarification"),
) -> ORJSONResponse:
    """
    Record a provider's response to a pending clarification request.

    State machine:
    1. Validate case is in PENDING_CLARIFICATION status
    2. Mark clarification as ANSWERED
    3. Transition case to PROCESSING (re-evaluate with new info)
    4. Enqueue EvaluationTask to re-run AI against updated evidence
    5. Increment clarification_count
    6. If count >= 3: auto-escalate to human reviewer
    """
    case_repo  = PACaseRepository(session)
    cl_repo    = ClarificationRepository(session)

    # --- Validate case ---
    case = await case_repo.get_by_id(case_id)
    if not case:
        raise CaseNotFoundError(details={"case_id": case_id})

    if case.status != CaseStatus.PENDING_CLARIFICATION:
        raise ResourceConflictError(
            message=f"Case is not awaiting clarification (current status: {case.status})",
            details={"case_id": case_id, "current_status": str(case.status)},
        )

    # --- Validate clarification record ---
    clarification = await cl_repo.get_by_id(body.clarification_id)
    if not clarification or clarification.case_id != case_id:
        raise ResourceNotFoundError(
            message="Clarification request not found",
            details={"clarification_id": body.clarification_id},
        )

    if clarification.status != ClarificationStatus.PENDING:
        raise ResourceConflictError(
            message=f"Clarification is already {clarification.status}",
            details={"clarification_id": body.clarification_id, "status": str(clarification.status)},
        )

    # --- Access control: only the submitting provider or admin can respond ---
    if current_user.role not in ("admin", "reviewer"):
        provider_id = str(getattr(case, "provider_id", ""))
        if provider_id != current_user.sub:
            raise PermissionDeniedError(
                message="Only the submitting provider can respond to clarifications",
            )

    # --- Record response ---
    now = datetime.now(UTC)
    clarification.status     = ClarificationStatus.ANSWERED
    clarification.response   = body.response
    clarification.answered_at = now
    await session.flush()

    # --- Transition case ---
    await case_repo.increment_clarification_count(case_id)

    MAX_CLARIFICATIONS = 3
    if case.clarification_count + 1 >= MAX_CLARIFICATIONS:
        # Auto-escalate: provider hasn't provided sufficient evidence
        await case_repo.transition_status(case_id, CaseStatus.ESCALATED, actor_id=current_user.sub)

        from app.db.repositories.reviewer_action import ReviewerActionRepository
        from app.models.enums import ReviewerActionType
        action_repo = ReviewerActionRepository(session)
        await action_repo.create(
            case_id=case_id,
            reviewer_id=current_user.sub,
            action_type=ReviewerActionType.ESCALATED,
            rationale=f"Auto-escalated after {MAX_CLARIFICATIONS} clarification attempts",
        )

        METRICS.clarification_exhausted_total.inc()
        logger.warning(
            "clarification.auto_escalated",
            case_id=case_id,
            clarification_count=case.clarification_count + 1,
        )
    else:
        # Re-queue for AI re-evaluation with new evidence
        await case_repo.transition_status(case_id, CaseStatus.PROCESSING, actor_id=current_user.sub)

        try:
            from app.queues.publisher import TaskPublisher
            from app.queues.models import EvaluationTask
            publisher = TaskPublisher()
            await publisher.publish(
                EvaluationTask(
                    case_id=case_id,
                    run_id=f"clarification-{body.clarification_id[:8]}",
                    evaluator_names=["policy_compliance", "medical_necessity"],
                    inputs={"clarification_response": body.response},
                    outputs={},
                    reference={},
                )
            )
        except Exception as exc:
            logger.warning(
                "clarification.requeue_failed",
                case_id=case_id,
                error=str(exc),
            )

    updated_case = await case_repo.get_by_id(case_id)

    METRICS.clarification_responses_total.labels(case_status=str(updated_case.status)).inc()

    logger.info(
        "clarification.responded",
        case_id=case_id,
        clarification_id=body.clarification_id,
        new_case_status=str(updated_case.status),
        clarification_count=updated_case.clarification_count,
        user_id=current_user.sub,
    )

    return ORJSONResponse(
        content=SuccessResponse(
            data=ClarificationResponseBody(
                clarification_id=body.clarification_id,
                case_id=case_id,
                case_number=case.case_number,
                status=str(updated_case.status),
                answered_at=now,
            )
        ).model_dump(mode="json"),
    )


# ----------------------------------------------------------
# GET /clarification/{case_id}
# ----------------------------------------------------------

@router.get(
    "/clarification/{case_id}",
    summary="List clarifications for a case",
    description="Returns all clarification requests and responses for the given case.",
    tags=["Clarification"],
)
async def list_clarifications(
    case_id: str,
    session: DbSession,
    current_user: CurrentUser,
) -> ORJSONResponse:
    """List all clarifications with their statuses and responses."""
    case_repo = PACaseRepository(session)
    case = await case_repo.get_by_id(case_id)
    if not case:
        raise CaseNotFoundError(details={"case_id": case_id})

    cl_repo = ClarificationRepository(session)
    clarifications = await cl_repo.get_by_case_id(case_id)

    items = [
        {
            "clarification_id": str(cl.id),
            "question": cl.question,
            "status": str(cl.status),
            "attempt_number": cl.attempt_number,
            "sent_at": cl.created_at.isoformat(),
            "answered_at": cl.answered_at.isoformat() if cl.answered_at else None,
            "response": cl.response,
        }
        for cl in clarifications
    ]

    return ORJSONResponse(
        content=SuccessResponse(data=items, meta={"total": len(items)}).model_dump(mode="json"),
    )
