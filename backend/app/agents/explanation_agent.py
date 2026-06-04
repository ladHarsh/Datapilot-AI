"""
Explanation Agent — AI-powered SQL Database Analysis Tool.

Responsible for translating complex SQL queries into business-friendly,
plain-English explanations.
"""

import logging
from typing import Dict, Any

from ..services.ai.explanation_service import ExplanationService

logger = logging.getLogger(__name__)


class ExplanationAgent:
    """Agent responsible for generating business-friendly SQL explanations."""

    def __init__(self) -> None:
        self.explanation_service = ExplanationService()

    def explain_query(self, sql: str, user_query: str) -> str:
        """
        Generate a clear, concise explanation of what the SQL query does.
        
        Args:
            sql: The generated SQL query.
            user_query: The original natural language question.
            
        Returns:
            A plain-English string explanation.
        """
        logger.info("Generating explanation for query.")
        
        result = self.explanation_service.explain_query(
            sql_query=sql,
            user_query=user_query
        )
        
        return result.get("explanation", "Could not generate an explanation for this query.")
