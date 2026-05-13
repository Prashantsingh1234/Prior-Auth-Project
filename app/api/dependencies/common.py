"""
FastAPI dependency providers.

Centralizes shared dependencies so routes stay clean and dependencies
are testable via dependency_overrides in tests.

Follows the FastAPI dependency injection pattern:
- Sync dependencies return values directly
- Async dependencies use `async def` and are awaited by FastAPI

RBAC enforcement pattern:
    @router.get("/admin-only")
    async def admin_route(user: TokenPayload = Depends(require_role("admin"))):
        ...
"""

from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config.settings import Settings, get_settings
from app.core.exceptions.base import (
    PermissionDeniedError,
    TokenExpiredError,
    TokenInvalidError,
)
from app.core.security.jwt import TokenPayload, decode_access_token

logger = structlog.get_logger(__name__)

# Bearer token extractor — auto_error=False so we can return custom errors
_bearer_scheme = HTTPBearer(auto_error=False)


# ----------------------------------------------------------
# Settings dependency
# ----------------------------------------------------------

def get_app_settings() -> Settings:
    """Provide the cached Settings singleton as a FastAPI dependency."""
    return get_settings()


SettingsDep = Annotated[Settings, Depends(get_app_settings)]


# ----------------------------------------------------------
# Authentication dependencies
# ----------------------------------------------------------

async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> TokenPayload:
    """
    Extract and validate the Bearer JWT from the Authorization header.

    Raises:
        HTTPException(401): No token provided
        TokenExpiredError: Token has expired
        TokenInvalidError: Token is malformed or has invalid signature
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(credentials.credentials)
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except TokenInvalidError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token is invalid",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Bind authenticated user to structlog context
    structlog.contextvars.bind_contextvars(
        user_id=payload.sub,
        user_role=payload.role,
    )

    return payload


CurrentUser = Annotated[TokenPayload, Depends(get_current_user)]


def require_role(*allowed_roles: str):
    """
    Factory that returns a dependency enforcing RBAC role requirements.

    Usage:
        @router.post("/review/{id}")
        async def review(user: TokenPayload = Depends(require_role("admin", "reviewer"))):
            ...
    """
    async def _role_checker(
        current_user: TokenPayload = Depends(get_current_user),
    ) -> TokenPayload:
        if current_user.role not in allowed_roles:
            logger.warning(
                "rbac.access_denied",
                user_id=current_user.sub,
                user_role=current_user.role,
                required_roles=list(allowed_roles),
            )
            raise PermissionDeniedError(
                details={
                    "your_role": current_user.role,
                    "required_roles": list(allowed_roles),
                }
            )
        return current_user

    return _role_checker


# ----------------------------------------------------------
# Pagination dependency
# ----------------------------------------------------------

class PaginationParams:
    """Standard pagination parameters for list endpoints."""

    def __init__(
        self,
        page: int = 1,
        page_size: int = 20,
    ) -> None:
        if page < 1:
            raise HTTPException(status_code=400, detail="page must be >= 1")
        if not 1 <= page_size <= 100:
            raise HTTPException(status_code=400, detail="page_size must be between 1 and 100")
        self.page = page
        self.page_size = page_size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


PaginationDep = Annotated[PaginationParams, Depends(PaginationParams)]


# ----------------------------------------------------------
# Request ID dependency
# ----------------------------------------------------------

async def get_request_id(
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
) -> str | None:
    """Extract the request ID from the X-Request-ID header if provided."""
    return x_request_id


RequestIdDep = Annotated[str | None, Depends(get_request_id)]
