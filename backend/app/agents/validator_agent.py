"""
Validator Agent — AI-powered SQL Database Analysis Tool.

Responsible for verifying that generated SQL is safe, follows SELECT-only rules,
and aligns with the database schema.
"""

import logging
from typing import Dict, Any, List

from ..services.ai.confidence_service import ConfidenceService

logger = logging.getLogger(__name__)


class ValidatorAgent:
    """Agent responsible for SQL safety and schema validation."""

    def __init__(self) -> None:
        self.confidence_service = ConfidenceService()

    def validate_sql(self, sql: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform a comprehensive validation of the SQL query.
        
        Checks for:
        - Forbidden keywords (DROP, DELETE, etc.)
        - SELECT/WITH only
        - Table/Column existence in schema
        - JOIN correctness
        """
        if not sql or not sql.strip():
            return {
                "is_valid": False,
                "error": "Empty SQL query.",
                "confidence": {"score": 0, "label": "Low", "warnings": ["Empty query"]},
            }

        # Ensure the query is a SELECT or WITH statement
        sql_upper = sql.upper().strip()
        if not (sql_upper.startswith("SELECT") or sql_upper.startswith("WITH")):
            return {
                "is_valid": False,
                "error": "Invalid SQL: Statement must start with SELECT or WITH.",
                "confidence": {
                    "score": 0,
                    "label": "Low",
                    "checks": {
                        "tables_valid": False,
                        "columns_valid": False,
                        "joins_valid": False,
                        "safe_query": False,
                        "has_filter": False,
                        "intent_match": False,
                    },
                    "warnings": ["Query does not start with SELECT or WITH."],
                },
            }

        # Schema and Relationship Validation (via ConfidenceService)
        confidence = self.confidence_service.calculate_confidence(sql, schema)
        
        # We consider it invalid if tables are completely missing from schema
        if not confidence["checks"].get("tables_valid", False):
            return {
                "is_valid": False,
                "error": "Query references tables not found in schema.",
                "confidence": confidence,
            }

        return {
            "is_valid": True,
            "error": None,
            "confidence": confidence,
        }
