"""
sql_cleaner.py — SQL AI Analytics Platform.

Centralizes all SQL string cleaning logic so it is not duplicated
across sql_generator, query_agent, or any agent/service.

Author : Member 2 — AI/LLM Engineer
"""

from __future__ import annotations

import re
from typing import Optional

from .ai_constants import SQL_FENCE_PATTERNS, DESTRUCTIVE_KEYWORDS


def strip_markdown(sql: str) -> str:
    """Remove markdown code fences and leading/trailing whitespace.

    Handles: ```sql ... ```, ```SQL ... ```, ~~~ ... ~~~
    """
    for fence in SQL_FENCE_PATTERNS:
        sql = sql.replace(fence, "")
    return sql.strip()


def normalize_whitespace(sql: str) -> str:
    """Collapse multiple spaces/newlines into single spaces."""
    return re.sub(r"\s+", " ", sql).strip()


def is_select_only(sql: str) -> bool:
    """Return True if sql is a read-only SELECT or CTE (WITH ... SELECT).

    Rejects anything that contains a destructive keyword at word boundaries.
    """
    sql_upper = sql.upper().strip()

    # Must begin with SELECT or WITH (CTE)
    if not (sql_upper.startswith("SELECT") or sql_upper.startswith("WITH")):
        return False

    # Must not contain destructive operations
    for kw in DESTRUCTIVE_KEYWORDS:
        if re.search(rf"\b{kw}\b", sql_upper):
            return False

    return True


def enforce_limit(sql: str, max_rows: int = 1000) -> str:
    """Append a LIMIT clause if the query has none.

    Prevents accidental full-table scans in interactive sessions.
    """
    if "LIMIT" not in sql.upper():
        return f"{sql.rstrip().rstrip(';')} LIMIT {max_rows}"
    return sql


def clean_sql(raw: str, enforce_row_limit: bool = False, max_rows: int = 1000) -> str:
    """Full cleaning pipeline for LLM SQL output.

    Steps:
    1. Strip markdown fences.
    2. Normalize whitespace.
    3. Optionally enforce LIMIT.
    """
    sql = strip_markdown(raw)
    sql = normalize_whitespace(sql)
    if enforce_row_limit:
        sql = enforce_limit(sql, max_rows)
    return sql


def extract_table_names(sql: str) -> list[str]:
    """Extract table names mentioned after FROM and JOIN keywords."""
    pattern = r"\b(?:FROM|JOIN)\s+([`\"\[]?[\w]+[`\"\]]?)"
    matches = re.findall(pattern, sql, re.IGNORECASE)
    # Strip any quoting characters
    return [re.sub(r"[`\"\[\]]", "", m).lower() for m in matches]


def extract_column_names(sql: str) -> list[str]:
    """Extract column names from a SELECT clause (best-effort)."""
    # Match content between SELECT and FROM
    match = re.search(r"SELECT\s+(.*?)\s+FROM", sql, re.IGNORECASE | re.DOTALL)
    if not match:
        return []
    select_clause = match.group(1)
    # Split by comma, strip aliases and function wrappers
    raw_cols = [c.strip() for c in select_clause.split(",")]
    cols: list[str] = []
    for col in raw_cols:
        # Take the last word (after alias 'AS'), strip table prefix
        col = re.split(r"\bAS\b", col, flags=re.IGNORECASE)[-1].strip()
        col = col.split(".")[-1].strip()
        col = re.sub(r"[^a-zA-Z0-9_*]", "", col)
        if col:
            cols.append(col.lower())
    return cols
