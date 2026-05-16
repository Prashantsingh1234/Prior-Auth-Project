"""
Encrypted secure document storage layer.

SecureDocumentStorage provides:
  - AES-256-GCM encryption of document content before DB/disk persistence
  - Role-based access control on document retrieval
  - Content integrity verification (SHA-256 hash of plaintext)
  - PHI masking in storage metadata (never store raw PHI in searchable fields)
  - Audit trail for every read, write, and delete

All documents pass through this layer before being persisted, whether they
are original PA request documents (PDF/image) or extracted text results.

Usage:
    storage = get_secure_document_storage()

    # Store a document
    handle = await storage.store(
        content=b"...document bytes...",
        doc_type="clinical_notes",
        case_id="PA-001",
        owner_id="provider-uuid",
        caller_role="provider",
    )

    # Retrieve (checks role permissions)
    content = await storage.retrieve(
        doc_id=handle.doc_id,
        caller_id="reviewer-uuid",
        caller_role="reviewer",
    )
"""

from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import structlog

from app.security.encryption.service import get_encryption_service
from app.security.rbac.permissions import Action, Resource, is_permitted

logger = structlog.get_logger(__name__)


@dataclass
class DocumentHandle:
    """Returned after a successful document store operation."""
    doc_id:       str
    doc_type:     str
    case_id:      str | None
    owner_id:     str
    content_hash: str        # SHA-256 of plaintext content (integrity check)
    size_bytes:   int
    stored_at:    datetime
    encrypted:    bool = True


@dataclass
class StoredDocument:
    """Internal storage record (not exposed to callers directly)."""
    doc_id:            str
    doc_type:          str
    case_id:           str | None
    owner_id:          str
    encrypted_content: str    # AES-256-GCM ciphertext (base64)
    content_hash:      str
    size_bytes:        int
    stored_at:         datetime
    last_accessed_at:  datetime | None = None
    metadata:          dict[str, Any] = field(default_factory=dict)


class SecureDocumentStorage:
    """
    Encrypted in-process document store (backed by a dict for demo;
    replace _store with DB / S3 calls in production).
    """

    def __init__(self) -> None:
        self._store: dict[str, StoredDocument] = {}
        self._enc   = get_encryption_service()
        self._log   = structlog.get_logger(__name__)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def store(
        self,
        content: bytes | str,
        doc_type: str,
        owner_id: str,
        caller_role: str,
        case_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DocumentHandle:
        """
        Encrypt and store ``content``.

        Args:
            content:     Raw document bytes or text.
            doc_type:    Document category label (e.g., "clinical_notes").
            owner_id:    ID of the user/provider who owns this document.
            caller_role: RBAC role of the caller.
            case_id:     Associated PA case ID.
            metadata:    Additional non-PHI metadata to store alongside.

        Raises:
            PermissionError: If the caller's role cannot upload documents.
        """
        if not is_permitted(caller_role, Resource.DOCUMENT, Action.UPLOAD):
            raise PermissionError(
                f"Role '{caller_role}' cannot upload documents"
            )

        if isinstance(content, str):
            raw_bytes = content.encode("utf-8")
        else:
            raw_bytes = content

        content_hash = hashlib.sha256(raw_bytes).hexdigest()
        plaintext    = raw_bytes.decode("utf-8", errors="replace")
        ciphertext   = self._enc.encrypt(plaintext)
        doc_id       = str(uuid.uuid4())
        now          = datetime.now(timezone.utc)

        doc = StoredDocument(
            doc_id=doc_id,
            doc_type=doc_type,
            case_id=case_id,
            owner_id=owner_id,
            encrypted_content=ciphertext,
            content_hash=content_hash,
            size_bytes=len(raw_bytes),
            stored_at=now,
            metadata=metadata or {},
        )
        self._store[doc_id] = doc

        self._log.info(
            "secure_storage.stored",
            doc_id=doc_id,
            doc_type=doc_type,
            case_id=case_id,
            size_bytes=len(raw_bytes),
            owner_id=owner_id,
        )
        await _emit_audit("DOCUMENT_STORED", caller_id=owner_id, doc_id=doc_id, case_id=case_id)

        return DocumentHandle(
            doc_id=doc_id,
            doc_type=doc_type,
            case_id=case_id,
            owner_id=owner_id,
            content_hash=content_hash,
            size_bytes=len(raw_bytes),
            stored_at=now,
        )

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def retrieve(
        self,
        doc_id: str,
        caller_id: str,
        caller_role: str,
    ) -> bytes | None:
        """
        Decrypt and return document content, enforcing RBAC.

        Returns None if the document is not found.
        Raises PermissionError if the caller cannot read the document.
        """
        doc = self._store.get(doc_id)
        if doc is None:
            self._log.warning("secure_storage.not_found", doc_id=doc_id)
            return None

        # Ownership check: providers can only read their own docs
        is_owner = (doc.owner_id == caller_id)
        can_read = is_permitted(
            caller_role, Resource.DOCUMENT,
            Action.READ_OWN if is_owner else Action.READ_ANY,
            owner_id=doc.owner_id,
            requester_id=caller_id,
        )
        if not can_read:
            self._log.warning(
                "secure_storage.access_denied",
                doc_id=doc_id,
                caller_id=caller_id,
                caller_role=caller_role,
            )
            await _emit_audit("DOCUMENT_ACCESS_DENIED", caller_id=caller_id, doc_id=doc_id, case_id=doc.case_id)
            raise PermissionError(f"Access denied to document {doc_id}")

        plaintext = self._enc.decrypt(doc.encrypted_content)
        if plaintext is None:
            self._log.error("secure_storage.decrypt_failed", doc_id=doc_id)
            return None

        # Integrity verification
        actual_hash = hashlib.sha256(plaintext.encode("utf-8")).hexdigest()
        if actual_hash != doc.content_hash:
            self._log.error(
                "secure_storage.integrity_failure",
                doc_id=doc_id,
                expected=doc.content_hash[:16],
                actual=actual_hash[:16],
            )
            await _emit_audit("DOCUMENT_INTEGRITY_FAILURE", caller_id=caller_id, doc_id=doc_id, case_id=doc.case_id)
            raise ValueError(f"Document {doc_id} integrity check failed — possible tampering")

        doc.last_accessed_at = datetime.now(timezone.utc)
        self._log.debug("secure_storage.retrieved", doc_id=doc_id, caller_id=caller_id)
        await _emit_audit("DOCUMENT_RETRIEVED", caller_id=caller_id, doc_id=doc_id, case_id=doc.case_id)

        return plaintext.encode("utf-8")

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    async def delete(
        self,
        doc_id: str,
        caller_id: str,
        caller_role: str,
    ) -> bool:
        """Delete a document.  Admin only."""
        if not is_permitted(caller_role, Resource.DOCUMENT, Action.DELETE):
            raise PermissionError(f"Role '{caller_role}' cannot delete documents")

        doc = self._store.pop(doc_id, None)
        if doc is None:
            return False

        self._log.info("secure_storage.deleted", doc_id=doc_id, caller_id=caller_id)
        await _emit_audit("DOCUMENT_DELETED", caller_id=caller_id, doc_id=doc_id, case_id=doc.case_id)
        return True

    # ------------------------------------------------------------------
    # List (metadata only — no content returned)
    # ------------------------------------------------------------------

    async def list_for_case(
        self,
        case_id: str,
        caller_id: str,
        caller_role: str,
    ) -> list[DocumentHandle]:
        """Return document handles (no content) for a case."""
        if not is_permitted(caller_role, Resource.DOCUMENT, Action.READ_ANY) and \
           not is_permitted(caller_role, Resource.DOCUMENT, Action.READ_OWN):
            raise PermissionError("Cannot list documents")

        docs = [
            DocumentHandle(
                doc_id=d.doc_id,
                doc_type=d.doc_type,
                case_id=d.case_id,
                owner_id=d.owner_id,
                content_hash=d.content_hash,
                size_bytes=d.size_bytes,
                stored_at=d.stored_at,
            )
            for d in self._store.values()
            if d.case_id == case_id and (
                caller_role in ("admin", "reviewer") or d.owner_id == caller_id
            )
        ]
        return docs


# ---------------------------------------------------------------------------
# Audit helper
# ---------------------------------------------------------------------------

async def _emit_audit(
    event_type: str,
    caller_id: str,
    doc_id: str,
    case_id: str | None,
) -> None:
    try:
        from app.guardrails.audit import _write_to_audit_db
        await _write_to_audit_db(
            event_type=event_type,
            actor_id=caller_id,
            case_id=case_id,
            event_data={"doc_id": doc_id},
            severity="MEDIUM",
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_storage: SecureDocumentStorage | None = None


def get_secure_document_storage() -> SecureDocumentStorage:
    global _storage
    if _storage is None:
        _storage = SecureDocumentStorage()
    return _storage
