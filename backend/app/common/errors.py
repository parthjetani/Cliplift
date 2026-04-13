"""Global exception handlers — structured JSON error responses.

All errors return a consistent shape:
    { "error": { "code": "...", "message": "...", "details": {...} } }
"""

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

logger = logging.getLogger(__name__)


def _error_response(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return JSONResponse(status_code=status_code, content=body)


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Convert FastAPI HTTPException to our standard error envelope."""
    code = {
        400: "bad_request",
        401: "unauthorized",
        402: "plan_limit_exceeded",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        422: "validation_error",
        429: "rate_limited",
        500: "internal_error",
    }.get(exc.status_code, "error")

    # For plan enforcement 402 errors, include upgrade metadata in details
    details = None
    if exc.status_code == 402 and hasattr(exc, "limit_name"):
        details = {
            "limit_name": exc.limit_name,
            "current_plan": exc.current_plan,
            "suggested_plan": getattr(exc, "suggested_plan", None),
        }

    return _error_response(
        status_code=exc.status_code,
        code=code,
        message=str(exc.detail),
        details=details,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Convert Pydantic validation errors to a friendly format."""
    return _error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        code="validation_error",
        message="Request validation failed",
        details={"errors": exc.errors()},
    )


async def integrity_error_handler(
    request: Request, exc: IntegrityError
) -> JSONResponse:
    """Database constraint violations (unique, FK, etc.)."""
    logger.warning(f"Integrity error on {request.url.path}: {exc}")
    return _error_response(
        status_code=status.HTTP_409_CONFLICT,
        code="conflict",
        message="Resource conflict (duplicate or invalid reference)",
    )


async def sqlalchemy_error_handler(
    request: Request, exc: SQLAlchemyError
) -> JSONResponse:
    """Catch-all for unexpected database errors."""
    logger.error(f"Database error on {request.url.path}: {exc}", exc_info=True)
    return _error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="database_error",
        message="A database error occurred",
    )


async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Last-resort handler — logs the traceback and returns a generic 500."""
    logger.exception(f"Unhandled exception on {request.url.path}")
    return _error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="internal_error",
        message="An unexpected error occurred",
    )


def register_error_handlers(app: FastAPI) -> None:
    """Wire all error handlers into the FastAPI app."""
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(IntegrityError, integrity_error_handler)
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
