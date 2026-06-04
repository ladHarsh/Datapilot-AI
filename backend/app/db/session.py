"""
db/session.py
─────────────
Internal database session management.

This module owns the engine and sessionmaker for the *internal* SQLite/Postgres
database that stores query history and app metadata.

For *user-supplied* target databases (MySQL / Postgres analytic targets),
see ``services/database/connection_service.py``.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.logger import db_logger

# ── Internal engine ───────────────────────────────────────────────────────────
_engine = create_engine(
    settings.INTERNAL_DB_URL,
    # SQLite-specific: allow the same connection across threads (for SQLite only)
    connect_args={"check_same_thread": False}
    if settings.INTERNAL_DB_URL.startswith("sqlite")
    else {},
    pool_pre_ping=True,
    echo=False,
)

# ── Session factory ───────────────────────────────────────────────────────────
SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a database session and guarantees cleanup.

    Usage
    -----
    @router.get("/example")
    def example(db: Session = Depends(get_db)):
        ...
    """
    db: Session = SessionLocal()
    try:
        yield db
    except Exception:
        db_logger.exception("Session error — rolling back")
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """
    Context-manager session for use outside of FastAPI request lifecycle
    (e.g., startup events, background tasks).

    Usage
    -----
    with session_scope() as db:
        db.add(record)
    """
    db: Session = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db_logger.exception("Transaction error — rolling back")
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    """
    Create all tables defined in ORM models against the internal engine.
    Called once at application startup.
    """
    from app.db.base import Base
    import app.db.models  # Registers all models via __init__.py

    Base.metadata.create_all(bind=_engine)
    db_logger.info("Internal database tables created / verified.")
