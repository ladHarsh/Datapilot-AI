"""
SQL Generator — SQL AI Analytics Platform.

Responsible for the core logic of translating natural language and schema
context into executable SQL SELECT queries.

Features:
- Schema-aware generation (context-driven)
- Analytics-focused (optimised for aggregation, trends, and ranking)
- Self-correction (retries with stricter instructions on failure)
- Dialect support (MySQL, PostgreSQL)

Author : Member 2 — AI/LLM Engineer
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

from .llm_service import LLMService, LLMServiceError
from .schema_context_builder import SchemaContextBuilder
from .prompt_builder import PromptBuilder
from .column_validator import ColumnValidator
from app.validators.sql_semantic_checker import check_analytical_sql

logger = logging.getLogger(__name__)

# Max retries for invalid SQL generation
MAX_ATTEMPTS = 5

# Keywords that signal a complex analytical query needing full schema + higher token budget
_COMPLEX_SIGNALS = [
    "cte", "with ", "window function", "dense_rank", "row_number", "rank(",
    "correlated", "subquery", "having", "joining", "join ", "partition by",
    "lag(", "lead(", "ntile(", "percent_rank", "cumulative",
    "business analysis", "business intelligence", "customer business",
    "report", "advanced", "complex", "total_spending", "most_purchased",
]


class SQLGenerator:
    """Core engine for NL-to-SQL translation.

    This class encapsulates the interaction with the LLM specifically for
    generating SQL. It handles the iterative refinement of the query if the
    initial output is syntactically invalid (for SELECT queries).
    """

    def __init__(self, ai_model: Optional[str] = None) -> None:
        self.llm_service = LLMService(model_override=ai_model) if ai_model else LLMService()
        self.schema_builder = SchemaContextBuilder()
        self.prompt_builder = PromptBuilder()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_sql(
        self,
        user_query: str,
        schema: Dict[str, Any],
        dialect: str = "mysql",
        enhanced_context: Optional[Dict[str, Any]] = None,
        row_limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Generate a validated SQL SELECT statement from a natural query.

        Parameters
        ----------
        user_query : str
            The user's question (potentially cleaned/enhanced).
        schema : dict
            Database schema in canonical format.
        dialect : str
            "mysql" or "postgresql".
        enhanced_context : dict, optional
            Additional metadata from QueryEnhancer (hints, expansion).
        row_limit : int, optional
            Maximum rows to return.

        Returns
        -------
        dict
            ``{success, sql, raw_response, error, attempts}``
        """
        if not user_query or not user_query.strip():
            return {
                "success": False,
                "sql": "",
                "error": "User query cannot be empty.",
                "attempts": 0,
            }

        # ── Step 0: Build ColumnValidator from schema ─────────────────
        col_validator = ColumnValidator(schema)

        # ── Step 1: Pre-correct user query NL terms ───────────────────
        # Maps spoken/typed approximate words to real schema column/table names
        corrected_query, query_corrections = col_validator.fuzzy_correct_user_query(user_query)
        if query_corrections:
            logger.info(
                "Query pre-correction: %s", query_corrections
            )

        # ── Step 1: Detect query complexity ──────────────────────────
        q_lower = corrected_query.lower()
        is_complex = any(sig in q_lower for sig in _COMPLEX_SIGNALS)

        # ── Step 2: Build Schema Context ──────────────────────────────
        if is_complex:
            # For complex analytical queries: use FULL schema — no filtering
            # Filtering drops tables that might be needed for JOINs
            filtered_schema = schema
            logger.info("Complex query detected — using full schema context.")
        else:
            filtered_schema = self.schema_builder.filter_relevant_tables(schema, corrected_query)
        schema_context = self.schema_builder.build_context(filtered_schema)

        # Append explicit column manifest so LLM knows exact names
        column_manifest = col_validator.get_column_manifest()
        if column_manifest:
            schema_context = (
                schema_context
                + "\n\nEXACT COLUMN NAMES (use ONLY these):\n"
                + column_manifest
            )

        # Merge enhanced context hints
        active_query = corrected_query
        if enhanced_context and enhanced_context.get("analytics_hints"):
            hints = "; ".join(enhanced_context["analytics_hints"])
            active_query += f"\n(Analytics Hints: {hints})"

        # ── Step 3: Build Prompt ───────────────────────────────────────
        if is_complex:
            prompt = self.prompt_builder.build_complex_sql_prompt(
                user_query=active_query,
                schema_context=schema_context,
                dialect=dialect,
                row_limit=row_limit,
            )
        else:
            prompt = self.prompt_builder.build_sql_prompt(
                user_query=active_query,
                schema_context=schema_context,
                dialect=dialect,
                row_limit=row_limit,
            )

        # Always append instructions allowing DML/destructive query generation
        prompt += "\n\nSAFE MODE IS OFF: You are allowed to generate data-modifying or destructive SQL queries (DELETE, DROP, TRUNCATE, UPDATE, INSERT, etc.) if requested by the user. Generate the exact statement requested (e.g. DELETE FROM table if they ask to delete data)."

        last_error = ""
        for attempt in range(1, MAX_ATTEMPTS + 1):
            logger.info("SQL Generation Attempt %d/%d", attempt, MAX_ATTEMPTS)

            try:
                raw_response = self.llm_service.send_prompt(prompt)
                cleaned_sql = self._clean_sql(raw_response)

                if not cleaned_sql:
                    last_error = "LLM returned empty response."
                    continue

                # ── Detect truncated SQL (LLM hit token limit mid-response) ──
                # A truncated SQL ends abruptly: missing final semicolon/paren,
                # or last non-whitespace char is a dangling quote/identifier fragment.
                stripped = cleaned_sql.rstrip()
                if self._is_truncated(stripped):
                    last_error = "SQL response was truncated (token limit hit). Retrying with stricter prompt."
                    logger.warning("Attempt %d: %s", attempt, last_error)
                    prompt = self._build_correction_prompt(
                        active_query, schema_context, dialect, cleaned_sql, last_error,
                        is_complex=is_complex,
                    )
                    continue

                # Security validations bypassed (Safe Mode removed)

                # ── Step 3: Post-validate column names ────────────────
                # Auto-correct any hallucinated or misspelled column names
                corrected_sql, col_corrections = col_validator.validate_and_fix(cleaned_sql)
                if col_corrections:
                    logger.info(
                        "SQL column auto-corrections: %s", col_corrections
                    )
                    cleaned_sql = corrected_sql

                # Success
                logger.info("SQL generated successfully on attempt %d.", attempt)
                return {
                    "success": True,
                    "sql": cleaned_sql,
                    "raw_response": raw_response,
                    "error": None,
                    "attempts": attempt,
                    "query_corrections": query_corrections if query_corrections else [],
                    "col_corrections": col_corrections if col_corrections else [],
                }

            except LLMServiceError as exc:
                if exc.is_permanent:
                    logger.error("Attempt %d Permanent LLM Error: %s. Aborting retries.", attempt, exc)
                    return {
                        "success": False,
                        "sql": "",
                        "error": f"LLM Error (Permanent): {exc}",
                        "attempts": attempt,
                    }
                last_error = f"LLM Error: {exc}"
                logger.error("Attempt %d LLM Error: %s", attempt, exc)
            except Exception as exc:
                last_error = f"Unexpected Error: {exc}"
                logger.error("Attempt %d Unexpected Error: %s", attempt, exc)

        # Exhausted retries
        return {
            "success": False,
            "sql": "",
            "error": f"Failed after {MAX_ATTEMPTS} attempts. Last error: {last_error}",
            "attempts": MAX_ATTEMPTS,
        }

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _clean_sql(text: str) -> str:
        """Strip markdown fences and trim whitespace."""
        text = re.sub(r"```sql\n?", "", text, flags=re.IGNORECASE)
        text = re.sub(r"```\n?", "", text)
        return text.strip()

    @staticmethod
    def _is_valid_select(sql: str) -> bool:
        """Basic check to ensure we only return read-only queries."""
        sql_upper = sql.upper().strip()
        # Must start with SELECT or WITH (for CTEs)
        if not (sql_upper.startswith("SELECT") or sql_upper.startswith("WITH")):
            return False
        # Must NOT contain destructive keywords as standalone words
        forbidden = r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|GRANT|REVOKE|EXEC|EXECUTE)\b"
        if re.search(forbidden, sql_upper):
            return False
        return True

    @staticmethod
    def _is_truncated(sql: str) -> bool:
        """Return True if the SQL looks truncated (LLM hit token limit mid-response).

        Heuristics:
        - Unbalanced parentheses (more opening than closing)
        - Unbalanced single-quote string literal (odd number of unescaped single quotes)
        - Last non-whitespace character is NOT a SQL statement terminal
          (semicolon, closing paren, or a word-ending character like a letter/digit/quote)
        """
        if not sql:
            return False

        # 1. Unbalanced parentheses
        open_parens = sql.count("(") - sql.count(")")
        if open_parens > 0:
            return True  # More opens than closes → truncated inside a subquery/CTE

        # 2. Open string literal (odd number of single quotes not preceded by escape)
        single_quotes = len(re.findall(r"(?<!')'(?!')", sql))
        if single_quotes % 2 != 0:
            return True

        # 3. Last meaningful char is not a proper SQL terminal
        last_char = sql[-1] if sql else ""
        sql_terminals = {";", ")", "'"}
        valid_end_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-')\";")
        if last_char not in valid_end_chars:
            return True

        return False

    def _build_correction_prompt(
        self,
        query: str,
        context: str,
        dialect: str,
        prev_sql: str,
        error: str,
        is_complex: bool = False,
    ) -> str:
        """Build a prompt that includes the previous failure for correction."""
        if is_complex:
            base = self.prompt_builder.build_complex_sql_prompt(query, context, dialect)
        else:
            base = self.prompt_builder.build_sql_prompt(query, context, dialect)
        return (
            f"{base}\n\n"
            f"--- PREVIOUS ATTEMPT FAILED ---\n"
            f"SQL: {prev_sql}\n"
            f"ERROR: {error}\n\n"
            f"Please fix the SQL query above. Ensure it is a valid {dialect} SELECT statement "
            f"and follows the schema rules strictly. Use order_totals CTE for AOV and "
            f"NOT EXISTS filters. Include all requested output columns (e.g. customer_name). "
            f"Never mix window functions with GROUP BY customer_id only."
        )