"""
Column Validator — DataPilot AI Backend

Post-processes generated SQL by:
1. Extracting all identifiers (potential column/table names)
2. Fuzzy-matching them against the real schema column names
3. Auto-replacing wrong column names with the closest valid match

This runs AFTER the LLM generates SQL, as a safety net to catch hallucinated
or misspelled column names before the query hits the database.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Token exclusion: SQL keywords we should never try to match against columns
# ─────────────────────────────────────────────────────────────────────────────
_SQL_RESERVED = frozenset({
    "SELECT", "FROM", "WHERE", "AND", "OR", "NOT", "IN", "IS", "NULL",
    "JOIN", "LEFT", "RIGHT", "INNER", "OUTER", "FULL", "CROSS", "ON",
    "GROUP", "BY", "ORDER", "HAVING", "LIMIT", "OFFSET", "AS", "DISTINCT",
    "UNION", "ALL", "EXCEPT", "INTERSECT", "CASE", "WHEN", "THEN", "ELSE",
    "END", "BETWEEN", "LIKE", "ILIKE", "EXISTS", "WITH", "RECURSIVE",
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TABLE",
    "INDEX", "VIEW", "TRIGGER", "PROCEDURE", "FUNCTION", "DATABASE",
    "SCHEMA", "PRIMARY", "KEY", "FOREIGN", "REFERENCES", "UNIQUE",
    "CHECK", "DEFAULT", "AUTO_INCREMENT", "SERIAL", "NOT", "NULL",
    "COUNT", "SUM", "AVG", "MAX", "MIN", "COALESCE", "IFNULL", "IF",
    "CONCAT", "SUBSTRING", "TRIM", "UPPER", "LOWER", "ROUND", "FLOOR",
    "CEIL", "ABS", "NOW", "CURDATE", "DATE", "YEAR", "MONTH", "DAY",
    "DATE_FORMAT", "DATE_TRUNC", "TO_CHAR", "EXTRACT", "INTERVAL",
    "CAST", "CONVERT", "TRUE", "FALSE", "ASC", "DESC", "ROW_NUMBER",
    "RANK", "DENSE_RANK", "OVER", "PARTITION", "ROWS", "RANGE",
    "UNBOUNDED", "PRECEDING", "FOLLOWING", "CURRENT", "ROW",
    # Common aliases
    "T1", "T2", "T3", "T4", "T5", "A", "B", "C", "D", "E",
})

# Identifier pattern (SQL identifiers, optionally backtick or double-quoted)
_IDENT_RE = re.compile(
    r"(?:`([^`]+)`|\"([^\"]+)\"|(?<!['\"])\\b([a-zA-Z_][a-zA-Z0-9_]*)\\b(?!['\"]))"
)


class ColumnValidator:
    """
    Validates and auto-corrects column names in LLM-generated SQL.

    Usage
    -----
    validator = ColumnValidator(schema)
    corrected_sql, corrections = validator.validate_and_fix(generated_sql)
    """

    def __init__(self, schema: Dict[str, Any]) -> None:
        # Build flat lookup: column_name_lower → (table_name, exact_column_name)
        self._col_map: Dict[str, Tuple[str, str]] = {}
        # Also keep table names
        self._table_names: Dict[str, str] = {}  # lower → exact

        for table in schema.get("tables", []):
            t_name: str = table.get("name", "")
            self._table_names[t_name.lower()] = t_name
            for col in table.get("columns", []):
                c_name: str = col.get("name", "")
                self._col_map[c_name.lower()] = (t_name, c_name)

        logger.info(
            "ColumnValidator initialised — %d tables, %d columns",
            len(self._table_names),
            len(self._col_map),
        )

    # ─────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────

    def validate_and_fix(self, sql: str) -> Tuple[str, List[Dict[str, str]]]:
        """
        Scan *sql* for identifier tokens, fuzzy-match against real schema,
        replace wrong column names with correct ones.

        Returns
        -------
        (corrected_sql, corrections)
            corrections is a list of {wrong, correct, confidence} dicts.
        """
        if not sql or not self._col_map:
            return sql, []

        corrections: List[Dict[str, str]] = []
        result_sql = sql

        # Extract all candidate identifiers from the SQL
        candidates = self._extract_identifiers(sql)

        for token, is_quoted in candidates:
            token_lower = token.lower()

            # Skip SQL reserved words and known-good names
            if token_lower in {k.lower() for k in _SQL_RESERVED}:
                continue
            if token_lower in self._col_map:
                continue  # exact match — already correct
            if token_lower in self._table_names:
                continue  # it's a table name — correct

            # Try fuzzy match against column names
            match, score = self._fuzzy_best_match(token_lower, self._col_map)

            if match and score >= 0.85:
                _, exact_col = self._col_map[match]
                if exact_col.lower() != token_lower:
                    corrections.append({
                        "wrong": token,
                        "correct": exact_col,
                        "confidence": f"{score:.0%}",
                    })
                    # Replace token in SQL (careful: whole-word, case-insensitive)
                    result_sql = re.sub(
                        rf"(?<![`\"\w]){re.escape(token)}(?![`\"\w])",
                        exact_col,
                        result_sql,
                        flags=re.IGNORECASE,
                    )

        if corrections:
            logger.info(
                "ColumnValidator: %d correction(s) applied: %s",
                len(corrections),
                corrections,
            )

        return result_sql, corrections

    def get_column_manifest(self) -> str:
        """
        Return a concise, newline-separated column inventory string for LLM injection.

        Format::
            TABLE.column_name (type)
        """
        lines = []
        seen_tables: Dict[str, List[str]] = {}
        for col_lower, (t_name, c_name) in self._col_map.items():
            seen_tables.setdefault(t_name, []).append(c_name)
        for t_name, cols in sorted(seen_tables.items()):
            cols_str = ", ".join(sorted(cols))
            lines.append(f"  {t_name}: {cols_str}")
        return "\n".join(lines)

    def fuzzy_correct_user_query(self, user_query: str) -> Tuple[str, List[Dict]]:
        """
        Correct user-typed/spoken column/table references in the natural-language
        query before sending it to the LLM.

        Returns (corrected_query, corrections_list).
        """
        if not user_query:
            return user_query, []

        words = user_query.split()
        corrected_words = []
        corrections = []

        for word in words:
            clean = re.sub(r"[^a-zA-Z0-9_]", "", word).lower()
            if len(clean) < 3:
                corrected_words.append(word)
                continue
            if clean in self._col_map or clean in self._table_names:
                corrected_words.append(word)
                continue
            if clean in {k.lower() for k in _SQL_RESERVED}:
                corrected_words.append(word)
                continue

            # Try schema match
            all_tokens = {**self._col_map, **{k: (k, v) for k, v in self._table_names.items()}}
            match, score = self._fuzzy_best_match(clean, all_tokens)

            if match and score >= 0.85:
                _, exact = all_tokens[match]
                if exact.lower() != clean:
                    corrections.append({"wrong": word, "correct": exact, "confidence": f"{score:.0%}"})
                    corrected_words.append(exact)
                    continue

            corrected_words.append(word)

        return " ".join(corrected_words), corrections

    # ─────────────────────────────────────────────────────────────────────
    # Private helpers
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    def _extract_identifiers(sql: str) -> List[Tuple[str, bool]]:
        """Extract (token, is_quoted) pairs from SQL text."""
        results = []
        # Quoted identifiers first (backtick or double-quote)
        for m in re.finditer(r"`([^`]+)`|\"([^\"]+)\"", sql):
            token = m.group(1) or m.group(2)
            results.append((token, True))
        # Unquoted bare identifiers
        clean = re.sub(r"`[^`]+`|\"[^\"]+\"|'[^']*'", " ", sql)
        for m in re.finditer(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b", clean):
            token = m.group(1)
            if token.upper() not in _SQL_RESERVED:
                results.append((token, False))
        return results

    @staticmethod
    def _bigrams(s: str) -> set:
        return set(s[i:i+2] for i in range(len(s) - 1))

    @classmethod
    def _fuzzy_score(cls, a: str, b: str) -> float:
        """Bigram-overlap Dice coefficient."""
        if a == b:
            return 1.0
        if not a or not b:
            return 0.0
        bg_a = cls._bigrams(a)
        bg_b = cls._bigrams(b)
        if not bg_a or not bg_b:
            return 0.0
        overlap = len(bg_a & bg_b)
        return (2.0 * overlap) / (len(bg_a) + len(bg_b))

    @classmethod
    def _fuzzy_best_match(
        cls, token: str, candidates: Dict[str, Any]
    ) -> Tuple[Optional[str], float]:
        """Return (best_key, best_score) from candidates dict."""
        best_key: Optional[str] = None
        best_score = 0.0
        for cand in candidates:
            s = cls._fuzzy_score(token, cand)
            if s > best_score:
                best_score = s
                best_key = cand
        return best_key, best_score
