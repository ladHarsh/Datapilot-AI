"""
sql_generation_workflow.py — SQL AI Analytics Platform.

Entry point and orchestration layer for the Text-to-SQL pipeline.

Responsibility:
  Receive user query + schema → coordinate agents/services → return SQL result.

This module separates orchestration from the Agent and Service layers.
Agents do AI reasoning; this workflow coordinates the sequence.

Flow:
  Query Enhancement → Schema Context → SQL Generation → Confidence → Response

Author : Member 2 — AI/LLM Engineer
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..agents.query_agent import QueryAgent
from ..cache.schema_cache import SchemaCache
from ..utils.schema_formatter import validate_schema

logger = logging.getLogger(__name__)

# Shared schema cache across requests
_schema_cache = SchemaCache()


def run(
    user_query: str,
    schema: Dict[str, Any],
    dialect: str = "mysql",
    context_hint: Optional[str] = None,
    mode: str = "text",
) -> Dict[str, Any]:
    """Run the full SQL generation workflow.

    Parameters
    ----------
    user_query : str
        Natural-language question from the user.
    schema : dict
        Database schema dictionary.
    dialect : str
        "mysql" or "postgresql".
    context_hint : str, optional
        Context from previous turn for conversational queries.
    mode : str
        "text" or "voice".

    Returns
    -------
    dict
        Full pipeline result including SQL, explanation, confidence, and chart.
    """
    # 1. Validate schema up front
    errors = validate_schema(schema)
    if errors:
        return {
            "success": False,
            "error": f"Invalid schema: {'; '.join(errors)}",
            "status": "validation_error",
        }

    # 2. Validate query
    if not user_query or not user_query.strip():
        return {
            "success": False,
            "error": "Query cannot be empty.",
            "status": "validation_error",
        }

    logger.info("[SQL Workflow] Starting — query='%s…' dialect=%s mode=%s",
                user_query[:60], dialect, mode)

    # 3. Run the agent pipeline
    agent = QueryAgent()
    result = agent.process_query(
        user_query=user_query,
        schema=schema,
        dialect=dialect,
        context_hint=context_hint,
        mode=mode,
    )

    logger.info(
        "[SQL Workflow] Complete — success=%s sql_len=%d",
        result.get("success"),
        len(result.get("sql", "")),
    )
    return result


def run_sql_only(
    user_query: str,
    schema: Dict[str, Any],
    dialect: str = "mysql",
) -> Dict[str, Any]:
    """Lightweight SQL-only workflow (no explanation or chart).

    Used for quick validation and testing.
    """
    errors = validate_schema(schema)
    if errors:
        return {"success": False, "sql": "", "error": f"Invalid schema: {'; '.join(errors)}"}

    agent = QueryAgent()
    return agent.generate_sql_only(user_query, schema, dialect)
