"""
Resolve merged connection parameters from request payload and active session.
"""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status


def merge_connection_params(
    payload: dict[str, Any],
    active_config: dict[str, Any] | None,
) -> dict[str, Any]:
    """Merge optional payload fields with the active connection configuration."""
    active = active_config or {}
    merged = {
        "host": payload.get("host") or active.get("host"),
        "port": payload.get("port") if payload.get("port") is not None else active.get("port"),
        "username": payload.get("username") or active.get("username"),
        "password": payload.get("password") if payload.get("password") is not None else active.get("password"),
        "database": payload.get("database") or active.get("database"),
        "database_type": payload.get("database_type") or active.get("database_type"),
        "file_path": payload.get("file_path") or active.get("file_path"),
    }
    return merged


def validate_connection_params(params: dict[str, Any]) -> dict[str, Any]:
    """Ensure required fields exist for the database type."""
    db_type = (params.get("database_type") or "").strip().lower()
    if not db_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing database_type.",
        )

    if db_type == "sqlite":
        if not params.get("file_path"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing SQLite file_path. Upload or reconnect your database file.",
            )
        params.setdefault("host", "local")
        params.setdefault("port", 0)
        params.setdefault("username", "sqlite")
        params.setdefault("password", "")
        params.setdefault("database", params.get("database") or "uploaded")
        return params

    required = ("host", "port", "username", "password", "database")
    missing = [k for k in required if params.get(k) in (None, "")]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing connection details. Please connect first or provide credentials.",
        )
    return params
