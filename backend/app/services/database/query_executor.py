"""
services/database/query_executor.py
─────────────────────────────────────
Secure, validated SQL execution service.

SECURITY CONTRACT
─────────────────
• Only SELECT statements are allowed.
• All tokens in BLOCKED_SQL_KEYWORDS are prohibited.
• A row-count cap and per-query timeout are enforced.
• Results are serialised to JSON-safe dicts via pandas.
• No raw user strings are interpolated into SQL.
"""
from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from sqlalchemy import Engine, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.core.config import settings
from app.core.constants import BLOCKED_SQL_KEYWORDS, DEFAULT_ROW_LIMIT
from app.core.exceptions import (
    InvalidSQLException,
    QueryExecutionError,
    QueryTimeoutError,
)
from app.core.logger import query_logger

# Pre-compiled regex: tokenise SQL for keyword scanning
_TOKEN_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\b")


# ══════════════════════════════════════════════════════════════════════════════
#  Security validation
# ══════════════════════════════════════════════════════════════════════════════

def validate_sql(sql: str) -> None:
    """
    Enforce SELECT-only policy on the provided SQL string.

    Raises
    ------
    InvalidSQLException: If the SQL is empty, not a SELECT, or contains
                         any blocked keyword.
    """
    sql_stripped = sql.strip()

    if not sql_stripped:
        raise InvalidSQLException("SQL query cannot be empty.")

    # Must start with SELECT (after stripping comments / whitespace)
    clean = re.sub(r"--[^\n]*", "", sql_stripped)          # strip line comments
    clean = re.sub(r"/\*.*?\*/", "", clean, flags=re.S)    # strip block comments
    clean = clean.strip()

    if not re.match(r"^(SELECT|WITH)\b", clean, re.IGNORECASE):
        raise InvalidSQLException(
            "Security Warning: Only SELECT and WITH statements are permitted. Data-changing and schema-changing operations (such as ALTER, DROP, DELETE, UPDATE) are blocked.",
            detail={"first_token": clean.split()[0] if clean else ""},
        )

    # Scan for blocked keywords
    tokens_upper = {tok.upper() for tok in _TOKEN_RE.findall(clean)}
    blocked_found = tokens_upper & BLOCKED_SQL_KEYWORDS
    if blocked_found:
        raise InvalidSQLException(
            f"Security Warning: Query contains forbidden keyword(s): {', '.join(sorted(blocked_found))}. Data-changing and schema-changing operations (such as ALTER, DROP, DELETE, UPDATE) are blocked.",
            detail={"blocked": list(blocked_found)},
        )

    query_logger.debug("SQL validation passed: %.120s…", sql_stripped)


# ══════════════════════════════════════════════════════════════════════════════
#  Execution
# ══════════════════════════════════════════════════════════════════════════════

def execute_query(
    engine: Engine,
    sql: str,
    *,
    row_limit: int = DEFAULT_ROW_LIMIT,
    timeout: int = settings.QUERY_TIMEOUT,
    user_query: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Validate and execute a SQL statement against *engine*.
    Supports SELECT and DML statements (DELETE, UPDATE, INSERT, etc.).

    Parameters
    ----------
    engine:     Active SQLAlchemy Engine for the target database.
    sql:        SQL string to execute.
    row_limit:  Maximum rows to return (hard cap at settings.MAX_ROWS).
    timeout:    Per-query timeout in seconds.
    user_query: Original natural-language query (stored in result for tracing).

    Returns
    -------
    Dict with keys: sql_query, user_query, columns, rows, row_count,
                    execution_duration, truncated.

    Raises
    ------
    InvalidSQLException:  On policy violation.
    QueryTimeoutError:    When execution exceeds the timeout.
    QueryExecutionError:  On any database-level error.
    """
    # 1. Enforce SELECT-only validation policy
    validate_sql(sql)

    # 2. Normalise row limit
    effective_limit = min(row_limit, settings.MAX_ROWS)

    # 3. Inject LIMIT if not already present (best-effort; only for SELECT/WITH)
    limited_sql = _inject_limit(sql, effective_limit + 1)

    query_logger.info(
        "Executing query (limit=%d, timeout=%ds): %.200s", effective_limit, timeout, sql
    )

    start = time.perf_counter()

    try:
        with engine.connect() as conn:
            # Set statement timeout for supported dialects
            _apply_timeout(conn, engine, timeout)

            result = conn.execute(text(limited_sql))
            
            # Check if query returns rows (DQL vs DML)
            if result.returns_rows:
                columns: List[str] = list(result.keys())
                fetched_rows = result.fetchall()
                is_dql = True
            else:
                conn.commit()
                columns = ["status"]
                fetched_rows = [(f"Query executed successfully. {result.rowcount} rows affected.",)]
                is_dql = False

    except OperationalError as exc:
        msg = str(exc)
        if "timeout" in msg.lower() or "statement timeout" in msg.lower():
            raise QueryTimeoutError(
                f"Query exceeded the {timeout}s timeout.",
                detail={"timeout": timeout},
            ) from exc
        raise QueryExecutionError(
            f"Database operational error: {msg}",
            detail={"sql": sql[:300]},
        ) from exc
    except SQLAlchemyError as exc:
        raise QueryExecutionError(
            f"Query execution failed: {exc}",
            detail={"sql": sql[:300]},
        ) from exc

    elapsed = round(time.perf_counter() - start, 4)

    # 4. Serialise to JSON-safe format via pandas
    if is_dql:
        df = pd.DataFrame(fetched_rows, columns=columns)
        
        # Actually enforce the row limit on the dataframe
        if len(df) > effective_limit:
            df = df.head(effective_limit)
            truncated = True
        else:
            truncated = False
            
        rows: List[Dict[str, Any]] = _dataframe_to_json_rows(df)
    else:
        rows = [{"status": fetched_rows[0][0]}]
        truncated = False

    query_logger.info(
        "Query completed: %d rows in %.3fs (truncated=%s)",
        len(rows), elapsed, truncated,
    )

    return {
        "sql_query": sql,
        "user_query": user_query,
        "columns": columns,
        "rows": rows,
        "row_count": len(rows) if is_dql else result.rowcount,
        "execution_duration": elapsed,
        "truncated": truncated,
        "explanation": None,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  Internal helpers
# ══════════════════════════════════════════════════════════════════════════════

def _inject_limit(sql: str, limit: int) -> str:
    """
    Append a LIMIT clause if the SQL doesn't already contain one.
    Only injects for SELECT or WITH queries.
    """
    clean_sql = sql.strip()
    # Strip comments first
    clean = re.sub(r"--[^\n]*", "", clean_sql)
    clean = re.sub(r"/\*.*?\*/", "", clean, flags=re.S)
    clean = clean.strip()

    # Only SELECT or WITH queries should have LIMIT injected
    if not re.match(r"^(SELECT|WITH)\b", clean, re.IGNORECASE):
        return sql

    clean_rstrip = sql.rstrip("; \n")
    if not re.search(r"\bLIMIT\b", clean_rstrip, re.IGNORECASE):
        return f"{clean_rstrip} LIMIT {limit}"
    return sql


def _apply_timeout(conn, engine, timeout: int) -> None:
    """Set a statement-level timeout for the current connection if supported."""
    dialect = engine.dialect.name
    try:
        if dialect == "postgresql":
            conn.execute(text(f"SET statement_timeout = {timeout * 1000}"))
        elif dialect == "mysql":
            conn.execute(text(f"SET SESSION MAX_EXECUTION_TIME = {timeout * 1000}"))
    except SQLAlchemyError:
        # Non-fatal — timeout enforcement falls back to application-level
        query_logger.warning("Could not set DB-level statement timeout for %s", dialect)


def _dataframe_to_json_rows(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Convert a DataFrame to a list of JSON-serialisable row dicts.
    Handles NaN, NaT, Decimal, and datetime objects.
    """
    import math
    import numpy as np

    # Replace pandas NA/NaT/NaN with None
    df = df.where(pd.notnull(df), other=None)

    rows = []
    for record in df.to_dict(orient="records"):
        safe_record: Dict[str, Any] = {}
        for k, v in record.items():
            if isinstance(v, pd.Timestamp):
                safe_record[k] = v.isoformat()
            elif hasattr(v, "__class__") and v.__class__.__name__ == "Decimal":
                safe_record[k] = float(v)
            elif isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                safe_record[k] = None
            elif isinstance(v, (np.float64, np.float32)) and (np.isnan(v) or np.isinf(v)):
                safe_record[k] = None
            elif v is np.nan:
                safe_record[k] = None
            else:
                safe_record[k] = v
        rows.append(safe_record)

    return rows


