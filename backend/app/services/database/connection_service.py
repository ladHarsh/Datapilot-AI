"""
services/database/connection_service.py
────────────────────────────────────────
Orchestrates the creation and retrieval of database engines.
"""
from __future__ import annotations

from sqlalchemy import Engine

from app.core.constants import SUPPORTED_DATABASES
from app.core.exceptions import DatabaseConnectionError
from app.core.logger import db_logger
from app.db.connectors.connection_manager import connection_manager
from app.db.connectors.mysql_connector import build_mysql_engine
from app.db.connectors.postgres_connector import build_postgres_engine
from app.db.connectors.sqlite_connector import build_sqlite_engine

_ACTIVE_CONFIG: dict | None = None

_FACTORY_MAP = {
    "mysql": build_mysql_engine,
    "postgresql": build_postgres_engine,
    "sqlite": build_sqlite_engine,
}


def get_engine(
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    database: str,
    database_type: str,
    file_path: str | None = None,
) -> Engine:
    """Return an active SQLAlchemy Engine for the requested database."""
    db_type = database_type.strip().lower()

    if db_type not in SUPPORTED_DATABASES:
        raise DatabaseConnectionError(
            f"Unsupported database type: '{database_type}'. "
            f"Supported: {SUPPORTED_DATABASES}",
            detail={"database_type": database_type},
        )

    factory_fn = _FACTORY_MAP[db_type]

    if db_type == "sqlite":
        cache_database = file_path or database
        db_logger.info("Requesting SQLite engine → %s", cache_database)
        engine = connection_manager.get_or_create(
            db_type=db_type,
            host=host or "local",
            port=port or 0,
            username=username or "sqlite",
            password=password or "",
            database=cache_database,
            factory_fn=factory_fn,
            file_path=file_path or database,
        )
        return engine

    db_logger.info(
        "Requesting engine → type=%s host=%s db=%s", db_type, host, database
    )
    engine = connection_manager.get_or_create(
        db_type=db_type,
        host=host,
        port=port,
        username=username,
        password=password,
        database=database,
        factory_fn=factory_fn,
    )
    db_logger.info("Engine ready → type=%s host=%s db=%s", db_type, host, database)
    return engine


def test_connection(
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    database: str,
    database_type: str,
    file_path: str | None = None,
) -> bool:
    """Attempt to open a connection; return True on success."""
    engine = get_engine(
        host=host,
        port=port,
        username=username,
        password=password,
        database=database,
        database_type=database_type,
        file_path=file_path,
    )
    return engine is not None


def set_active_connection(config: dict) -> None:
    global _ACTIVE_CONFIG
    _ACTIVE_CONFIG = config
    db_logger.info("Active connection configuration updated.")


def get_active_connection() -> dict | None:
    return _ACTIVE_CONFIG


def clear_active_connection() -> None:
    global _ACTIVE_CONFIG
    _ACTIVE_CONFIG = None
    db_logger.info("Active connection configuration cleared.")


def disconnect_engine(config: dict) -> None:
    db_type = config.get("database_type", "")
    database = (
        config.get("file_path")
        if db_type == "sqlite"
        else config.get("database")
    )
    connection_manager.remove(
        db_type=db_type,
        host=config.get("host", "local"),
        port=config.get("port", 0),
        username=config.get("username", "sqlite"),
        database=database,
    )
