"""
test_voice_queries.py — SQL AI Analytics Platform.

Unit tests for VoiceQueryCleaner and VoiceAgent.
All tests are deterministic (no LLM calls).

Author : Member 2 — AI/LLM Engineer
"""

from __future__ import annotations

import pytest
import json
import os
os.environ["LLM_PROVIDER"] = "gemini"
os.environ["GEMINI_API_KEY"] = "test-key"

from app.services.ai.voice_query_cleaner import VoiceQueryCleaner
from app.agents.voice_agent import VoiceAgent


# Load sample voice queries from examples
_EXAMPLES_PATH = os.path.join(
    os.path.dirname(__file__), "..", "examples", "sample_queries.json"
)


@pytest.fixture
def cleaner():
    return VoiceQueryCleaner()


@pytest.fixture
def voice_agent():
    return VoiceAgent(use_llm=False)


class TestVoiceQueryCleaner:

    def test_filler_removal(self, cleaner):
        result = cleaner.clean("um uh show me all users")
        assert "um" not in result["cleaned_query"]
        assert "uh" not in result["cleaned_query"]

    def test_contraction_expansion_whos(self, cleaner):
        result = cleaner.clean("who's the top customer")
        assert "who is" in result["cleaned_query"].lower()

    def test_contraction_expansion_cant(self, cleaner):
        result = cleaner.clean("I can't find the revenue total")
        assert "cannot" in result["cleaned_query"].lower()

    def test_duplicate_word_removal(self, cleaner):
        result = cleaner.clean("show show me the the orders")
        assert "show show" not in result["cleaned_query"].lower()
        assert "the the" not in result["cleaned_query"].lower()

    def test_empty_input_returns_error(self, cleaner):
        result = cleaner.clean("")
        assert result["cleaned_query"] == ""
        assert "error" in result

    def test_success_flag_present(self, cleaner):
        result = cleaner.clean("show revenue")
        assert "success" in result
        assert result["success"] is True

    def test_confidence_high_on_minimal_change(self, cleaner):
        result = cleaner.clean("show total revenue")
        assert result["confidence"] in ("high", "medium")

    def test_changes_made_list(self, cleaner):
        result = cleaner.clean("um show me data")
        assert isinstance(result["changes_made"], list)

    def test_original_query_preserved(self, cleaner):
        raw = "um show me all orders"
        result = cleaner.clean(raw)
        assert result["original_query"] == raw


class TestVoiceAgent:

    def test_process_returns_final_query(self, voice_agent):
        result = voice_agent.process("um show me all customers")
        assert "final_query" in result
        assert len(result["final_query"]) > 0

    def test_process_strips_fillers(self, voice_agent):
        result = voice_agent.process("uh how many orders are pending")
        assert "uh" not in result["final_query"].lower()

    def test_changes_tracked(self, voice_agent):
        result = voice_agent.process("basically show me revenue by month")
        assert "changes_made" in result
        assert isinstance(result["changes_made"], list)

    def test_empty_voice_input(self, voice_agent):
        result = voice_agent.process("")
        assert result.get("success") is False or "error" in result

    def test_sample_voice_query(self):
        """Load and process a sample voice query from examples/sample_queries.json."""
        with open(_EXAMPLES_PATH) as f:
            queries = json.load(f)
        voice_queries = [q for q in queries if q.get("voice")]
        if not voice_queries:
            pytest.skip("No voice queries found in sample_queries.json")
        agent = VoiceAgent(use_llm=False)
        for q in voice_queries:
            result = agent.process(q["natural_language"])
            assert "final_query" in result
            assert "um" not in result["final_query"].lower()
            assert "uh" not in result["final_query"].lower()
