"""Document repository — OCR pipeline state management and dedup."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models.document import UploadedDocument
from app.models.enums import OCRStatus


class DocumentRepository(BaseRepository[UploadedDocument]):
    """Repository for UploadedDocument records."""

    model = UploadedDocument

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_case_id(self, case_id: str) -> list[UploadedDocument]:
        """Return all non-deleted documents for a case."""
        stmt = (
            select(UploadedDocument)
            .where(
                UploadedDocument.case_id == case_id,
                UploadedDocument.deleted_at.is_(None),
            )
            .order_by(UploadedDocument.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_checksum(self, checksum_sha256: str) -> UploadedDocument | None:
        """
        Find an existing document by SHA-256 checksum.
        Used for duplicate detection — if found, skip re-OCR.
        """
        stmt = select(UploadedDocument).where(
            UploadedDocument.checksum_sha256 == checksum_sha256,
            UploadedDocument.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_pending_ocr(self, limit: int = 50) -> list[UploadedDocument]:
        """Return documents waiting for OCR processing."""
        stmt = (
            select(UploadedDocument)
            .where(
                UploadedDocument.ocr_status == OCRStatus.PENDING,
                UploadedDocument.deleted_at.is_(None),
            )
            .order_by(UploadedDocument.created_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_ocr_result(
        self,
        document_id: str,
        ocr_status: OCRStatus,
        extracted_text: str | None = None,
        ocr_confidence: float | None = None,
        ocr_provider=None,
        ocr_raw_response: dict | None = None,
        error_message: str | None = None,
    ) -> UploadedDocument:
        """
        Update OCR pipeline results on a document.
        Called by the OCR service after processing completes.
        """
        kwargs = {
            "ocr_status": ocr_status,
        }
        if extracted_text is not None:
            kwargs["extracted_text"] = extracted_text
        if ocr_confidence is not None:
            kwargs["ocr_confidence"] = ocr_confidence
        if ocr_provider is not None:
            kwargs["ocr_provider"] = ocr_provider
        if ocr_raw_response is not None:
            kwargs["ocr_raw_response"] = ocr_raw_response
        if error_message is not None:
            kwargs["error_message"] = error_message

        return await self.update(document_id, **kwargs)

    async def increment_processing_attempts(self, document_id: str) -> UploadedDocument:
        """Increment the retry counter on a document."""
        doc = await self.get_by_id_or_raise(document_id)
        doc.processing_attempts += 1
        await self.session.flush()
        return doc
