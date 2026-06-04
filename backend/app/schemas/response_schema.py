"""
schemas/response_schema.py
───────────────────────────
Generic envelope schemas used across all API endpoints.

Every API response is wrapped in either SuccessResponse or ErrorResponse,
giving callers a consistent contract regardless of the endpoint.
"""
from __future__ import annotations

from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


# ══════════════════════════════════════════════════════════════════════════════
#  Generic envelope
# ══════════════════════════════════════════════════════════════════════════════

class SuccessResponse(BaseModel, Generic[T]):
    """
    Standard success envelope.

    Attributes
    ----------
    success : Always ``True``.
    message : Human-readable summary of the operation.
    data    : The actual payload (type-parametrised).
    """

    success: bool = True
    message: str
    data: Optional[T] = None

    model_config = {"json_schema_extra": {
        "example": {
            "success": True,
            "message": "Operation completed successfully.",
            "data": {},
        }
    }}


class ErrorResponse(BaseModel):
    """
    Standard error envelope.

    Attributes
    ----------
    success : Always ``False``.
    message : User-friendly error description.
    detail  : Optional dict with additional diagnostic information.
    """

    success: bool = False
    message: str
    detail: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"json_schema_extra": {
        "example": {
            "success": False,
            "message": "Connection refused.",
            "detail": {"host": "localhost", "port": 3306},
        }
    }}


# ══════════════════════════════════════════════════════════════════════════════
#  Specialised response shapes
# ══════════════════════════════════════════════════════════════════════════════

class QueryResponse(BaseModel):
    """
    Response for query-execution endpoints.
    Wraps query metadata alongside the tabular result.
    """

    success: bool = True
    message: str = "Query executed successfully."
    sql_query: str
    user_query: Optional[str] = None
    columns: List[str]
    rows: List[Dict[str, Any]]
    row_count: int
    execution_duration: float
    truncated: bool = False
    explanation: Optional[str] = None


class HistoryItemResponse(BaseModel):
    """Single query-history record returned to the client."""

    id: int
    connection_key: Optional[str] = None
    database_type: Optional[str] = None
    database_name: Optional[str] = None
    user_query: Optional[str] = None
    generated_sql: str
    row_count: int
    execution_duration: float
    status: str
    error_message: Optional[str] = None
    created_at: str   # ISO-8601 string


class PaginatedHistoryResponse(BaseModel):
    """Paginated list of history records."""

    success: bool = True
    message: str = "History retrieved successfully."
    total: int
    page: int
    page_size: int
    items: List[HistoryItemResponse]


class HealthResponse(BaseModel):
    """Response for the health-check endpoint."""

    status: str = "ok"
    app_name: str
    version: str = "1.0.0"
    active_connections: int = 0
