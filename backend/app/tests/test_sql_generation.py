"""
test_sql_generation.py — SQL AI Analytics Platform.

Extended test suite covering Phase 2 & 3 features:
- Voice query cleaning
- Query enhancement
- Analytics insight generation
- Full pipeline integration

Author : Member 2 — AI/LLM Engineer
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

import os
os.environ["LLM_PROVIDER"] = "gemini"
os.environ["GEMINI_API_KEY"] = "test-key"

import json
import os

# Load sample schema from central JSON
_examples_path = os.path.join(os.path.dirname(__file__), "..", "examples", "schema_examples.json")
with open(_examples_path) as f:
    _schemas = json.load(f)
SAMPLE_SCHEMA = _schemas["schemas"]["ecommerce"]
from app.agents.query_agent import QueryAgent
from app.services.ai.voice_query_cleaner import VoiceQueryCleaner
from app.services.ai.query_enhancer import QueryEnhancer
from app.services.ai.analytics_insight_generator import AnalyticsInsightGenerator


# =========================================================
# 1. Voice Cleaning Tests
# =========================================================

class TestVoiceCleaning:
    
    def test_basic_filler_removal(self):
        cleaner = VoiceQueryCleaner()
        raw = "um show me uh top clients by revenue mtd"
        result = cleaner.clean(raw)
        # Should remove 'um' and 'uh'
        assert "um" not in result["cleaned_query"].lower()
        assert "uh" not in result["cleaned_query"].lower()
        assert "show me top clients by revenue mtd" in result["cleaned_query"].lower()

    def test_contraction_expansion(self):
        cleaner = VoiceQueryCleaner()
        raw = "who's the top sales rep"
        result = cleaner.clean(raw)
        assert "who is" in result["cleaned_query"].lower()


# =========================================================
# 2. Query Enhancement Tests
# =========================================================

class TestQueryEnhancement:
    
    def test_abbreviation_expansion(self):
        enhancer = QueryEnhancer()
        query = "show revenue mtd"
        result = enhancer.enhance(query)
        assert "revenue" in result["enhanced_query"].lower()
        assert "month to date" in result["enhanced_query"].lower()

    def test_ambiguity_detection(self):
        enhancer = QueryEnhancer()
        query = "show some things"
        result = enhancer.enhance(query)
        assert len(result.get("ambiguities", [])) > 0


# =========================================================
# 3. Analytics Insight Tests
# =========================================================

class TestAnalyticsInsights:
    
    def test_insight_generation_logic(self):
        generator = AnalyticsInsightGenerator()
        cols = ["month", "revenue"]
        rows = [["Jan", 100], ["Feb", 150], ["Mar", 120]]
        
        result = generator.generate(cols, rows, "show revenue trend")
        
        assert result["success"] is True
        assert len(result["insights"]) > 0
        assert any("upward" in i.lower() or "increase" in i.lower() for i in result["insights"])


# =========================================================
# 4. Integrated QueryAgent Tests
# =========================================================

class TestQueryAgentAdvanced:

    @patch("app.services.ai.llm_service.genai")
    def test_voice_mode_pipeline(self, mock_genai):
        """Test process_query with mode='voice'."""
        # Mock LLM responses for multiple calls in the pipeline
        mock_model = MagicMock()
        mock_model.generate_content.side_effect = [
            MagicMock(text="Show me all users"), # Voice LLM pass
            MagicMock(text="SELECT * FROM users LIMIT 100"), # SQL generation
            MagicMock(text="This report lists user details."), # Explanation
            MagicMock(text="bar_chart\nJustification: comparison"), # Visualization
            MagicMock(text="Overall growth is positive.") # Analytics Narrative
        ]
        mock_genai.GenerativeModel.return_value = mock_model
        mock_genai.configure = MagicMock()

        agent = QueryAgent()
        # Voice input with filler words
        raw_voice = "um show me all users please"
        
        result = agent.process_query(
            user_query=raw_voice,
            schema=SAMPLE_SCHEMA,
            mode="voice"
        )
        
        assert result["success"] is True
        assert "SELECT" in result["sql"]

    @patch("app.services.ai.llm_service.genai")
    def test_analytics_integration(self, mock_genai):
        """Test that passing result_rows triggers insight generation."""
        mock_model = MagicMock()
        mock_model.generate_content.side_effect = [
            MagicMock(text="SELECT month, revenue FROM orders"), # SQL generation
            MagicMock(text="This report shows monthly revenue."), # Explanation
            MagicMock(text="line_chart\nJustification: trend"), # Visualization
            MagicMock(text="Growth peaked in February.") # Analytics Narrative
        ]
        mock_genai.GenerativeModel.return_value = mock_model
        mock_genai.configure = MagicMock()
        
        agent = QueryAgent()
        
        # Results from a previous execution
        cols = ["month", "revenue"]
        rows = [["Jan", 1000], ["Feb", 2000]]
        
        result = agent.process_query(
            user_query="revenue trend",
            schema=SAMPLE_SCHEMA,
            result_columns=cols,
            result_rows=rows
        )
        
        assert result["success"] is True
        # Check for analytics fields
        assert len(result["insights"]) > 0
        assert len(result["insight_cards"]) > 0
        assert result["narrative"] is not None