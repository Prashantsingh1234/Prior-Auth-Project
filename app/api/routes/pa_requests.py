"""
PA Request submission and listing.

POST /pa-requests       — Submit a new prior authorization request
GET  /pa-requests       — List PA requests (alias for GET /cases)
GET  /cases             — List cases with filtering + pagination

Design:
- JSON request body with patient/provider/clinical details
- Documents uploaded separately via POST /cases/{id}/documents
- Returns 202 Accepted immediately; AI processing runs asynchronously
- Queue enqueues IngestionTask which triggers the full pipeline
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import ORJSONResponse

from app.api.dependencies.common import CurrentUser, PaginationDep
from app.api.dependencies.database import DbSession
from app.api.dependencies.rate_limiter import rate_limit
from app.api.schemas.cases import CaseDetailResponse, CaseListItemSchema, CaseListResponse
from app.api.schemas.common import PaginationMeta, SuccessResponse
from app.api.schemas.pa_request import PARequestCreate, PARequestSubmitResponse
from app.core.exceptions.base import (
    CaseNotFoundError,
    ResourceConflictError,
    ValidationError,
)
from app.db.repositories.pa_case import PACaseRepository
from app.db.repositories.patient import PatientRepository
from app.db.repositories.provider import ProviderRepository
from app.models.enums import CasePriority, CaseStatus, ServiceType
from app.monitoring.metrics import METRICS

logger = structlog.get_logger(__name__)

router = APIRouter()


# ----------------------------------------------------------
# Helper: build repository instances
# ----------------------------------------------------------

def _repos(session: DbSession):
    return (
        PACaseRepository(session),
        PatientRepository(session),
        ProviderRepository(session),
    )


# ----------------------------------------------------------
# POST /pa-requests
# ----------------------------------------------------------

@router.post(
    "/pa-requests",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=SuccessResponse[PARequestSubmitResponse],
    summary="Submit a prior authorization request",
    description=(
        "Creates a new PA case. Patient and provider records are created or matched. "
        "Returns 202 Accepted — AI processing (OCR, extraction, evaluation) proceeds asynchronously. "
        "Poll GET /cases/{id} to track progress."
    ),
    tags=["PA Requests"],
    responses={
        202: {"description": "Case accepted for processing"},
        409: {"description": "Duplicate submission detected"},
        422: {"description": "Validation error"},
        429: {"description": "Rate limit exceeded"},
    },
)
async def submit_pa_request(
    body: PARequestCreate,
    request: Request,
    session: DbSession,
    current_user: CurrentUser,
    _rate_limit = rate_limit("pa_requests"),
) -> ORJSONResponse:
    """
    Submit a new prior authorization request.

    Processing pipeline (async, after this endpoint returns 202):
    1. IngestionWorker picks up IngestionTask
    2. OCRWorker processes each uploaded document
    3. EmbeddingWorker chunks + embeds text
    4. LangGraph workflow runs: extraction → retrieval → evaluation → reasoning → decision
    5. If confidence low: ClarificationWorker generates questions
    6. Case moves to UNDER_REVIEW once AI evaluation completes
    """
    case_repo, patient_repo, provider_repo = _repos(session)

    # --- Resolve or create patient ---
    if body.patient.patient_id:
        patient = await patient_repo.get_by_id(body.patient.patient_id)
        if not patient:
            raise CaseNotFoundError(
                message=f"Patient {body.patient.patient_id} not found",
                details={"patient_id": body.patient.patient_id},
            )
    else:
        existing = await patient_repo.find_by_member_id(body.patient.member_id)
        if existing:
            patient = existing
        else:
            patient = await patient_repo.create(
                first_name=body.patient.first_name,
                last_name=body.patient.last_name,
                date_of_birth=body.patient.date_of_birth,
                gender=body.patient.gender,
                member_id=body.patient.member_id,
                group_number=body.patient.group_number,
                insurance_plan_name=body.patient.insurance_plan_name,
                insurance_plan_id=body.patient.insurance_plan_id,
            )

    # --- Resolve or create provider ---
    provider = await provider_repo.find_by_npi(body.provider.npi)
    if not provider:
        provider = await provider_repo.create(
            npi=body.provider.npi,
            first_name=body.provider.first_name,
            last_name=body.provider.last_name,
            specialty=body.provider.specialty,
            organization_name=body.provider.organization_name,
            phone=body.provider.phone,
            fax=body.provider.fax,
        )

    # --- Duplicate guard: same patient + same CPT codes already pending ---
    existing_cases = await case_repo.get_cases_for_patient(str(patient.id), limit=5)
    active_statuses = {
        CaseStatus.SUBMITTED, CaseStatus.PROCESSING,
        CaseStatus.PENDING_CLARIFICATION, CaseStatus.UNDER_REVIEW,
    }
    for ec in existing_cases:
        if ec.status in active_statuses:
            overlap = set(ec.cpt_codes or []) & set(body.cpt_codes)
            if overlap:
                raise ResourceConflictError(
                    message="An active PA request for this patient with overlapping procedure codes already exists.",
                    details={
                        "existing_case_id": str(ec.id),
                        "existing_case_number": ec.case_number,
                        "overlapping_cpt_codes": list(overlap),
                    },
                )

    # --- Create the PA case ---
    case = await case_repo.create_case(
        patient_id=str(patient.id),
        provider_id=str(provider.id),
        service_type=body.service_type,
        cpt_codes=body.cpt_codes,
        icd_codes=body.icd_codes,
        priority=body.priority,
        requested_service_description=body.requested_service_description,
        clinical_notes=body.clinical_notes,
        external_reference_id=body.external_reference_id,
        source_channel=body.source_channel or "api",
    )

    # --- Enqueue processing task ---
    try:
        from app.queues.publisher import TaskPublisher
        from app.queues.models import IngestionTask
        publisher = TaskPublisher()
        await publisher.publish(
            IngestionTask(
                case_id=str(case.id),
                document_id=None,
                document_url=None,
                document_type="PENDING",
                owner_id=current_user.sub,
            )
        )
    except Exception as exc:
        logger.warning(
            "pa_request.queue_enqueue_failed",
            case_id=str(case.id),
            error=str(exc),
        )
        # Non-fatal: case is created, can be re-queued via admin endpoint

    # Prometheus
    METRICS.pa_requests_submitted_total.labels(
        service_type=str(body.service_type),
        priority=str(body.priority),
        channel=body.source_channel or "api",
    ).inc()

    logger.info(
        "pa_request.submitted",
        case_id=str(case.id),
        case_number=case.case_number,
        patient_id=str(patient.id),
        provider_npi=provider.npi,
        service_type=str(body.service_type),
        priority=str(body.priority),
        user_id=current_user.sub,
    )

    return ORJSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content=SuccessResponse(
            data=PARequestSubmitResponse(
                case_id=str(case.id),
                case_number=case.case_number,
                status=str(case.status),
                priority=str(case.priority),
                submitted_at=case.submitted_at,
            )
        ).model_dump(mode="json"),
    )


# ----------------------------------------------------------
# GET /cases  (list with filters)
# ----------------------------------------------------------

@router.get(
    "/cases",
    response_model=SuccessResponse[CaseListResponse],
    summary="List PA cases",
    description=(
        "Returns a paginated, filterable list of PA cases. "
        "Reviewers see all cases; providers see only their own submissions."
    ),
    tags=["Cases"],
    responses={
        200: {"description": "Paginated case list"},
        401: {"description": "Authentication required"},
        429: {"description": "Rate limit exceeded"},
    },
)
async def list_cases(
    session: DbSession,
    current_user: CurrentUser,
    pagination: PaginationDep,
    _rate_limit = rate_limit("cases_list"),
    status_filter: list[str] | None = Query(default=None, alias="status"),
    priority_filter: list[str] | None = Query(default=None, alias="priority"),
    service_type_filter: list[str] | None = Query(default=None, alias="service_type"),
    assigned_to_me: bool = Query(default=False),
    sort_by: str = Query(default="submitted_at"),
    sort_dir: str = Query(default="desc"),
) -> ORJSONResponse:
    """List cases visible to the current user."""
    case_repo = PACaseRepository(session)

    # Parse enum filters
    statuses: list[CaseStatus] | None = None
    if status_filter:
        try:
            statuses = [CaseStatus(s) for s in status_filter]
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=f"Invalid status value: {exc}")

    priorities: list[CasePriority] | None = None
    if priority_filter:
        try:
            priorities = [CasePriority(p) for p in priority_filter]
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=f"Invalid priority value: {exc}")

    reviewer_id: str | None = None
    if assigned_to_me or current_user.role == "provider":
        reviewer_id = current_user.sub

    cases = await case_repo.get_reviewer_queue(
        reviewer_id=reviewer_id,
        statuses=statuses,
        priorities=priorities,
        skip=pagination.offset,
        limit=pagination.limit,
    )

    total = await _count_cases(case_repo, statuses, priorities, reviewer_id)
    meta  = PaginationMeta.build(pagination.page, pagination.page_size, total)

    # Eager-load patient+provider for list items
    case_items = []
    for c in cases:
        try:
            # Relationships may not be loaded in queue query — use lightweight version
            case_items.append(CaseListItemSchema.from_orm(c))
        except Exception as exc:
            logger.warning("cases.list_item_serialize_failed", case_id=str(c.id), error=str(exc))

    return ORJSONResponse(
        content=SuccessResponse(
            data=CaseListResponse(
                cases=case_items,
                meta=meta.model_dump(),
            ),
            meta=meta.model_dump(),
        ).model_dump(mode="json"),
    )


async def _count_cases(
    repo: PACaseRepository,
    statuses: list[CaseStatus] | None,
    priorities: list[CasePriority] | None,
    reviewer_id: str | None,
) -> int:
    """Return total count for pagination (simplified — uses status count map)."""
    try:
        counts = await repo.count_by_status()
        if statuses:
            return sum(counts.get(str(s), 0) for s in statuses)
        return sum(counts.values())
    except Exception:
        return 0
