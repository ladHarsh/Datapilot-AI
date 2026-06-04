"""
services/database/stats_service.py
──────────────────────────────────
Fast database statistics using information_schema / catalog views.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.logger import db_logger

_USER_TABLE_PATTERN = re.compile(
    r"(user|users|customer|customers|employee|employees|member|members|account|accounts)$",
    re.IGNORECASE,
)


def get_database_stats(engine: Engine) -> Dict[str, Any]:
    """
    Return approximate row counts and table metadata for dashboard metrics.

    Uses catalog statistics (no full table scans).
    """
    dialect = engine.dialect.name
    db_name = engine.url.database or ""

    try:
        if dialect == "mysql":
            table_rows = _mysql_table_rows(engine, db_name)
        elif dialect == "postgresql":
            table_rows = _postgres_table_rows(engine)
        elif dialect == "sqlite":
            table_rows = _fallback_table_rows(engine)
        else:
            table_rows = _fallback_table_rows(engine)

        total_rows = sum(r["row_count"] for r in table_rows)
        user_tables = [
            r for r in table_rows if _USER_TABLE_PATTERN.search(r["table_name"])
        ]
        active_users = user_tables[0]["row_count"] if user_tables else 0

        return {
            "database": db_name,
            "dialect": dialect,
            "table_count": len(table_rows),
            "total_rows": total_rows,
            "active_users": active_users,
            "tables": table_rows,
        }
    except SQLAlchemyError as exc:
        db_logger.warning("StatsService: failed to load stats — %s", exc)
        return {
            "database": db_name,
            "dialect": dialect,
            "table_count": 0,
            "total_rows": 0,
            "active_users": 0,
            "tables": [],
        }


def _mysql_table_rows(engine: Engine, db_name: str) -> List[Dict[str, Any]]:
    sql = text(
        """
        SELECT table_name, COALESCE(table_rows, 0) AS row_count
        FROM information_schema.tables
        WHERE table_schema = :db
          AND table_type = 'BASE TABLE'
        ORDER BY table_name
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql, {"db": db_name}).fetchall()
    return [{"table_name": r[0], "row_count": int(r[1] or 0)} for r in rows]


def _postgres_table_rows(engine: Engine) -> List[Dict[str, Any]]:
    sql = text(
        """
        SELECT relname AS table_name, COALESCE(n_live_tup, 0)::bigint AS row_count
        FROM pg_stat_user_tables
        ORDER BY relname
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql).fetchall()
    return [{"table_name": r[0], "row_count": int(r[1] or 0)} for r in rows]


def _fallback_table_rows(engine: Engine) -> List[Dict[str, Any]]:
    from sqlalchemy import inspect

    inspector = inspect(engine)
    result: List[Dict[str, Any]] = []
    for name in inspector.get_table_names():
        try:
            with engine.connect() as conn:
                count = conn.execute(text(f'SELECT COUNT(*) FROM "{name}"')).scalar()
            result.append({"table_name": name, "row_count": int(count or 0)})
        except SQLAlchemyError:
            result.append({"table_name": name, "row_count": 0})
    return result
