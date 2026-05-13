"""
JWT authentication utilities.

Handles:
- Token creation (access + refresh)
- Token verification and decoding
- Password hashing with bcrypt

Design decisions:
- SecretStr prevents accidental logging of the signing key
- Short access token TTL (30 min) with longer refresh token (7 days)
- Explicit algorithm whitelist prevents algorithm confusion attacks
- Custom claims include role for RBAC enforcement in dependencies
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config.settings import get_settings
from app.core.exceptions.base import TokenExpiredError, TokenInvalidError

logger = structlog.get_logger(__name__)

# bcrypt password hashing context
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ----------------------------------------------------------
# Token payload schema
# ----------------------------------------------------------

class TokenPayload:
    """Validated JWT payload."""

    def __init__(self, sub: str, role: str, exp: datetime, jti: str | None = None) -> None:
        self.sub = sub           # Subject — user UUID
        self.role = role         # RBAC role: admin | reviewer | provider
        self.exp = exp           # Expiration datetime
        self.jti = jti           # JWT ID for revocation tracking


# ----------------------------------------------------------
# Token creation
# ----------------------------------------------------------

def create_access_token(
    subject: str,
    role: str,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """
    Create a signed JWT access token.

    Args:
        subject: User UUID string
        role: RBAC role (admin | reviewer | provider)
        extra_claims: Optional additional claims to embed

    Returns:
        Signed JWT string
    """
    settings = get_settings()
    now = datetime.now(UTC)
    expire = now + timedelta(minutes=settings.access_token_expire_minutes)

    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": expire,
    }
    if extra_claims:
        payload.update(extra_claims)

    token = jwt.encode(
        payload,
        settings.secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )

    logger.debug(
        "jwt.access_token_created",
        subject=subject,
        role=role,
        expires_at=expire.isoformat(),
    )
    return token


def create_refresh_token(subject: str, role: str) -> str:
    """
    Create a long-lived refresh token.

    Refresh tokens are used to obtain new access tokens without re-authenticating.
    They should be stored securely (HttpOnly cookie or secure storage).
    """
    settings = get_settings()
    now = datetime.now(UTC)
    expire = now + timedelta(days=settings.refresh_token_expire_days)

    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "type": "refresh",
        "iat": now,
        "exp": expire,
    }

    return jwt.encode(
        payload,
        settings.secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


# ----------------------------------------------------------
# Token verification
# ----------------------------------------------------------

def decode_access_token(token: str) -> TokenPayload:
    """
    Decode and validate a JWT access token.

    Raises:
        TokenExpiredError: Token has passed its expiration time
        TokenInvalidError: Token is malformed, signature invalid, or wrong type
    """
    settings = get_settings()

    try:
        payload = jwt.decode(
            token,
            settings.secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "role", "exp", "type"]},
        )
    except JWTError as exc:
        error_msg = str(exc).lower()
        if "expired" in error_msg:
            raise TokenExpiredError() from exc
        raise TokenInvalidError(details={"reason": str(exc)}) from exc

    if payload.get("type") != "access":
        raise TokenInvalidError(
            message="Provided token is not an access token",
            details={"token_type": payload.get("type")},
        )

    return TokenPayload(
        sub=payload["sub"],
        role=payload["role"],
        exp=datetime.fromtimestamp(payload["exp"], tz=UTC),
        jti=payload.get("jti"),
    )


# ----------------------------------------------------------
# Password utilities
# ----------------------------------------------------------

def hash_password(plain_password: str) -> str:
    """Return bcrypt hash of a plain-text password."""
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a stored bcrypt hash."""
    return _pwd_context.verify(plain_password, hashed_password)
