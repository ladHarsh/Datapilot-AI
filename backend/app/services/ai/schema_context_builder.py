"""
Schema Context Builder — AI-powered SQL Database Analysis Tool.

Transforms raw database schema dictionaries (produced by Member 1's
``schema_service.py``) into compact, AI-readable plain-text context strings
optimised for LLM prompt injection.

Author : Member 2 — AI/LLM Engineer
Created: 2026-05-12
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SchemaContextBuilder:
    """Converts a structured schema dictionary into a concise text
    representation that an LLM can reason about efficiently.

    The output format is designed to:
    * Clearly enumerate tables, columns (with types), and constraints.
    * Highlight primary keys and foreign-key relationships.
    * Minimise token usage — no redundant prose, no JSON overhead.

    Example output::

        TABLE: users
          id            INT          PK
          email         VARCHAR(255)
          created_at    TIMESTAMP

        TABLE: orders
          id            INT          PK
          user_id       INT          FK -> users.id
          total         DECIMAL(10,2)

        RELATIONSHIPS:
          orders.user_id -> users.id
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_context(self, schema: Dict[str, Any]) -> str:
        """Build a compact, AI-readable context string from a schema dict.

        Parameters
        ----------
        schema : dict
            Database schema in the canonical format::

                {
                    "tables": [
                        {
                            "name": "table_name",
                            "columns": [
                                {"name": "col", "type": "INT",
                                 "nullable": True, "primary_key": False}
                            ],
                            "foreign_keys": [
                                {"column": "fk_col",
                                 "references_table": "other_table",
                                 "references_column": "id"}
                            ]
                        }
                    ]
                }

        Returns
        -------
        str
            Plain-text schema context ready for LLM prompt injection.

        Raises
        ------
        ValueError
            If *schema* is ``None`` or missing the ``"tables"`` key.
        """
        if not schema or "tables" not in schema:
            raise ValueError(
                "Invalid schema: expected a dict with a 'tables' key."
            )

        tables: List[Dict[str, Any]] = schema["tables"]
        if not tables:
            return "DATABASE SCHEMA: (no tables found)"

        logger.info(
            "Building schema context for %d table(s).", len(tables)
        )

        sections: List[str] = []
        all_relationships: List[str] = []

        for table in tables:
            table_block, relationships = self._format_table(table)
            sections.append(table_block)
            all_relationships.extend(relationships)

        # Assemble final context
        context_parts: List[str] = ["DATABASE SCHEMA:", ""]
        context_parts.append("\n\n".join(sections))

        if all_relationships:
            context_parts.append("")
            context_parts.append("RELATIONSHIPS:")
            for rel in all_relationships:
                context_parts.append(f"  {rel}")

        context = "\n".join(context_parts)
        logger.info(
            "Schema context built — %d chars, %d table(s), %d relationship(s).",
            len(context),
            len(tables),
            len(all_relationships),
        )
        return context

    def filter_relevant_tables(
        self,
        schema: Dict[str, Any],
        user_query: str,
        max_tables: int = 20,
    ) -> Dict[str, Any]:
        """Return a filtered copy of *schema* containing only the tables
        most relevant to *user_query*.

        Relevance is determined by keyword matching: each table is scored
        by how many query keywords appear in its name, column names, or
        foreign-key references.  Tables directly linked via foreign keys
        to a matched table are also included to preserve relationship
        context.

        Parameters
        ----------
        schema : dict
            Full database schema dictionary.
        user_query : str
            The user's natural-language question or SQL fragment.
        max_tables : int
            Maximum number of tables to include (default ``20``).

        Returns
        -------
        dict
            A new schema dict with at most *max_tables* entries.
        """
        if not schema or "tables" not in schema:
            return schema

        tables: List[Dict[str, Any]] = schema["tables"]

        # If already within budget, return as-is
        if len(tables) <= max_tables:
            logger.info(
                "Schema has %d tables (<= %d) — no filtering needed.",
                len(tables),
                max_tables,
            )
            return schema

        logger.info(
            "Schema has %d tables (> %d). Filtering by relevance to query.",
            len(tables),
            max_tables,
        )

        keywords = self._extract_keywords(user_query)
        scored: List[tuple[float, Dict[str, Any]]] = []

        for table in tables:
            score = self._score_table(table, keywords)
            scored.append((score, table))

        # Sort descending by score
        scored.sort(key=lambda pair: pair[0], reverse=True)

        # Take top tables by score
        selected_names: set[str] = set()
        selected_tables: List[Dict[str, Any]] = []

        for _score, table in scored[:max_tables]:
            selected_names.add(table["name"])
            selected_tables.append(table)

        # Also pull in FK-referenced tables that aren't already selected
        extra_tables: List[Dict[str, Any]] = []
        table_lookup = {t["name"]: t for t in tables}

        for table in list(selected_tables):
            for fk in table.get("foreign_keys", []):
                ref = fk.get("references_table", "")
                if ref and ref not in selected_names:
                    if ref in table_lookup:
                        extra_tables.append(table_lookup[ref])
                        selected_names.add(ref)

        selected_tables.extend(extra_tables)

        # Final trim if we overshot
        selected_tables = selected_tables[:max_tables]

        logger.info(
            "Filtered to %d relevant table(s).", len(selected_tables)
        )
        return {"tables": selected_tables}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_table(
        table: Dict[str, Any],
    ) -> tuple[str, List[str]]:
        """Format a single table definition into compact text lines.

        Parameters
        ----------
        table : dict
            A single table entry from the schema.

        Returns
        -------
        tuple[str, list[str]]
            A ``(table_block, relationships)`` pair where *table_block*
            is the formatted text and *relationships* is a list of
            human-readable FK descriptions.
        """
        table_name: str = table.get("name", "unknown")
        columns: List[Dict[str, Any]] = table.get("columns", [])
        foreign_keys: List[Dict[str, Any]] = table.get("foreign_keys", [])

        # Build a quick FK lookup: column_name -> "ref_table.ref_col"
        fk_map: Dict[str, str] = {}
        relationships: List[str] = []
        for fk in foreign_keys:
            col = fk.get("column", "")
            ref_table = fk.get("references_table", "")
            ref_col = fk.get("references_column", "")
            if col and ref_table and ref_col:
                fk_map[col] = f"{ref_table}.{ref_col}"
                relationships.append(
                    f"{table_name}.{col} -> {ref_table}.{ref_col}"
                )

        # Determine column-name width for alignment
        max_name_len = max(
            (len(c.get("name", "")) for c in columns), default=10
        )
        max_type_len = max(
            (len(c.get("type", "")) for c in columns), default=4
        )

        lines: List[str] = [f"TABLE: {table_name}"]

        for col in columns:
            col_name: str = col.get("name", "")
            col_type: str = col.get("type", "")
            is_pk: bool = col.get("primary_key", False)
            nullable: bool = col.get("nullable", True)

            # Build constraint tags
            tags: List[str] = []
            if is_pk:
                tags.append("PK")
            if col_name in fk_map:
                tags.append(f"FK -> {fk_map[col_name]}")
            if not nullable and not is_pk:
                tags.append("NOT NULL")

            tag_str = "  ".join(tags)
            padded_name = col_name.ljust(max_name_len)
            padded_type = col_type.ljust(max_type_len)

            line = f"  {padded_name}  {padded_type}"
            if tag_str:
                line += f"  {tag_str}"

            lines.append(line)

        return "\n".join(lines), relationships

    @staticmethod
    def _extract_keywords(text: str) -> List[str]:
        """Extract meaningful keywords from a natural-language query.

        Strips common SQL noise words and returns lowercase tokens useful
        for relevance scoring.

        Parameters
        ----------
        text : str
            User query or SQL fragment.

        Returns
        -------
        list[str]
            Lowercase keyword tokens.
        """
        # Common stop words and SQL noise to ignore
        stop_words = {
            "select", "from", "where", "and", "or", "the", "a", "an",
            "is", "in", "on", "for", "to", "of", "with", "by", "as",
            "all", "each", "every", "show", "me", "get", "find", "list",
            "how", "many", "much", "what", "which", "that", "this",
            "are", "was", "were", "be", "been", "being", "have", "has",
            "do", "does", "did", "will", "would", "could", "should",
            "not", "no", "but", "if", "then", "than", "between",
            "join", "left", "right", "inner", "outer", "group",
            "order", "limit", "count", "sum", "avg", "min", "max",
            "insert", "update", "delete", "create", "drop", "alter",
            "table", "column", "index", "into", "values", "set",
        }

        tokens = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", text.lower())
        return [t for t in tokens if t not in stop_words and len(t) > 1]

    @staticmethod
    def _fuzzy_match(keyword: str, target: str) -> float:
        """Return a 0–1 fuzzy similarity between *keyword* and *target*.

        Uses a simple bigram overlap score — lightweight, no external deps.
        Returns 0.0 for very short strings, 1.0 for identical strings.
        """
        if not keyword or not target:
            return 0.0
        if keyword == target:
            return 1.0
        # Exact substring already handled by caller
        def bigrams(s: str):
            return set(s[i:i+2] for i in range(len(s) - 1))
        bg_kw = bigrams(keyword)
        bg_tg = bigrams(target)
        if not bg_kw or not bg_tg:
            return 0.0
        overlap = len(bg_kw & bg_tg)
        return (2.0 * overlap) / (len(bg_kw) + len(bg_tg))

    @classmethod
    def _score_table(
        cls, table: Dict[str, Any], keywords: List[str]
    ) -> float:
        """Score a table's relevance against a list of keywords.

        Scoring rules:
        * **+3.0** — keyword exact/substring matches the table name.
        * **+2.0** — fuzzy match ≥ 0.7 on table name (handles misspellings).
        * **+1.5** — keyword matches a column name.
        * **+1.0** — fuzzy match ≥ 0.7 on a column name.
        * **+0.8** — keyword matches a foreign-key reference table/column.

        Parameters
        ----------
        table : dict
            A single table entry from the schema.
        keywords : list[str]
            Lowercase keyword tokens from the user query.

        Returns
        -------
        float
            Aggregate relevance score (higher = more relevant).
        """
        score: float = 0.0
        table_name = table.get("name", "").lower()
        columns = table.get("columns", [])
        foreign_keys = table.get("foreign_keys", [])

        col_names = [c.get("name", "").lower() for c in columns]
        fk_refs = [
            f"{fk.get('references_table', '')}."
            f"{fk.get('references_column', '')}".lower()
            for fk in foreign_keys
        ]

        for kw in keywords:
            # Table name match (strongest signal)
            if kw in table_name or table_name in kw:
                score += 3.0
            else:
                # Fuzzy match on table name (catches misspellings)
                fz = cls._fuzzy_match(kw, table_name)
                if fz >= 0.70:
                    score += 2.0 * fz

            # Column name match
            matched_col = False
            for cn in col_names:
                if kw in cn or cn in kw:
                    score += 1.5
                    matched_col = True
                    break
            if not matched_col:
                for cn in col_names:
                    fz = cls._fuzzy_match(kw, cn)
                    if fz >= 0.70:
                        score += 1.0 * fz
                        break

            # FK reference match
            for ref in fk_refs:
                if kw in ref:
                    score += 0.8
                    break

        return score


# ---------------------------------------------------------------------------
# Quick smoke test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    sample_schema: Dict[str, Any] = {
        "tables": [
            {
                "name": "users",
                "columns": [
                    {"name": "id", "type": "INT", "nullable": False, "primary_key": True},
                    {"name": "email", "type": "VARCHAR(255)", "nullable": False, "primary_key": False},
                    {"name": "name", "type": "VARCHAR(100)", "nullable": True, "primary_key": False},
                    {"name": "created_at", "type": "TIMESTAMP", "nullable": False, "primary_key": False},
                ],
                "foreign_keys": [],
            },
            {
                "name": "orders",
                "columns": [
                    {"name": "id", "type": "INT", "nullable": False, "primary_key": True},
                    {"name": "user_id", "type": "INT", "nullable": False, "primary_key": False},
                    {"name": "total", "type": "DECIMAL(10,2)", "nullable": False, "primary_key": False},
                    {"name": "status", "type": "VARCHAR(50)", "nullable": True, "primary_key": False},
                ],
                "foreign_keys": [
                    {"column": "user_id", "references_table": "users", "references_column": "id"}
                ],
            },
            {
                "name": "products",
                "columns": [
                    {"name": "id", "type": "INT", "nullable": False, "primary_key": True},
                    {"name": "name", "type": "VARCHAR(200)", "nullable": False, "primary_key": False},
                    {"name": "price", "type": "DECIMAL(10,2)", "nullable": False, "primary_key": False},
                ],
                "foreign_keys": [],
            },
        ]
    }

    builder = SchemaContextBuilder()
    print(builder.build_context(sample_schema))
    print("\n--- Filtered (keyword: 'orders') ---\n")
    filtered = builder.filter_relevant_tables(sample_schema, "show all orders")
    print(builder.build_context(filtered))
