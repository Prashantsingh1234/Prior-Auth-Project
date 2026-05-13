"""
Session and JWT token caching.

Two concerns handled here:

1. Session cache: stores the decoded user payload (user_id, role, permissions)
   so the auth dependency can skip a DB lookup on every request after the
   first successful JWT decode in a session.

2. Token revocation: when a user logs out or an admin revokes a token, the
   token's 'jti' (JWT ID) is written to Redis with a TTL equal to the token's
   remaining validity. The auth dependency checks this list before trusting
   a valid-looking JWT.

Key design:
    Session:  pa:v1:session:{user_id}
    Revoked:  pa:v1:token:revoked:{jti}
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

from app.services.caching.base import BaseCacheService
from app.services.caching.keys import TTL, session_key, token_revoked_key

logger = structlog.get_logger(__name__)

# Payload stored in the session cache for each authenticated user
_SESSION_FIELDS = frozenset({
    "user_id", "email", "role", "permissions",
    "first_name", "last_name", "cached_at",
})


class SessionCache(BaseCacheService):
    """Cache for user session payloads and JWT token revocation list."""

    domain = "session"
    default_ttl = TTL.SESSION

    # ------------------------------------------------------------------
    # Session payload
    # ------------------------------------------------------------------

    async def get_session(self, user_id: str) -> dict[str, Any] | None:
        """
        Return the cached session payload for a user, or None.

        Args:
            user_id: UUID of the authenticated user

        Returns:
            Dict with user_id, role, permissions, etc. or None on miss.
        """
        key = session_key(user_id)
        return await self._get(key)

    async def set_session(
        self,
        user_id: str,
        payload: dict[str, Any],
        ttl: int | None = None,
    ) -> None:
        """
        Store a user session payload.

        Args:
            user_id: UUID of the authenticated user
            payload: Session data (role, permissions, profile fields, etc.)
            ttl:     Override default TTL — set to remaining JWT lifetime
                     for precise expiry alignment.
        """
        key = session_key(user_id)
        sanitized = {k: v for k, v in payload.items()}
        sanitized["cached_at"] = datetime.now(UTC).isoformat()
        await self._set(key, sanitized, ttl=ttl)
        logger.debug(
            "session.cached",
            user_id=user_id,
            role=payload.get("role"),
            ttl=ttl or self.default_ttl,
        )

    async def invalidate_session(self, user_id: str) -> bool:
        """
        Remove a user's cached session.

        Call this on logout, role change, or password reset.
        Returns True if the session existed.
        """
        key = session_key(user_id)
        deleted = await self._delete(key)
        if deleted:
            logger.info("session.invalidated", user_id=user_id)
        return deleted

    async def refresh_session_ttl(
        self, user_id: str, ttl: int | None = None
    ) -> None:
        """
        Re-read + re-write the session to reset its TTL.

        Called when a user successfully uses a refresh token so their session
        stays warm without a DB lookup.
        """
        existing = await self.get_session(user_id)
        if existing is not None:
            await self.set_session(user_id, existing, ttl=ttl)

    # ------------------------------------------------------------------
    # JWT token revocation (deny-list)
    # ------------------------------------------------------------------

    async def revoke_token(self, jti: str, expires_in_seconds: int) -> None:
        """
        Add a JWT to the revocation deny-list.

        Args:
            jti:                The JWT ID claim (unique per token)
            expires_in_seconds: Seconds until the token naturally expires.
                                We set the same TTL so the deny-list entry
                                auto-cleans when the token would have expired.
        """
        key = token_revoked_key(jti)
        # Value is irrelevant — presence of the key means "revoked"
        await self._set(key, {"revoked": True}, ttl=expires_in_seconds)
        logger.info("jwt.token_revoked", jti=jti, expires_in=expires_in_seconds)

    async def is_token_revoked(self, jti: str) -> bool:
        """
        Return True if the token JTI is on the deny-list.

        Called on every authenticated request, after signature verification,
        before granting access.
        """
        key = token_revoked_key(jti)
        result = await self._get(key)
        return result is not None
