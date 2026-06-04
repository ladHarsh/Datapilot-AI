"""
analytics_workflow.py — SQL AI Analytics Platform.

Entry point for the Analytics Insight generation pipeline.

Flow:
  Query Result (columns + rows) → AnalyticsAgent → Insights + Cards + Narrative

Author : Member 2 — AI/LLM Engineer
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..agents.query_agent import QueryAgent

logger = logging.getLogger(__name__)


def run(
    columns: List[str],
    rows: List[List[Any]],
    user_query: str = "",
    sql_query: str = "",
) -> Dict[str, Any]:
    """Generate business insights from SQL query results.

    Parameters
    ----------
    columns : list[str]
        Column names from the result set.
    rows : list[list]
        Result data rows.
    user_query : str
        The original natural-language question (for context).
    sql_query : str
        The SQL that produced these results (for context).

    Returns
    -------
    dict
        ``{success, insights, insight_cards, narrative, trends,
           top_performers, anomalies, summary_stats}``
    """
    if not rows:
        return {
            "success": True,
            "insights": ["No data to analyze — the query returned zero rows."],
            "insight_cards": [],
            "narrative": "No results were returned for this query.",
            "trends": [],
            "top_performers": [],
            "anomalies": [],
            "summary_stats": {},
        }

    if not columns:
        return {"success": False, "error": "Columns list cannot be empty."}

    logger.info(
        "[Analytics Workflow] Analyzing %d rows × %d cols for query: '%s…'",
        len(rows), len(columns), user_query[:40],
    )

    agent = QueryAgent()
    result = agent.generate_insights(columns, rows, user_query=user_query)

    logger.info(
        "[Analytics Workflow] Complete — %d insights generated.",
        len(result.get("insights", [])),
    )
    return result
