"""
Prompt Builder — AI-powered SQL Database Analysis Tool.

Constructs structured, task-specific prompts for different AI operations
(SQL generation, explanation, optimization, chart recommendation) by
loading templates from ``backend/app/prompts/`` and injecting runtime
context.

ARCHITECTURE NOTE (2026-05-27):
  SQL generation uses a single unified prompt (sql_prompt.txt) that
  self-classifies each query into SIMPLE, MEDIUM, or ANALYTICAL tier
  before writing any SQL. build_complex_sql_prompt() is kept for
  backward compatibility but delegates to build_sql_prompt().

  Fallback chain (if sql_prompt.txt is missing):
    sql_prompt.txt  →  _FALLBACK_SQL_GENERATION  (hardcoded)

Author : Member 2 — AI/LLM Engineer
Created: 2026-05-12
Updated: 2026-05-27 — Unified sql_prompt.txt replacing simple/complex split
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

_PROMPTS_DIR: Path = Path(__file__).resolve().parents[2] / "prompts"

# ═══════════════════════════════════════════════════════════════════════════
# Dialect instruction blocks — single source of truth, referenced by both
# simple and complex prompt builders.
# ═══════════════════════════════════════════════════════════════════════════
_DIALECT_INSTRUCTIONS: dict[str, str] = {
    "mysql": (
        "MySQL syntax rules:\n"
        "- Pagination: LIMIT n\n"
        "- Null coalescing: IFNULL(col, default)\n"
        "- Date formatting: DATE_FORMAT(col, '%Y-%m')\n"
        "- Reserved word escaping: backticks (`col`)\n"
        "- String concatenation: CONCAT(a, b)"
    ),
    "postgresql": (
        "PostgreSQL syntax rules:\n"
        "- Pagination: LIMIT n  or  FETCH FIRST n ROWS ONLY\n"
        "- Null coalescing: COALESCE(col, default)\n"
        "- Date formatting: TO_CHAR(col, 'YYYY-MM')\n"
        "- Reserved word escaping: double-quotes (\"col\")\n"
        "- String concatenation: a || b"
    ),
}

# ═══════════════════════════════════════════════════════════════════════════
# Fallback template — SIMPLE / MEDIUM queries
#
# Design intent:
#   - Covers SELECT, basic JOINs, GROUP BY, ORDER BY, simple subqueries.
#   - Does NOT mention CTEs, window functions, or correlated subqueries.
#     Those belong exclusively in the complex prompt.
#   - Rules are short and positive ("do X") rather than long prohibition
#     lists that the model pattern-matches without reasoning.
# ═══════════════════════════════════════════════════════════════════════════
_FALLBACK_SQL_GENERATION = """\
You are an expert SQL analyst. Translate the user's question into a single \
{dialect} SELECT statement.

HARD CONSTRAINTS
1. Use ONLY tables and columns listed in DATABASE SCHEMA. Never invent names.
2. If a user column does not exist, pick the closest real column semantically; \
   if none fits, omit it.
3. Return the raw SQL only — no markdown fences, no explanation, no preamble.
4. Default LIMIT {row_limit} unless the user specifies otherwise.

QUERY RULES
- Always alias tables (e.g. FROM orders o).
- JOIN on declared foreign keys. Default to INNER JOIN.
- Use WHERE for row filters, HAVING for aggregate filters.
- Use GROUP BY with every aggregate (COUNT, SUM, AVG, MAX, MIN).
- Add ORDER BY when ranking or sorting is implied.

NLP TOLERANCE
- Correct spelling errors by matching intent to the nearest real column/table.
- Interpret business slang: MTD = month-to-date, YTD = year-to-date, \
  LTV = lifetime value.
- Understand voice-typed fragments ("montly revenut") as natural language.

{dialect_instructions}

DATABASE SCHEMA
{schema_context}

EXAMPLES

Q: How many orders per customer?
A: SELECT c.customer_id, c.customer_name, COUNT(o.order_id) AS order_count
   FROM customers c
   JOIN orders o ON c.customer_id = o.customer_id
   GROUP BY c.customer_id, c.customer_name
   ORDER BY order_count DESC
   LIMIT {row_limit};

Q: Top 5 products by revenue last month
A: SELECT p.product_name, SUM(oi.quantity * oi.price) AS total_revenue
   FROM products p
   JOIN order_items oi ON p.product_id = oi.product_id
   JOIN orders o ON oi.order_id = o.order_id
   WHERE o.created_at >= DATE_SUB(NOW(), INTERVAL 1 MONTH)
   GROUP BY p.product_id, p.product_name
   ORDER BY total_revenue DESC
   LIMIT 5;

Q: Customers who never ordered
A: SELECT c.customer_id, c.customer_name
   FROM customers c
   LEFT JOIN orders o ON c.customer_id = o.customer_id
   WHERE o.order_id IS NULL
   LIMIT {row_limit};

USER QUESTION
{user_query}

SQL:
"""

# ═══════════════════════════════════════════════════════════════════════════
# Fallback template — used only when sql_prompt.txt is missing from disk.
# The full production version lives in app/prompts/sql_prompt.txt.
# ═══════════════════════════════════════════════════════════════════════════
_FALLBACK_SQL_GENERATION = """\
You are a senior SQL analyst. Translate the user question into a single \
correct, efficient {dialect} SELECT statement.

STEP 1 — Classify the query as SIMPLE, MEDIUM, or ANALYTICAL (silent).
STEP 2 — Use the SIMPLEST tier that fully answers the question.
STEP 3 — For ANALYTICAL queries use CTEs and window functions; \
          for SIMPLE/MEDIUM avoid unnecessary CTEs.

HARD CONSTRAINTS
1. Use ONLY tables and columns in DATABASE SCHEMA. Never invent names.
2. Derive missing display columns: CONCAT('Customer ', id) for MySQL, \
   'Customer ' || id for SQLite/PostgreSQL.
3. Return raw SQL only — no markdown fences, no explanation.
4. Default LIMIT {row_limit} unless specified.
5. Two-step AOV: SUM per order_id first, then AVG per customer_id.
6. Most-purchased category: SUM qty → ROW_NUMBER → filter rn = 1.
7. No LIMIT inside EXISTS. No HAVING MIN >= AVG.
8. Every derived table must have an alias (MySQL requirement).
9. Alias scope: only use aliases defined in the current SELECT block.

{dialect_instructions}

DATABASE SCHEMA
{schema_context}

USER QUESTION
{user_query}

SQL:
"""

# ─── Other fallback templates (unchanged from original) ───────────────────

_FALLBACK_EXPLANATION = """\
You are a helpful SQL tutor. Explain the following SQL query in clear, \
simple English.

RULES:
- Break the explanation into numbered steps.
- Keep the explanation concise — no more than 8 sentences.
- Do NOT rewrite the SQL query.

USER'S ORIGINAL QUESTION:
{user_query}

SQL QUERY TO EXPLAIN:
{sql_query}

EXPLANATION:
"""

_FALLBACK_OPTIMIZATION = """\
You are a senior database performance engineer. Analyse the SQL query \
below and suggest concrete optimizations.

RULES:
- Suggest index creation if beneficial.
- Rate the query: GOOD, ACCEPTABLE, or NEEDS IMPROVEMENT.
- Return plain text, no markdown fences.

DATABASE SCHEMA:
{schema_context}

SQL QUERY TO OPTIMIZE:
{sql_query}

OPTIMIZATION SUGGESTIONS:
"""

_FALLBACK_CHART = """\
You are a data visualization expert. Recommend the single best chart type.

ALLOWED CHART TYPES (return exactly one):
- bar_chart
- line_chart
- pie_chart
- scatter_plot
- table_only

Return ONLY the chart type on the first line, followed by a one-sentence \
justification on the second line.

SQL QUERY:
{sql_query}

USER'S ORIGINAL QUESTION:
{user_query}

RESULT COLUMNS:
{result_columns}

RECOMMENDED CHART:
"""


class PromptBuilder:
    """Builds structured, task-specific prompts by loading templates and
    injecting runtime context (schema, user query, SQL, etc.).

    Template hierarchy
    ------------------
    1. ``prompts/sql_prompt.txt``         — simple/medium SQL generation
    2. ``prompts/complex_sql_prompt.txt`` — analytical SQL generation
    3. Hardcoded fallbacks in this module — used only when files are missing

    The simple and complex prompts are intentionally disjoint: the complex
    prompt does not repeat rules from the simple prompt.  Each file has one
    responsibility.

    Parameters
    ----------
    prompts_dir : Path or str, optional
        Override the default prompts directory.  Useful for testing.
    """

    def __init__(self, prompts_dir: Optional[Path] = None) -> None:
        self._prompts_dir: Path = Path(prompts_dir) if prompts_dir else _PROMPTS_DIR
        logger.info("PromptBuilder initialised — templates dir: %s", self._prompts_dir)

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def build_sql_prompt(
        self,
        user_query: str,
        schema_context: str,
        dialect: str = "mysql",
        row_limit: Optional[int] = None,
    ) -> str:
        """Build a SQL generation prompt for any query tier.

        Loads ``master_sql_prompt.txt`` which self-classifies the query as
        SIMPLE, MEDIUM, or ANALYTICAL in Step 1, then applies only the rules
        relevant to that tier. This prevents CTE explosion on simple queries
        and ensures analytical patterns are applied only when needed.

        Parameters
        ----------
        user_query : str
            The user's natural-language question (handles spelling errors,
            voice input, and business slang automatically).
        schema_context : str
            Pre-formatted schema text from SchemaContextBuilder.
        dialect : str
            One of ``"mysql"``, ``"postgresql"``, or ``"sqlite"``.
            Defaults to ``"mysql"``.
        row_limit : int, optional
            The custom row limit configured by the user.

        Returns
        -------
        str
            Fully assembled prompt ready to send to the LLM.
        """
        dialect = dialect.lower().strip()

        # Normalise dialect — map any unsupported value to mysql
        if dialect not in ("mysql", "postgresql", "sqlite"):
            logger.warning(
                "Unsupported dialect '%s' — falling back to mysql.", dialect
            )
            dialect = "mysql"

        template = self._load_template("sql_prompt.txt", _FALLBACK_SQL_GENERATION)

        # sql_prompt.txt uses {dialect}, {schema_context}, {user_query}, and {row_limit}
        limit_val = row_limit if row_limit is not None else 100
        prompt = template.format(
            dialect=dialect,
            schema_context=schema_context,
            user_query=user_query,
            row_limit=limit_val,
        )

        logger.info(
            "Built SQL prompt — dialect=%s, len=%d chars", dialect, len(prompt)
        )
        return prompt

    def build_complex_sql_prompt(
        self,
        user_query: str,
        schema_context: str,
        dialect: str = "mysql",
        row_limit: Optional[int] = None,
    ) -> str:
        """Deprecated: delegates to build_sql_prompt.

        Kept so existing callers do not break. The master prompt handles
        all complexity tiers internally via Step 1 self-classification.

        Parameters
        ----------
        user_query : str
            The user's complex natural-language analytical question.
        schema_context : str
            Full schema text (all tables; no table filtering for complex queries).
        dialect : str
            SQL dialect — ``"mysql"``, ``"postgresql"``, or ``"sqlite"``.
        row_limit : int, optional
            The custom row limit configured by the user.

        Returns
        -------
        str
            Fully assembled prompt (identical to build_sql_prompt output).
        """
        logger.info(
            "build_complex_sql_prompt called — delegating to build_sql_prompt"
        )
        return self.build_sql_prompt(
            user_query=user_query,
            schema_context=schema_context,
            dialect=dialect,
            row_limit=row_limit,
        )

    def build_explanation_prompt(self, sql_query: str, user_query: str) -> str:
        """Build a prompt that asks the LLM to explain a SQL query in
        plain English.
        """
        template = self._load_template(
            "explanation_prompt.txt", _FALLBACK_EXPLANATION
        )
        prompt = template.format(sql_query=sql_query, user_query=user_query)
        logger.info("Built explanation prompt — len=%d chars", len(prompt))
        return prompt

    def build_optimization_prompt(
        self, sql_query: str, schema_context: str
    ) -> str:
        """Build a prompt that asks the LLM to suggest query optimizations."""
        template = self._load_template(
            "optimization_prompt.txt", _FALLBACK_OPTIMIZATION
        )
        prompt = template.format(
            sql_query=sql_query, schema_context=schema_context
        )
        logger.info("Built optimization prompt — len=%d chars", len(prompt))
        return prompt

    def build_chart_prompt(
        self,
        columns: List[str],
        row_count: int = 0,
        user_query: str = "",
        sql_query: str = "",
    ) -> str:
        """Build a prompt that asks the LLM to recommend the best chart type."""
        template = self._load_template("chart_prompt.txt", _FALLBACK_CHART)
        columns_str = ", ".join(columns) if columns else "(no columns)"
        prompt = template.format(
            sql_query=sql_query or "(not provided)",
            user_query=user_query,
            result_columns=columns_str,
        )
        logger.info(
            "Built chart prompt — columns=%d, len=%d chars",
            len(columns),
            len(prompt),
        )
        return prompt

    def build_voice_prompt(self, voice_input: str) -> str:
        """Build a prompt for LLM-based voice query normalisation."""
        _fallback = (
            "Clean the following speech-to-text query, remove filler words, "
            "and return only the cleaned natural-language question:\n\n"
            "{voice_input}\n\nCleaned query:"
        )
        template = self._load_template("voice_prompt.txt", _fallback)
        prompt = template.format(voice_input=voice_input)
        logger.info("Built voice prompt — len=%d chars", len(prompt))
        return prompt

    def build_analytics_prompt(
        self,
        user_query: str,
        insights: list,
        summary_stats: dict,
    ) -> str:
        """Build a prompt for LLM-based analytics narrative generation."""
        _fallback = (
            "You are a business analyst. Based on the following data insights, "
            "write a 3-5 sentence professional executive summary:\n\n"
            "User question: {user_query}\n\n"
            "Insights:\n{insights_list}\n\n"
            "Statistics:\n{summary_stats}\n\nSummary:"
        )
        template = self._load_template("analytics_prompt.txt", _fallback)
        insights_list = (
            "\n".join(f"• {i}" for i in insights) if insights else "(none)"
        )
        stats_str = (
            "\n".join(
                f"  {col}: min={v.get('min', 0):.2f}, "
                f"max={v.get('max', 0):.2f}, avg={v.get('mean', 0):.2f}"
                for col, v in summary_stats.items()
            )
            if summary_stats
            else "(none)"
        )
        prompt = template.format(
            user_query=user_query,
            insights_list=insights_list,
            summary_stats=stats_str,
        )
        logger.info("Built analytics prompt — len=%d chars", len(prompt))
        return prompt

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _load_template(self, filename: str, fallback: str) -> str:
        """Load a prompt template from disk; fall back to the hardcoded
        string if the file is missing or unreadable.
        """
        filepath = self._prompts_dir / filename
        try:
            content = filepath.read_text(encoding="utf-8")
            logger.debug("Loaded template from %s", filepath)
            return content
        except FileNotFoundError:
            logger.warning("Template not found: %s — using fallback.", filepath)
            return fallback
        except OSError as exc:
            logger.warning(
                "Could not read template %s (%s) — using fallback.", filepath, exc
            )
            return fallback


# ─── Quick smoke test ────────────────────────────────────────────────────────
if __name__ == "__main__":
    builder = PromptBuilder()

    sample_schema = (
        "TABLE: customers\n"
        "  customer_id    INT          PK\n"
        "  customer_name  VARCHAR(100)\n"
        "\n"
        "TABLE: orders\n"
        "  order_id     INT            PK\n"
        "  customer_id  INT            FK -> customers.customer_id\n"
        "  created_at   DATETIME\n"
        "\n"
        "TABLE: order_items\n"
        "  item_id     INT            PK\n"
        "  order_id    INT            FK -> orders.order_id\n"
        "  product_id  INT            FK -> products.product_id\n"
        "  quantity    INT\n"
        "  price       DECIMAL(10,2)\n"
        "\n"
        "TABLE: products\n"
        "  product_id    INT          PK\n"
        "  product_name  VARCHAR(100)\n"
        "  category      VARCHAR(50)\n"
    )

    sep = "=" * 60

    print(sep, "SIMPLE SQL — MySQL", sep, sep="\n")
    print(builder.build_sql_prompt(
        "Show top 3 customers by total spend", sample_schema, dialect="mysql"
    ))

    print(sep, "COMPLEX SQL — PostgreSQL", sep, sep="\n")
    print(builder.build_complex_sql_prompt(
        "For each customer show their average order value and most purchased category",
        sample_schema,
        dialect="postgresql",
    ))

    print(sep, "EXPLANATION", sep, sep="\n")
    print(builder.build_explanation_prompt(
        "SELECT c.customer_name, SUM(oi.quantity * oi.price) AS total "
        "FROM customers c JOIN orders o ON c.customer_id = o.customer_id "
        "JOIN order_items oi ON o.order_id = oi.order_id "
        "GROUP BY c.customer_name;",
        "Total spend per customer",
    ))