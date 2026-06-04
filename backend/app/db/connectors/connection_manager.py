"""
db/connectors/connection_manager.py
────────────────────────────────────
Thread-safe, singleton connection manager.

• Caches active engines keyed by a deterministic connection key.
• Reuses existing engines to avoid connection-pool exhaustion.
• Supports safe disposal and removal of stale engines.
"""
from __future__ import annotations

import hashlib
import threading
from typing import Dict, Optional

from sqlalchemy import Engine

from app.core.exceptions import DatabaseConnectionError
from app.core.logger import db_logger


def _make_key(db_type: str, host: str, port: int, username: str, database: str) -> str:
    """
    Build a deterministic, opaque cache key for a connection config.
    Deliberately excludes the password from the key (security).
    """
    raw = f"{db_type}|{host}|{port}|{username}|{database}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


class ConnectionManager:
    """
    Singleton registry of active SQLAlchemy engines.

    Usage
    -----
    manager = ConnectionManager.instance()
    engine  = manager.get_or_create(db_type, host, port, user, pw, db, factory_fn)
    """

    _instance: Optional["ConnectionManager"] = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        self._engines: Dict[str, Engine] = {}
        self._engine_lock = threading.Lock()

    # ── Singleton access ──────────────────────────────────────────────────────
    @classmethod
    def instance(cls) -> "ConnectionManager":
        """Return the process-wide singleton instance (thread-safe)."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ── Public API ────────────────────────────────────────────────────────────
    def get_or_create(
        self,
        db_type: str,
        host: str,
        port: int,
        username: str,
        password: str,
        database: str,
        factory_fn,  # Callable[[...], Engine]
        file_path: str | None = None,
    ) -> Engine:
        """
        Return a cached engine if one already exists for this config,
        otherwise call ``factory_fn`` to create a new one and cache it.

        Parameters
        ----------
        db_type:    "mysql" | "postgresql"
        host:       Server hostname.
        port:       Server port.
        username:   DB user.
        password:   DB password (used only for engine creation, never stored).
        database:   Target schema/database name.
        factory_fn: Callable(host, port, username, password, database) -> Engine.

        Returns
        -------
        Active SQLAlchemy Engine.
        """
        key = _make_key(db_type, host, port, username, database)

        with self._engine_lock:
            if key in self._engines:
                db_logger.debug(
                    "Reusing cached engine [%s] → %s@%s:%s/%s",
                    key, username, host, port, database,
                )
                return self._engines[key]

        db_logger.info(
            "Creating new engine [%s] → %s@%s:%s/%s [%s]",
            key, username, host, port, database, db_type,
        )
        kwargs = {
            "host": host,
            "port": port,
            "username": username,
            "password": password,
            "database": database,
        }
        if file_path is not None:
            kwargs["file_path"] = file_path

        engine = factory_fn(**kwargs)


        with self._engine_lock:
            self._engines[key] = engine

        return engine

    def remove(
        self,
        db_type: str,
        host: str,
        port: int,
        username: str,
        database: str,
    ) -> None:
        """Dispose of and remove a cached engine."""
        key = _make_key(db_type, host, port, username, database)
        with self._engine_lock:
            engine = self._engines.pop(key, None)
        if engine:
            engine.dispose()
            db_logger.info("Disposed engine [%s]", key)

    def dispose_all(self) -> None:
        """Dispose every cached engine (called on application shutdown)."""
        with self._engine_lock:
            for key, engine in self._engines.items():
                engine.dispose()
                db_logger.info("Disposed engine [%s] during shutdown", key)
            self._engines.clear()

    @property
    def active_count(self) -> int:
        """Return number of currently cached engines."""
        with self._engine_lock:
            return len(self._engines)


# Module-level singleton
connection_manager: ConnectionManager = ConnectionManager.instance()
