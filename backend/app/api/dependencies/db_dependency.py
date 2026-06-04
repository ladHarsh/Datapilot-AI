"""
api/dependencies/db_dependency.py
──────────────────────────────────
FastAPI dependency providers.

Import and use these with ``Depends()`` in route handlers.
"""
from __future__ import annotations

from typing import Generator

from fastapi import Depends
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.database_schema import DatabaseConnectRequest
from app.services.database.connection_service import get_engine


def get_internal_db() -> Generator[Session, None, None]:
    """
    Yield a SQLAlchemy Session for the internal application database.

    Usage
    -----
    @router.get("/example")
    def example(db: Session = Depends(get_internal_db)):
        ...
    """
    yield from get_db()


def get_target_engine(payload: DatabaseConnectRequest) -> Engine:
    """
    Resolve a target database engine from a connection-request payload.

    Intended for endpoints that accept DatabaseConnectRequest in the body
    and need an Engine without the caller managing the lifecycle.

    Usage
    -----
    @router.post("/query")
    def run_query(
        payload: QueryExecuteRequest,
        engine: Engine = Depends(get_target_engine),
    ):
        ...

    Note: ``QueryExecuteRequest`` inherits all DatabaseConnectRequest fields,
    so this dependency works transparently for both request types.
    """
    return get_engine(
        host=payload.host,
        port=payload.port,
        username=payload.username,
        password=payload.password,
        database=payload.database,
        database_type=payload.database_type,
    )
