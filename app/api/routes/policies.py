"""Policy management endpoints (Admin workflow)."""

from __future__ import annotations

import mimetypes
import os
from datetime import UTC, date, datetime

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import ORJSONResponse

from app.api.dependencies.common import CurrentUser, PaginationDep, require_role
from app.core.security.jwt import TokenPayload
from app.api.dependencies.database import DbSession
from app.api.dependencies.rate_limiter import rate_limit
from app.api.schemas.common import PaginationMeta, SuccessResponse
from app.api.schemas.policy import (
    PolicyChunkListResponse,
    PolicyListItem,
    PolicyListResponse,
    PolicyProcessResponse,
)
from app.core.config.settings import get_settings
from app.core.exceptions.base import FileTooLargeError, InvalidFileTypeError, ResourceNotFoundError
from app.db.repositories.policy import PolicyChunkRepository, PolicyRepository
from app.models.enums import PolicyEmbeddingStatus, PolicyProcessingStatus
from app.security.storage.service import SecureStorage
from app.services.policy.ingestion import PolicyIngestionService, build_policy_key, default_namespace
from app.services.vector.pinecone_indexer import PineconePolicyIndexer

logger = structlog.get_logger(__name__)
router = APIRouter()

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


@router.get(
    "/policies",
    response_model=SuccessResponse[PolicyListResponse],
    summary="List policies (Policy Management)",
    tags=["Policies"],
)
async def list_policies(
    session: DbSession,
    current_user: CurrentUser,
    pagination: PaginationDep,
    search: str | None = None,
    status: str | None = None,
    namespace: str | None = None,
) -> ORJSONResponse:
    processing_status: PolicyProcessingStatus | None = None
    if status:
        try:
            processing_status = PolicyProcessingStatus(status)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid status '{status}'. Valid values: {[e.value for e in PolicyProcessingStatus]}")

    repo = PolicyRepository(session)
    items, total = await repo.list_policies(
        search=search,
        status=processing_status,
        namespace=namespace,
        offset=pagination.offset,
        limit=pagination.limit,
    )

    data = PolicyListResponse(
        items=[PolicyListItem.from_orm_row(p) for p in items],
        total=total,
    )
    meta = PaginationMeta.build(pagination.page, pagination.page_size, total).model_dump(mode="json")
    return ORJSONResponse(content=SuccessResponse(data=data, meta=meta).model_dump(mode="json"))


@router.post(
    "/policies",
    status_code=status.HTTP_201_CREATED,
    response_model=SuccessResponse[dict],
    summary="Upload a policy document (manual)",
    tags=["Policies"],
)
async def upload_policy(
    session: DbSession,
    current_user: TokenPayload = Depends(require_role("admin")),
    _rate_limit=rate_limit("policies_upload"),
    file: UploadFile = File(..., description="Policy PDF/document"),
    policy_name: str = Form(...),
    policy_version: str = Form(default="v1"),
    policy_type: str | None = Form(default=None),
    effective_date: date | None = Form(default=None),
    pinecone_namespace: str | None = Form(default=None),
    policy_key: str | None = Form(default=None, description="Optional stable policy identifier"),
) -> ORJSONResponse:
    settings = get_settings()

    filename = file.filename or "policy"
    ext = os.path.splitext(filename)[-1].lower()
    content_type = file.content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"

    if ext not in _ALLOWED_EXTENSIONS and content_type not in _ALLOWED_CONTENT_TYPES:
        raise InvalidFileTypeError(details={"filename": filename, "content_type": content_type, "extension": ext})

    file_bytes = await file.read()
    file_size = len(file_bytes)

    if file_size == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if file_size > settings.max_upload_size_bytes:
        raise FileTooLargeError(details={"file_size_bytes": file_size, "max_bytes": settings.max_upload_size_bytes})

    repo = PolicyRepository(session)

    key = (policy_key or build_policy_key(policy_name or filename, policy_version)).strip()
    existing = await repo.get_by_key(key)
    if existing:
        raise HTTPException(status_code=409, detail=f"Policy key already exists: {key}")

    storage = SecureStorage()
    storage_path = await storage.upload(
        data=file_bytes,
        path=f"policies/{key}/{filename}",
        content_type=content_type,
        metadata={"policy_key": key, "uploaded_by": current_user.sub},
    )

    policy = await repo.create(
        policy_key=key,
        policy_name=policy_name,
        policy_version=policy_version,
        policy_type=policy_type,
        effective_date=effective_date,
        original_filename=filename,
        storage_path=storage_path,
        mime_type=content_type,
        file_size_bytes=file_size,
        pinecone_namespace=(pinecone_namespace or default_namespace()),
        processing_status=PolicyProcessingStatus.UPLOADED,
        embedding_status=PolicyEmbeddingStatus.NONE,
        total_chunks=0,
        last_error=None,
        last_processed_at=None,
    )

    return ORJSONResponse(
        status_code=status.HTTP_201_CREATED,
        content=SuccessResponse(
            data={"policy_id": str(policy.id), "policy_key": policy.policy_key}
        ).model_dump(mode="json"),
    )


@router.post(
    "/policies/{policy_id}/process",
    response_model=SuccessResponse[PolicyProcessResponse],
    summary="Process a policy (extract -> chunk -> embed -> store)",
    tags=["Policies"],
)
async def process_policy(
    policy_id: str,
    session: DbSession,
    current_user: TokenPayload = Depends(require_role("admin")),
) -> ORJSONResponse:
    repo = PolicyRepository(session)
    chunk_repo = PolicyChunkRepository(session)

    policy = await repo.get_by_id_or_raise(policy_id, not_found_exception=ResourceNotFoundError)

    # Read source document bytes
    storage = SecureStorage()
    try:
        content = await storage.download(path=policy.storage_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read policy file: {exc}")

    svc = PolicyIngestionService()

    try:
        # If reprocessing, remove prior vectors first (avoid namespace bloat)
        existing_vector_ids = await chunk_repo.get_vector_ids(policy_id)
        if existing_vector_ids:
            try:
                await PineconePolicyIndexer().delete_by_ids(
                    namespace=policy.pinecone_namespace,
                    ids=existing_vector_ids,
                )
            except Exception:
                # Non-fatal: proceed; new vectors will still upsert with deterministic IDs.
                logger.warning("policies.delete_existing_vectors_failed", policy_id=policy_id)

        await repo.update(policy_id, processing_status=PolicyProcessingStatus.EXTRACTED, last_error=None)
        extracted_text, warnings = await svc.extract_text(
            policy_document_id=str(policy.id),
            filename=policy.original_filename,
            mime_type=policy.mime_type or "",
            content=content,
        )
        await repo.update(policy_id, extracted_text=extracted_text, extraction_warnings=warnings)

        await chunk_repo.hard_delete_for_policy(policy_id)
        await repo.update(policy_id, processing_status=PolicyProcessingStatus.CHUNKED, total_chunks=0)

        total_chunks, chunk_rows, ingest_warnings = await svc.process_and_index(
            policy_key=policy.policy_key,
            policy_name=policy.policy_name,
            policy_version=policy.policy_version,
            policy_type=policy.policy_type,
            effective_date=policy.effective_date,
            namespace=policy.pinecone_namespace,
            text=extracted_text,
        )
        warnings = list(warnings) + list(ingest_warnings)

        # Persist chunks in DB
        if chunk_rows:
            await chunk_repo.bulk_create(
                [
                    {"policy_document_id": str(policy.id), **row}
                    for row in chunk_rows
                ]
            )

        await repo.update(
            policy_id,
            processing_status=PolicyProcessingStatus.STORED,
            embedding_status=PolicyEmbeddingStatus.STORED if total_chunks else PolicyEmbeddingStatus.NONE,
            total_chunks=total_chunks,
            last_processed_at=datetime.now(UTC),
            last_error=None,
        )

        data = PolicyProcessResponse(
            policy_id=str(policy.id),
            status=PolicyProcessingStatus.STORED,
            total_chunks=total_chunks,
            warnings=warnings,
        )
        return ORJSONResponse(content=SuccessResponse(data=data).model_dump(mode="json"))
    except Exception as exc:
        logger.exception("policies.process_failed", policy_id=policy_id, error=str(exc))
        await repo.update(
            policy_id,
            processing_status=PolicyProcessingStatus.FAILED,
            last_error=str(exc)[:2000],
        )
        raise HTTPException(status_code=500, detail=f"Processing failed: {exc}")


@router.get(
    "/policies/{policy_id}/chunks",
    response_model=SuccessResponse[PolicyChunkListResponse],
    summary="List processed chunks for a policy",
    tags=["Policies"],
)
async def list_policy_chunks(
    policy_id: str,
    session: DbSession,
    current_user: CurrentUser,
    pagination: PaginationDep,
) -> ORJSONResponse:
    _ = await PolicyRepository(session).get_by_id_or_raise(policy_id, not_found_exception=ResourceNotFoundError)
    repo = PolicyChunkRepository(session)
    items, total = await repo.list_chunks(
        policy_document_id=policy_id,
        offset=pagination.offset,
        limit=pagination.limit,
    )
    from app.api.schemas.policy import PolicyChunkItem

    data = PolicyChunkListResponse(
        items=[PolicyChunkItem.from_orm_row(c) for c in items],
        total=total,
    )
    meta = PaginationMeta.build(pagination.page, pagination.page_size, total).model_dump(mode="json")
    return ORJSONResponse(content=SuccessResponse(data=data, meta=meta).model_dump(mode="json"))


@router.delete(
    "/policies/{policy_id}/embeddings",
    response_model=SuccessResponse[dict],
    summary="Delete policy embeddings from Pinecone (keep metadata)",
    tags=["Policies"],
)
async def delete_policy_embeddings(
    policy_id: str,
    session: DbSession,
    current_user: TokenPayload = Depends(require_role("admin")),
) -> ORJSONResponse:
    policy_repo = PolicyRepository(session)
    chunk_repo = PolicyChunkRepository(session)
    policy = await policy_repo.get_by_id_or_raise(policy_id, not_found_exception=ResourceNotFoundError)

    vector_ids = await chunk_repo.get_vector_ids(policy_id)
    deleted = await PineconePolicyIndexer().delete_by_ids(namespace=policy.pinecone_namespace, ids=vector_ids)

    await policy_repo.update(policy_id, embedding_status=PolicyEmbeddingStatus.DELETED)
    return ORJSONResponse(content=SuccessResponse(data={"deleted_vectors": deleted}).model_dump(mode="json"))


@router.delete(
    "/policies/{policy_id}/chunks",
    response_model=SuccessResponse[dict],
    summary="Delete policy chunks from DB (keep file + policy record)",
    tags=["Policies"],
)
async def delete_policy_chunks(
    policy_id: str,
    session: DbSession,
    current_user: TokenPayload = Depends(require_role("admin")),
) -> ORJSONResponse:
    policy_repo = PolicyRepository(session)
    chunk_repo = PolicyChunkRepository(session)
    policy = await policy_repo.get_by_id_or_raise(policy_id, not_found_exception=ResourceNotFoundError)

    deleted = await chunk_repo.hard_delete_for_policy(policy_id)
    await policy_repo.update(
        policy_id,
        total_chunks=0,
        processing_status=PolicyProcessingStatus.EXTRACTED if policy.extracted_text else PolicyProcessingStatus.UPLOADED,
    )
    return ORJSONResponse(content=SuccessResponse(data={"deleted_chunks": deleted}).model_dump(mode="json"))


@router.delete(
    "/policies/{policy_id}",
    response_model=SuccessResponse[dict],
    summary="Delete a policy (Pinecone vectors + DB metadata)",
    tags=["Policies"],
)
async def delete_policy(
    policy_id: str,
    session: DbSession,
    current_user: TokenPayload = Depends(require_role("admin")),
) -> ORJSONResponse:
    policy_repo = PolicyRepository(session)
    chunk_repo = PolicyChunkRepository(session)
    policy = await policy_repo.get_by_id_or_raise(policy_id, not_found_exception=ResourceNotFoundError)

    vector_ids = await chunk_repo.get_vector_ids(policy_id)
    deleted_vectors = await PineconePolicyIndexer().delete_by_ids(namespace=policy.pinecone_namespace, ids=vector_ids)

    # Hard delete ensures chunk records are removed and no orphaned UI data remains.
    await policy_repo.hard_delete(policy_id)
    return ORJSONResponse(
        content=SuccessResponse(
            data={"deleted_vectors": deleted_vectors, "deleted_policy_id": policy_id}
        ).model_dump(mode="json")
    )
