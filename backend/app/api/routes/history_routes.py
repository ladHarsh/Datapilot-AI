"""
api/routes/history_routes.py
──────────────────────────────
Endpoints for query history management.

GET  /history           — Paginated list of past queries.
GET  /history/{id}      — Single history record.
POST /history/replay    — Re-execute a historical query with fresh credentials.
DELETE /history/{id}    — Soft-delete (mark as deleted) a history record.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.api.dependencies.auth_dependency import get_current_user
from app.api.dependencies.db_dependency import get_internal_db
from app.core.constants import TAG_HISTORY
from app.core.logger import app_logger
from app.db.models.query_history_model import QueryHistory
from app.db.models.user_model import User
from app.schemas.query_schema import QueryReplayRequest
from app.schemas.response_schema import (
    HistoryItemResponse,
    PaginatedHistoryResponse,
    QueryResponse,
    SuccessResponse,
)
from app.services.database.connection_service import get_active_connection, get_engine
from app.services.database.connection_resolver import merge_connection_params, validate_connection_params
from app.services.database.query_executor import execute_query
from app.services.database.transaction_service import commit

router = APIRouter(prefix="/history", tags=[TAG_HISTORY])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _to_response(record: QueryHistory) -> HistoryItemResponse:
    return HistoryItemResponse(
        id=record.id,
        connection_key=record.connection_key,
        database_type=record.database_type,
        database_name=record.database_name,
        user_query=record.user_query,
        generated_sql=record.generated_sql,
        row_count=record.row_count,
        execution_duration=record.execution_duration,
        status=record.status,
        error_message=record.error_message,
        created_at=record.created_at.isoformat() if record.created_at else "",
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=PaginatedHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="List query history (paginated)",
)
def list_history(
    page: int = Query(1, ge=1, description="Page number (1-indexed)."),
    page_size: int = Query(20, ge=1, le=100, description="Items per page."),
    database_name: Optional[str] = Query(None, description="Filter by database name."),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status."),
    db: Session = Depends(get_internal_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedHistoryResponse:
    """Return a paginated list of past queries for the logged-in user."""
    app_logger.info("History list for user %d → page=%d size=%d", current_user.id, page, page_size)

    query = db.query(QueryHistory).filter(QueryHistory.user_id == current_user.id)

    if database_name:
        query = query.filter(QueryHistory.database_name == database_name)
    if status_filter:
        query = query.filter(QueryHistory.status == status_filter)

    total = query.count()
    records = (
        query.order_by(desc(QueryHistory.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return PaginatedHistoryResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[_to_response(r) for r in records],
    )


@router.get(
    "/{history_id}",
    response_model=SuccessResponse[HistoryItemResponse],
    status_code=status.HTTP_200_OK,
    summary="Get a single history record by ID",
)
def get_history_item(
    history_id: int,
    db: Session = Depends(get_internal_db),
    current_user: User = Depends(get_current_user),
) -> SuccessResponse[HistoryItemResponse]:
    """Retrieve a single query-history record."""
    record = db.query(QueryHistory).filter(
        QueryHistory.id == history_id,
        QueryHistory.user_id == current_user.id
    ).first()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"History record with id={history_id} not found.",
        )
    return SuccessResponse(
        message="History record retrieved.",
        data=_to_response(record),
    )


@router.post(
    "/replay",
    response_model=QueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Re-execute a historical query",
    description="Fetches a stored query from history and re-executes it against the supplied database credentials.",
)
def replay_query(
    payload: QueryReplayRequest,
    db: Session = Depends(get_internal_db),
    current_user: User = Depends(get_current_user),
) -> QueryResponse:
    """Re-run a query from history with fresh connection credentials."""
    record = db.query(QueryHistory).filter(
        QueryHistory.id == payload.history_id,
        QueryHistory.user_id == current_user.id
    ).first()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"History record with id={payload.history_id} not found.",
        )

    app_logger.info("Replaying history id=%d sql=%.80s", record.id, record.generated_sql)

    conn_params = validate_connection_params(
        merge_connection_params(payload.model_dump(exclude_none=True), get_active_connection())
    )
    engine = get_engine(
        host=conn_params["host"],
        port=int(conn_params["port"]),
        username=conn_params["username"],
        password=conn_params["password"],
        database=conn_params["database"],
        database_type=conn_params["database_type"],
        file_path=conn_params.get("file_path"),
    )

    result = execute_query(
        engine,
        record.generated_sql,
        user_query=record.user_query,
    )

    # Save replay as a new history entry
    new_record = QueryHistory(
        user_id=current_user.id,
        database_type=payload.database_type,
        database_name=payload.database,
        user_query=record.user_query,
        query_title=record.query_title,
        generated_sql=record.generated_sql,
        row_count=result["row_count"],
        execution_duration=result["execution_duration"],
        status="success",
    )
    db.add(new_record)
    commit(db)

    return QueryResponse(
        success=True,
        message=f"Query replayed successfully from history id={payload.history_id}.",
        sql_query=result["sql_query"],
        user_query=result.get("user_query"),
        columns=result["columns"],
        rows=result["rows"],
        row_count=result["row_count"],
        execution_duration=result["execution_duration"],
        truncated=result["truncated"],
    )


@router.delete(
    "/{history_id}",
    response_model=SuccessResponse[None],
    status_code=status.HTTP_200_OK,
    summary="Delete a history record",
)
def delete_history_item(
    history_id: int,
    db: Session = Depends(get_internal_db),
    current_user: User = Depends(get_current_user),
) -> SuccessResponse[None]:
    """Permanently remove a query-history record."""
    record = db.query(QueryHistory).filter(
        QueryHistory.id == history_id,
        QueryHistory.user_id == current_user.id
    ).first()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"History record with id={history_id} not found.",
        )
    db.delete(record)
    commit(db)
    app_logger.info("History record %d deleted.", history_id)
    return SuccessResponse(message=f"History record {history_id} deleted successfully.")


@router.delete(
    "",
    response_model=SuccessResponse[None],
    status_code=status.HTTP_200_OK,
    summary="Clear all query history",
)
def clear_history(
    db: Session = Depends(get_internal_db),
    current_user: User = Depends(get_current_user),
) -> SuccessResponse[None]:
    """Delete all query-history records for the logged-in user."""
    db.query(QueryHistory).filter(QueryHistory.user_id == current_user.id).delete()
    commit(db)
    app_logger.info("All history records for user %d cleared.", current_user.id)
    return SuccessResponse(message="All query history cleared successfully.")
