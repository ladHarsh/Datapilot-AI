"""
voice_workflow.py — SQL AI Analytics Platform.

Entry point for the Voice → SQL pipeline.

Flow:
  Raw Voice Text → VoiceAgent (clean + enhance) → SQL Workflow → Response

The workflow validates the raw transcription, passes it through voice
cleaning/enhancement, then delegates to the full SQL workflow.

Author : Member 2 — AI/LLM Engineer
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from ..agents.query_agent import QueryAgent
from ..utils.schema_formatter import validate_schema

logger = logging.getLogger(__name__)


def run(
    raw_voice_text: str,
    schema: Dict[str, Any],
    dialect: str = "mysql",
    context_hint: Optional[str] = None,
) -> Dict[str, Any]:
    """Run the full voice-to-SQL pipeline.

    Parameters
    ----------
    raw_voice_text : str
        Raw output from a speech-to-text engine.
    schema : dict
        Database schema dictionary.
    dialect : str
        "mysql" or "postgresql".
    context_hint : str, optional
        Previous conversation context.

    Returns
    -------
    dict
        Full result including cleaned query, SQL, explanation, and chart.
    """
    if not raw_voice_text or not raw_voice_text.strip():
        return {
            "success": False,
            "error": "Voice input cannot be empty.",
            "status": "validation_error",
        }

    errors = validate_schema(schema)
    if errors:
        return {
            "success": False,
            "error": f"Invalid schema: {'; '.join(errors)}",
            "status": "validation_error",
        }

    logger.info("[Voice Workflow] Input: '%s…'", raw_voice_text[:60])

    agent = QueryAgent()
    result = agent.process_query(
        user_query=raw_voice_text,
        schema=schema,
        dialect=dialect,
        context_hint=context_hint,
        mode="voice",
    )

    logger.info(
        "[Voice Workflow] Complete — cleaned='%s…' success=%s",
        result.get("cleaned_query", "")[:40],
        result.get("success"),
    )
    return result


def clean_voice_only(raw_voice_text: str) -> Dict[str, Any]:
    """Clean a voice query without running the SQL pipeline.

    Use this when the frontend wants to show the user their cleaned query
    before submitting for SQL generation.
    """
    if not raw_voice_text or not raw_voice_text.strip():
        return {"success": False, "error": "Empty voice input."}

    agent = QueryAgent()
    return agent.process_voice_input(raw_voice_text)
