"""Unit tests for JWT authentication utilities."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from app.core.config.settings import Settings
from app.core.exceptions.base import TokenExpiredError, TokenInvalidError
from app.core.security.jwt import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    hash_password,
    verify_password,
)

TEST_SETTINGS = Settings(
    secret_key="test-secret-key-minimum-32-characters",
    environment="development",
)


@pytest.fixture(autouse=True)
def patch_settings():
    with patch("app.core.security.jwt.get_settings", return_value=TEST_SETTINGS):
        yield


class TestAccessTokenCreation:

    def test_create_access_token_returns_string(self) -> None:
        token = create_access_token(subject="user-123", role="reviewer")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_decode_valid_token(self) -> None:
        token = create_access_token(subject="user-123", role="reviewer")
        payload = decode_access_token(token)
        assert payload.sub == "user-123"
        assert payload.role == "reviewer"

    def test_token_contains_correct_role(self) -> None:
        for role in ["admin", "reviewer", "provider"]:
            token = create_access_token(subject="u1", role=role)
            payload = decode_access_token(token)
            assert payload.role == role

    def test_expired_token_raises(self) -> None:
        """Token with past expiry raises TokenExpiredError."""
        # Create token with -1 minute TTL (already expired)
        expired_settings = Settings(
            secret_key="test-secret-key-minimum-32-characters",
            access_token_expire_minutes=-1,
        )
        with patch("app.core.security.jwt.get_settings", return_value=expired_settings):
            token = create_access_token(subject="u1", role="reviewer")
        with pytest.raises(TokenExpiredError):
            decode_access_token(token)

    def test_tampered_token_raises(self) -> None:
        """Modifying token payload raises TokenInvalidError."""
        token = create_access_token(subject="u1", role="reviewer")
        # Corrupt the token by flipping a character
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(TokenInvalidError):
            decode_access_token(tampered)

    def test_refresh_token_rejected_as_access_token(self) -> None:
        """Refresh token cannot be used as access token."""
        refresh_token = create_refresh_token(subject="u1", role="reviewer")
        with pytest.raises(TokenInvalidError, match="access token"):
            decode_access_token(refresh_token)

    def test_garbage_token_raises(self) -> None:
        with pytest.raises(TokenInvalidError):
            decode_access_token("not.a.real.token")


class TestPasswordHashing:

    def test_hash_produces_bcrypt_string(self) -> None:
        hashed = hash_password("my-password")
        assert hashed.startswith("$2b$")

    def test_verify_correct_password(self) -> None:
        hashed = hash_password("correct-password")
        assert verify_password("correct-password", hashed) is True

    def test_reject_wrong_password(self) -> None:
        hashed = hash_password("correct-password")
        assert verify_password("wrong-password", hashed) is False

    def test_different_hashes_for_same_password(self) -> None:
        """bcrypt uses random salt — same password produces different hashes."""
        h1 = hash_password("same-password")
        h2 = hash_password("same-password")
        assert h1 != h2
        assert verify_password("same-password", h1) is True
        assert verify_password("same-password", h2) is True
