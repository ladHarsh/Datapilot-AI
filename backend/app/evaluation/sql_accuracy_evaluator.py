"""
sql_accuracy_evaluator.py — SQL AI Analytics Platform.

Evaluates the structural accuracy of a generated SQL query against
an expected SQL pattern or reference query.

Checks:
- Structural pattern matching (SELECT, JOIN, GROUP BY, ORDER BY)
- Table coverage (all expected tables referenced)
- Aggregation type matching (SUM vs COUNT vs AVG)
- Keyword presence

This is used in evaluation pipelines and regression testing.

Author : Member 2 — AI/LLM Engineer
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from ..utils.sql_cleaner import extract_table_names

logger = logging.getLogger(__name__)


class SQLAccuracyEvaluator:
    """Evaluate structural accuracy of generated SQL.

    Usage::

        evaluator = SQLAccuracyEvaluator()
        result = evaluator.evaluate(
            generated_sql="SELECT user_id, SUM(total) FROM orders GROUP BY user_id",
            expected_pattern=r"SELECT.*SUM.*GROUP BY",
        )
        # result["score"] → 100, result["passed"] → True
    """

    def evaluate(
        self,
        generated_sql: str,
        expected_pattern: Optional[str] = None,
        expected_tables: Optional[List[str]] = None,
        expected_keywords: Optional[List[str]] = None,
        reference_sql: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run structural evaluation checks on generated SQL.

        Parameters
        ----------
        generated_sql : str
            The SQL produced by the LLM.
        expected_pattern : str, optional
            Regex pattern the SQL must match (e.g. r"SUM.*GROUP BY").
        expected_tables : list[str], optional
            Table names that must appear in the query.
        expected_keywords : list[str], optional
            SQL keywords that must be present (e.g. ["JOIN", "ORDER BY"]).
        reference_sql : str, optional
            Gold-standard SQL for token-level similarity comparison.

        Returns
        -------
        dict
            ``{score, passed, checks, failures, similarity_score}``
        """
        sql_upper = generated_sql.upper()
        checks: Dict[str, bool] = {}
        failures: List[str] = []
        total_weight = 0
        earned_weight = 0

        # ── 1. Pattern Match ──────────────────────────────────────
        if expected_pattern:
            total_weight += 40
            match = bool(re.search(expected_pattern, generated_sql, re.IGNORECASE | re.DOTALL))
            checks["pattern_match"] = match
            if match:
                earned_weight += 40
            else:
                failures.append(f"Pattern not matched: {expected_pattern}")

        # ── 2. Table Coverage ─────────────────────────────────────
        if expected_tables:
            total_weight += 30
            found_tables = set(extract_table_names(generated_sql))
            required_tables = {t.lower() for t in expected_tables}
            all_present = required_tables.issubset(found_tables)
            checks["table_coverage"] = all_present
            if all_present:
                earned_weight += 30
            else:
                missing = required_tables - found_tables
                failures.append(f"Missing tables: {', '.join(missing)}")

        # ── 3. Keyword Presence ───────────────────────────────────
        if expected_keywords:
            total_weight += 30
            all_found = True
            for kw in expected_keywords:
                if kw.upper() not in sql_upper:
                    failures.append(f"Missing keyword: {kw}")
                    all_found = False
            checks["keyword_presence"] = all_found
            if all_found:
                earned_weight += 30

        # ── 4. Reference SQL Similarity ───────────────────────────
        similarity_score = None
        if reference_sql:
            similarity_score = self._token_similarity(generated_sql, reference_sql)

        # ── 5. Final Score ────────────────────────────────────────
        if total_weight == 0:
            # No criteria provided — just check it's a SELECT
            score = 100 if generated_sql.strip().upper().startswith(("SELECT", "WITH")) else 0
            passed = score == 100
        else:
            score = int((earned_weight / total_weight) * 100)
            passed = score >= 70  # >= 70% considered passing

        return {
            "score":            score,
            "passed":           passed,
            "checks":           checks,
            "failures":         failures,
            "similarity_score": similarity_score,
        }

    @staticmethod
    def _token_similarity(sql_a: str, sql_b: str) -> float:
        """Compute Jaccard similarity between SQL keyword token sets."""
        def tokenize(sql: str) -> set:
            return set(re.findall(r"\b[A-Za-z_]\w*\b", sql.upper()))

        tokens_a = tokenize(sql_a)
        tokens_b = tokenize(sql_b)

        if not tokens_a and not tokens_b:
            return 1.0
        if not tokens_a or not tokens_b:
            return 0.0

        intersection = tokens_a & tokens_b
        union = tokens_a | tokens_b
        return round(len(intersection) / len(union), 4)
