"""
test_langgraph_workflow.py — SQL AI Analytics Platform.

Integration tests for LangGraphWorkflow pipeline state management.
Uses mocked LLM to test node transitions and state propagation.

Author : Member 2 — AI/LLM Engineer
"""

from __future__ import annotations

import os
import pytest
from unittest.mock import MagicMock, patch

# Force gemini provider for tests so mocks are triggered
os.environ["LLM_PROVIDER"] = "gemini"
os.environ["GEMINI_API_KEY"] = "test-key"


SAMPLE_SCHEMA = {
    "tables": [
        {
            "name": "users",
            "columns": [
                {"name": "id",    "type": "INT",          "nullable": False, "primary_key": True},
                {"name": "email", "type": "VARCHAR(255)", "nullable": False, "primary_key": False},
                {"name": "name",  "type": "VARCHAR(100)", "nullable": True,  "primary_key": False},
            ],
            "foreign_keys": [],
        },
        {
            "name": "orders",
            "columns": [
                {"name": "id",      "type": "INT",           "nullable": False, "primary_key": True},
                {"name": "user_id", "type": "INT",           "nullable": False, "primary_key": False},
                {"name": "total",   "type": "DECIMAL(10,2)", "nullable": False, "primary_key": False},
            ],
            "foreign_keys": [
                {"column": "user_id", "references_table": "users", "references_column": "id"}
            ],
        },
    ]
}


class TestLangGraphWorkflowState:

    @patch("app.services.ai.llm_service.genai")
    def test_pipeline_output_has_required_keys(self, mock_genai):
        """Workflow must return all required keys."""
        mock_model = MagicMock()
        mock_model.generate_content.return_value.text = \
            "SELECT id, name FROM users LIMIT 10"
        mock_genai.GenerativeModel.return_value = mock_model
        mock_genai.configure = MagicMock()

        from app.agents.langgraph_workflow import LangGraphWorkflow
        wf = LangGraphWorkflow()
        result = wf.run_pipeline("Show all users", SAMPLE_SCHEMA)

        for key in ("success", "sql", "explanation", "confidence_score",
                    "confidence_label", "recommended_chart", "warnings"):
            assert key in result, f"Missing key: {key}"

    @patch("app.services.ai.llm_service.genai")
    def test_successful_pipeline_sets_success_true(self, mock_genai):
        """A valid query should set success=True."""
        mock_model = MagicMock()
        mock_model.generate_content.return_value.text = \
            "SELECT SUM(total) FROM orders GROUP BY user_id"
        mock_genai.GenerativeModel.return_value = mock_model
        mock_genai.configure = MagicMock()

        from app.agents.langgraph_workflow import LangGraphWorkflow
        wf = LangGraphWorkflow()
        result = wf.run_pipeline("Total orders by user", SAMPLE_SCHEMA)

        assert result["success"] is True
        assert "SELECT" in result["sql"].upper()

    @patch("app.services.ai.llm_service.genai")
    def test_invalid_sql_sets_success_false(self, mock_genai):
        """When LLM returns non-SQL, success must be False."""
        mock_model = MagicMock()
        mock_model.generate_content.return_value.text = "I cannot generate SQL for this."
        mock_genai.GenerativeModel.return_value = mock_model
        mock_genai.configure = MagicMock()

        from app.agents.langgraph_workflow import LangGraphWorkflow
        wf = LangGraphWorkflow()
        result = wf.run_pipeline("DROP the users table", SAMPLE_SCHEMA)

        assert result["success"] is False

    @patch("app.services.ai.llm_service.genai")
    def test_voice_mode_accepted(self, mock_genai):
        """Workflow should accept mode='voice' without error."""
        mock_model = MagicMock()
        mock_model.generate_content.return_value.text = \
            "SELECT * FROM users LIMIT 5"
        mock_genai.GenerativeModel.return_value = mock_model
        mock_genai.configure = MagicMock()

        from app.agents.langgraph_workflow import LangGraphWorkflow
        wf = LangGraphWorkflow()
        result = wf.run_pipeline("show users", SAMPLE_SCHEMA, mode="voice")

        assert "success" in result

    @patch("app.services.ai.llm_service.genai")
    def test_analytics_triggered_with_result_rows(self, mock_genai):
        """Passing result_rows should trigger analytics node."""
        mock_model = MagicMock()
        mock_model.generate_content.return_value.text = \
            "SELECT month, revenue FROM orders GROUP BY month"
        mock_genai.GenerativeModel.return_value = mock_model
        mock_genai.configure = MagicMock()

        from app.agents.langgraph_workflow import LangGraphWorkflow
        wf = LangGraphWorkflow()
        result = wf.run_pipeline(
            user_query="revenue trend",
            schema=SAMPLE_SCHEMA,
            result_columns=["month", "revenue"],
            result_rows=[["Jan", 1000], ["Feb", 2000]],
        )

        assert "success" in result
        # Insights should be populated when rows are passed
        assert "insights" in result
