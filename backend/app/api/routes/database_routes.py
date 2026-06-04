"""
api/routes/database_routes.py
──────────────────────────────
Endpoints for managing database connections and inspecting schemas.

POST /connect  — Validate credentials and establish a connection.
GET  /schema   — Retrieve full schema (tables, columns, keys) for a connected DB.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Query, UploadFile, status, HTTPException
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.api.dependencies.db_dependency import get_internal_db
from app.api.dependencies.auth_dependency import get_current_user
from app.core.constants import TAG_DATABASE
from app.core.logger import app_logger
from app.schemas.database_schema import (
    DatabaseConnectRequest,
    DatabaseSchemaResponse,
    DatabaseStatsResponse,
)
from app.services.database.stats_service import get_database_stats
from app.schemas.response_schema import SuccessResponse
from app.services.database.connection_service import (
    clear_active_connection,
    disconnect_engine,
    get_active_connection,
    get_engine,
    set_active_connection,
)
from app.services.database.schema_service import get_schema_with_ai_prompt
from app.services.database.connection_resolver import merge_connection_params, validate_connection_params
from app.services.database.upload_service import process_upload
from app.core.exceptions import DatabaseConnectionError
from app.db.models.user_model import User

router = APIRouter(prefix="/database", tags=[TAG_DATABASE])


@router.post(
    "/connect",
    response_model=SuccessResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Connect to a MySQL or PostgreSQL database",
    description=(
        "Validates the supplied credentials by opening a test connection. "
        "Returns connection metadata on success."
    ),
)
def connect_database(
    payload: DatabaseConnectRequest,
    db: Session = Depends(get_internal_db),
    current_user: User = Depends(get_current_user),
) -> SuccessResponse[dict]:
    """
    Establish (or reuse) a connection to the target database.
    """
    app_logger.info(
        "Connect request for user %d → type=%s host=%s db=%s user=%s",
        current_user.id, payload.database_type, payload.host, payload.database, payload.username,
    )

    config = validate_connection_params(payload.model_dump(exclude_none=True))
    engine: Engine = get_engine(
        host=config["host"],
        port=int(config["port"]),
        username=config["username"],
        password=config["password"],
        database=config["database"],
        database_type=config["database_type"],
        file_path=config.get("file_path"),
    )

    set_active_connection(config)

    app_logger.info(
        "Connection established for user %d → %s@%s:%d/%s",
        current_user.id, payload.username, payload.host, payload.port, payload.database,
    )

    return SuccessResponse(
        message="Database connected successfully.",
        data={
            "host": config["host"],
            "port": config["port"],
            "database": config["database"],
            "database_type": config["database_type"],
            "username": config["username"],
            "dialect": engine.dialect.name,
            "file_path": config.get("file_path"),
            "source_filename": config.get("source_filename"),
        },
    )


@router.post(
    "/upload",
    response_model=SuccessResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Upload SQLite or CSV files and connect",
)
async def upload_database(
    files: list[UploadFile] = File(..., description="SQLite (.db/.sqlite) or CSV files"),
    current_user: User = Depends(get_current_user),
) -> SuccessResponse[dict]:
    """Save uploaded files, merge/open them as SQLite, and activate the connection."""
    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")

    uploaded_files = []
    for file in files:
        if not file.filename:
            continue
        content = await file.read()
        uploaded_files.append((content, file.filename))

    if not uploaded_files:
        raise HTTPException(status_code=400, detail="No valid files provided.")

    try:
        config = process_upload(uploaded_files, current_user.id)
    except DatabaseConnectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    engine = get_engine(
        host=config["host"],
        port=config["port"],
        username=config["username"],
        password=config["password"],
        database=config["database"],
        database_type=config["database_type"],
        file_path=config["file_path"],
    )
    set_active_connection(config)

    app_logger.info(
        "Upload connect for user %d → files=%s tables dialect=%s",
        current_user.id,
        config.get("source_filename"),
        engine.dialect.name,
    )

    return SuccessResponse(
        message="Databases uploaded and connected successfully.",
        data={
            **{k: v for k, v in config.items() if k != "password"},
            "dialect": engine.dialect.name,
        },
    )


@router.post(
    "/schema",
    response_model=SuccessResponse[DatabaseSchemaResponse],
    status_code=status.HTTP_200_OK,
    summary="Retrieve schema for a connected database",
)
def get_schema(
    payload: DatabaseConnectRequest,
    force_refresh: bool = Query(False, description="Bypass schema TTL cache."),
    current_user: User = Depends(get_current_user),
) -> SuccessResponse[DatabaseSchemaResponse]:
    """Load and return the schema for the target database."""
    app_logger.info(
        "Schema request for user %d → type=%s host=%s db=%s",
        current_user.id, payload.database_type, payload.host, payload.database,
    )

    conn_params = validate_connection_params(
        merge_connection_params(payload.model_dump(exclude_none=True), get_active_connection())
    )

    engine: Engine = get_engine(
        host=conn_params["host"],
        port=int(conn_params["port"]),
        username=conn_params["username"],
        password=conn_params["password"],
        database=conn_params["database"],
        database_type=conn_params["database_type"],
        file_path=conn_params.get("file_path"),
    )

    schema_dict = get_schema_with_ai_prompt(engine, force_refresh=force_refresh)
    schema_response = DatabaseSchemaResponse(**schema_dict)

    app_logger.info(
        "Schema returned for user %d → %d table(s) from %s",
        current_user.id, schema_response.table_count, conn_params["database"],
    )

    return SuccessResponse(
        message=f"Schema loaded: {schema_response.table_count} table(s) found.",
        data=schema_response,
    )


@router.post(
    "/stats",
    response_model=SuccessResponse[DatabaseStatsResponse],
    status_code=status.HTTP_200_OK,
    summary="Get database statistics (row counts, tables)",
)
def fetch_database_stats(
    payload: DatabaseConnectRequest,
    current_user: User = Depends(get_current_user),
) -> SuccessResponse[DatabaseStatsResponse]:
    """Return approximate row counts from catalog statistics."""
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
    stats = get_database_stats(engine)
    return SuccessResponse(
        message="Database statistics loaded.",
        data=DatabaseStatsResponse(**stats),
    )


@router.post(
    "/disconnect",
    response_model=SuccessResponse[None],
    summary="Disconnect from the current database",
)
def disconnect_database(current_user: User = Depends(get_current_user)) -> SuccessResponse[None]:
    """Dispose of the active database connection and clear state."""
    config = get_active_connection()
    if config:
        disconnect_engine(config)
        clear_active_connection()
        return SuccessResponse(message="Database disconnected successfully.")

    return SuccessResponse(message="No active connection to disconnect.")


@router.get(
    "/status",
    response_model=SuccessResponse[dict | None],
    summary="Get current database connection status",
)
def get_connection_status(current_user: User = Depends(get_current_user)) -> SuccessResponse[dict | None]:
    """Return the currently active connection metadata (if any)."""
    config = get_active_connection()
    if config:
        # Exclude password for security
        status_data = {k: v for k, v in config.items() if k != "password"}
        return SuccessResponse(
            message="Active connection found.",
            data=status_data
        )

    return SuccessResponse(
        message="No active database connection.",
        data=None
    )
