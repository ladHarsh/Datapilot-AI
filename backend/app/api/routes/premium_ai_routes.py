"""
api/routes/premium_ai_routes.py
─────────────────────────────────
On-demand premium AI endpoints — Deep Reasoning & Reports Layer.

These endpoints are intentionally slower and user-triggered.
They power the "✨ Optimize Query" and "📄 Business Report" features.

POST /query/optimize
    Uses Nemotron 120B for deep SQL optimization, index recommendations,
    bottleneck analysis, and intelligent follow-up query suggestions.

POST /query/generate-report
    Uses GPT-OSS 120B for professional multi-paragraph business reports
    summarizing query results with trends and executive observations.

Author: DataPilot AI Team
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.dependencies.auth_dependency import get_current_user
from app.core.constants import TAG_QUERY
from app.core.model_config import QUERY_OPTIMIZER_MODEL, REPORT_MODEL
from app.db.models.user_model import User
from app.services.ai.llm_service import LLMService, LLMServiceError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/query", tags=[TAG_QUERY])


# ─── Request / Response schemas ──────────────────────────────────────────────

class OptimizeQueryRequest(BaseModel):
    sql:        str = Field(..., min_length=1)
    user_query: str = Field(..., min_length=1)
    dialect:    str = Field("mysql", pattern="^(mysql|postgresql|sqlite)$")
    schema_context: Optional[str] = None   # optional serialized schema info
    execution_ms:   Optional[float] = None  # measured execution time for context


class OptimizeQueryResponse(BaseModel):
    success:              bool
    optimized_sql:        Optional[str]   = None
    bottleneck_analysis:  Optional[str]   = None
    index_recommendations: List[str]      = []
    follow_up_queries:    List[str]       = []
    model_used:           Optional[str]   = None
    error:                Optional[str]   = None


class GenerateReportRequest(BaseModel):
    sql:         str = Field(..., min_length=1)
    user_query:  str = Field(..., min_length=1)
    columns:     List[str]           = []
    rows:        List[Dict[str, Any]] = []
    explanation: Optional[str]       = None


class GenerateReportResponse(BaseModel):
    success:           bool
    report_markdown:   Optional[str] = None
    executive_summary: Optional[str] = None
    model_used:        Optional[str] = None
    error:             Optional[str] = None


# ─── Helper: build optimizer prompt ──────────────────────────────────────────

def _build_optimizer_prompt(
    sql: str,
    user_query: str,
    dialect: str,
    schema_context: Optional[str],
    execution_ms: Optional[float],
) -> str:
    schema_section = f"\n\nDatabase Schema:\n{schema_context}" if schema_context else ""
    perf_section   = f"\n\nMeasured execution time: {execution_ms:.1f}ms" if execution_ms else ""

    return f"""You are a senior database performance engineer and SQL expert.

Analyze the following SQL query and provide expert optimization recommendations.

User Request: {user_query}
SQL Dialect: {dialect}{schema_section}{perf_section}

SQL to Analyze:
```sql
{sql}
```

Provide your response in this exact structure:

## Optimized SQL
Provide a rewritten, optimized version of the SQL. If the query is already optimal, state that clearly.

## Bottleneck Analysis
Identify the 2-3 key performance bottlenecks in the original query (e.g., missing indexes, full table scans, inefficient JOINs, subquery anti-patterns).

## Index Recommendations
List specific CREATE INDEX statements that would most improve this query's performance.

## Intelligent Follow-Up Queries
Suggest 3 related analytical queries the user might want to run next, formatted as natural language questions.

Be concise, precise, and actionable. Focus on real performance impact."""


def _build_report_prompt(
    sql: str,
    user_query: str,
    columns: List[str],
    rows: List[Dict[str, Any]],
    explanation: Optional[str],
) -> str:
    # Summarize data for the prompt (don't send all rows to LLM)
    sample_rows = rows[:10]
    col_str  = ", ".join(columns) if columns else "N/A"
    row_str  = "\n".join(str(r) for r in sample_rows) if sample_rows else "No data"
    row_count = len(rows)

    exp_section = f"\n\nQuery Explanation:\n{explanation}" if explanation else ""

    return f"""You are a business analyst writing a clear, simple report based on query results.

User's Question: {user_query}
Total Rows Returned: {row_count}
Columns: {col_str}{exp_section}

Sample Data (first 10 rows):
{row_str}

Write a short, easy-to-read business report with these exact sections.
Use ONLY standard markdown: ## for headings, - for bullet points, and plain text.
Do NOT use **bold** markers, *italic* markers, or any special symbols.
Keep the language simple — write as if explaining to a non-technical manager.

## Executive Summary
2 sentences. What did the data show? State the single most important finding.

## Key Insights
3-4 bullet points. Each bullet = one clear, specific finding from the data.
Include actual numbers from the data where relevant.

## Business Observations
2 short paragraphs. What does this mean for the business?
Mention any trends, risks, or opportunities — be specific, not generic.

## Recommended Actions
2-3 bullet points. Concrete next steps based on the data.
Each action should be specific and actionable.

Rules:
- Use short sentences. One idea per sentence.
- Use actual values from the data.
- Do not add any sections beyond the four listed above.
- Do not use asterisks, underscores, or markdown formatting within the text."""



# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.post(
    "/optimize",
    response_model=OptimizeQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="✨ Optimize Query — Deep SQL analysis with Nemotron 120B",
    description=(
        "On-demand deep SQL optimization. Uses Nemotron 120B for advanced reasoning. "
        "Returns optimized SQL, index recommendations, bottleneck analysis, "
        "and intelligent follow-up query suggestions. "
        "This endpoint is intentionally slower (10-60s) — it is user-triggered."
    ),
)
async def optimize_query(
    payload: OptimizeQueryRequest,
    current_user: User = Depends(get_current_user),
) -> OptimizeQueryResponse:
    """Deep SQL optimization using Nemotron 120B."""

    prompt = _build_optimizer_prompt(
        sql=payload.sql,
        user_query=payload.user_query,
        dialect=payload.dialect,
        schema_context=payload.schema_context,
        execution_ms=payload.execution_ms,
    )

    # Try Nemotron first, fall back to any available model
    model_used = QUERY_OPTIMIZER_MODEL
    raw_response: Optional[str] = None

    for model_override in (QUERY_OPTIMIZER_MODEL, None):
        try:
            llm = LLMService(model_override=model_override)
            llm.max_tokens = 2048
            raw_response = llm.send_prompt(prompt)
            model_used = model_override or llm.model
            break
        except LLMServiceError as exc:
            logger.warning("Optimizer LLM failed (model=%s): %s", model_override, exc)
            if model_override is None:
                return OptimizeQueryResponse(
                    success=False,
                    error=f"All AI providers failed: {exc}",
                )

    if not raw_response:
        return OptimizeQueryResponse(success=False, error="Empty response from optimizer.")

    # Parse sections from response
    sections = _parse_markdown_sections(raw_response)

    opt_sql    = sections.get("Optimized SQL", "").strip()
    bottleneck = sections.get("Bottleneck Analysis", "").strip()
    indexes_raw = sections.get("Index Recommendations", "")
    followups_raw = sections.get("Intelligent Follow-Up Queries", "")

    index_recs = [
        line.strip("- ").strip()
        for line in indexes_raw.split("\n")
        if line.strip() and not line.strip().startswith("#")
    ]
    follow_ups = [
        line.strip("- 0123456789.").strip()
        for line in followups_raw.split("\n")
        if line.strip() and not line.strip().startswith("#")
    ]

    logger.info(
        "optimize_query complete for user %s | model=%s", current_user.id, model_used
    )

    return OptimizeQueryResponse(
        success=True,
        optimized_sql=opt_sql or payload.sql,
        bottleneck_analysis=bottleneck,
        index_recommendations=[r for r in index_recs if r][:6],
        follow_up_queries=[f for f in follow_ups if f][:5],
        model_used=str(model_used),
    )


@router.post(
    "/generate-report",
    response_model=GenerateReportResponse,
    status_code=status.HTTP_200_OK,
    summary="📄 Generate Business Report — GPT-OSS 120B",
    description=(
        "On-demand professional business report generation. Uses GPT-OSS 120B. "
        "Produces a structured markdown report with executive summary, key insights, "
        "business observations, and recommended actions. "
        "This endpoint is intentionally slower (15-60s) — it is user-triggered."
    ),
)
async def generate_report(
    payload: GenerateReportRequest,
    current_user: User = Depends(get_current_user),
) -> GenerateReportResponse:
    """Professional business report using GPT-OSS 120B."""

    prompt = _build_report_prompt(
        sql=payload.sql,
        user_query=payload.user_query,
        columns=payload.columns,
        rows=payload.rows,
        explanation=payload.explanation,
    )

    model_used = REPORT_MODEL
    raw_response: Optional[str] = None

    for model_override in (REPORT_MODEL, None):
        try:
            llm = LLMService(model_override=model_override)
            llm.max_tokens = 3000
            raw_response = llm.send_prompt(prompt)
            model_used = model_override or llm.model
            break
        except LLMServiceError as exc:
            logger.warning("Report LLM failed (model=%s): %s", model_override, exc)
            if model_override is None:
                return GenerateReportResponse(
                    success=False,
                    error=f"All AI providers failed: {exc}",
                )

    if not raw_response:
        return GenerateReportResponse(success=False, error="Empty response from report model.")

    sections = _parse_markdown_sections(raw_response)
    exec_summary = sections.get("Executive Summary", "").strip()

    logger.info(
        "generate_report complete for user %s | model=%s", current_user.id, model_used
    )

    return GenerateReportResponse(
        success=True,
        report_markdown=raw_response.strip(),
        executive_summary=exec_summary,
        model_used=str(model_used),
    )


# ─── Utility ─────────────────────────────────────────────────────────────────

def _parse_markdown_sections(text: str) -> Dict[str, str]:
    """Parse a markdown response into a dict of section_title → content."""
    sections: Dict[str, str] = {}
    current_title = ""
    current_lines: List[str] = []

    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("## "):
            if current_title:
                sections[current_title] = "\n".join(current_lines).strip()
            current_title = stripped[3:].strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_title:
        sections[current_title] = "\n".join(current_lines).strip()

    return sections
