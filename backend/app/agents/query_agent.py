"""
Query Agent — SQL AI Analytics Platform.

Main facade for the AI layer. Provides high-level methods for:
1. Full Pipeline Processing (NL → SQL → Explanation → Visualization → Analytics)
2. Voice-to-Cleaned-NL Processing
3. Standalone SQL Generation / Explanation

Author : Member 2 — AI/LLM Engineer
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .langgraph_workflow import LangGraphWorkflow
from .voice_agent import VoiceAgent
from .analytics_agent import AnalyticsAgent
from ..services.ai.schema_context_builder import SchemaContextBuilder
from ..services.ai.prompt_builder import PromptBuilder
from ..services.ai.llm_service import LLMService, LLMServiceError
from ..services.ai.explanation_service import ExplanationService

logger = logging.getLogger(__name__)


class QueryAgent:
    """Entry point for all AI-driven SQL and analytics operations.

    Orchestrates specialized agents and services to provide a seamless
    experience for the end user.
    """

    def __init__(self) -> None:
        """Initialize all internal AI components."""
        # Services
        self.schema_builder = SchemaContextBuilder()
        self.prompt_builder = PromptBuilder()
        self.llm_service = LLMService()
        self.explanation_service = ExplanationService()

        # Agents
        self.workflow = LangGraphWorkflow()
        self.voice_agent = VoiceAgent(use_llm=True)
        self.analytics_agent = AnalyticsAgent(use_llm=True)

        logger.info("QueryAgent successfully initialized.")

    # ------------------------------------------------------------------
    # Main Pipeline Entry
    # ------------------------------------------------------------------

    def process_query(
        self,
        user_query: str,
        schema: Dict[str, Any],
        dialect: str = "mysql",
        result_columns: Optional[List[str]] = None,
        result_rows: Optional[List[List[Any]]] = None,
        context_hint: Optional[str] = None,
        mode: str = "text",
    ) -> Dict[str, Any]:
        """Run the full AI analytics pipeline.

        Parameters
        ----------
        user_query : str
            The user's question (or transcription if voice mode).
        schema : dict
            Database schema dictionary.
        dialect : str
            "mysql" or "postgresql".
        result_columns : list, optional
            Columns from query execution (triggers analytics insights).
        result_rows : list, optional
            Rows from query execution (triggers analytics insights).
        context_hint : str, optional
            Context from previous interactions.
        mode : str
            "text" or "voice".

        Returns
        -------
        dict
            Comprehensive response containing SQL, explanation, chart,
            insights, and confidence metrics.
        """
        try:
            self._validate_input(user_query, schema)

            # If voice mode, clean the query first before starting the workflow
            if mode == "voice":
                voice_result = self.voice_agent.process(user_query, context_hint=context_hint)
                active_query = voice_result["final_query"]
                logger.info("Voice query cleaned: '%s' -> '%s'", user_query, active_query)
            else:
                active_query = user_query

            # Run the LangGraph workflow
            workflow_result = self.workflow.run_pipeline(
                user_query=active_query,
                schema=schema,
                dialect=dialect,
                result_columns=result_columns,
                result_rows=result_rows,
                context_hint=context_hint,
                mode=mode
            )

            # Assemble frontend-ready payload
            return {
                "success":             workflow_result.get("success", False),
                "user_query":          user_query,
                "cleaned_query":       workflow_result.get("user_query"),  # This is the enhanced/voice-cleaned one
                "sql":                 workflow_result.get("sql", ""),
                "explanation":         workflow_result.get("explanation", ""),
                "confidence_score":    workflow_result.get("confidence_score", 0),
                "confidence_label":    workflow_result.get("confidence_label", "Low"),
                "recommended_chart":   workflow_result.get("recommended_chart", "table_only"),
                "chart_justification": workflow_result.get("chart_justification", ""),
                "warnings":            workflow_result.get("warnings", []),
                "ambiguities":         workflow_result.get("ambiguities", []),
                "insights":            workflow_result.get("insights", []),
                "insight_cards":       workflow_result.get("insight_cards", []),
                "narrative":           workflow_result.get("narrative"),
                "error":               workflow_result.get("error"),
                "status":              workflow_result.get("status"),
            }

        except Exception as exc:
            logger.exception("QueryAgent.process_query failed.")
            return {
                "success": False,
                "user_query": user_query,
                "error": str(exc),
                "status": "error"
            }

    # ------------------------------------------------------------------
    # Voice-specific Entry
    # ------------------------------------------------------------------

    def process_voice_input(
        self,
        raw_text: str,
        context_hint: Optional[str] = None
    ) -> Dict[str, Any]:
        """Clean and normalize a voice transcription into a query.

        This is used when the frontend only wants to clean the voice text
        before showing it to the user for confirmation.
        """
        return self.voice_agent.process(raw_text, context_hint=context_hint)

    # ------------------------------------------------------------------
    # Analytics-specific Entry
    # ------------------------------------------------------------------

    def generate_insights(
        self,
        columns: List[str],
        rows: List[List[Any]],
        user_query: str = ""
    ) -> Dict[str, Any]:
        """Generate insights for an existing set of results.

        Used when a query was executed and the user now wants AI analysis
        of those specific results.
        """
        return self.analytics_agent.analyze(columns, rows, user_query=user_query)

    # ------------------------------------------------------------------
    # Legacy / Utility
    # ------------------------------------------------------------------

    def generate_sql_only(
        self,
        user_query: str,
        schema: Dict[str, Any],
        dialect: str = "mysql"
    ) -> Dict[str, Any]:
        """Quickly generate SQL without running the full workflow."""
        try:
            self._validate_input(user_query, schema)
            context = self.schema_builder.build_context(schema)
            prompt = self.prompt_builder.build_sql_prompt(user_query, context, dialect)
            sql = self.llm_service.send_prompt(prompt)
            return {"success": True, "sql": sql.strip(), "error": None}
        except Exception as exc:
            return {"success": False, "sql": "", "error": str(exc)}

    @staticmethod
    def _validate_input(user_query: str, schema: Dict[str, Any]) -> None:
        """Basic validation for inputs."""
        if not user_query or not user_query.strip():
            raise ValueError("Query cannot be empty.")
        if not schema or "tables" not in schema:
            raise ValueError("Invalid schema provided.")