"""
hallucination_checker.py — SQL AI Analytics Platform.

Detects schema hallucinations in generated SQL queries.

A "hallucination" in Text-to-SQL occurs when the LLM references:
- Tables that do not exist in the connected database schema.
- Columns that do not exist on those tables.
- Joins between non-existent foreign key relationships.

This is critical for production — a hallucinated SQL query will fail
at runtime and erodes user trust.

Author : Member 2 — AI/LLM Engineer
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Set

from ..utils.sql_cleaner import extract_table_names, extract_column_names
from ..utils.schema_formatter import to_table_list, to_column_map

logger = logging.getLogger(__name__)


class HallucinationChecker:
    """Detect schema hallucinations in LLM-generated SQL.

    Usage::

        checker = HallucinationChecker()
        result = checker.check(sql="SELECT * FROM ghosts", schema=my_schema)
        # result["hallucinations"] → ["Table 'ghosts' not in schema"]
        # result["clean"] → False
    """

    def check(
        self,
        sql: str,
        schema: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Run full hallucination detection on a generated SQL query.

        Parameters
        ----------
        sql : str
            The generated SQL query.
        schema : dict
            The database schema dictionary.

        Returns
        -------
        dict
            ``{clean, hallucinations, hallucinated_tables, hallucinated_columns,
               severity}``
            where *severity* is "none" | "low" | "high".
        """
        hallucinations: List[str] = []
        hallucinated_tables: List[str] = []
        hallucinated_columns: List[str] = []

        schema_tables = {t.lower() for t in to_table_list(schema)}
        col_map = {t.lower(): {c.lower() for c in cols}
                   for t, cols in to_column_map(schema).items()}

        # ── 1. Table Hallucination ─────────────────────────────────
        sql_tables = extract_table_names(sql)
        for tbl in sql_tables:
            if tbl and tbl not in schema_tables:
                msg = f"Table '{tbl}' does not exist in the schema."
                hallucinations.append(msg)
                hallucinated_tables.append(tbl)
                logger.warning("[Hallucination] %s", msg)

        # ── 2. Column Hallucination ────────────────────────────────
        sql_cols = extract_column_names(sql)
        # Build union of all valid columns across used tables
        valid_cols: Set[str] = set()
        for tbl in sql_tables:
            if tbl in col_map:
                valid_cols.update(col_map[tbl])
        # Also add SQL functions and wildcards as valid
        sql_builtins = {"*", "count", "sum", "avg", "min", "max", "distinct",
                        "coalesce", "ifnull", "nullif", "now", "date", "year",
                        "month", "day", "concat", "length", "upper", "lower"}

        for col in sql_cols:
            if col in sql_builtins or col.isdigit():
                continue
            if valid_cols and col not in valid_cols:
                msg = f"Column '{col}' not found in schema tables used."
                hallucinations.append(msg)
                hallucinated_columns.append(col)
                logger.warning("[Hallucination] %s", msg)

        # ── 3. Determine Severity ──────────────────────────────────
        if not hallucinations:
            severity = "none"
        elif hallucinated_tables:
            severity = "high"   # table-level hallucinations are critical
        else:
            severity = "low"    # column-level may be aliases or functions

        return {
            "clean":                 len(hallucinations) == 0,
            "hallucinations":        hallucinations,
            "hallucinated_tables":   hallucinated_tables,
            "hallucinated_columns":  hallucinated_columns,
            "severity":              severity,
        }
