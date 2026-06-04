"""
db/connectors/postgres_connector.py
────────────────────────────────────
Creates a pooled SQLAlchemy engine for PostgreSQL using psycopg2 driver.
"""
from __future__ import annotations

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.core.constants import MAX_OVERFLOW, POOL_RECYCLE, POOL_SIZE, POOL_TIMEOUT
from app.core.exceptions import DatabaseConnectionError
from app.core.logger import db_logger


from urllib.parse import quote_plus

def build_postgres_engine(
    host: str,
    port: int,
    username: str,
    password: str,
    database: str,
    *,
    pool_size: int = POOL_SIZE,
    max_overflow: int = MAX_OVERFLOW,
    pool_recycle: int = POOL_RECYCLE,
    pool_timeout: int = POOL_TIMEOUT,
    connect_timeout: int = 10,
    sslmode: str = "prefer",
) -> Engine:
    """
    Build and return a pooled SQLAlchemy Engine for PostgreSQL.

    Parameters
    ----------
    host:             PostgreSQL server hostname or IP.
    port:             PostgreSQL server port (default 5432).
    username:         Database user.
    password:         Database password.
    database:         Target database name.
    pool_size:        Number of persistent connections in the pool.
    max_overflow:     Extra connections allowed beyond pool_size.
    pool_recycle:     Seconds before recycling idle connections.
    pool_timeout:     Seconds to wait for a free connection from the pool.
    connect_timeout:  Seconds before a TCP connection attempt times out.
    sslmode:          PostgreSQL SSL mode (prefer|require|disable|…).

    Returns
    -------
    SQLAlchemy Engine (PostgreSQL/psycopg2).

    Raises
    ------
    DatabaseConnectionError: If the engine cannot reach the database.
    """
    # URL-encode credentials to handle special characters (@, :, etc.)
    safe_user = quote_plus(username)
    safe_pass = quote_plus(password)

    url = (
        f"postgresql+psycopg2://{safe_user}:{safe_pass}@{host}:{port}/{database}"
        f"?connect_timeout={connect_timeout}&sslmode={sslmode}"
    )

    db_logger.info(
        "Building PostgreSQL engine → host=%s port=%s db=%s", host, port, database
    )

    try:
        engine = create_engine(
            url,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_recycle=pool_recycle,
            pool_timeout=pool_timeout,
            pool_pre_ping=True,
            echo=False,
        )
        _verify_connection(engine, host, database)
        return engine

    except DatabaseConnectionError:
        raise
    except SQLAlchemyError as exc:
        raise DatabaseConnectionError(
            f"Failed to build PostgreSQL engine: {exc}",
            detail={"host": host, "port": port, "database": database},
        ) from exc


def _verify_connection(engine: Engine, host: str, database: str) -> None:
    """Run a lightweight ping query to validate the engine is reachable."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_logger.info(
            "PostgreSQL connection verified → host=%s db=%s", host, database
        )
    except OperationalError as exc:
        raise DatabaseConnectionError(
            f"Cannot reach PostgreSQL server at {host}: {exc}",
            detail={"host": host, "database": database},
        ) from exc
