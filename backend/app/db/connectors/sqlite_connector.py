"""
db/connectors/sqlite_connector.py
──────────────────────────────────
Creates a SQLAlchemy engine for uploaded SQLite database files.
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.exceptions import DatabaseConnectionError
from app.core.logger import db_logger


def build_sqlite_engine(
    host: str = "local",
    port: int = 0,
    username: str = "sqlite",
    password: str = "",
    database: str = "",
    *,
    file_path: str | None = None,
    **_,
) -> Engine:
    """
    Build a SQLAlchemy engine for a SQLite file on disk.

    ``database`` may hold the file path when ``file_path`` is omitted.
    """
    path_str = file_path or database
    if not path_str:
        raise DatabaseConnectionError(
            "SQLite connection requires a file_path.",
            detail={"database_type": "sqlite"},
        )

    db_path = Path(path_str).resolve()
    if not db_path.is_file():
        raise DatabaseConnectionError(
            f"SQLite database file not found: {db_path}",
            detail={"file_path": str(db_path)},
        )

    url = f"sqlite:///{db_path.as_posix()}"
    db_logger.info("Opening SQLite file → %s", db_path)

    try:
        engine = create_engine(
            url,
            connect_args={"check_same_thread": False},
            pool_pre_ping=True,
        )
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return engine
    except SQLAlchemyError as exc:
        raise DatabaseConnectionError(
            f"Failed to open SQLite database: {exc}",
            detail={"file_path": str(db_path)},
        ) from exc
