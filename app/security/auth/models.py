"""
Auth system data models.

Separates the DB-persisted user representation from request/response schemas
so that password hashes and sensitive fields never leak into API responses.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------

class UserRole:
    ADMIN    = "admin"
    REVIEWER = "reviewer"
    PROVIDER = "provider"
    ALL      = frozenset({ADMIN, REVIEWER, PROVIDER})

    @classmethod
    def is_valid(cls, role: str) -> bool:
        return role in cls.ALL


# ---------------------------------------------------------------------------
# DB-level user record (never returned directly in API responses)
# ---------------------------------------------------------------------------

class UserInDB(BaseModel):
    """User record as stored in the database (includes hashed password)."""

    user_id:       str = Field(default_factory=lambda: str(uuid.uuid4()))
    email:         str
    username:      str
    hashed_password: str
    role:          str
    is_active:     bool = True
    is_locked:     bool = False
    created_at:    datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at:    datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_login_at: datetime | None = None
    failed_login_attempts: int = 0
    locked_until:  datetime | None = None
    npi:           str | None = None    # Provider NPI (encrypted in real DB)
    organization:  str | None = None

    model_config = {"arbitrary_types_allowed": True}

    def to_public(self) -> "UserPublic":
        return UserPublic(
            user_id=self.user_id,
            email=self.email,
            username=self.username,
            role=self.role,
            is_active=self.is_active,
            created_at=self.created_at,
            last_login_at=self.last_login_at,
            organization=self.organization,
        )


# ---------------------------------------------------------------------------
# API request models
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    """POST /auth/login request body."""

    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=8, max_length=200)

    model_config = {"json_schema_extra": {"example": {
        "username": "dr.smith",
        "password": "secure-password-123",
    }}}


class RefreshRequest(BaseModel):
    """POST /auth/refresh request body."""
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    """POST /auth/change-password request body."""
    current_password: str
    new_password:     str = Field(..., min_length=12)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        errors = []
        if not any(c.isupper() for c in v):
            errors.append("must contain an uppercase letter")
        if not any(c.islower() for c in v):
            errors.append("must contain a lowercase letter")
        if not any(c.isdigit() for c in v):
            errors.append("must contain a digit")
        if not any(c in "!@#$%^&*()_+-=[]{}|;':\",./<>?" for c in v):
            errors.append("must contain a special character")
        if errors:
            raise ValueError("Password " + "; ".join(errors))
        return v


class CreateUserRequest(BaseModel):
    """POST /users request body (admin only)."""
    email:       str     = Field(..., description="User email address")
    username:    str     = Field(..., min_length=3, max_length=50)
    password:    str     = Field(..., min_length=12)
    role:        str     = Field(..., description="admin | reviewer | provider")
    npi:         str | None = Field(default=None, description="Provider NPI")
    organization: str | None = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if not UserRole.is_valid(v):
            raise ValueError(f"role must be one of {list(UserRole.ALL)}")
        return v


# ---------------------------------------------------------------------------
# API response models
# ---------------------------------------------------------------------------

class UserPublic(BaseModel):
    """Safe user representation returned in API responses (no passwords/hashes)."""
    user_id:       str
    email:         str
    username:      str
    role:          str
    is_active:     bool
    created_at:    datetime
    last_login_at: datetime | None
    organization:  str | None

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """Returned by /auth/login and /auth/refresh."""
    access_token:  str
    refresh_token: str
    token_type:    str = "bearer"
    expires_in:    int      # seconds until access token expires
    user:          UserPublic


class MessageResponse(BaseModel):
    """Generic success message."""
    message: str
    detail:  Any | None = None
