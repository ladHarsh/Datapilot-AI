"""
response_parser.py — SQL AI Analytics Platform.

Parses and validates raw LLM text responses into structured dictionaries.
All parsing logic is centralized here to avoid duplication in agents/services.

Author : Member 2 — AI/LLM Engineer
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from .sql_cleaner import strip_markdown, is_select_only

logger = logging.getLogger(__name__)


def parse_sql_response(raw: str) -> Dict[str, Any]:
    """Extract and clean an SQL query from an LLM response.

    Returns
    -------
    dict
        ``{sql, valid, error}``
    """
    if not raw or not raw.strip():
        return {"sql": "", "valid": False, "error": "Empty response from LLM."}

    sql = strip_markdown(raw)
    sql = re.sub(r"\s+", " ", sql).strip()

    if not sql:
        return {"sql": "", "valid": False, "error": "Only markdown fence found, no SQL."}

    valid = is_select_only(sql)
    return {
        "sql": sql,
        "valid": valid,
        "error": None if valid else "Response is not a valid read-only SQL query.",
    }


def parse_chart_response(raw: str) -> Dict[str, Any]:
    """Extract chart type and justification from LLM response.

    Expected LLM format:
        bar_chart
        Justification: Comparing discrete categories.

    Returns
    -------
    dict
        ``{chart_type, justification}``
    """
    from .ai_constants import SUPPORTED_CHARTS, CHART_TABLE_ONLY

    lines = [l.strip() for l in raw.strip().splitlines() if l.strip()]
    if not lines:
        return {"chart_type": CHART_TABLE_ONLY, "justification": "No response."}

    # First line should be the chart type
    chart_type = lines[0].lower().strip().replace(" ", "_")
    if chart_type not in SUPPORTED_CHARTS:
        # Try to find a supported chart name anywhere in the response
        for supported in SUPPORTED_CHARTS:
            if supported in raw.lower():
                chart_type = supported
                break
        else:
            chart_type = CHART_TABLE_ONLY

    # Remaining lines form the justification
    justification = ""
    for line in lines[1:]:
        line = re.sub(r"^justification[:\s]*", "", line, flags=re.IGNORECASE)
        if line:
            justification = line
            break

    return {"chart_type": chart_type, "justification": justification}


def parse_explanation_response(raw: str) -> str:
    """Clean and normalise an explanation response.

    Removes common AI preamble, limits to 4 sentences.
    """
    if not raw:
        return ""

    # Remove common AI filler openers
    preamble = [
        r"^sure[,!.]?\s*",
        r"^of course[,!.]?\s*",
        r"^here('s| is) .*?:\s*",
        r"^this sql query",
        r"^the sql query",
    ]
    text = raw.strip()
    for pat in preamble:
        text = re.sub(pat, "", text, flags=re.IGNORECASE)

    # Limit to 4 sentences
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    if len(sentences) > 4:
        text = " ".join(sentences[:4])

    return text.strip().capitalize()


def parse_json_response(raw: str) -> Optional[Dict[str, Any]]:
    """Attempt to extract and parse a JSON object from an LLM response.

    Handles responses where JSON is embedded inside markdown fences.
    """
    # Remove markdown fences
    cleaned = re.sub(r"```(?:json)?\n?", "", raw, flags=re.IGNORECASE)
    cleaned = cleaned.replace("```", "").strip()

    # Find the first { ... } or [ ... ] block
    match = re.search(r"(\{.*\}|\[.*\])", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError as e:
            logger.warning("JSON parse failed: %s", e)
    return None


def extract_insight_list(raw: str) -> List[str]:
    """Extract a bulleted or numbered list of insights from LLM output.

    Returns a list of cleaned insight strings.
    """
    lines = raw.strip().splitlines()
    insights: List[str] = []
    for line in lines:
        # Strip list markers: -, *, 1., 2., etc.
        cleaned = re.sub(r"^[-*\d.)\s]+", "", line).strip()
        if len(cleaned) > 10:  # ignore very short fragments
            insights.append(cleaned)
    return insights
