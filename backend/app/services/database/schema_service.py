"""
services/database/schema_service.py
─────────────────────────────────────
Business logic for loading, formatting, and serving database schema data.
"""
from __future__ import annotations

from typing import Any, Dict

from sqlalchemy import Engine

from app.db.schema_loader import format_schema_for_ai, load_schema
from app.core.logger import db_logger
from app.schemas.database_schema import DatabaseSchemaResponse


def get_schema(engine: Engine, *, force_refresh: bool = False) -> Dict[str, Any]:
    """
    Load the schema from the target database and return a frontend-friendly dict.

    Parameters
    ----------
    engine:        Active SQLAlchemy Engine for the target database.
    force_refresh: When True, bypass the TTL cache and re-inspect.

    Returns
    -------
    Raw schema dict (matches the structure of DatabaseSchemaResponse).
    """
    db_logger.info("SchemaService.get_schema called (force_refresh=%s)", force_refresh)
    raw = load_schema(engine, force_refresh=force_refresh)
    return raw


def get_schema_with_ai_prompt(
    engine: Engine, *, force_refresh: bool = False
) -> Dict[str, Any]:
    """
    Load the schema and enrich it with an AI-prompt–ready text block.

    Returns
    -------
    Schema dict with an additional ``ai_prompt_schema`` key.
    """
    raw = load_schema(engine, force_refresh=force_refresh)
    raw["ai_prompt_schema"] = format_schema_for_ai(raw)
    db_logger.debug("AI prompt schema generated (%d chars)", len(raw["ai_prompt_schema"]))
    return raw


def build_schema_response(schema_dict: Dict[str, Any]) -> DatabaseSchemaResponse:
    """
    Convert the raw schema dict produced by schema_loader into a validated
    Pydantic response model.
    """
    return DatabaseSchemaResponse(**schema_dict)


# ═══════════════════════════════════════════════════════════════════════════
# Schema compression — reduces prompt size for SQL generation
# ═══════════════════════════════════════════════════════════════════════════

import re
from typing import List, Set


def filter_schema_to_relevant_tables(
    schema: Dict[str, Any],
    user_query: str,
    max_tables: int = 8,
) -> Dict[str, Any]:
    """Return a copy of *schema* containing only the tables most relevant
    to *user_query*.

    Scoring
    -------
    Each table scores +1 for every query word that appears (case-insensitive
    substring match) in the table name, any column name, or any column type.

    FK expansion
    ------------
    Any table directly referenced by a FK from a top-scoring table (one hop)
    is automatically included even if its own score is zero.

    Fallback
    --------
    If all scores are zero (no match at all), the full schema is returned
    unchanged so the LLM never silently fails due to a missing table.
    """
    tables: List[Dict[str, Any]] = schema.get("tables", [])
    if not tables:
        return schema

    # ── Tokenize user query into lowercase words ─────────────────────
    query_words: List[str] = [
        w for w in re.split(r"[\s,;:.!?'\"()\[\]{}]+", user_query.lower())
        if len(w) >= 2  # skip single-char noise
    ]
    if not query_words:
        return schema

    # ── Score each table ─────────────────────────────────────────────
    scores: Dict[str, int] = {}
    for table in tables:
        tname = table["name"].lower()
        score = 0
        for word in query_words:
            # Match against table name
            if word in tname:
                score += 1
            # Match against column names and types
            for col in table.get("columns", []):
                if word in col["name"].lower():
                    score += 1
                if word in str(col.get("type", "")).lower():
                    score += 1
        scores[tname] = score

    # ── Fallback: if every score is 0, return the full schema ────────
    if max(scores.values()) == 0:
        db_logger.debug(
            "Schema filter: all scores zero for query '%s' — returning full schema.",
            user_query[:80],
        )
        return schema

    # ── Select top tables by score ───────────────────────────────────
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    selected: Set[str] = set()
    for tname, score in ranked:
        if score > 0 and len(selected) < max_tables:
            selected.add(tname)

    # ── FK expansion (one hop) ───────────────────────────────────────
    fk_additions: Set[str] = set()
    for table in tables:
        if table["name"].lower() in selected:
            for fk in table.get("foreign_keys", []):
                ref = fk.get("referred_table", "").lower()
                if ref and ref not in selected:
                    fk_additions.add(ref)
    selected |= fk_additions

    # ── Build filtered schema ────────────────────────────────────────
    filtered_tables = [t for t in tables if t["name"].lower() in selected]

    db_logger.info(
        "Schema filter: %d/%d tables selected for query '%s'.",
        len(filtered_tables), len(tables), user_query[:80],
    )

    return {
        **schema,
        "tables": filtered_tables,
        "table_count": len(filtered_tables),
    }
