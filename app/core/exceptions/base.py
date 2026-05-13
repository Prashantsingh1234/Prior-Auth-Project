"""
Custom exception hierarchy for the PA Review Platform.

Design:
- All platform exceptions inherit from PABaseException for uniform handling
- Each exception carries an error_code for machine-readable classification
- HTTP status codes are declared on the exception class, not in handler logic
- This keeps business logic free from HTTP concerns while keeping handler code minimal

Error Code Convention:  DOMAIN_SPECIFIC_ERROR
  e.g. AUTH_INVALID_TOKEN, OCR_CONFIDENCE_TOO_LOW, CASE_NOT_FOUND
"""

from __future__ import annotations

from http import HTTPStatus
from typing import Any


class PABaseException(Exception):
    """
    Root exception for all PA platform errors.

    All subclasses must define:
    - http_status: maps to HTTP response code
    - error_code: machine-readable string for clients / monitoring
    """

    http_status: int = HTTPStatus.INTERNAL_SERVER_ERROR
    error_code: str = "INTERNAL_ERROR"
    default_message: str = "An unexpected error occurred"

    def __init__(
        self,
        message: str | None = None,
        error_code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message or self.default_message
        if error_code:
            self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """Serialize exception for API error responses."""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
        }


# ----------------------------------------------------------
# Authentication & Authorization
# ----------------------------------------------------------

class AuthenticationError(PABaseException):
    """Raised when credentials are missing or invalid."""
    http_status = HTTPStatus.UNAUTHORIZED
    error_code = "AUTH_INVALID_CREDENTIALS"
    default_message = "Authentication failed"


class TokenExpiredError(PABaseException):
    """Raised when a JWT token has expired."""
    http_status = HTTPStatus.UNAUTHORIZED
    error_code = "AUTH_TOKEN_EXPIRED"
    default_message = "Access token has expired"


class TokenInvalidError(PABaseException):
    """Raised when a JWT token is malformed or has an invalid signature."""
    http_status = HTTPStatus.UNAUTHORIZED
    error_code = "AUTH_TOKEN_INVALID"
    default_message = "Access token is invalid"


class PermissionDeniedError(PABaseException):
    """Raised when authenticated user lacks required role/permission."""
    http_status = HTTPStatus.FORBIDDEN
    error_code = "AUTH_PERMISSION_DENIED"
    default_message = "You do not have permission to perform this action"


# ----------------------------------------------------------
# Resource Errors
# ----------------------------------------------------------

class ResourceNotFoundError(PABaseException):
    """Raised when a requested resource (case, document, etc.) does not exist."""
    http_status = HTTPStatus.NOT_FOUND
    error_code = "RESOURCE_NOT_FOUND"
    default_message = "The requested resource was not found"


class ResourceConflictError(PABaseException):
    """Raised on duplicate resource creation or state conflict."""
    http_status = HTTPStatus.CONFLICT
    error_code = "RESOURCE_CONFLICT"
    default_message = "Resource already exists or is in a conflicting state"


# ----------------------------------------------------------
# Validation Errors
# ----------------------------------------------------------

class ValidationError(PABaseException):
    """Raised for business-rule validation failures (beyond Pydantic schema)."""
    http_status = HTTPStatus.UNPROCESSABLE_ENTITY
    error_code = "VALIDATION_ERROR"
    default_message = "Request validation failed"


class InvalidFileTypeError(PABaseException):
    """Raised when an uploaded file has a disallowed extension or MIME type."""
    http_status = HTTPStatus.UNPROCESSABLE_ENTITY
    error_code = "UPLOAD_INVALID_FILE_TYPE"
    default_message = "Uploaded file type is not supported"


class FileTooLargeError(PABaseException):
    """Raised when an uploaded file exceeds the maximum allowed size."""
    http_status = HTTPStatus.REQUEST_ENTITY_TOO_LARGE
    error_code = "UPLOAD_FILE_TOO_LARGE"
    default_message = "Uploaded file exceeds maximum allowed size"


# ----------------------------------------------------------
# OCR / Document Intelligence
# ----------------------------------------------------------

class OCRError(PABaseException):
    """Base class for all OCR-related failures."""
    http_status = HTTPStatus.INTERNAL_SERVER_ERROR
    error_code = "OCR_ERROR"
    default_message = "Document processing failed"


class OCRConfidenceTooLowError(OCRError):
    """
    Raised when all OCR providers return confidence below threshold.
    Triggers the fallback pipeline (Azure → PaddleOCR).
    """
    error_code = "OCR_CONFIDENCE_TOO_LOW"
    default_message = "OCR confidence is too low for reliable extraction"


class OCRTimeoutError(OCRError):
    """Raised when OCR provider times out."""
    error_code = "OCR_TIMEOUT"
    default_message = "OCR processing timed out"


class DocumentCorruptedError(OCRError):
    """Raised when the uploaded document is unreadable or corrupted."""
    http_status = HTTPStatus.UNPROCESSABLE_ENTITY
    error_code = "DOCUMENT_CORRUPTED"
    default_message = "The document could not be processed — it may be corrupted"


# ----------------------------------------------------------
# AI / LLM
# ----------------------------------------------------------

class LLMError(PABaseException):
    """Base class for LLM-related failures."""
    http_status = HTTPStatus.INTERNAL_SERVER_ERROR
    error_code = "LLM_ERROR"
    default_message = "AI processing failed"


class LLMTimeoutError(LLMError):
    """Raised when LLM call exceeds timeout."""
    error_code = "LLM_TIMEOUT"
    default_message = "AI reasoning timed out"


class LLMHallucinationDetectedError(LLMError):
    """Raised when groundedness check detects unsupported claims."""
    error_code = "LLM_HALLUCINATION_DETECTED"
    default_message = "AI response could not be grounded in retrieved evidence"


# ----------------------------------------------------------
# Retrieval / Vector Search
# ----------------------------------------------------------

class RetrievalError(PABaseException):
    """Base class for Pinecone / RAG retrieval failures."""
    http_status = HTTPStatus.INTERNAL_SERVER_ERROR
    error_code = "RETRIEVAL_ERROR"
    default_message = "Policy retrieval failed"


class PolicyNotFoundError(RetrievalError):
    """Raised when no matching policy is found for the given CPT/ICD codes."""
    http_status = HTTPStatus.NOT_FOUND
    error_code = "POLICY_NOT_FOUND"
    default_message = "No matching policy found for the provided codes"


# ----------------------------------------------------------
# PA Case Workflow
# ----------------------------------------------------------

class CaseNotFoundError(ResourceNotFoundError):
    """Raised when a prior authorization case ID does not exist."""
    error_code = "CASE_NOT_FOUND"
    default_message = "Prior authorization case not found"


class CaseAlreadyDecidedError(ResourceConflictError):
    """Raised when attempting to modify a case that has already been decided."""
    error_code = "CASE_ALREADY_DECIDED"
    default_message = "Case has already been decided and cannot be modified"


class ClarificationLimitExceededError(PABaseException):
    """Raised when clarification loop exceeds maximum attempts (3)."""
    http_status = HTTPStatus.UNPROCESSABLE_ENTITY
    error_code = "CLARIFICATION_LIMIT_EXCEEDED"
    default_message = "Maximum clarification attempts exceeded — case has been escalated"


# ----------------------------------------------------------
# Infrastructure
# ----------------------------------------------------------

class DatabaseError(PABaseException):
    """Raised for unrecoverable database errors."""
    http_status = HTTPStatus.INTERNAL_SERVER_ERROR
    error_code = "DATABASE_ERROR"
    default_message = "A database error occurred"


class CacheError(PABaseException):
    """Raised for Redis cache errors (non-fatal — should degrade gracefully)."""
    http_status = HTTPStatus.INTERNAL_SERVER_ERROR
    error_code = "CACHE_ERROR"
    default_message = "Cache operation failed"


class QueueError(PABaseException):
    """Raised when message queue operations fail."""
    http_status = HTTPStatus.INTERNAL_SERVER_ERROR
    error_code = "QUEUE_ERROR"
    default_message = "Message queue operation failed"


class ExternalServiceError(PABaseException):
    """Raised when an external service (Azure, Pinecone, etc.) is unavailable."""
    http_status = HTTPStatus.BAD_GATEWAY
    error_code = "EXTERNAL_SERVICE_ERROR"
    default_message = "An external service is currently unavailable"


class RateLimitExceededError(PABaseException):
    """Raised when client exceeds configured rate limits."""
    http_status = HTTPStatus.TOO_MANY_REQUESTS
    error_code = "RATE_LIMIT_EXCEEDED"
    default_message = "Too many requests — please retry after a moment"
