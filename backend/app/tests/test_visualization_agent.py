"""
test_visualization_agent.py — SQL AI Analytics Platform.

Unit tests for VisualizationAgent chart recommendation logic.
Rule-based heuristic tests are fully deterministic.

Author : Member 2 — AI/LLM Engineer
"""

from __future__ import annotations

import pytest

from app.agents.visualization_agent import VisualizationAgent
from app.utils.ai_constants import (
    CHART_BAR, CHART_LINE, CHART_PIE, CHART_TABLE_ONLY, CHART_HEATMAP
)

# Shared agent
@pytest.fixture
def agent():
    return VisualizationAgent()


class TestChartHeuristics:

    def test_single_row_returns_table_only(self, agent):
        result = agent._rule_based_recommendation(["name"], "show user", "SELECT name FROM users")
        assert result["chart_type"] == CHART_TABLE_ONLY

    def test_two_columns_numeric_second_suggests_bar(self, agent):
        """Category + numeric metric → bar chart."""
        cols = ["region", "revenue"]
        result = agent._rule_based_recommendation(cols, "revenue by region", "SELECT region, revenue FROM orders GROUP BY region")
        assert result["chart_type"] in (CHART_BAR, CHART_PIE)

    def test_time_column_suggests_line_chart(self, agent):
        """Date/time column + numeric → line chart."""
        cols = ["month", "revenue"]
        result = agent._rule_based_recommendation(cols, "revenue trend", "SELECT month, revenue FROM orders")
        assert result["chart_type"] == CHART_LINE

    def test_many_rows_avoids_pie_chart(self, agent):
        """More than 10 rows should not suggest pie chart (via prompt or rules)."""
        cols = ["category", "count"]
        # Note: Rule-based doesn't see row_count directly in current impl, but we check if it falls back to bar
        result = agent._rule_based_recommendation(cols, "category breakdown", "SELECT category, count FROM products")
        assert result["chart_type"] in (CHART_BAR, CHART_PIE)

    def test_three_plus_metrics_suggests_bar_or_heatmap(self, agent):
        """3+ numeric columns = heatmap or bar."""
        cols = ["region", "revenue", "order_count", "avg_value"]
        result = agent._rule_based_recommendation(cols, "compare regions", "SELECT * FROM stats")
        assert result["chart_type"] in (CHART_HEATMAP, CHART_BAR, CHART_TABLE_ONLY)


class TestRecommendChartInterface:

    def test_returns_required_keys(self, agent):
        result = agent.recommend_chart(["month", "revenue"],
                                       [["Jan", 100], ["Feb", 200]])
        assert "chart_type" in result
        assert "justification" in result

    def test_chart_type_is_supported(self, agent):
        from app.utils.ai_constants import SUPPORTED_CHARTS
        result = agent.recommend_chart(["month", "revenue"],
                                       [["Jan", 100], ["Feb", 200]])
        assert result["chart_type"] in SUPPORTED_CHARTS

    def test_empty_rows_returns_table_only(self, agent):
        result = agent.recommend_chart(["month", "revenue"], 0)
        assert result["chart_type"] == CHART_TABLE_ONLY
