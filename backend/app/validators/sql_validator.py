"""
SQL Validator Module
====================
Validates AI-generated SQL queries before execution.
Allows only safe read-only operations (SELECT, WITH).
Blocks all dangerous DML/DDL operations.
"""

import re
import logging
from enum import Enum
from dataclasses import dataclass
from typing import Optional

import sqlparse
from sqlparse.sql import Statement
from sqlparse.tokens import Keyword, DDL, DML

logger = logging.getLogger(__name__)


class ValidationStatus(str, Enum):
    SAFE = "safe"
    BLOCKED = "blocked"


class BlockedReason(str, Enum):
    DANGEROUS_STATEMENT = "dangerous_statement_type"
    MULTIPLE_STATEMENTS = "multiple_statements_detected"
    EMPTY_QUERY = "empty_query"
    PARSE_ERROR = "parse_error"
    COMMENT_ONLY = "comment_only_query"


# ─── Allowed and blocked statement types ─────────────────────────────────────
ALLOWED_STATEMENT_TYPES = {"SELECT", "WITH", "SHOW"}

BLOCKED_STATEMENT_TYPES = {
    "DELETE",
    "DROP",
    "UPDATE",
    "INSERT",
    "ALTER",
    "TRUNCATE",
    "CREATE",
    "REPLACE",
    "MERGE",
    "CALL",
    "EXEC",
    "EXECUTE",
    "GRANT",
    "REVOKE",
    "RENAME",
    "LOCK",
    "UNLOCK",
}


@dataclass
class ValidationResult:
    """Structured result returned after SQL validation."""
    status: ValidationStatus
    statement_type: Optional[str]
    is_read_only: bool
    message: str
    blocked_reason: Optional[BlockedReason] = None
    raw_query: str = ""
    normalized_query: str = ""

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "statement_type": self.statement_type,
            "is_read_only": self.is_read_only,
            "message": self.message,
            "blocked_reason": self.blocked_reason.value if self.blocked_reason else None,
            "raw_query": self.raw_query,
            "normalized_query": self.normalized_query,
        }


class SQLValidator:
    """
    Validates AI-generated SQL queries for safety and compliance.

    Rules:
    - Only SELECT and WITH (CTE) queries are permitted.
    - Multiple statements in a single query are blocked.
    - Empty or comment-only queries are rejected.
    - All DML/DDL operations are explicitly blocked.
    """

    def __init__(self):
        self._comment_pattern = re.compile(
            r"(--[^\n]*|/\*.*?\*/)", re.DOTALL | re.IGNORECASE
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def validate(self, raw_sql: str) -> ValidationResult:
        """
        Main entry point. Validates a raw SQL string.

        Args:
            raw_sql: The AI-generated SQL query string.

        Returns:
            ValidationResult with status (safe/blocked) and metadata.
        """
        logger.info("SQL Validator: starting validation.")

        # 1. Empty check
        if not raw_sql or not raw_sql.strip():
            logger.warning("SQL Validator: empty query received.")
            return ValidationResult(
                status=ValidationStatus.BLOCKED,
                statement_type=None,
                is_read_only=False,
                message="Query is empty or blank.",
                blocked_reason=BlockedReason.EMPTY_QUERY,
                raw_query=raw_sql or "",
            )

        # 2. Strip and normalize
        normalized = self._normalize(raw_sql)

        # 3. Check for comment-only query (after normalization)
        if not normalized.strip():
            logger.warning("SQL Validator: comment-only query detected.")
            return ValidationResult(
                status=ValidationStatus.BLOCKED,
                statement_type=None,
                is_read_only=False,
                message="Query contains only comments — no executable SQL found.",
                blocked_reason=BlockedReason.COMMENT_ONLY,
                raw_query=raw_sql,
                normalized_query=normalized,
            )

        # 4. Parse statements
        try:
            statements = sqlparse.parse(normalized)
        except Exception as exc:
            logger.error("SQL Validator: parse error — %s", exc)
            return ValidationResult(
                status=ValidationStatus.BLOCKED,
                statement_type=None,
                is_read_only=False,
                message=f"Failed to parse SQL: {exc}",
                blocked_reason=BlockedReason.PARSE_ERROR,
                raw_query=raw_sql,
                normalized_query=normalized,
            )

        # 5. Block multiple statements
        executable_statements = [s for s in statements if s.get_type() or str(s).strip()]
        if len(executable_statements) > 1:
            logger.warning("SQL Validator: multiple statements detected.")
            return ValidationResult(
                status=ValidationStatus.BLOCKED,
                statement_type=None,
                is_read_only=False,
                message="Multiple SQL statements detected. Only a single statement is allowed.",
                blocked_reason=BlockedReason.MULTIPLE_STATEMENTS,
                raw_query=raw_sql,
                normalized_query=normalized,
            )

        # 6. Detect statement type
        stmt = statements[0]
        stmt_type = self._detect_statement_type(stmt, normalized)

        # 7. Check against allowed/blocked lists
        if stmt_type in BLOCKED_STATEMENT_TYPES:
            logger.warning("SQL Validator: blocked statement type — %s", stmt_type)
            return ValidationResult(
                status=ValidationStatus.BLOCKED,
                statement_type=stmt_type,
                is_read_only=False,
                message=f"Statement type '{stmt_type}' is not permitted. Only SELECT and WITH are allowed.",
                blocked_reason=BlockedReason.DANGEROUS_STATEMENT,
                raw_query=raw_sql,
                normalized_query=normalized,
            )

        if stmt_type not in ALLOWED_STATEMENT_TYPES:
            logger.warning("SQL Validator: unknown/unsupported statement type — %s", stmt_type)
            return ValidationResult(
                status=ValidationStatus.BLOCKED,
                statement_type=stmt_type,
                is_read_only=False,
                message=f"Statement type '{stmt_type}' is not recognized or allowed.",
                blocked_reason=BlockedReason.DANGEROUS_STATEMENT,
                raw_query=raw_sql,
                normalized_query=normalized,
            )

        # 8. All checks passed
        logger.info("SQL Validator: query is SAFE (type=%s).", stmt_type)
        return ValidationResult(
            status=ValidationStatus.SAFE,
            statement_type=stmt_type,
            is_read_only=True,
            message="Query passed all validation checks and is safe to execute.",
            raw_query=raw_sql,
            normalized_query=normalized,
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    def _normalize(self, sql: str) -> str:
        """Strip comments and collapse whitespace."""
        without_comments = self._comment_pattern.sub(" ", sql)
        return " ".join(without_comments.split()).strip()

    def _detect_statement_type(self, stmt: Statement, normalized_sql: str) -> str:
        """
        Detect the SQL statement type.
        Falls back to regex-based detection if sqlparse returns None.
        """
        first_word = normalized_sql.strip().split()[0].upper() if normalized_sql.strip() else ""
        if first_word == "WITH":
            return "WITH"

        stmt_type = stmt.get_type()
        if stmt_type and stmt_type.upper() != "UNKNOWN":
            return stmt_type.upper()

        # Fallback: check first significant token
        first_word = normalized_sql.strip().split()[0].upper() if normalized_sql.strip() else ""
        if first_word in ALLOWED_STATEMENT_TYPES | BLOCKED_STATEMENT_TYPES:
            return first_word

        # Deep token scan
        for token in stmt.flatten():
            if token.ttype in (DDL, DML, Keyword):
                word = token.value.upper()
                if word in ALLOWED_STATEMENT_TYPES | BLOCKED_STATEMENT_TYPES:
                    return word

        return first_word or "UNKNOWN"


# ── Module-level convenience function ─────────────────────────────────────────

def validate_sql(raw_sql: str) -> dict:
    """
    Convenience function for quick validation.

    Args:
        raw_sql: SQL string to validate.

    Returns:
        dict with validation result.
    """
    validator = SQLValidator()
    result = validator.validate(raw_sql)
    return result.to_dict()
