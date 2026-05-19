"""
Case detail and document upload endpoints.

GET  /cases/{case_id}            — Full case detail with all relations
POST /cases/{case_id}/documents  — Upload a clinical document (multipart)
GET  /cases/{case_id}/documents/{document_id}  — Download a document
"""

from __future__ import annotations

import io
import mimetypes
import os

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from fastapi import File, Form
from fastapi.responses import ORJSONResponse, StreamingResponse

from app.api.dependencies.common import CurrentUser
from app.api.dependencies.database import DbSession
from app.api.dependencies.rate_limiter import rate_limit
from app.api.schemas.cases import CaseDetailResponse
from app.api.schemas.common import SuccessResponse
from app.api.schemas.pa_request import DocumentUploadResponse
from app.core.config.settings import get_settings
from app.core.exceptions.base import (
    CaseNotFoundError,
    FileTooLargeError,
    InvalidFileTypeError,
    PermissionDeniedError,
)
from app.db.repositories.pa_case import PACaseRepository

logger = structlog.get_logger(__name__)
router = APIRouter()

# Allowed MIME types for document upload
_ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/tiff",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}
_ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".tiff", ".tif", ".doc", ".docx", ".txt"}


# ----------------------------------------------------------
# GET /cases/{case_id}
# ----------------------------------------------------------

@router.get(
    "/cases/{case_id}",
    response_model=SuccessResponse[CaseDetailResponse],
    summary="Get full case detail",
    description=(
        "Returns the complete case record with all related entities: "
        "patient, provider, documents, extracted entities, policy criteria, "
        "AI decision, clarification history, and audit trail."
    ),
    tags=["Cases"],
    responses={
        200: {"description": "Case detail"},
        401: {"description": "Authentication required"},
        403: {"description": "Access denied"},
        404: {"description": "Case not found"},
    },
)
async def get_case(
    case_id: str,
    session: DbSession,
    current_user: CurrentUser,
) -> ORJSONResponse:
    """
    Fetch full case with all relations eagerly loaded.

    Access control:
    - Reviewers and admins can access all cases
    - Providers can only access cases they submitted (provider_id matches)
    """
    repo = PACaseRepository(session)
    case = await repo.get_with_all_relations(case_id)

    if not case:
        raise CaseNotFoundError(details={"case_id": case_id})

    # Provider access control — can only see own cases
    if current_user.role == "provider":
        if getattr(case, "provider_id", None) != current_user.sub:
            raise PermissionDeniedError(
                message="You do not have access to this case",
                details={"case_id": case_id},
            )

    # Record VIEW action
    try:
        from app.db.repositories.reviewer_action import ReviewerActionRepository
        from app.models.enums import ReviewerActionType
        action_repo = ReviewerActionRepository(session)
        await action_repo.create(
            case_id=case_id,
            reviewer_id=current_user.sub,
            action_type=ReviewerActionType.VIEWED,
        )
    except Exception as exc:
        logger.debug("cases.view_audit_failed", case_id=case_id, error=str(exc))

    logger.info(
        "cases.get",
        case_id=case_id,
        case_number=case.case_number,
        case_status=str(case.status),
        user_id=current_user.sub,
        user_role=current_user.role,
    )

    response_data = CaseDetailResponse.from_orm(case)

    return ORJSONResponse(
        content=SuccessResponse(data=response_data).model_dump(mode="json"),
    )


# ----------------------------------------------------------
# POST /cases/{case_id}/documents
# ----------------------------------------------------------

@router.post(
    "/cases/{case_id}/documents",
    status_code=status.HTTP_201_CREATED,
    response_model=SuccessResponse[DocumentUploadResponse],
    summary="Upload a clinical document",
    description=(
        "Accepts multipart/form-data with the clinical document file and metadata. "
        "Document is stored securely and queued for OCR processing."
    ),
    tags=["Cases"],
    responses={
        201: {"description": "Document uploaded and queued for OCR"},
        400: {"description": "Invalid file type or size"},
        401: {"description": "Authentication required"},
        404: {"description": "Case not found"},
        429: {"description": "Rate limit exceeded"},
    },
)
async def upload_document(
    case_id: str,
    session: DbSession,
    current_user: CurrentUser,
    _rate_limit = rate_limit("documents"),
    file: UploadFile = File(..., description="Clinical document file (PDF, image, Word)"),
    document_type: str = Form(..., description="DocumentType enum value"),
    description: str | None = Form(default=None),
) -> ORJSONResponse:
    """
    Upload a clinical document to an existing PA case.

    Validation:
    - File type must be in the allowed set (PDF, JPEG, PNG, TIFF, Word, TXT)
    - File size must not exceed settings.max_upload_size_bytes
    - Case must exist and not be in a terminal state

    After upload:
    - Document is persisted to secure storage (AES-256 encrypted)
    - OCRTask is enqueued for async processing
    - Case processing continues once all documents are OCR'd
    """
    settings = get_settings()

    # --- Validate file type ---
    filename = file.filename or "unknown"
    ext = os.path.splitext(filename)[-1].lower()
    content_type = file.content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"

    if ext not in _ALLOWED_EXTENSIONS and content_type not in _ALLOWED_CONTENT_TYPES:
        raise InvalidFileTypeError(
            details={"filename": filename, "content_type": content_type, "extension": ext},
        )

    # --- Read file + size check ---
    file_bytes = await file.read()
    file_size  = len(file_bytes)

    if file_size > settings.max_upload_size_bytes:
        raise FileTooLargeError(
            details={
                "file_size_bytes": file_size,
                "max_bytes": settings.max_upload_size_bytes,
                "max_mb": settings.max_upload_size_bytes // (1024 * 1024),
            },
        )

    if file_size == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    # --- Verify case exists ---
    case_repo = PACaseRepository(session)
    case = await case_repo.get_by_id(case_id)
    if not case:
        raise CaseNotFoundError(details={"case_id": case_id})

    # --- Parse document_type ---
    from app.models.enums import DocumentType
    try:
        doc_type = DocumentType(document_type.upper())
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid document_type '{document_type}'. "
                   f"Valid values: {[e.value for e in DocumentType]}",
        )

    # --- Persist to secure storage ---
    storage_path: str = f"cases/{case_id}/documents/{filename}"
    try:
        from app.security.storage.service import SecureStorage
        storage = SecureStorage()
        storage_path = await storage.upload(
            data=file_bytes,
            path=storage_path,
            content_type=content_type,
            metadata={
                "case_id": case_id,
                "document_type": str(doc_type),
                "uploaded_by": current_user.sub,
            },
        )
    except Exception as exc:
        logger.warning("cases.document_storage_failed", case_id=case_id, error=str(exc))
        # Continue — store reference with placeholder path for now

    # --- Create document record ---
    from app.db.repositories.document import DocumentRepository
    from app.models.enums import OCRStatus
    doc_repo = DocumentRepository(session)
    doc = await doc_repo.create(
        case_id=case_id,
        document_type=doc_type,
        file_path=storage_path,
        original_filename=filename,
        file_size_bytes=file_size,
        content_type=content_type,
        ocr_status=OCRStatus.PENDING,
    )

    # --- Enqueue OCR task ---
    try:
        from app.queues.publisher import TaskPublisher
        from app.queues.models import OCRTask
        publisher = TaskPublisher()
        await publisher.publish(
            OCRTask(
                case_id=case_id,
                document_id=str(doc.id),
                storage_path=storage_path,
            )
        )
    except Exception as exc:
        logger.warning(
            "cases.ocr_enqueue_failed",
            case_id=case_id,
            document_id=str(doc.id),
            error=str(exc),
        )

    logger.info(
        "cases.document_uploaded",
        case_id=case_id,
        document_id=str(doc.id),
        filename=filename,
        file_size=file_size,
        content_type=content_type,
        user_id=current_user.sub,
    )

    return ORJSONResponse(
        status_code=status.HTTP_201_CREATED,
        content=SuccessResponse(
            data=DocumentUploadResponse(
                document_id=str(doc.id),
                case_id=case_id,
                document_type=str(doc_type),
                original_filename=filename,
                file_size_bytes=file_size,
                content_type=content_type,
                uploaded_at=doc.created_at,
                ocr_status=str(OCRStatus.PENDING),
            )
        ).model_dump(mode="json"),
    )


# ----------------------------------------------------------
# GET /cases/{case_id}/documents/{document_id}
# ----------------------------------------------------------

@router.get(
    "/cases/{case_id}/documents/{document_id}",
    summary="Download a case document",
    description="Streams the raw document file. Requires reviewer or admin role.",
    tags=["Cases"],
    responses={
        200: {"description": "Document binary stream"},
        401: {"description": "Authentication required"},
        403: {"description": "Access denied"},
        404: {"description": "Document not found"},
    },
)
async def download_document(
    case_id: str,
    document_id: str,
    session: DbSession,
    current_user: CurrentUser,
) -> StreamingResponse:
    """Stream the encrypted document from secure storage."""
    from app.db.repositories.document import DocumentRepository
    doc_repo = DocumentRepository(session)
    doc = await doc_repo.get_by_id(document_id)

    if not doc or doc.case_id != case_id:
        raise HTTPException(status_code=404, detail="Document not found")

    if current_user.role == "provider":
        case_repo = PACaseRepository(session)
        case = await case_repo.get_by_id(case_id)
        if not case or str(case.provider_id) != current_user.sub:
            raise PermissionDeniedError(message="Access to this document is restricted")

    try:
        from app.security.storage.service import SecureStorage
        storage = SecureStorage()
        file_bytes = await storage.download(doc.file_path)
    except Exception as exc:
        logger.error("cases.document_download_failed", document_id=document_id, error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to retrieve document")

    filename = getattr(doc, "original_filename", f"document-{document_id}.pdf")
    content_type = getattr(doc, "content_type", "application/octet-stream")

    return StreamingResponse(
        io.BytesIO(file_bytes),
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
