"""
test_confidence_service.py — SQL AI Analytics Platform.

Unit tests for ConfidenceService (basic schema validator)
and ConfidenceEvaluator (multi-signal production evaluator).
All tests are deterministic (no LLM calls).

Author : Member 2 — AI/LLM Engineer
"""

from __future__ import annotations

import pytest

from app.services.ai.confidence_service import ConfidenceService
from app.evaluation.confidence_evaluator import ConfidenceEvaluator

SIMPLE_SCHEMA = {
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
                {"name": "status",  "type": "VARCHAR(50)",   "nullable": True,  "primary_key": False},
            ],
            "foreign_keys": [
                {"column": "user_id", "references_table": "users", "references_column": "id"}
            ],
        },
    ]
}


# =========================================================
# ConfidenceService Tests (basic schema layer)
# =========================================================

class TestConfidenceService:

    @pytest.fixture
    def svc(self):
        return ConfidenceService()

    def test_high_score_valid_query(self, svc):
        result = svc.calculate_confidence(
            "SELECT id, email FROM users WHERE id = 1", SIMPLE_SCHEMA
        )
        assert result["score"] >= 70
        assert result["label"] in ("High", "Medium")

    def test_low_score_unknown_table(self, svc):
        result = svc.calculate_confidence(
            "SELECT * FROM ghost_table", SIMPLE_SCHEMA
        )
        assert result["score"] < 50
        assert result["label"] == "Low"

    def test_safe_query_flag(self, svc):
        result = svc.calculate_confidence("SELECT * FROM users", SIMPLE_SCHEMA)
        assert result["checks"]["safe_query"] is True

    def test_unsafe_query_blocked(self, svc):
        result = svc.calculate_confidence("DROP TABLE users", SIMPLE_SCHEMA)
        assert result["checks"]["safe_query"] is False

    def test_warnings_on_unknown_column(self, svc):
        result = svc.calculate_confidence(
            "SELECT ghost_column FROM users", SIMPLE_SCHEMA
        )
        assert len(result["warnings"]) > 0

    def test_result_has_all_required_keys(self, svc):
        result = svc.calculate_confidence("SELECT * FROM users", SIMPLE_SCHEMA)
        for key in ("score", "label", "checks", "warnings"):
            assert key in result


# =========================================================
# ConfidenceEvaluator Tests (multi-signal production layer)
# =========================================================

class TestConfidenceEvaluator:

    @pytest.fixture
    def evaluator(self):
        return ConfidenceEvaluator()

    def test_high_confidence_valid_sql(self, evaluator):
        result = evaluator.evaluate(
            sql="SELECT id, email FROM users WHERE id = 1",
            schema=SIMPLE_SCHEMA,
            user_query="find user by id",
        )
        assert result["final_score"] >= 70

    def test_safety_failure_on_drop(self, evaluator):
        result = evaluator.evaluate(
            sql="DROP TABLE users",
            schema=SIMPLE_SCHEMA,
        )
        assert result["signals"]["safety"]["passed"] is False
        assert result["final_score"] < 50

    def test_hallucination_detected(self, evaluator):
        result = evaluator.evaluate(
            sql="SELECT * FROM phantom_table",
            schema=SIMPLE_SCHEMA,
        )
        assert result["signals"]["hallucination"]["passed"] is False
        assert result["signals"]["hallucination"]["severity"] == "high"

    def test_recommendation_present(self, evaluator):
        result = evaluator.evaluate(
            sql="SELECT * FROM users",
            schema=SIMPLE_SCHEMA,
        )
        assert "recommendation" in result
        assert len(result["recommendation"]) > 0

    def test_label_is_valid(self, evaluator):
        result = evaluator.evaluate(
            sql="SELECT email FROM users",
            schema=SIMPLE_SCHEMA,
        )
        assert result["label"] in ("High", "Medium", "Low")
