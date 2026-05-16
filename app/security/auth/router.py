"""
Authentication API endpoints.

Routes:
  POST /auth/login           Authenticate and receive token pair
  POST /auth/refresh         Exchange refresh token for new access token
  POST /auth/logout          Revoke tokens
  GET  /auth/me              Get current user profile
  POST /auth/change-password Change password (authenticated)
  POST /users                Create user (admin only)
  GET  /users/{user_id}      Get user by ID (admin only)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.dependencies.common import CurrentUser, require_role
from app.core.security.jwt import TokenPayload
from app.security.auth.models import (
    ChangePasswordRequest,
    CreateUserRequest,
    LoginRequest,
    MessageResponse,
    RefreshRequest,
    TokenResponse,
    UserPublic,
)
from app.security.auth.service import get_auth_service
from app.security.rbac.middleware import AdminRequired

router = APIRouter(prefix="/auth", tags=["Auth"])
user_router = APIRouter(prefix="/users", tags=["User Management"])


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and receive JWT tokens",
    responses={
        400: {"description": "Invalid credentials or account locked"},
        429: {"description": "Too many failed attempts"},
    },
)
async def login(request: Request, body: LoginRequest) -> TokenResponse:
    """
    Exchange credentials for a JWT access + refresh token pair.

    Access tokens expire in 30 minutes.
    Refresh tokens expire in 7 days.
    After 5 failed attempts the account is locked for 15 minutes.
    """
    ip = request.client.host if request.client else None
    service = get_auth_service()
    try:
        return await service.login(body, ip_address=ip)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Exchange refresh token for a new access token",
)
async def refresh_token(body: RefreshRequest) -> TokenResponse:
    service = get_auth_service()
    try:
        return await service.refresh(body.refresh_token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Revoke tokens and invalidate session",
)
async def logout(
    request: Request,
    current_user: CurrentUser,
) -> MessageResponse:
    # Extract raw token from Authorization header for blacklisting
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.removeprefix("Bearer ").strip()

    service = get_auth_service()
    await service.logout(access_token=token, user_id=current_user.sub)
    return MessageResponse(message="Successfully logged out")


@router.get(
    "/me",
    response_model=UserPublic,
    summary="Get current authenticated user profile",
)
async def get_me(current_user: CurrentUser) -> UserPublic:
    service = get_auth_service()
    user = await service.get_user(current_user.sub)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.post(
    "/change-password",
    response_model=MessageResponse,
    summary="Change password for the authenticated user",
)
async def change_password(
    body: ChangePasswordRequest,
    current_user: CurrentUser,
) -> MessageResponse:
    service = get_auth_service()
    try:
        await service.change_password(
            user_id=current_user.sub,
            current_password=body.current_password,
            new_password=body.new_password,
        )
        return MessageResponse(message="Password updated successfully")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ---------------------------------------------------------------------------
# User management (admin only)
# ---------------------------------------------------------------------------

@user_router.post(
    "",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user (admin only)",
)
async def create_user(
    body: CreateUserRequest,
    current_user: TokenPayload = Depends(AdminRequired()),
) -> UserPublic:
    service = get_auth_service()
    try:
        return await service.create_user(body, created_by=current_user.sub)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@user_router.get(
    "/{user_id}",
    response_model=UserPublic,
    summary="Get user by ID (admin only)",
)
async def get_user(
    user_id: str,
    current_user: TokenPayload = Depends(AdminRequired()),
) -> UserPublic:
    service = get_auth_service()
    user = await service.get_user(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user
