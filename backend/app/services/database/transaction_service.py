"""
services/database/transaction_service.py
─────────────────────────────────────────
Utilities for managing transactions against the *internal* application DB
(query history, metadata) as well as helper hooks for future write operations.

For the target analytic databases, we deliberately keep sessions read-only
(SELECT enforcement is handled in query_executor.py).
"""
from __future__ import annotations

from typing import Callable, TypeVar

from sqlalchemy.orm import Session

from app.core.logger import db_logger

R = TypeVar("R")


def commit(db: Session) -> None:
    """
    Commit the current transaction.

    Parameters
    ----------
    db: Active SQLAlchemy Session.
    """
    try:
        db.commit()
        db_logger.debug("Transaction committed.")
    except Exception:
        db_logger.exception("Commit failed — rolling back.")
        db.rollback()
        raise


def rollback(db: Session) -> None:
    """
    Roll back the current transaction without raising.

    Parameters
    ----------
    db: Active SQLAlchemy Session.
    """
    try:
        db.rollback()
        db_logger.debug("Transaction rolled back.")
    except Exception:
        db_logger.warning("Rollback itself failed — session may be in bad state.")


def cleanup(db: Session) -> None:
    """
    Close the session and release its connection back to the pool.

    Parameters
    ----------
    db: Active SQLAlchemy Session.
    """
    try:
        db.close()
        db_logger.debug("Session closed and returned to pool.")
    except Exception:
        db_logger.warning("Error while closing session.")


def run_in_transaction(db: Session, fn: Callable[[], R]) -> R:
    """
    Execute *fn* inside an explicit transaction.

    Commits on success, rolls back on any exception, and re-raises.

    Parameters
    ----------
    db: Active SQLAlchemy Session.
    fn: Zero-argument callable to run inside the transaction.

    Returns
    -------
    Whatever *fn* returns.
    """
    try:
        result = fn()
        commit(db)
        return result
    except Exception:
        rollback(db)
        raise
