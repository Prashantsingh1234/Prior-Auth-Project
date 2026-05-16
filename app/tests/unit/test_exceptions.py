"""
Unit tests for the custom exception hierarchy.

Verifies:
- Each exception maps to the correct HTTP status code
- error_code strings follow the DOMAIN_SPECIFIC_ERROR convention
- to_dict() serializes all fields
- Custom messages and details are preserved
- Inheritance chain is correct
"""

from __future__ import annotations

import pytest

from app.core.exceptions.base import (
    AuthenticationError,
    CaseAlreadyDecidedError,
    CaseNotFoundError,
    ClarificationLimitExceededError,
    DatabaseError,
    FileTooLargeError,
    InvalidFileTypeError,
    LLMError,
    LLMHallucinationDetectedError,
    LLMTimeoutError,
    OCRError,
    PABaseException,
    PermissionDeniedError,
    PolicyNotFoundError,
    QueueError,
    RateLimitExceededError,
    ResourceConflictError,
    ResourceNotFoundError,
    RetrievalError,
    TokenExpiredError,
    TokenInvalidError,
    ValidationError,
)


class TestPABaseException:
    def test_default_message_used_when_none_given(self):
        exc = PABaseException()
        assert exc.message == PABaseException.default_message

    def test_custom_message_overrides_default(self):
        exc = PABaseException(message="Custom error")
        assert exc.message == "Custom error"

    def test_details_default_to_empty_dict(self):
        exc = PABaseException()
        assert exc.details == {}

    def test_details_preserved(self):
        exc = PABaseException(details={"key": "value"})
        assert exc.details == {"key": "value"}

    def test_to_dict_contains_required_keys(self):
        exc = PABaseException(message="boom", details={"x": 1})
        d = exc.to_dict()
        assert "error_code" in d
        assert "message" in d
        assert "details" in d

    def test_to_dict_message_matches(self):
        exc = PABaseException(message="specific message")
        assert exc.to_dict()["message"] == "specific message"

    def test_to_dict_details_matches(self):
        exc = PABaseException(details={"case_id": "abc-123"})
        assert exc.to_dict()["details"] == {"case_id": "abc-123"}

    def test_custom_error_code_override(self):
        exc = PABaseException(error_code="CUSTOM_CODE")
        assert exc.error_code == "CUSTOM_CODE"
        assert exc.to_dict()["error_code"] == "CUSTOM_CODE"

    def test_str_representation_is_message(self):
        exc = PABaseException(message="test message")
        assert str(exc) == "test message"


class TestHTTPStatusMapping:
    """Each exception must map to the correct HTTP status code."""

    @pytest.mark.parametrize("exc_class,expected_status", [
        (AuthenticationError, 401),
        (TokenExpiredError, 401),
        (TokenInvalidError, 401),
        (PermissionDeniedError, 403),
        (ResourceNotFoundError, 404),
        (CaseNotFoundError, 404),
        (PolicyNotFoundError, 404),
        (ResourceConflictError, 409),
        (CaseAlreadyDecidedError, 409),
        (ValidationError, 422),
        (InvalidFileTypeError, 422),
        (FileTooLargeError, 413),
        (RateLimitExceededError, 429),
        (DatabaseError, 500),
        (QueueError, 503),
        (LLMError, 502),
        (LLMTimeoutError, 504),
        (OCRError, 500),
        (RetrievalError, 502),
        (ClarificationLimitExceededError, 409),
    ])
    def test_http_status(self, exc_class, expected_status):
        exc = exc_class()
        assert exc.http_status == expected_status, (
            f"{exc_class.__name__} should map to {expected_status}, got {exc.http_status}"
        )


class TestErrorCodes:
    """Error codes must be non-empty uppercase strings."""

    @pytest.mark.parametrize("exc_class", [
        AuthenticationError,
        TokenExpiredError,
        TokenInvalidError,
        PermissionDeniedError,
        ResourceNotFoundError,
        CaseNotFoundError,
        ResourceConflictError,
        CaseAlreadyDecidedError,
        ValidationError,
        InvalidFileTypeError,
        FileTooLargeError,
        RateLimitExceededError,
        DatabaseError,
        QueueError,
        LLMError,
        LLMTimeoutError,
        LLMHallucinationDetectedError,
        OCRError,
        RetrievalError,
        ClarificationLimitExceededError,
    ])
    def test_error_code_is_uppercase(self, exc_class):
        exc = exc_class()
        code = exc.error_code
        assert code == code.upper(), f"{exc_class.__name__}.error_code '{code}' should be uppercase"

    @pytest.mark.parametrize("exc_class", [
        AuthenticationError, CaseNotFoundError, PermissionDeniedError,
        DatabaseError, LLMError, RateLimitExceededError,
    ])
    def test_error_code_is_non_empty(self, exc_class):
        assert exc_class.error_code, f"{exc_class.__name__} has empty error_code"

    @pytest.mark.parametrize("exc_class", [
        AuthenticationError, CaseNotFoundError, PermissionDeniedError,
        DatabaseError, LLMError, RateLimitExceededError,
    ])
    def test_error_code_follows_convention(self, exc_class):
        """Error codes must contain an underscore (DOMAIN_SPECIFIC_ERROR format)."""
        assert "_" in exc_class.error_code, (
            f"{exc_class.__name__}.error_code '{exc_class.error_code}' "
            "must follow DOMAIN_SPECIFIC_ERROR convention"
        )


class TestInheritanceChain:
    """All domain exceptions must inherit from PABaseException."""

    @pytest.mark.parametrize("exc_class", [
        AuthenticationError, TokenExpiredError, TokenInvalidError,
        PermissionDeniedError, ResourceNotFoundError, CaseNotFoundError,
        ResourceConflictError, CaseAlreadyDecidedError, ValidationError,
        InvalidFileTypeError, FileTooLargeError, DatabaseError, QueueError,
        LLMError, LLMTimeoutError, OCRError, RetrievalError,
        ClarificationLimitExceededError, RateLimitExceededError,
    ])
    def test_inherits_from_base(self, exc_class):
        exc = exc_class()
        assert isinstance(exc, PABaseException)
        assert isinstance(exc, Exception)

    def test_case_not_found_inherits_from_resource_not_found(self):
        exc = CaseNotFoundError()
        assert isinstance(exc, ResourceNotFoundError)

    def test_token_errors_inherit_from_auth_error(self):
        assert issubclass(TokenExpiredError, PABaseException)
        assert issubclass(TokenInvalidError, PABaseException)

    def test_llm_timeout_inherits_from_llm_error(self):
        exc = LLMTimeoutError()
        assert isinstance(exc, LLMError)


class TestSpecificExceptions:

    def test_file_too_large_preserves_size_details(self):
        exc = FileTooLargeError(details={"file_size_bytes": 52_428_800, "max_bytes": 26_214_400})
        assert exc.details["file_size_bytes"] == 52_428_800
        assert exc.details["max_bytes"] == 26_214_400

    def test_case_not_found_preserves_case_id(self):
        exc = CaseNotFoundError(details={"case_id": "abc-123"})
        assert exc.details["case_id"] == "abc-123"

    def test_rate_limit_exceeded_correct_status(self):
        exc = RateLimitExceededError()
        assert exc.http_status == 429

    def test_hallucination_detected_inherits_llm(self):
        exc = LLMHallucinationDetectedError()
        assert isinstance(exc, LLMError)

    def test_clarification_limit_is_conflict(self):
        exc = ClarificationLimitExceededError()
        assert exc.http_status == 409

    def test_permission_denied_preserves_details(self):
        exc = PermissionDeniedError(
            message="Only reviewers can approve cases",
            details={"required_role": "reviewer", "current_role": "provider"},
        )
        d = exc.to_dict()
        assert d["message"] == "Only reviewers can approve cases"
        assert d["details"]["required_role"] == "reviewer"
