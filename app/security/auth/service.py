"""
AuthService — full JWT authentication lifecycle.

Responsibilities:
  - User registration (admin-only via CreateUserRequest)
  - Login: credentials → access + refresh token pair
  - Token refresh: refresh token → new access token
  - Logout: token blacklisting (Redis-backed)
  - Password change with current-password verification
  - Brute-force protection: account lockout after N failed attempts
  - Audit logging for all auth events

Token blacklist:
  - Revoked tokens (on logout) are stored in Redis with TTL = token expiry
  - Token validation checks the blacklist before accepting any token
  - Refresh tokens are stored in Redis (allowlist — delete on logout)

In-memory user store:
  The demo uses an in-memory dict.  In production, replace _users with
  async DB queries against a users table.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from app.core.config.settings import get_settings
from app.core.exceptions.base import TokenExpiredError, TokenInvalidError
from app.core.security.jwt import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.security.auth.models import (
    CreateUserRequest,
    LoginRequest,
    TokenResponse,
    UserInDB,
    UserPublic,
)

logger = structlog.get_logger(__name__)

_MAX_FAILED_ATTEMPTS = 5
_LOCKOUT_MINUTES     = 15


class AuthService:
    """
    Authentication service.

    One instance per application (use get_auth_service()).
    """

    def __init__(self) -> None:
        # In-memory user store — replace with DB in production
        self._users: dict[str, UserInDB] = {}
        # email → user_id index
        self._by_email: dict[str, str]    = {}
        # username → user_id index
        self._by_username: dict[str, str] = {}
        self._log = structlog.get_logger(__name__)
        self._seed_defaults()

    # ------------------------------------------------------------------
    # Login / logout
    # ------------------------------------------------------------------

    async def login(self, request: LoginRequest, ip_address: str | None = None) -> TokenResponse:
        """
        Authenticate a user and return a token pair.

        Raises:
            ValueError: Invalid credentials or locked account
        """
        user_id = self._by_username.get(request.username) or self._by_email.get(request.username)
        user = self._users.get(user_id) if user_id else None

        if user is None:
            # Constant-time failure to prevent username enumeration
            verify_password("dummy", hash_password("dummy"))
            raise ValueError("Invalid credentials")

        # Check lockout
        if user.is_locked:
            if user.locked_until and datetime.now(UTC) < user.locked_until:
                raise ValueError(
                    f"Account locked until {user.locked_until.isoformat()}. "
                    "Contact support if you believe this is an error."
                )
            # Lockout expired — reset
            user.is_locked = False
            user.failed_login_attempts = 0
            user.locked_until = None

        if not user.is_active:
            raise ValueError("Account is deactivated")

        if not verify_password(request.password, user.hashed_password):
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= _MAX_FAILED_ATTEMPTS:
                user.is_locked   = True
                user.locked_until = datetime.now(UTC) + timedelta(minutes=_LOCKOUT_MINUTES)
                self._log.warning(
                    "auth.account_locked",
                    user_id=user.user_id,
                    attempts=user.failed_login_attempts,
                )
                await self._emit_audit("AUTH_ACCOUNT_LOCKED", user.user_id, ip_address)
            raise ValueError("Invalid credentials")

        # Successful login
        user.failed_login_attempts = 0
        user.last_login_at = datetime.now(UTC)

        access_token  = create_access_token(subject=user.user_id, role=user.role)
        refresh_token = create_refresh_token(subject=user.user_id, role=user.role)

        await self._store_refresh_token(user.user_id, refresh_token)

        self._log.info("auth.login_success", user_id=user.user_id, role=user.role)
        await self._emit_audit("AUTH_LOGIN", user.user_id, ip_address)

        settings = get_settings()
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.access_token_expire_minutes * 60,
            user=user.to_public(),
        )

    async def logout(self, access_token: str, user_id: str) -> None:
        """Revoke access and refresh tokens (adds to blacklist)."""
        await self._blacklist_token(access_token)
        await self._revoke_refresh_tokens(user_id)
        self._log.info("auth.logout", user_id=user_id)
        await self._emit_audit("AUTH_LOGOUT", user_id, None)

    async def refresh(self, refresh_token: str) -> TokenResponse:
        """Exchange a valid refresh token for a new access token."""
        try:
            from jose import jwt, JWTError
            settings = get_settings()
            payload  = jwt.decode(
                refresh_token,
                settings.secret_key.get_secret_value(),
                algorithms=[settings.jwt_algorithm],
                options={"require": ["sub", "role", "exp", "type"]},
            )
        except Exception as exc:
            raise TokenInvalidError(details={"reason": str(exc)}) from exc

        if payload.get("type") != "refresh":
            raise TokenInvalidError(message="Not a refresh token")

        user_id = payload["sub"]
        role    = payload["role"]
        user    = self._users.get(user_id)
        if user is None or not user.is_active:
            raise TokenInvalidError(message="User not found or inactive")

        # Verify the refresh token is still in our allowlist
        valid = await self._verify_refresh_token(user_id, refresh_token)
        if not valid:
            raise TokenInvalidError(message="Refresh token has been revoked")

        access_token  = create_access_token(subject=user_id, role=role)
        settings      = get_settings()
        self._log.debug("auth.token_refreshed", user_id=user_id)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,  # Return same refresh token (rotation optional)
            expires_in=settings.access_token_expire_minutes * 60,
            user=user.to_public(),
        )

    # ------------------------------------------------------------------
    # User management (admin only)
    # ------------------------------------------------------------------

    async def create_user(
        self,
        request: CreateUserRequest,
        created_by: str,
    ) -> UserPublic:
        """Create a new user (admin privilege required — enforced at route level)."""
        if request.email in self._by_email:
            raise ValueError(f"Email '{request.email}' is already registered")
        if request.username in self._by_username:
            raise ValueError(f"Username '{request.username}' is already taken")

        user = UserInDB(
            user_id=str(uuid.uuid4()),
            email=request.email,
            username=request.username,
            hashed_password=hash_password(request.password),
            role=request.role,
            npi=request.npi,
            organization=request.organization,
        )
        self._users[user.user_id]    = user
        self._by_email[user.email]   = user.user_id
        self._by_username[user.username] = user.user_id

        self._log.info("auth.user_created", new_user_id=user.user_id, role=user.role, by=created_by)
        await self._emit_audit("AUTH_USER_CREATED", created_by, None, {"new_user_id": user.user_id})
        return user.to_public()

    async def change_password(
        self,
        user_id: str,
        current_password: str,
        new_password: str,
    ) -> None:
        """Change a user's password after verifying the current one."""
        user = self._users.get(user_id)
        if user is None:
            raise ValueError("User not found")
        if not verify_password(current_password, user.hashed_password):
            raise ValueError("Current password is incorrect")
        user.hashed_password = hash_password(new_password)
        user.updated_at = datetime.now(UTC)
        self._log.info("auth.password_changed", user_id=user_id)
        await self._emit_audit("AUTH_PASSWORD_CHANGED", user_id, None)

    async def get_user(self, user_id: str) -> UserPublic | None:
        user = self._users.get(user_id)
        return user.to_public() if user else None

    async def is_token_blacklisted(self, token: str) -> bool:
        """Check if a token has been revoked."""
        try:
            from app.services.caching.redis_client import get_redis
            redis = get_redis()
            return await redis.exists(f"blacklist:{token}") > 0
        except Exception:
            return False  # Fail open — Redis failure should not block all auth

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _seed_defaults(self) -> None:
        """Seed default admin and test accounts (development only)."""
        defaults = [
            ("admin@pa-review.com",    "admin",    hash_password("Admin@secure123!"),    "admin"),
            ("reviewer@pa-review.com", "reviewer", hash_password("Review@secure123!"),   "reviewer"),
            ("provider@pa-review.com", "provider", hash_password("Provider@secure123!"), "provider"),
        ]
        for email, username, pw, role in defaults:
            uid = str(uuid.uuid4())
            user = UserInDB(
                user_id=uid, email=email, username=username,
                hashed_password=pw, role=role,
            )
            self._users[uid]      = user
            self._by_email[email] = uid
            self._by_username[username] = uid

    async def _store_refresh_token(self, user_id: str, token: str) -> None:
        try:
            settings = get_settings()
            ttl      = settings.refresh_token_expire_days * 86400
            from app.services.caching.redis_client import get_redis
            redis = get_redis()
            await redis.setex(f"refresh:{user_id}", ttl, token)
        except Exception:
            pass

    async def _verify_refresh_token(self, user_id: str, token: str) -> bool:
        try:
            from app.services.caching.redis_client import get_redis
            redis  = get_redis()
            stored = await redis.get(f"refresh:{user_id}")
            return stored is not None and stored.decode() == token
        except Exception:
            return True  # Redis failure — be permissive (log and monitor)

    async def _revoke_refresh_tokens(self, user_id: str) -> None:
        try:
            from app.services.caching.redis_client import get_redis
            redis = get_redis()
            await redis.delete(f"refresh:{user_id}")
        except Exception:
            pass

    async def _blacklist_token(self, token: str) -> None:
        try:
            from app.services.caching.redis_client import get_redis
            settings = get_settings()
            redis    = get_redis()
            ttl      = settings.access_token_expire_minutes * 60
            await redis.setex(f"blacklist:{token}", ttl, "1")
        except Exception:
            pass

    async def _emit_audit(
        self,
        event_type: str,
        actor_id: str,
        ip_address: str | None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        try:
            from app.guardrails.audit import _write_to_audit_db
            await _write_to_audit_db(
                event_type=event_type,
                actor_id=actor_id,
                case_id=None,
                event_data={"ip": ip_address, **(extra or {})},
                severity="MEDIUM",
            )
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_auth_service: AuthService | None = None


def get_auth_service() -> AuthService:
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service
