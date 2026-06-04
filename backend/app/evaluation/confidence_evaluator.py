"""
confidence_evaluator.py — SQL AI Analytics Platform.

Combines multiple validation signals into a unified, production-grade
confidence score for a generated SQL query.

Signals used:
1. Schema validity (tables + columns present in schema)
2. Hallucination check (no phantom tables/columns)
3. SQL accuracy (pattern / keyword matching)
4. Query safety (no destructive keywords)
5. Intent alignment (NL concepts reflected in SQL)

This provides a more robust score than the basic ConfidenceService,
which only runs schema validation checks.

Author : Member 2 — AI/LLM Engineer
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..evaluation.hallucination_checker import HallucinationChecker
from ..evaluation.sql_accuracy_evaluator import SQLAccuracyEvaluator
from ..utils.sql_cleaner import is_select_only
from ..utils.ai_constants import (
    CONFIDENCE_HIGH_THRESHOLD,
    CONFIDENCE_MEDIUM_THRESHOLD,
)

logger = logging.getLogger(__name__)

_hallucination_checker = HallucinationChecker()
_accuracy_evaluator    = SQLAccuracyEvaluator()


class ConfidenceEvaluator:
    """Multi-signal confidence evaluator for generated SQL.

    Unlike ``ConfidenceService`` (which is a quick schema validator),
    this class combines all evaluation modules for a comprehensive score.

    Usage::

        evaluator = ConfidenceEvaluator()
        result = evaluator.evaluate(
            sql="SELECT SUM(total) FROM orders GROUP BY user_id",
            schema=my_schema,
            user_query="total orders by user",
        )
        # result["final_score"] → 87
        # result["label"] → "High"
    """

    def evaluate(
        self,
        sql: str,
        schema: Dict[str, Any],
        user_query: str = "",
        expected_pattern: Optional[str] = None,
        expected_tables: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Run full multi-signal confidence evaluation.

        Parameters
        ----------
        sql : str
            Generated SQL query.
        schema : dict
            Database schema.
        user_query : str
            Original NL query (for intent alignment).
        expected_pattern : str, optional
            Regex pattern for accuracy check.
        expected_tables : list[str], optional
            Tables that must appear in the SQL.

        Returns
        -------
        dict
            ``{final_score, label, signals, warnings, recommendation}``
        """
        signals: Dict[str, Any] = {}
        warnings: List[str] = []
        score = 0

        # ── Signal 1: Safety (20pts) ──────────────────────────────
        is_safe = is_select_only(sql)
        signals["safety"] = {"passed": is_safe, "weight": 20}
        if is_safe:
            score += 20
        else:
            warnings.append("CRITICAL: Query contains destructive SQL keywords.")

        # ── Signal 2: Hallucination Check (30pts) ─────────────────
        halluc_result = _hallucination_checker.check(sql, schema)
        signals["hallucination"] = {
            "passed":   halluc_result["clean"],
            "severity": halluc_result["severity"],
            "weight":   30,
        }
        if halluc_result["clean"]:
            score += 30
        else:
            if halluc_result["severity"] == "high":
                warnings.append(
                    f"Hallucinated tables detected: {halluc_result['hallucinated_tables']}"
                )
            else:
                warnings.extend(halluc_result["hallucinations"])

        # ── Signal 3: Structural Accuracy (30pts) ─────────────────
        accuracy_result = _accuracy_evaluator.evaluate(
            generated_sql=sql,
            expected_pattern=expected_pattern,
            expected_tables=expected_tables,
        )
        signals["accuracy"] = {
            "score":  accuracy_result["score"],
            "passed": accuracy_result["passed"],
            "weight": 30,
        }
        # Scale 0-100 accuracy score to 0-30 points
        score += int(accuracy_result["score"] / 100 * 30)
        if not accuracy_result["passed"]:
            warnings.extend(accuracy_result["failures"])

        # ── Signal 4: Intent Alignment (20pts) ────────────────────
        intent_ok = self._check_intent_alignment(user_query, sql)
        signals["intent_alignment"] = {"passed": intent_ok, "weight": 20}
        if intent_ok:
            score += 20
        else:
            warnings.append(
                "Generated SQL may not fully address the user's analytical intent."
            )

        # ── Final Score & Label ───────────────────────────────────
        if not signals["safety"]["passed"]:
            final_score = 0
        else:
            final_score = min(100, max(0, score))
        label = (
            "High"   if final_score >= CONFIDENCE_HIGH_THRESHOLD   else
            "Medium" if final_score >= CONFIDENCE_MEDIUM_THRESHOLD else
            "Low"
        )

        recommendation = self._generate_recommendation(signals, warnings, final_score)

        return {
            "final_score":    final_score,
            "label":          label,
            "signals":        signals,
            "warnings":       warnings,
            "recommendation": recommendation,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _check_intent_alignment(nl: str, sql: str) -> bool:
        """Check if key NL intent keywords are reflected in the SQL."""
        if not nl:
            return True
        nl_lower = nl.lower()
        sql_upper = sql.upper()
        checks = [
            ("total" in nl_lower or "sum" in nl_lower or "revenue" in nl_lower,
             "SUM" in sql_upper),
            ("average" in nl_lower or "mean" in nl_lower,
             "AVG" in sql_upper),
            ("count" in nl_lower or "how many" in nl_lower,
             "COUNT" in sql_upper),
            ("trend" in nl_lower or "over time" in nl_lower or "monthly" in nl_lower,
             "GROUP BY" in sql_upper),
        ]
        for intent_present, sql_reflects in checks:
            if intent_present and not sql_reflects:
                return False
        return True

    @staticmethod
    def _generate_recommendation(signals, warnings, score: int) -> str:
        if score >= 80:
            return "Query is ready for execution."
        if not signals.get("safety", {}).get("passed"):
            return "BLOCK: Query contains destructive keywords. Do not execute."
        if not signals.get("hallucination", {}).get("passed"):
            return "REVIEW: Hallucinated schema elements detected. Regenerate query."
        if score >= 50:
            return "CAUTION: Query may be partially correct. Review before executing."
        return "REJECT: Low confidence. Rephrase the question and retry."
