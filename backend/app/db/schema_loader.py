"""
db/schema_loader.py
────────────────────
Extracts full database schema metadata using SQLAlchemy's Inspector.

Returns a structured dict containing:
  • table names
  • columns (name, type, nullable, default)
  • primary keys
  • foreign keys
  • indexes

Also provides an AI-prompt–friendly text representation of the schema.
A simple in-process TTL cache prevents redundant round-trips.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.exceptions import SchemaLoadError
from app.core.logger import db_logger

# ── Simple in-process TTL cache ───────────────────────────────────────────────
_cache: Dict[str, Dict[str, Any]] = {}
_cache_ts: Dict[str, float] = {}
_CACHE_TTL: int = 300   # 5 minutes


def _cache_key(engine: Engine) -> str:
    return str(engine.url).split("?")[0]   # strip query params / credentials


def _is_stale(key: str) -> bool:
    return (time.time() - _cache_ts.get(key, 0)) > _CACHE_TTL


# ══════════════════════════════════════════════════════════════════════════════
#  Public API
# ══════════════════════════════════════════════════════════════════════════════

def load_schema(engine: Engine, *, force_refresh: bool = False) -> Dict[str, Any]:
    """
    Extract and return the full schema of the database attached to *engine*.

    Parameters
    ----------
    engine:        An active SQLAlchemy Engine for the target database.
    force_refresh: Bypass the in-process cache and re-inspect the DB.

    Returns
    -------
    A dict with keys:
      ``database``   — Database/schema name.
      ``dialect``    — SQLAlchemy dialect name (mysql / postgresql / …).
      ``tables``     — List of table descriptors (see ``_describe_table``).
      ``table_count``— Total number of tables discovered.

    Raises
    ------
    SchemaLoadError: On any SQLAlchemy or introspection error.
    """
    key = _cache_key(engine)

    if not force_refresh and key in _cache and not _is_stale(key):
        db_logger.debug("Schema cache hit for %s", key)
        return _cache[key]

    db_logger.info("Inspecting schema for %s", key)

    try:
        inspector = inspect(engine)
        table_names: List[str] = inspector.get_table_names()

        tables = [_describe_table(inspector, table) for table in table_names]

        # Best-effort: derive DB name from engine URL
        db_name: str = engine.url.database or "unknown"

        schema: Dict[str, Any] = {
            "database": db_name,
            "dialect": engine.dialect.name,
            "table_count": len(tables),
            "tables": tables,
        }

        _cache[key] = schema
        _cache_ts[key] = time.time()

        db_logger.info(
            "Schema loaded: %d table(s) from %s", len(tables), db_name
        )
        return schema

    except SQLAlchemyError as exc:
        raise SchemaLoadError(
            f"Failed to load schema: {exc}",
            detail={"engine_url": key},
        ) from exc


def invalidate_cache(engine: Engine) -> None:
    """Remove the cached schema entry for the given engine."""
    key = _cache_key(engine)
    _cache.pop(key, None)
    _cache_ts.pop(key, None)
    db_logger.debug("Schema cache invalidated for %s", key)


def format_schema_for_ai(schema: Dict[str, Any]) -> str:
    """
    Convert a schema dict (from ``load_schema``) into a compact, token-efficient
    text block suitable for inclusion in an LLM prompt.

    Format example
    --------------
    Database: mydb (mysql)

    TABLE orders
      - id          : INTEGER  [PK]
      - customer_id : INTEGER  [FK → customers.id]
      - total       : FLOAT
      - created_at  : DATETIME
    """
    lines: List[str] = [
        f"Database: {schema['database']} ({schema['dialect']})",
        f"Total tables: {schema['table_count']}",
        "",
    ]

    for table in schema["tables"]:
        lines.append(f"TABLE {table['name']}")
        pk_set = set(table.get("primary_keys", []))

        for col in table["columns"]:
            col_name = col["name"]
            col_type = col["type"]

            annotations: List[str] = []
            if col_name in pk_set:
                annotations.append("PK")
            if not col["nullable"]:
                annotations.append("NOT NULL")

            for fk in table.get("foreign_keys", []):
                if fk["constrained_column"] == col_name:
                    annotations.append(
                        f"FK → {fk['referred_table']}.{fk['referred_column']}"
                    )

            suffix = f"  [{', '.join(annotations)}]" if annotations else ""
            lines.append(f"  - {col_name:<25} : {col_type}{suffix}")

        lines.append("")   # blank line between tables

    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
#  Internal helpers
# ══════════════════════════════════════════════════════════════════════════════

def _describe_table(inspector, table_name: str) -> Dict[str, Any]:
    """Return a structured descriptor dict for a single table."""
    columns = _get_columns(inspector, table_name)
    pks = inspector.get_pk_constraint(table_name).get("constrained_columns", [])
    fks = _get_foreign_keys(inspector, table_name)
    indexes = _get_indexes(inspector, table_name)

    return {
        "name": table_name,
        "columns": columns,
        "primary_keys": pks,
        "foreign_keys": fks,
        "indexes": indexes,
        "column_count": len(columns),
    }


def _get_columns(inspector, table_name: str) -> List[Dict[str, Any]]:
    cols = []
    for col in inspector.get_columns(table_name):
        cols.append(
            {
                "name": col["name"],
                "type": str(col["type"]),
                "nullable": col.get("nullable", True),
                "default": str(col["default"]) if col.get("default") is not None else None,
                "autoincrement": col.get("autoincrement", False),
            }
        )
    return cols


def _get_foreign_keys(inspector, table_name: str) -> List[Dict[str, str]]:
    fks = []
    for fk in inspector.get_foreign_keys(table_name):
        for local_col, ref_col in zip(
            fk.get("constrained_columns", []),
            fk.get("referred_columns", []),
        ):
            fks.append(
                {
                    "constrained_column": local_col,
                    "referred_table": fk.get("referred_table", ""),
                    "referred_column": ref_col,
                }
            )
    return fks


def _get_indexes(inspector, table_name: str) -> List[Dict[str, Any]]:
    return [
        {
            "name": idx.get("name"),
            "columns": idx.get("column_names", []),
            "unique": idx.get("unique", False),
        }
        for idx in inspector.get_indexes(table_name)
    ]
