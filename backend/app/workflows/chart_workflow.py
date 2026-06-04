"""
chart_workflow.py — SQL AI Analytics Platform.

Entry point for chart type recommendation.

Flow:
  Query Result + SQL → VisualizationAgent → Chart Type + Justification

Author : Member 2 — AI/LLM Engineer
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..agents.visualization_agent import VisualizationAgent
from ..utils.ai_constants import CHART_TABLE_ONLY

logger = logging.getLogger(__name__)

# Shared agent instance (stateless, safe to reuse)
_viz_agent = VisualizationAgent()


def run(
    columns: List[str],
    rows: List[List[Any]],
    sql_query: str = "",
    user_query: str = "",
) -> Dict[str, Any]:
    """Recommend the best chart type for a given result set.

    Parameters
    ----------
    columns : list[str]
        Column names from the query result.
    rows : list[list]
        Result data rows.
    sql_query : str
        The SQL query that produced these results.
    user_query : str
        The original user question.

    Returns
    -------
    dict
        ``{chart_type, justification}``
    """
    if not columns or not rows:
        return {
            "chart_type": CHART_TABLE_ONLY,
            "justification": "No data to visualize.",
        }

    logger.info(
        "[Chart Workflow] Recommending chart for %d rows × %d cols.",
        len(rows), len(columns),
    )

    result = _viz_agent.recommend_chart(
        columns=columns,
        rows=rows,
        sql_query=sql_query,
        user_query=user_query,
    )

    logger.info("[Chart Workflow] Recommended: %s", result.get("chart_type"))
    return result
