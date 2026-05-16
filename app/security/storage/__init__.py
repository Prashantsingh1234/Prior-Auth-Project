"""Secure storage sub-package."""
from app.security.storage.service import (
    DocumentHandle,
    SecureDocumentStorage,
    get_secure_document_storage,
)

__all__ = ["DocumentHandle", "SecureDocumentStorage", "get_secure_document_storage"]
