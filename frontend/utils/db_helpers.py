"""Database connection helpers for the Streamlit frontend."""

from __future__ import annotations

from typing import Any

NETWORK_DB_KEYS = ("host", "port", "username", "password", "database", "database_type")
SQLITE_DB_KEYS = ("file_path", "database", "database_type")


def is_valid_db_info(db_info: dict | None) -> bool:
    if not db_info:
        return False

    db_type = str(db_info.get("database_type", "")).strip().lower()
    if db_type == "sqlite":
        return bool(db_info.get("file_path")) and bool(db_info.get("database"))
    return all(db_info.get(key) not in (None, "") for key in NETWORK_DB_KEYS)


def normalize_db_info(db_info: dict) -> dict[str, Any] | None:
    """Return a clean payload for backend API calls, or None if incomplete."""
    if not db_info:
        return None

    db_type = str(db_info.get("database_type", "")).strip().lower()
    if db_type in ("postgresql", "postgres"):
        db_type = "postgresql"
    elif db_type in ("mysql", "mariadb"):
        db_type = "mysql"
    elif db_type == "sqlite":
        if not db_info.get("file_path"):
            return None
        return {
            "database_type": "sqlite",
            "file_path": str(db_info["file_path"]),
            "database": str(db_info.get("database", "uploaded")).strip(),
            "host": str(db_info.get("host", "local")),
            "port": int(db_info.get("port", 0)),
            "username": str(db_info.get("username", "sqlite")),
            "password": str(db_info.get("password", "")),
        }

    if not all(db_info.get(key) not in (None, "") for key in NETWORK_DB_KEYS):
        return None

    return {
        "host": str(db_info["host"]).strip(),
        "port": int(db_info["port"]),
        "username": str(db_info["username"]).strip(),
        "password": str(db_info["password"]),
        "database": str(db_info["database"]).strip(),
        "database_type": db_type,
    }


def first_table_name(schema_data: dict | None) -> str | None:
    if not schema_data:
        return None
    names = list(schema_data.keys())
    return names[0] if names else None
