"""
Schema Validator Module
========================
Validates that AI-generated SQL references only tables and columns
that actually exist in the connected database schema.
Prevents hallucinated schema references from reaching the query executor.
"""

import re
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Set

from sqlalchemy import text, inspect as sa_inspect
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


@dataclass
class SchemaValidationResult:
    """Result of schema validation against the live database."""
    is_valid: bool
    missing_tables: List[str]
    missing_columns: Dict[str, List[str]]   # {table: [missing_cols]}
    invalid_references: List[str]
    validated_tables: List[str]
    validated_columns: Dict[str, List[str]]
    message: str

    def to_dict(self) -> dict:
        return {
            "is_valid": self.is_valid,
            "missing_tables": self.missing_tables,
            "missing_columns": self.missing_columns,
            "invalid_references": self.invalid_references,
            "validated_tables": self.validated_tables,
            "validated_columns": self.validated_columns,
            "message": self.message,
        }


class SchemaValidator:
    """
    Validates SQL queries against the actual database schema.

    Uses SQLAlchemy inspector to retrieve live schema metadata.
    Falls back to cached schema if database is unreachable.
    """

    def __init__(self, engine: Engine):
        self.engine = engine
        self._schema_cache: Optional[Dict[str, Set[str]]] = None  # {table: {columns}}

    # ── Public API ────────────────────────────────────────────────────────────

    def validate(self, sql: str, schema: str = None) -> SchemaValidationResult:
        """
        Validate SQL against live database schema.

        Args:
            sql:    The SQL query string.
            schema: Optional database schema name (e.g., 'public' for PostgreSQL).

        Returns:
            SchemaValidationResult with validation status.
        """
        logger.info("SchemaValidator: starting validation.")

        # Load schema metadata
        db_schema = self._load_schema(schema)
        if db_schema is None:
            logger.error("SchemaValidator: could not load database schema.")
            return SchemaValidationResult(
                is_valid=False,
                missing_tables=[],
                missing_columns={},
                invalid_references=["Could not connect to database to validate schema."],
                validated_tables=[],
                validated_columns={},
                message="Schema validation failed: unable to retrieve database schema.",
            )

        # Extract references from SQL
        referenced_tables = self._extract_tables(sql)
        referenced_columns = self._extract_columns(sql)

        missing_tables: List[str] = []
        missing_columns: Dict[str, List[str]] = {}
        invalid_references: List[str] = []
        validated_tables: List[str] = []
        validated_columns: Dict[str, List[str]] = {}

        # Validate tables
        for table in referenced_tables:
            table_lower = table.lower()
            if table_lower in db_schema:
                validated_tables.append(table)
            else:
                missing_tables.append(table)
                invalid_references.append(f"Table '{table}' does not exist in the database schema.")
                logger.warning("SchemaValidator: table '%s' not found in schema.", table)

        # Validate columns (only for tables that exist)
        for table, columns in referenced_columns.items():
            table_lower = table.lower()
            if table_lower not in db_schema:
                continue  # Already flagged as missing table

            db_columns = db_schema[table_lower]
            table_valid_cols = []
            table_missing_cols = []

            for col in columns:
                col_lower = col.lower()
                if col_lower == "*":    # wildcard allowed
                    table_valid_cols.append(col)
                elif col_lower in db_columns:
                    table_valid_cols.append(col)
                else:
                    table_missing_cols.append(col)
                    invalid_references.append(
                        f"Column '{col}' does not exist in table '{table}'."
                    )
                    logger.warning("SchemaValidator: column '%s' not in table '%s'.", col, table)

            if table_valid_cols:
                validated_columns[table] = table_valid_cols
            if table_missing_cols:
                missing_columns[table] = table_missing_cols

        is_valid = (len(missing_tables) == 0 and len(missing_columns) == 0)

        if is_valid:
            message = "Schema validation passed. All referenced tables and columns exist."
        else:
            parts = []
            if missing_tables:
                parts.append(f"Missing tables: {', '.join(missing_tables)}")
            if missing_columns:
                col_details = "; ".join(
                    f"{t}: [{', '.join(cols)}]" for t, cols in missing_columns.items()
                )
                parts.append(f"Missing columns: {col_details}")
            message = "Schema validation failed. " + " | ".join(parts)

        logger.info("SchemaValidator: is_valid=%s missing_tables=%s", is_valid, missing_tables)

        return SchemaValidationResult(
            is_valid=is_valid,
            missing_tables=missing_tables,
            missing_columns=missing_columns,
            invalid_references=invalid_references,
            validated_tables=validated_tables,
            validated_columns=validated_columns,
            message=message,
        )

    def invalidate_cache(self):
        """Force a fresh schema load on next validation."""
        self._schema_cache = None
        logger.info("SchemaValidator: schema cache invalidated.")

    # ── Private helpers ───────────────────────────────────────────────────────

    def _load_schema(self, schema: str = None) -> Optional[Dict[str, Set[str]]]:
        """Load table→columns mapping from the live database."""
        if self._schema_cache is not None:
            return self._schema_cache

        try:
            inspector = sa_inspect(self.engine)
            table_names = inspector.get_table_names(schema=schema)
            db_schema: Dict[str, Set[str]] = {}

            for table in table_names:
                cols = inspector.get_columns(table, schema=schema)
                db_schema[table.lower()] = {c["name"].lower() for c in cols}

            self._schema_cache = db_schema
            logger.info("SchemaValidator: loaded %d tables from schema.", len(db_schema))
            return db_schema

        except Exception as exc:
            logger.error("SchemaValidator: failed to load schema — %s", exc)
            return None

    def _extract_tables(self, sql: str) -> List[str]:
        """
        Extract table names referenced in the SQL query using regex heuristics.
        Handles: FROM table, JOIN table, INTO table, UPDATE table patterns.
        """
        patterns = [
            r"\bFROM\s+([`\"\[]?[\w]+[`\"\]]?(?:\s*,\s*[`\"\[]?[\w]+[`\"\]]?)*)",
            r"\b(?:INNER\s+|LEFT\s+|RIGHT\s+|FULL\s+OUTER\s+|CROSS\s+)?JOIN\s+([`\"\[]?[\w]+[`\"\]]?)",
            r"\bJOIN\s+([`\"\[]?[\w]+[`\"\]]?)",
            r"\bUPDATE\s+([`\"\[]?[\w]+[`\"\]]?)",
            r"\bINTO\s+([`\"\[]?[\w]+[`\"\]]?)",
        ]

        tables: Set[str] = set()
        for pattern in patterns:
            matches = re.findall(pattern, sql, re.IGNORECASE)
            for match in matches:
                # Handle comma-separated table lists
                for table in match.split(","):
                    cleaned = re.sub(r"[`\"\[\]\s]", "", table).strip()
                    # Remove alias (e.g., "orders o" → "orders")
                    parts = cleaned.split()
                    if parts:
                        # Filter out SQL keywords that aren't table names
                        table_name = parts[0].strip()
                        if table_name and not self._is_sql_keyword(table_name):
                            tables.add(table_name)

        # Remove subquery aliases (names that appear after parentheses)
        subquery_aliases = re.findall(r"\)\s+(?:AS\s+)?(\w+)", sql, re.IGNORECASE)
        tables -= set(subquery_aliases)

        return list(tables)

    def _extract_columns(self, sql: str) -> Dict[str, List[str]]:
        """
        Attempt to extract table.column references.
        Returns a dict of {table: [columns]}.
        """
        result: Dict[str, List[str]] = {}

        # Match "table.column" patterns
        dot_refs = re.findall(r"\b([\w]+)\.([\w\*]+)\b", sql)
        for table, column in dot_refs:
            if not self._is_sql_keyword(table):
                result.setdefault(table, []).append(column)

        return result

    def _is_sql_keyword(self, word: str) -> bool:
        """Check if a word is a common SQL keyword (not a table name)."""
        SQL_KEYWORDS = {
            "select", "from", "where", "join", "inner", "outer", "left", "right",
            "full", "cross", "on", "as", "and", "or", "not", "in", "is", "null",
            "like", "between", "exists", "all", "any", "union", "intersect",
            "except", "group", "by", "having", "order", "limit", "offset",
            "with", "case", "when", "then", "else", "end", "distinct", "top",
            "insert", "update", "delete", "into", "values", "set", "create",
            "drop", "alter", "table", "index", "view", "database", "schema",
        }
        return word.lower() in SQL_KEYWORDS
