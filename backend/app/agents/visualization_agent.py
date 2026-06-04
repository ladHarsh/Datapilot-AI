"""
Visualization Agent — SQL AI Analytics Platform.

Analyses the structure of the SQL result set and the user's intent to
recommend the most appropriate chart type for data visualisation.

Supports: bar_chart, line_chart, pie_chart, scatter_plot, heatmap, table_only.

Author : Member 2 — AI/LLM Engineer
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional

from ..services.ai.llm_service import LLMService, LLMServiceError
from ..services.ai.prompt_builder import PromptBuilder

logger = logging.getLogger(__name__)

# Allowed chart types (must match chart_prompt.txt)
_ALLOWED_CHARTS = {
    "bar_chart", "line_chart", "pie_chart",
    "scatter_plot", "heatmap", "table_only",
}


class VisualizationAgent:
    """Recommend the optimal chart type for a SQL query result.

    Uses a two-layer approach:
    1. **LLM recommendation** via ``chart_prompt.txt`` for nuanced advice.
    2. **Rule-based fallback** when the LLM is unavailable or returns an
       invalid response.

    Usage::

        agent = VisualizationAgent()
        rec = agent.recommend_chart(
            columns=["month", "revenue"],
            row_count=12,
            user_query="show monthly revenue trend",
            sql_query="SELECT DATE_FORMAT(...) AS month, SUM(total) ...",
        )
        # rec["chart_type"] → "line_chart"
    """

    def __init__(self) -> None:
        self._prompt_builder = PromptBuilder()
        self._llm: Optional[LLMService] = None
        try:
            self._llm = LLMService()
        except Exception as exc:
            logger.warning("VisualizationAgent: LLM not available (%s). Using rules only.", exc)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def recommend_chart(
        self,
        columns: List[str],
        row_count: int = 0,
        user_query: str = "",
        sql_query: str = "",
    ) -> Dict[str, str]:
        """Recommend a chart type based on result metadata and user intent.

        Parameters
        ----------
        columns : list[str]
            Column names in the result set.
        row_count : int
            Number of result rows (0 if not yet executed).
        user_query : str
            Original natural-language question.
        sql_query : str
            Generated SQL for structural analysis.

        Returns
        -------
        dict
            ``{chart_type, justification}``
        """
        # If no column data or no rows, default to table
        if not columns or row_count == 0:
            return {
                "chart_type":    "table_only",
                "justification": "No result columns or rows available.",
            }

        # ── Try LLM first ─────────────────────────────────────────────
        if self._llm:
            try:
                prompt = self._prompt_builder.build_chart_prompt(
                    columns=columns,
                    row_count=row_count,
                    user_query=user_query,
                    sql_query=sql_query,
                )
                response  = self._llm.send_prompt(prompt).strip()
                chart_rec = self._parse_llm_response(response)
                if chart_rec:
                    return chart_rec
            except LLMServiceError as exc:
                logger.warning("VisualizationAgent: LLM failed (%s). Using rules.", exc)
            except Exception as exc:
                logger.warning("VisualizationAgent: unexpected error (%s). Using rules.", exc)

        # ── Rule-based fallback ────────────────────────────────────────
        return self._rule_based_recommendation(columns, user_query, sql_query)

    def recommend_chart_fast(
        self,
        columns: List[str],
        row_count: int = 0,
        user_query: str = "",
        sql_query: str = "",
    ) -> Dict[str, str]:
        """Instant rule-based chart recommendation — NO LLM call.

        This is the default fast-path used by the streaming pipeline.
        Returns in <1ms. Uses the same heuristic engine as the fallback
        in ``recommend_chart()`` but skips the LLM attempt entirely.

        Parameters
        ----------
        columns : list[str]
            Column names in the result set.
        row_count : int
            Number of result rows.
        user_query : str
            Original natural-language question.
        sql_query : str
            Generated SQL for structural analysis.

        Returns
        -------
        dict
            ``{chart_type, justification}``
        """
        if not columns or row_count == 0:
            return {
                "chart_type":    "table_only",
                "justification": "No result columns or rows available.",
            }
        return self._rule_based_recommendation(columns, user_query, sql_query)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_llm_response(response: str) -> Optional[Dict[str, str]]:
        """Extract chart_type and justification from LLM response."""
        if not response:
            return None
        # Find first valid chart type token in the response
        for line in response.lower().split("\n"):
            for chart in _ALLOWED_CHARTS:
                if chart in line:
                    justification = response.strip().split("\n")[0]
                    return {
                        "chart_type":    chart,
                        "justification": justification,
                    }
        return None

    @staticmethod
    def _rule_based_recommendation(
        columns: List[str],
        user_query: str,
        sql_query: str,
    ) -> Dict[str, str]:
        """Determine chart type using keyword and structure heuristics."""
        q  = user_query.lower()
        sq = sql_query.lower()
        cols_lower = [c.lower() for c in columns]

        # ── Heatmap: two categorical + one numeric ─────────────────────
        if re.search(r"\bby\s+\w+\s+and\s+\w+\b", q) or (
            len(columns) >= 3
            and not any(
                re.search(r"(date|month|year|week|day)", c) for c in cols_lower
            )
        ):
            return {
                "chart_type":    "heatmap",
                "justification": "Two categorical dimensions detected. Heatmap shows cross-tabulation.",
            }

        # ── Line chart: time-series ────────────────────────────────────
        time_keywords = r"\b(date|month|year|week|day|time|period|trend|growth|over)\b"
        has_time_col  = any(re.search(time_keywords, c) for c in cols_lower)
        if has_time_col or re.search(time_keywords, q):
            return {
                "chart_type":    "line_chart",
                "justification": "Time dimension detected. Line chart best shows trends over time.",
            }

        # ── Pie chart: proportion / breakdown with few categories ───────
        if re.search(r"\b(proportion|share|breakdown|distribution|percent)\b", q):
            return {
                "chart_type":    "pie_chart",
                "justification": "Proportional breakdown requested. Pie chart shows relative sizes.",
            }

        # ── Scatter plot: correlation between two numeric metrics ───────
        numeric_count = sum(
            1 for c in cols_lower
            if re.search(r"(count|sum|total|amount|revenue|cost|price|rate|score|value)", c)
        )
        if numeric_count >= 2 and re.search(r"\b(correlation|vs|versus|compare|scatter)\b", q):
            return {
                "chart_type":    "scatter_plot",
                "justification": "Multiple metrics and correlation query detected.",
            }

        # ── Bar chart: categorical comparison ─────────────────────────
        if re.search(r"\b(top|rank|category|group|per|by|each|compare)\b", q) or (
            "group by" in sq and len(columns) <= 5
        ):
            return {
                "chart_type":    "bar_chart",
                "justification": "Categorical grouping detected. Bar chart compares categories.",
            }

        # ── Default: table ─────────────────────────────────────────────
        return {
            "chart_type":    "table_only",
            "justification": "No clear visualisation pattern. Tabular display recommended.",
        }
