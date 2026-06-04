"""
db/connectors/mysql_connector.py
─────────────────────────────────
Creates a pooled SQLAlchemy engine for MySQL using PyMySQL driver.
"""
from __future__ import annotations

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.core.constants import MAX_OVERFLOW, POOL_RECYCLE, POOL_SIZE, POOL_TIMEOUT
from app.core.exceptions import DatabaseConnectionError
from app.core.logger import db_logger


from urllib.parse import quote_plus

def build_mysql_engine(
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
) -> Engine:
    """
    Build and return a pooled SQLAlchemy Engine for MySQL.

    Parameters
    ----------
    host:            MySQL server hostname or IP.
    port:            MySQL server port (default 3306).
    username:        Database user.
    password:        Database password.
    database:        Target schema/database name.
    pool_size:       Number of persistent connections in the pool.
    max_overflow:    Extra connections allowed beyond pool_size.
    pool_recycle:    Seconds before recycling idle connections.
    pool_timeout:    Seconds to wait for a free connection from the pool.
    connect_timeout: Seconds before a new TCP connection attempt times out.

    Returns
    -------
    SQLAlchemy Engine (MySQL/PyMySQL).

    Raises
    ------
    DatabaseConnectionError: If the engine cannot reach the database.
    """
    # URL-encode credentials to handle special characters (@, :, etc.)
    safe_user = quote_plus(username)
    safe_pass = quote_plus(password)

    # PyMySQL driver — charset=utf8mb4 for full Unicode support
    url = (
        f"mysql+pymysql://{safe_user}:{safe_pass}@{host}:{port}/{database}"
        f"?charset=utf8mb4&connect_timeout={connect_timeout}"
    )

    db_logger.info(
        "Building MySQL engine → host=%s port=%s db=%s", host, port, database
    )

    try:
        engine = create_engine(
            url,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_recycle=pool_recycle,
            pool_timeout=pool_timeout,
            pool_pre_ping=True,          # verify connections before use
            echo=False,
        )
        _verify_connection(engine, host, database)
        return engine

    except DatabaseConnectionError:
        raise
    except SQLAlchemyError as exc:
        raise DatabaseConnectionError(
            f"Failed to build MySQL engine: {exc}",
            detail={"host": host, "port": port, "database": database},
        ) from exc


def _verify_connection(engine: Engine, host: str, database: str) -> None:
    """Run a lightweight ping query to validate the engine is reachable."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_logger.info("MySQL connection verified → host=%s db=%s", host, database)
    except OperationalError as exc:
        raise DatabaseConnectionError(
            f"Cannot reach MySQL server at {host}: {exc}",
            detail={"host": host, "database": database},
        ) from exc
