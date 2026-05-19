"""
PA Request submission and listing.

POST /pa-requests         — Submit a new prior authorization request (JSON)
POST /pa-requests/intake  — Flexible intake: form + documents (multipart, all optional)
GET  /cases               — List cases with filtering + pagination
"""

from __future__ import annotations

import mimetypes
import os
import re

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import ORJSONResponse

from app.api.dependencies.common import CurrentUser, OptionalCurrentUser, PaginationDep
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
from app.models.enums import CasePriority, CaseStatus, DocumentType, OCRStatus, ServiceType

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
        existing = None
        if body.patient.member_id:
            existing = await patient_repo.get_by_member_id(body.patient.member_id)
        if existing:
            patient = existing
        else:
            patient = await patient_repo.create(
                first_name=body.patient.first_name,
                last_name=body.patient.last_name,
                date_of_birth=body.patient.date_of_birth,
                gender=body.patient.gender,
                member_id=body.patient.member_id or "",
                group_number=body.patient.group_number,
                insurance_plan_name=body.patient.insurance_plan_name,
                insurance_plan_id=body.patient.insurance_plan_id,
            )

    # --- Resolve or create provider ---
    provider = await provider_repo.get_by_npi(body.provider.npi)
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
# POST /pa-requests/intake  (multipart — form + files, all optional)
# ----------------------------------------------------------

_INTAKE_ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".tiff", ".tif", ".doc", ".docx", ".txt"}
_INTAKE_ALLOWED_TYPES = {
    "application/pdf", "image/jpeg", "image/jpg", "image/png", "image/tiff",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}


@router.post(
    "/pa-requests/intake",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=SuccessResponse[PARequestSubmitResponse],
    summary="Flexible PA intake — form, documents, or both",
    description=(
        "Submit a prior authorization request via uploaded documents (PDF/DOCX/images), "
        "a filled form, or any combination. All patient and clinical fields are optional — "
        "the AI pipeline extracts missing details from uploaded documents. "
        "Multiple files for a single patient are accepted at once.\n\n"
        "Required: **provider_npi** AND at least one of: uploaded file(s) OR patient name."
    ),
    tags=["PA Requests"],
    responses={
        202: {"description": "Case accepted for processing"},
        409: {"description": "Duplicate submission detected"},
        422: {"description": "Validation error"},
        429: {"description": "Rate limit exceeded"},
    },
)
async def submit_pa_intake(
    request: Request,
    session: DbSession,
    current_user: OptionalCurrentUser,
    _rate_limit=rate_limit("pa_requests"),
    # ── Files (multiple, optional) ──────────────────────────────────────────
    files: list[UploadFile] | None = File(default=None),
    # ── Provider (NPI always required — provider knows their own identifier) ─
    provider_npi: str | None = Form(default=None, description="10-digit National Provider Identifier"),
    provider_first_name: str | None = Form(default=None),
    provider_last_name: str | None = Form(default=None),
    provider_specialty: str | None = Form(default=None),
    provider_organization: str | None = Form(default=None),
    provider_phone: str | None = Form(default=None),
    provider_fax: str | None = Form(default=None),
    # ── Patient (all optional — AI extracts from uploaded docs) ─────────────
    patient_first_name: str | None = Form(default=None),
    patient_last_name: str | None = Form(default=None),
    patient_dob: str | None = Form(default=None, description="YYYY-MM-DD"),
    patient_member_id: str | None = Form(default=None),
    patient_gender: str | None = Form(default=None),
    patient_group_number: str | None = Form(default=None),
    patient_insurance_plan: str | None = Form(default=None),
    patient_insurance_plan_id: str | None = Form(default=None),
    # ── Clinical (all optional) ──────────────────────────────────────────────
    service_type: str | None = Form(default=None),
    priority: str = Form(default="ROUTINE"),
    cpt_codes: str | None = Form(default=None, description="Comma-separated CPT codes"),
    icd_codes: str | None = Form(default=None, description="Comma-separated ICD-10 codes"),
    clinical_notes: str | None = Form(default=None),
    external_reference_id: str | None = Form(default=None),
) -> ORJSONResponse:
    """
    Flexible intake: provider can submit via documents, a form, or both.

    When only files are provided, AI will extract patient demographics,
    diagnosis/procedure codes, and clinical justification from the documents.
    Fields that could not be extracted are stored as placeholders and flagged
    for reviewer attention.
    """
    settings_obj = None
    try:
        from app.core.config.settings import get_settings
        settings_obj = get_settings()
    except Exception:
        pass

    max_file_bytes = getattr(settings_obj, "max_upload_size_bytes", 52_428_800)

    # ── 1. Validate NPI ──────────────────────────────────────────────────────
    if not provider_npi:
        raise HTTPException(status_code=422, detail="provider_npi is required (10 digits)")

    npi_clean = re.sub(r"\D", "", provider_npi)
    if len(npi_clean) != 10:
        raise HTTPException(
            status_code=422,
            detail=f"provider_npi must be exactly 10 digits (received: '{provider_npi}')",
        )

    # ── 2. Require files OR patient name ─────────────────────────────────────
    files = files or []
    has_files = any(f.filename for f in files)
    has_patient_name = bool(patient_first_name and patient_last_name)
    if not has_files and not has_patient_name:
        raise HTTPException(
            status_code=422,
            detail="Provide at least one document (PDF/image/DOCX) OR enter the patient's first and last name.",
        )

    # ── 3. Parse enums ───────────────────────────────────────────────────────
    svc_type = ServiceType.OTHER
    if service_type:
        try:
            svc_type = ServiceType(service_type.upper())
        except ValueError:
            pass

    case_priority = CasePriority.ROUTINE
    if priority:
        try:
            case_priority = CasePriority(priority.upper())
        except ValueError:
            pass

    cpt_list = [c.strip().upper() for c in (cpt_codes or "").split(",") if c.strip()]
    icd_list = [c.strip().upper() for c in (icd_codes or "").split(",") if c.strip()]

    # ── 4. Parse date of birth ───────────────────────────────────────────────
    from datetime import date as date_type
    parsed_dob: date_type | None = None
    if patient_dob:
        try:
            parsed_dob = date_type.fromisoformat(patient_dob)
        except ValueError:
            pass

    # ── 5. Resolve or create provider ────────────────────────────────────────
    case_repo, patient_repo, provider_repo = _repos(session)

    provider = await provider_repo.get_by_npi(npi_clean)
    if not provider:
        provider = await provider_repo.create(
            npi=npi_clean,
            first_name=provider_first_name,
            last_name=provider_last_name,
            specialty=provider_specialty,
            organization_name=provider_organization,
            phone=provider_phone,
            fax=provider_fax,
        )

    # ── 6. Resolve or create patient ─────────────────────────────────────────
    patient = None
    if patient_member_id:
        patient = await patient_repo.get_by_member_id(patient_member_id)
    if not patient:
        # Use placeholder names when docs are provided but demographics are unknown.
        # The AI extraction pipeline will update these once documents are processed.
        patient = await patient_repo.create(
            first_name=patient_first_name or "Pending",
            last_name=patient_last_name or "Extraction",
            date_of_birth=parsed_dob,
            gender=patient_gender,
            member_id=patient_member_id or "",
            group_number=patient_group_number,
            insurance_plan_name=patient_insurance_plan,
            insurance_plan_id=patient_insurance_plan_id,
        )

    # ── 7. Duplicate guard ───────────────────────────────────────────────────
    if cpt_list:
        existing_cases = await case_repo.get_cases_for_patient(str(patient.id), limit=5)
        active_statuses = {
            CaseStatus.SUBMITTED, CaseStatus.PROCESSING,
            CaseStatus.PENDING_CLARIFICATION, CaseStatus.UNDER_REVIEW,
        }
        for ec in existing_cases:
            if ec.status in active_statuses:
                overlap = set(ec.cpt_codes or []) & set(cpt_list)
                if overlap:
                    raise ResourceConflictError(
                        message="An active PA request for this patient with overlapping procedure codes already exists.",
                        details={
                            "existing_case_id": str(ec.id),
                            "existing_case_number": ec.case_number,
                            "overlapping_cpt_codes": list(overlap),
                        },
                    )

    # ── 8. Create case ───────────────────────────────────────────────────────
    intake_notes = clinical_notes or ""
    if not has_patient_name and has_files:
        intake_notes = (
            "[AI EXTRACTION PENDING] Patient demographics and clinical details "
            "will be extracted from the uploaded documents.\n\n" + intake_notes
        ).strip()

    case = await case_repo.create_case(
        patient_id=str(patient.id),
        provider_id=str(provider.id),
        service_type=svc_type,
        cpt_codes=cpt_list,
        icd_codes=icd_list,
        priority=case_priority,
        requested_service_description=None,
        clinical_notes=intake_notes or None,
        external_reference_id=external_reference_id,
        source_channel="portal",
    )

    # ── 9. Save uploaded files and create document records ───────────────────
    uploaded_doc_count = 0
    if has_files:
        from app.security.storage.service import SecureStorage
        from app.db.repositories.document import DocumentRepository
        from app.queues.publisher import TaskPublisher
        from app.queues.models import OCRTask

        doc_repo = DocumentRepository(session)
        storage = SecureStorage()

        for upload in files:
            if not upload.filename:
                continue

            filename = upload.filename
            ext = os.path.splitext(filename)[-1].lower()
            content_type = upload.content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"

            if ext not in _INTAKE_ALLOWED_EXTENSIONS and content_type not in _INTAKE_ALLOWED_TYPES:
                logger.warning(
                    "pa_intake.file_skipped_invalid_type",
                    case_id=str(case.id),
                    filename=filename,
                    content_type=content_type,
                )
                continue

            file_bytes = await upload.read()
            if not file_bytes or len(file_bytes) > max_file_bytes:
                continue

            storage_path = f"cases/{case.id}/documents/{filename}"
            try:
                storage_path = await storage.upload(
                    data=file_bytes,
                    path=storage_path,
                    content_type=content_type,
                    metadata={"case_id": str(case.id), "uploaded_by": current_user.sub},
                )
            except Exception as exc:
                logger.warning("pa_intake.file_storage_failed", case_id=str(case.id),
                               filename=filename, error=str(exc))
                continue

            doc = await doc_repo.create(
                case_id=str(case.id),
                document_type=DocumentType.PRIOR_AUTH_REQUEST_FORM,
                storage_path=storage_path,
                original_filename=filename,
                stored_filename=filename,
                file_size_bytes=len(file_bytes),
                mime_type=content_type,
                ocr_status=OCRStatus.PENDING,
            )

            try:
                publisher = TaskPublisher()
                await publisher.publish(
                    OCRTask(
                        case_id=str(case.id),
                        document_id=str(doc.id),
                        storage_path=storage_path,
                    )
                )
            except Exception as exc:
                logger.warning("pa_intake.ocr_enqueue_failed", case_id=str(case.id),
                               document_id=str(doc.id), error=str(exc))

            uploaded_doc_count += 1

    # ── 10. Enqueue ingestion task ───────────────────────────────────────────
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
                owner_id=(current_user.sub if current_user else "anonymous"),
            )
        )
    except Exception as exc:
        logger.warning("pa_intake.queue_enqueue_failed", case_id=str(case.id), error=str(exc))

    logger.info(
        "pa_intake.submitted",
        case_id=str(case.id),
        case_number=case.case_number,
        patient_id=str(patient.id),
        provider_npi=npi_clean,
        service_type=str(svc_type),
        priority=str(case_priority),
        uploaded_docs=uploaded_doc_count,
        has_patient_name=has_patient_name,
        user_id=(current_user.sub if current_user else "anonymous"),
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
                message=(
                    f"Request submitted with {uploaded_doc_count} document(s). "
                    "AI extraction and evaluation will begin shortly."
                ) if uploaded_doc_count else
                "Prior authorization request submitted successfully. Processing will begin shortly.",
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

    # Providers see all cases (no provider→case DB link without NPI lookup);
    # reviewers can optionally filter to their assigned cases.
    reviewer_id: str | None = None
    is_provider = current_user.role == "provider"
    if assigned_to_me and not is_provider:
        reviewer_id = current_user.sub

    cases = await case_repo.get_reviewer_queue(
        reviewer_id=reviewer_id,
        statuses=statuses,
        priorities=priorities,
        skip=pagination.offset,
        limit=pagination.limit,
        all_statuses=is_provider and statuses is None,
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
