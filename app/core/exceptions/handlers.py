"""
Global FastAPI exception handlers.

Registered once in main.py via register_exception_handlers().
Maps exception types to structured JSON error responses.

Response envelope:
{
  "success": false,
  "error": {
    "code":    "CASE_NOT_FOUND",
    "message": "Prior authorization case not found",
    "details": {},
    "request_id": "abc-123"
  }
}
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import ORJSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions.base import PABaseException

logger = structlog.get_logger(__name__)


def _error_response(
    request: Request,
    status_code: int,
    error_code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> ORJSONResponse:
    """Build the standard error response envelope."""
    request_id = getattr(request.state, "request_id", "unknown")
    return ORJSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": {
                "code": error_code,
                "message": message,
                "details": details or {},
                "request_id": request_id,
            },
        },
    )


async def pa_exception_handler(request: Request, exc: PABaseException) -> ORJSONResponse:
    """Handle all custom PA platform exceptions."""
    # Log at warning for client errors, error for server errors
    if exc.http_status >= 500:
        logger.error(
            "pa_exception.server_error",
            error_code=exc.error_code,
            message=exc.message,
            path=request.url.path,
            method=request.method,
            exc_info=exc,
        )
    else:
        logger.warning(
            "pa_exception.client_error",
            error_code=exc.error_code,
            message=exc.message,
            path=request.url.path,
            method=request.method,
        )

    return _error_response(
        request=request,
        status_code=exc.http_status,
        error_code=exc.error_code,
        message=exc.message,
        details=exc.details,
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> ORJSONResponse:
    """Handle FastAPI / Starlette HTTP exceptions."""
    logger.warning(
        "http_exception",
        status_code=exc.status_code,
        detail=exc.detail,
        path=request.url.path,
        method=request.method,
    )
    return _error_response(
        request=request,
        status_code=exc.status_code,
        error_code=f"HTTP_{exc.status_code}",
        message=str(exc.detail),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> ORJSONResponse:
    """
    Handle Pydantic v2 request validation errors (422 Unprocessable Entity).
    Reformat Pydantic's error list into a clean details dict.
    """
    formatted_errors: list[dict[str, Any]] = []
    for error in exc.errors():
        loc = " -> ".join(str(loc) for loc in error.get("loc", []))
        formatted_errors.append(
            {
                "field": loc,
                "message": error.get("msg", "Invalid value"),
                "type": error.get("type", "unknown"),
            }
        )

    logger.warning(
        "validation_error",
        errors=formatted_errors,
        path=request.url.path,
        method=request.method,
    )

    return _error_response(
        request=request,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        error_code="VALIDATION_ERROR",
        message="Request validation failed",
        details={"errors": formatted_errors},
    )


async def sqlalchemy_exception_handler(
    request: Request, exc: SQLAlchemyError
) -> ORJSONResponse:
    """
    Handle SQLAlchemy database errors.
    Never expose raw DB error messages to clients — log internally only.
    """
    logger.error(
        "database_error",
        exc_info=exc,
        path=request.url.path,
        method=request.method,
    )
    return _error_response(
        request=request,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code="DATABASE_ERROR",
        message="A database error occurred. The issue has been logged.",
    )


async def generic_exception_handler(request: Request, exc: Exception) -> ORJSONResponse:
    """
    Catch-all handler for unexpected exceptions.
    Logs full stack trace, returns generic 500 to client.
    Never leak internal details in the response.
    """
    logger.error(
        "unhandled_exception",
        exc_info=exc,
        path=request.url.path,
        method=request.method,
        exception_type=type(exc).__name__,
    )
    return _error_response(
        request=request,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code="INTERNAL_ERROR",
        message="An unexpected error occurred. Our team has been notified.",
    )


def register_exception_handlers(app: FastAPI) -> None:
    """
    Register all exception handlers with the FastAPI application.
    Called once from create_application() in main.py.
    """
    app.add_exception_handler(PABaseException, pa_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, generic_exception_handler)
