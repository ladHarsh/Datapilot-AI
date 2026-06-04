"""
core/exceptions.py
──────────────────
Custom domain exceptions and FastAPI global exception handlers.

All custom exceptions carry a user-friendly message and an optional detail
dictionary so route handlers can surface clean error responses.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.constants import (
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
    HTTP_408_TIMEOUT,
    HTTP_500_INTERNAL,
)
from app.core.logger import app_logger


# ══════════════════════════════════════════════════════════════════════════════
#  Custom Exception Classes
# ══════════════════════════════════════════════════════════════════════════════

class AppBaseException(Exception):
    """Base class for all application-level exceptions."""

    def __init__(
        self,
        message: str,
        status_code: int = HTTP_500_INTERNAL,
        detail: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.detail = detail or {}
        super().__init__(self.message)


class DatabaseConnectionError(AppBaseException):
    """Raised when a connection to a target database cannot be established."""

    def __init__(self, message: str, detail: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, status_code=HTTP_400_BAD_REQUEST, detail=detail)


class InvalidSQLException(AppBaseException):
    """Raised when the supplied SQL statement is not a valid/allowed SELECT."""

    def __init__(self, message: str, detail: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, status_code=HTTP_400_BAD_REQUEST, detail=detail)


class QueryExecutionError(AppBaseException):
    """Raised when a SQL query fails during execution against the database."""

    def __init__(self, message: str, detail: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, status_code=HTTP_500_INTERNAL, detail=detail)


class SchemaLoadError(AppBaseException):
    """Raised when the schema inspector fails to extract database metadata."""

    def __init__(self, message: str, detail: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, status_code=HTTP_500_INTERNAL, detail=detail)


class QueryTimeoutError(AppBaseException):
    """Raised when a query exceeds the configured execution timeout."""

    def __init__(self, message: str, detail: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, status_code=HTTP_408_TIMEOUT, detail=detail)


class ResourceNotFoundError(AppBaseException):
    """Raised when a requested resource (e.g. history record) does not exist."""

    def __init__(self, message: str, detail: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, status_code=HTTP_404_NOT_FOUND, detail=detail)


# ══════════════════════════════════════════════════════════════════════════════
#  Global Exception Handlers
# ══════════════════════════════════════════════════════════════════════════════

def _error_body(message: str, detail: Dict[str, Any]) -> Dict[str, Any]:
    return {"success": False, "message": message, "detail": detail}


def register_exception_handlers(app: FastAPI) -> None:
    """
    Attach global exception handlers to the FastAPI application.

    Call this once from ``main.py`` during app initialisation.
    """

    @app.exception_handler(AppBaseException)
    async def handle_app_exception(
        request: Request, exc: AppBaseException
    ) -> JSONResponse:
        app_logger.error(
            "AppException [%s] %s | path=%s",
            exc.__class__.__name__,
            exc.message,
            request.url.path,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.message, exc.detail),
        )

    @app.exception_handler(Exception)
    async def handle_generic_exception(
        request: Request, exc: Exception
    ) -> JSONResponse:
        app_logger.exception(
            "Unhandled exception on %s: %s", request.url.path, str(exc)
        )
        return JSONResponse(
            status_code=HTTP_500_INTERNAL,
            content=_error_body(
                "An unexpected error occurred. Please try again later.",
                {"type": exc.__class__.__name__},
            ),
        )
