"""
test_prompt_builder.py — SQL AI Analytics Platform.

Unit tests for PromptBuilder — validates that prompts are non-empty,
contain required keywords, and respect token budgets.
All tests are deterministic (no LLM calls).

Author : Member 2 — AI/LLM Engineer
"""

from __future__ import annotations

import pytest

from app.services.ai.prompt_builder import PromptBuilder
from app.utils.token_counter import count_tokens
from app.utils.ai_constants import PROMPT_TOKEN_BUDGET


@pytest.fixture
def builder():
    return PromptBuilder()


SIMPLE_SCHEMA_CONTEXT = (
    "TABLE: users\n"
    "  - id INT [PK] NOT NULL\n"
    "  - email VARCHAR(255) NOT NULL\n"
    "  - name VARCHAR(100)\n"
)


class TestSQLPromptBuilder:

    def test_sql_prompt_contains_query(self, builder):
        prompt = builder.build_sql_prompt("Show all users", SIMPLE_SCHEMA_CONTEXT)
        assert "Show all users" in prompt

    def test_sql_prompt_contains_schema(self, builder):
        prompt = builder.build_sql_prompt("Show all users", SIMPLE_SCHEMA_CONTEXT)
        assert "users" in prompt

    def test_sql_prompt_contains_dialect(self, builder):
        prompt = builder.build_sql_prompt("Show all users", SIMPLE_SCHEMA_CONTEXT, dialect="postgresql")
        assert "postgresql" in prompt.lower() or "postgres" in prompt.lower()

    def test_sql_prompt_is_nonempty(self, builder):
        prompt = builder.build_sql_prompt("test query", SIMPLE_SCHEMA_CONTEXT)
        assert len(prompt) > 50

    def test_sql_prompt_within_token_budget(self, builder):
        prompt = builder.build_sql_prompt("Show all users", SIMPLE_SCHEMA_CONTEXT)
        assert count_tokens(prompt) <= PROMPT_TOKEN_BUDGET


class TestExplanationPromptBuilder:

    def test_explanation_prompt_contains_sql(self, builder):
        sql = "SELECT * FROM users LIMIT 100"
        prompt = builder.build_explanation_prompt(sql, "Show all users")
        assert "SELECT" in prompt

    def test_explanation_prompt_contains_user_query(self, builder):
        prompt = builder.build_explanation_prompt(
            "SELECT * FROM users", "Show all users"
        )
        assert "Show all users" in prompt

    def test_explanation_prompt_nonempty(self, builder):
        prompt = builder.build_explanation_prompt("SELECT 1", "test")
        assert len(prompt) > 20


class TestVoicePromptBuilder:

    def test_voice_prompt_contains_input(self, builder):
        prompt = builder.build_voice_prompt("um show me revenue")
        assert "revenue" in prompt.lower()

    def test_voice_prompt_instructs_cleaning(self, builder):
        prompt = builder.build_voice_prompt("uh show me data")
        # Should contain instructions to clean
        assert any(kw in prompt.lower() for kw in ["clean", "filler", "rephrase", "normalize"])


class TestAnalyticsPromptBuilder:

    def test_analytics_prompt_contains_insights(self, builder):
        insights = ["Revenue increased 20%", "Top performer: East region"]
        prompt = builder.build_analytics_prompt(
            user_query="revenue trend",
            insights=insights,
            summary_stats={"revenue": {"mean": 15000.0, "max": 25000.0}},
        )
        assert "Revenue increased 20%" in prompt

    def test_analytics_prompt_nonempty(self, builder):
        prompt = builder.build_analytics_prompt(
            user_query="test",
            insights=["Insight A"],
            summary_stats={},
        )
        assert len(prompt) > 20
