"""
api/routes/query_routes.py
───────────────────────────
Endpoint for executing validated SQL queries against a target database.

POST /query — Validate, execute, and return structured results.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth_dependency import get_current_user
from app.api.dependencies.db_dependency import get_internal_db
from app.core.constants import TAG_QUERY
from app.core.logger import app_logger, query_logger
from app.db.models.query_history_model import QueryHistory
from app.db.models.user_model import User
from app.schemas.query_schema import (
    QueryExecuteRequest,
    QueryGenerateRequest,
    QueryGenerateResponse,
    InsightsRequest,
    InsightsResponse,
)
from app.schemas.response_schema import QueryResponse
from app.services.ai.sql_generator import SQLGenerator
from app.services.ai.explanation_service import ExplanationService
from app.agents import AnalyticsAgent, VisualizationAgent

from app.services.database.schema_service import get_schema
from app.services.database.connection_service import get_active_connection, get_engine
from app.services.database.connection_resolver import merge_connection_params, validate_connection_params
from app.services.database.query_executor import execute_query
from app.services.database.transaction_service import commit

router = APIRouter(prefix="/query", tags=[TAG_QUERY])

@router.post(
    "/generate",
    response_model=QueryGenerateResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate SQL using AI",
)
def generate_sql_endpoint(
    payload: QueryGenerateRequest,
    current_user: User = Depends(get_current_user),
) -> QueryGenerateResponse:
    conn_params = validate_connection_params(
        merge_connection_params(payload.model_dump(exclude_none=True), get_active_connection())
    )
    engine = get_engine(
        host=conn_params["host"], port=int(conn_params["port"]),
        username=conn_params["username"], password=conn_params["password"],
        database=conn_params["database"], database_type=conn_params["database_type"],
        file_path=conn_params.get("file_path"),
    )
    schema = get_schema(engine)
    
    generator = SQLGenerator(ai_model=payload.ai_model)
    gen_result = generator.generate_sql(
        payload.user_query,
        schema,
        dialect=conn_params["database_type"],
        row_limit=payload.row_limit,
    )
    
    if not gen_result.get("success"):
        return QueryGenerateResponse(success=False, sql_query="", error=gen_result.get("error"))
        
    sql_query = gen_result["sql"]
    
    explanation = None
    if payload.explanation_mode not in ("None", "No Explanation"):
        explainer = ExplanationService(ai_model=payload.ai_model)
        explain_result = explainer.explain_query(
            sql_query, 
            payload.user_query,
            explanation_mode=payload.explanation_mode or "Detailed Explanation"
        )
        if explain_result.get("success"):
            explanation = explain_result.get("explanation")
    
    return QueryGenerateResponse(success=True, sql_query=sql_query, explanation=explanation)


@router.post(
    "/execute",
    response_model=QueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute a SELECT SQL query",
    description=(
        "Accepts a validated SELECT SQL statement (optionally paired with the "
        "natural-language question that produced it), executes it securely "
        "against the target database, persists the run to history, and "
        "returns the tabular result."
    ),
)
def execute_sql_query(
    payload: QueryExecuteRequest,
    db: Session = Depends(get_internal_db),
    current_user: User = Depends(get_current_user),
) -> QueryResponse:
    """
    Secure SQL execution endpoint.

    Workflow
    --------
    1. Resolve (or create) the target engine via ConnectionManager.
    2. Delegate to query_executor (validation + execution).
    3. Persist result metadata to query_history.
    4. Return a QueryResponse envelope.
    """
    query_logger.info(
        "Query execute → db=%s type=%s sql=%.120s",
        payload.database, payload.database_type, payload.sql_query,
    )

    conn_params = validate_connection_params(
        merge_connection_params(payload.model_dump(exclude_none=True), get_active_connection())
    )

    engine = get_engine(
        host=conn_params["host"],
        port=int(conn_params["port"]),
        username=conn_params["username"],
        password=conn_params["password"],
        database=conn_params["database"],
        database_type=conn_params["database_type"],
        file_path=conn_params.get("file_path"),
    )

    result = execute_query(
        engine,
        payload.sql_query,
        row_limit=payload.row_limit,
        timeout=payload.timeout,
        user_query=payload.user_query,
    )

    # ── Persist to history ────────────────────────────────────────────────────
    _save_history(
        db=db,
        user_id=current_user.id,
        payload=payload,
        result=result,
        status="success",
    )

    return QueryResponse(
        success=True,
        message="Query executed successfully.",
        sql_query=result["sql_query"],
        user_query=result.get("user_query"),
        columns=result["columns"],
        rows=result["rows"],
        row_count=result["row_count"],
        execution_duration=result["execution_duration"],
        truncated=result["truncated"],
        explanation=result.get("explanation"),
    )


_visualization_agent = VisualizationAgent()


@router.post(
    "/insights",
    response_model=InsightsResponse,
    summary="Generate AI insights for a query result set",
)
def generate_query_insights(
    payload: InsightsRequest,
    current_user: User = Depends(get_current_user),
) -> InsightsResponse:
    """Accepts query result data and returns AI-powered insight cards,
    an executive narrative, a chart recommendation, and confidence info.
    """
    columns = payload.columns
    rows    = payload.rows
    user_q  = payload.user_query

    # ── 1. Analytics insight generation ───────────────────────────────────────
    try:
        agent = AnalyticsAgent(use_llm=True, ai_model=payload.ai_model)
        analytics_result = agent.analyze(
            columns=columns,
            rows=rows,
            user_query=user_q,
        )
        insight_cards = analytics_result.get("insight_cards", [])
        insights_list = analytics_result.get("insights", [])
        narrative     = analytics_result.get("narrative")
    except Exception:
        insight_cards = []
        insights_list = []
        narrative     = None

    # ── 2. Chart recommendation ────────────────────────────────────────────────
    try:
        chart_rec = _visualization_agent.recommend_chart(
            columns=columns,
            row_count=len(rows),
            user_query=user_q,
        )
        recommended_chart   = chart_rec.get("chart_type", "table_only")
        chart_justification = chart_rec.get("justification", "")
    except Exception:
        recommended_chart   = "table_only"
        chart_justification = ""

    # ── 3. Simple confidence heuristic (rule-based; real score comes from workflow) ─
    word_count  = len(user_q.split())
    conf_score  = min(0.95, 0.5 + word_count * 0.04)
    conf_label  = "High" if conf_score >= 0.75 else ("Medium" if conf_score >= 0.50 else "Low")

    return InsightsResponse(
        success             = True,
        insight_cards       = insight_cards,
        insights            = insights_list,
        narrative           = narrative,
        recommended_chart   = recommended_chart,
        chart_justification = chart_justification,
        confidence_score    = round(conf_score, 2),
        confidence_label    = conf_label,
        ambiguities         = [],
        warnings            = [],
    )


# ── Internal helpers ───────────────────────────────────────────────────────────

def _extract_table_names(sql: str) -> str | None:
    """Best-effort extraction of table names from a SELECT query."""
    # Simple regex to find words after FROM or JOIN
    import re
    matches = re.findall(r"\bFROM\s+([A-Za-z0-9_.]+)\b|\bJOIN\s+([A-Za-z0-9_.]+)\b", sql, re.IGNORECASE)
    tables = [m[0] or m[1] for m in matches]
    return ",".join(set(tables)) if tables else None

def _save_history(
    db: Session,
    user_id: int,
    payload: QueryExecuteRequest,
    result: dict,
    status: str,
    error_message: str | None = None,
) -> None:
    """Persist a query run to the internal query_history table."""
    try:
        active_config = get_active_connection()
        record = QueryHistory(
            user_id=user_id,
            database_type=payload.database_type or (active_config.get("database_type") if active_config else "unknown"),
            database_name=payload.database or (active_config.get("database") if active_config else "unknown"),
            user_query=payload.user_query,
            generated_sql=payload.sql_query,
            row_count=result.get("row_count", 0),
            execution_duration=result.get("execution_duration", 0.0),
            status=status,
            error_message=error_message,
        )
        db.add(record)
        
        commit(db)
        query_logger.debug("History record saved.")
    except Exception:
        app_logger.warning("Failed to persist query history — non-fatal.", exc_info=True)
