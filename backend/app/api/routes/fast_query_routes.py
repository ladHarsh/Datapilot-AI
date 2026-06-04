"""
api/routes/fast_query_routes.py
────────────────────────────────
High-performance AI query endpoint — DataPilot Speed Engine.

POST /query/fast-analyze
    ┌─ Phase 1 (≤ 2-5s) ───────────────────────────────────────────┐
    │  Classify complexity → Extract schema → Generate SQL          │
    │  Execute SQL → Return sql + data IMMEDIATELY                  │
    └───────────────────────────────────────────────────────────────┘
    ┌─ Phase 2 (≤ 10-15s, background via SSE stream) ──────────────┐
    │  Explanation + Insights + Chart — run in PARALLEL             │
    │  Stream each result chunk as it completes                     │
    └───────────────────────────────────────────────────────────────┘

GET  /query/stream-analyze
    Full SSE streaming endpoint — sends live pipeline stage updates.

GET  /query/cache-stats
    Returns performance cache statistics.

Author: DataPilot Performance Team
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, AsyncGenerator, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.dependencies.auth_dependency import get_current_user
from app.core.constants import TAG_QUERY
from app.db.models.user_model import User
from app.services.ai.llm_service import LLMService
from app.services.ai.sql_generator import SQLGenerator
from app.services.ai.explanation_service import ExplanationService
from app.services.ai.query_complexity import classify_query, QueryComplexity
from app.services.ai.intent_detector import IntentDetector
from app.services.ai.performance_cache import (
    schema_context_cache, sql_result_cache, explanation_cache, insights_cache, chart_cache,
    make_schema_key, make_query_key, make_explanation_key, make_data_key, make_chart_key,
    get_all_cache_stats,
)
from app.agents.analytics_agent import AnalyticsAgent
from app.agents.visualization_agent import VisualizationAgent
from app.services.database.schema_service import get_schema, filter_schema_to_relevant_tables
from app.services.database.connection_service import get_active_connection, get_engine
from app.services.database.connection_resolver import merge_connection_params, validate_connection_params
from app.services.database.query_executor import execute_query
from app.core.exceptions import QueryExecutionError, QueryTimeoutError, InvalidSQLException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/query", tags=[TAG_QUERY])

# Shared executor for running blocking LLM calls off the event loop
_executor = ThreadPoolExecutor(max_workers=6, thread_name_prefix="dp-ai")

# Singleton agents (instantiated once, reused — avoids per-request init cost)
_visualization_agent = VisualizationAgent()

from app.core.model_config import (
    SQL_FAST_MODEL as _SQL_FAST_MODEL,
    EXPLANATION_FAST_MODEL,
    INSIGHTS_FAST_MODEL,
)

# Alias for readability inside this module
EXPLANATION_FALLBACK_MODEL = "gemini-2.5-flash"


# ─── Request / Response schemas ──────────────────────────────────────────────

class FastAnalyzeRequest(BaseModel):
    user_query: str                 = Field(..., min_length=1)
    ai_model:   Optional[str]      = None
    explanation_mode: str          = Field("Detailed", pattern="^(Detailed|Brief|None)$")
    auto_insights: bool            = True
    row_limit:  int                = Field(100, ge=1, le=2000)

    # Connection params (same as existing endpoints)
    host:          Optional[str]   = None
    port:          Optional[int]   = None
    username:      Optional[str]   = None
    password:      Optional[str]   = None
    database:      Optional[str]   = None
    database_type: Optional[str]   = None
    file_path:     Optional[str]   = None


class FastAnalyzeResponse(BaseModel):
    success:          bool
    complexity:       str
    complexity_reason: str
    sql:              str
    columns:          List[str]
    rows:             List[Dict[str, Any]]
    row_count:        int
    execution_duration: float
    explanation:      Optional[str]  = None
    insight_cards:    List[Any]      = []
    narrative:        Optional[str]  = None
    recommended_chart: Optional[str] = None
    chart_justification: str         = ""
    confidence_score: Optional[float] = None
    confidence_label: Optional[str]   = None
    ambiguities:      List[str]       = []
    warnings:         List[str]       = []
    cache_hit:        bool            = False
    timing:           Dict[str, float] = {}
    error:            Optional[str]    = None


# ─── Core helpers ─────────────────────────────────────────────────────────────

def _get_engine_from_request(payload: FastAnalyzeRequest):
    """Resolve SQLAlchemy engine from request payload + active session."""
    conn_params = validate_connection_params(
        merge_connection_params(payload.model_dump(exclude_none=True), get_active_connection())
    )
    raw_port = conn_params.get("port")
    try:
        port = int(raw_port) if raw_port is not None else 0
    except (ValueError, TypeError):
        port = 0

    return get_engine(
        host=conn_params["host"],
        port=port,
        username=conn_params["username"],
        password=conn_params["password"],
        database=conn_params["database"],
        database_type=conn_params["database_type"],
        file_path=conn_params.get("file_path"),
    ), conn_params


def _run_explanation(sql: str, user_query: str, mode: str, ai_model: Optional[str]) -> str:
    """Blocking explanation call — runs in thread pool."""
    exp_key = make_explanation_key(sql, mode)
    cached = explanation_cache.get(exp_key)
    if cached:
        logger.info("Cache HIT — explanation [key=%s]", exp_key)
        return cached

    for model in (EXPLANATION_FAST_MODEL, ai_model):
        try:
            svc = ExplanationService(ai_model=model)
            result = svc.explain_query(sql, user_query, explanation_mode=mode)
            if result.get("success"):
                explanation_cache.set(exp_key, result["explanation"])
                return result["explanation"]
        except Exception as exc:
            logger.warning("Explanation failed on model %s: %s — trying fallback", model, exc)
    return ExplanationService()._generate_fallback(sql, user_query)


def _run_insights(
    columns: List[str],
    rows: List[List[Any]],
    user_query: str,
    ai_model: Optional[str],
) -> Dict[str, Any]:
    """Blocking analytics call — runs in thread pool."""
    # Check cache first
    data_key = make_data_key(columns, rows)
    cached = insights_cache.get(data_key)
    if cached:
        logger.info("Cache HIT — insights [key=%s]", data_key)
        return cached

    try:
        # Always use the fast insights model (Groq), not the user-selected model
        agent = AnalyticsAgent(use_llm=True, ai_model=INSIGHTS_FAST_MODEL)
        result = agent.analyze(columns=columns, rows=rows, user_query=user_query)
        insights_cache.set(data_key, result)
        return result
    except Exception as exc:
        logger.warning("Insights failed: %s", exc)
        return {"insight_cards": [], "narrative": None}


def _run_chart(
    columns: List[str],
    row_count: int,
    user_query: str,
    sql: str,
) -> Dict[str, Any]:
    """Chart recommendation — ALWAYS rule-based (no LLM, instant response)."""
    chart_key = make_chart_key(columns, user_query)
    cached = chart_cache.get(chart_key)
    if cached:
        logger.info("Cache HIT — chart [key=%s]", chart_key)
        return cached

    try:
        # Use rule-based fast path directly — bypasses LLM entirely
        result = _visualization_agent.recommend_chart_fast(
            columns=columns,
            row_count=row_count,
            user_query=user_query,
            sql_query=sql,
        )
        chart_cache.set(chart_key, result)
        return result
    except Exception as exc:
        logger.warning("Chart recommendation failed: %s", exc)
        return {"chart_type": "table_only", "justification": ""}


# ─── Main fast endpoint ────────────────────────────────────────────────────────

@router.post(
    "/fast-analyze",
    response_model=FastAnalyzeResponse,
    status_code=status.HTTP_200_OK,
    summary="🚀 Fast AI Analysis — SQL + Execute + Insights in one optimized call",
    description=(
        "Optimized pipeline: classify complexity → generate SQL → execute → "
        "run explanation + insights + chart in parallel background threads. "
        "Typical latency: EASY 3-5s, MEDIUM 8-15s, HARD 15-25s."
    ),
)
async def fast_analyze(
    payload: FastAnalyzeRequest,
    current_user: User = Depends(get_current_user),
) -> FastAnalyzeResponse:
    timing: Dict[str, float] = {}
    t_start = time.monotonic()

    # ── Step 0: Classify query complexity (< 1ms) ─────────────────────────────
    complexity, complexity_reason = classify_query(payload.user_query)
    timing["complexity_ms"] = round((time.monotonic() - t_start) * 1000, 1)
    logger.info(
        "Query complexity: %s — '%s'", complexity.value, payload.user_query[:60]
    )

    # ── Step 1: Resolve engine + schema ───────────────────────────────────────
    t_schema = time.monotonic()
    try:
        engine, conn_params = _get_engine_from_request(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Connection failed: {exc}")

    # Schema context cache — avoid re-introspecting on every request
    schema_key = make_schema_key(
        conn_params.get("host", ""),
        conn_params.get("database", ""),
        conn_params.get("database_type", ""),
    )
    full_schema = schema_context_cache.get(schema_key)
    if not full_schema:
        full_schema = get_schema(engine)
        schema_context_cache.set(schema_key, full_schema)
    schema = filter_schema_to_relevant_tables(full_schema, payload.user_query)
    timing["schema_ms"] = round((time.monotonic() - t_schema) * 1000, 1)

    # ── Step 1.5: Intent Detection ────────────────────────────────────────────
    t_intent = time.monotonic()
    detector = IntentDetector()
    intent_res = detector.detect_intent(
        payload.user_query,
        schema=schema,
        dialect=conn_params.get("database_type", "mysql")
    )
    timing["intent_detect_ms"] = round((time.monotonic() - t_intent) * 1000, 1)

    if intent_res["intent"] == "Conversation":
        return FastAnalyzeResponse(
            success=True,
            complexity="easy",
            complexity_reason="Conversational greeting/pleasantry",
            sql="",
            columns=[],
            rows=[],
            row_count=0,
            execution_duration=0.0,
            explanation=intent_res["response"],
            timing=timing,
        )

    if intent_res["intent"] == "Ambiguous":
        return FastAnalyzeResponse(
            success=True,
            complexity="easy",
            complexity_reason="Ambiguous database input",
            sql="",
            columns=[],
            rows=[],
            row_count=0,
            execution_duration=0.0,
            explanation="It looks like your query is ambiguous. Did you mean one of these?",
            ambiguities=intent_res["suggestions"],
            timing=timing,
        )

    # ── Step 2: SQL Generation (with cache) ───────────────────────────────────
    t_sql = time.monotonic()
    query_key = make_query_key(payload.user_query, schema_key, conn_params.get("database_type", "mysql"))
    cached_sql_result = sql_result_cache.get(query_key)

    if cached_sql_result:
        logger.info("Cache HIT — SQL [key=%s]", query_key)
        sql = cached_sql_result["sql"]
        cache_hit = True
    else:
        cache_hit = False
        loop = asyncio.get_event_loop()
        generator = SQLGenerator(ai_model=_SQL_FAST_MODEL)
        gen_result = await loop.run_in_executor(
            _executor,
            lambda: generator.generate_sql(
                payload.user_query,
                schema,
                dialect=conn_params.get("database_type", "mysql"),
            ),
        )
        if not gen_result.get("success"):
            return FastAnalyzeResponse(
                success=False,
                complexity=complexity.value,
                complexity_reason=complexity_reason,
                sql="",
                columns=[],
                rows=[],
                row_count=0,
                execution_duration=0.0,
                error=gen_result.get("error", "SQL generation failed"),
                timing=timing,
            )
        sql = gen_result["sql"]

    timing["sql_gen_ms"] = round((time.monotonic() - t_sql) * 1000, 1)

    # ── Step 3: Execute SQL (with execution-error retry) ──────────────────────
    t_exec = time.monotonic()
    loop = asyncio.get_event_loop()

    _MAX_EXEC_RETRIES = 2
    exec_result = None
    exec_error_msg: Optional[str] = None

    for _exec_attempt in range(1 + _MAX_EXEC_RETRIES):
        try:
            exec_result = await loop.run_in_executor(
                _executor,
                lambda _sql=sql: execute_query(
                    engine,
                    _sql,
                    row_limit=payload.row_limit,
                    timeout=30,
                    user_query=payload.user_query,
                ),
            )
            exec_error_msg = None
            break  # execution succeeded — exit retry loop

        except InvalidSQLException as exc:
            logger.warning("SQL validation blocked execution: %s", exc)
            return FastAnalyzeResponse(
                success=True,
                complexity=complexity.value,
                complexity_reason=complexity_reason,
                sql="",
                columns=[],
                rows=[],
                row_count=0,
                execution_duration=0.0,
                explanation="",
                insight_cards=[],
                narrative="Sorry, I cannot modify or delete database data. DataPilot AI is a read-only analytics platform designed for querying and analyzing data only.",
                recommended_chart="table_only",
                timing=timing,
            )

        except QueryTimeoutError as exc:
            logger.warning("SQL execution timed out (attempt %d): %s", _exec_attempt + 1, exc)
            return FastAnalyzeResponse(
                success=False,
                complexity=complexity.value,
                complexity_reason=complexity_reason,
                sql=sql,
                columns=[],
                rows=[],
                row_count=0,
                execution_duration=0.0,
                error=str(exc),
                timing=timing,
            )

        except (QueryExecutionError, Exception) as exc:
            exec_error_msg = str(exc)
            logger.warning(
                "SQL execution failed (attempt %d/%d): %s",
                _exec_attempt + 1, 1 + _MAX_EXEC_RETRIES, exec_error_msg,
            )

            if _exec_attempt >= _MAX_EXEC_RETRIES:
                # Exhausted retries — return clean error response
                return FastAnalyzeResponse(
                    success=False,
                    complexity=complexity.value,
                    complexity_reason=complexity_reason,
                    sql=sql,
                    columns=[],
                    rows=[],
                    row_count=0,
                    execution_duration=0.0,
                    error=f"Database execution failed: {exec_error_msg}",
                    timing=timing,
                )

            # Re-generate SQL with the DB error as correction context
            logger.info("Regenerating SQL with execution error context (attempt %d)…", _exec_attempt + 2)
            regen_generator = SQLGenerator(ai_model=_SQL_FAST_MODEL)
            regen_result = await loop.run_in_executor(
                _executor,
                lambda _err=exec_error_msg: regen_generator.generate_sql(
                    payload.user_query + f"\n\n[PREVIOUS SQL FAILED WITH: {_err}. Fix the SQL to avoid this error.]",
                    schema,
                    dialect=conn_params.get("database_type", "mysql"),
                ),
            )
            if regen_result.get("success") and regen_result.get("sql"):
                sql = regen_result["sql"]
                cache_hit = False  # don't use stale cache for corrected SQL
                logger.info("SQL regenerated successfully on correction attempt %d.", _exec_attempt + 2)
            else:
                logger.warning("SQL regeneration also failed — aborting.")
                return FastAnalyzeResponse(
                    success=False,
                    complexity=complexity.value,
                    complexity_reason=complexity_reason,
                    sql=sql,
                    columns=[],
                    rows=[],
                    row_count=0,
                    execution_duration=0.0,
                    error=f"Database execution failed and SQL correction also failed: {exec_error_msg}",
                    timing=timing,
                )

    timing["sql_exec_ms"] = round((time.monotonic() - t_exec) * 1000, 1)

    columns = exec_result.get("columns", []) if exec_result else []
    rows    = exec_result.get("rows", []) if exec_result else []
    exec_dur = exec_result.get("execution_duration", 0.0) if exec_result else 0.0

    # Cache the successful SQL for future identical queries
    if not cache_hit and sql and exec_result:
        sql_result_cache.set(query_key, {"sql": sql})

    # ── Step 4: Parallel background tasks ─────────────────────────────────────
    # Explanation + Insights + Chart all run CONCURRENTLY
    t_parallel = time.monotonic()

    explanation_fut = None
    insights_fut    = None
    chart_fut       = None

    if payload.explanation_mode != "None":
        explanation_fut = loop.run_in_executor(
            _executor,
            lambda: _run_explanation(sql, payload.user_query, payload.explanation_mode, EXPLANATION_FAST_MODEL),
        )

    if rows and columns and payload.auto_insights:
        insights_fut = loop.run_in_executor(
            _executor,
            lambda: _run_insights(columns, rows, payload.user_query, payload.ai_model),
        )

    chart_fut = loop.run_in_executor(
        _executor,
        lambda: _run_chart(columns, len(rows), payload.user_query, sql),
    )

    # Await all parallel tasks together
    results = await asyncio.gather(
        explanation_fut or asyncio.sleep(0),
        insights_fut or asyncio.sleep(0),
        chart_fut,
        return_exceptions=True,
    )

    explanation_result = results[0] if explanation_fut else ""
    insights_result    = results[1] if insights_fut else {}
    chart_result       = results[2]

    timing["parallel_ms"] = round((time.monotonic() - t_parallel) * 1000, 1)
    timing["total_ms"]    = round((time.monotonic() - t_start) * 1000, 1)

    # ── Unpack parallel results ────────────────────────────────────────────────
    explanation = explanation_result if isinstance(explanation_result, str) else ""

    if isinstance(insights_result, dict):
        insight_cards = insights_result.get("insight_cards", [])
        narrative     = insights_result.get("narrative")
    else:
        insight_cards = []
        narrative     = None

    if isinstance(chart_result, dict):
        recommended_chart   = chart_result.get("chart_type", "table_only")
        chart_justification = chart_result.get("justification", "")
    else:
        recommended_chart   = "table_only"
        chart_justification = ""

    # Simple confidence score
    word_count  = len(payload.user_query.split())
    conf_score  = round(min(0.95, 0.5 + word_count * 0.04), 2)
    conf_label  = "High" if conf_score >= 0.75 else ("Medium" if conf_score >= 0.50 else "Low")

    logger.info(
        "fast-analyze complete | complexity=%s | sql=%.1fms | exec=%.1fms | parallel=%.1fms | total=%.1fms | cache=%s",
        complexity.value,
        timing.get("sql_gen_ms", 0),
        timing.get("sql_exec_ms", 0),
        timing.get("parallel_ms", 0),
        timing.get("total_ms", 0),
        cache_hit,
    )

    return FastAnalyzeResponse(
        success=True,
        complexity=complexity.value,
        complexity_reason=complexity_reason,
        sql=sql,
        columns=columns,
        rows=rows,
        row_count=len(rows),
        execution_duration=exec_dur,
        explanation=explanation,
        insight_cards=insight_cards,
        narrative=narrative,
        recommended_chart=recommended_chart,
        chart_justification=chart_justification,
        confidence_score=conf_score,
        confidence_label=conf_label,
        cache_hit=cache_hit,
        timing=timing,
    )


# ─── SSE Streaming endpoint ──────────────────────────────────────────────────

@router.post(
    "/stream-analyze",
    summary="🔴 Live streaming analysis with real-time pipeline stage updates",
    description=(
        "Server-Sent Events endpoint. Streams pipeline stage updates as they happen. "
        "Frontend receives: stage_update, sql_ready, data_ready, explanation_ready, "
        "insights_ready, complete — each as a JSON SSE event."
    ),
)
async def stream_analyze(
    payload: FastAnalyzeRequest,
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """SSE streaming endpoint for real-time pipeline progress."""

    async def event_stream() -> AsyncGenerator[str, None]:
        loop = asyncio.get_event_loop()
        t_start = time.monotonic()

        def sse(event: str, data: dict) -> str:
            return f"event: {event}\ndata: {json.dumps(data)}\n\n"

        # ── Stage 1: Complexity + Schema ──────────────────────────────────────
        complexity, reason = classify_query(payload.user_query)
        yield sse("stage_update", {
            "stage": "classifying",
            "message": f"Query classified as {complexity.value.upper()} — {reason}",
            "complexity": complexity.value,
        })

        try:
            engine, conn_params = _get_engine_from_request(payload)
        except Exception as exc:
            yield sse("error", {"message": f"Connection failed: {exc}"})
            return

        schema_key = make_schema_key(
            conn_params.get("host", ""),
            conn_params.get("database", ""),
            conn_params.get("database_type", ""),
        )
        full_schema = schema_context_cache.get(schema_key)
        if not full_schema:
            full_schema = get_schema(engine)
            schema_context_cache.set(schema_key, full_schema)
        schema = filter_schema_to_relevant_tables(full_schema, payload.user_query)

        # ── Stage 1.5: Intent Detection ────────────────────────────────────────
        yield sse("stage_update", {"stage": "classifying", "message": "Detecting query intent…"})
        detector = IntentDetector()
        intent_res = await loop.run_in_executor(
            _executor,
            lambda: detector.detect_intent(
                payload.user_query,
                schema=schema,
                dialect=conn_params.get("database_type", "mysql")
            )
        )

        if intent_res["intent"] == "Conversation":
            yield sse("intent_conversation", {
                "response": intent_res["response"],
                "elapsed_ms": round((time.monotonic() - t_start) * 1000, 1)
            })
            yield sse("complete", {
                "recommended_chart": "table_only",
                "chart_justification": "",
                "confidence_score": 1.0,
                "confidence_label": "High",
                "total_ms": round((time.monotonic() - t_start) * 1000, 1),
            })
            return

        if intent_res["intent"] == "Ambiguous":
            yield sse("intent_ambiguous", {
                "suggestions": intent_res["suggestions"],
                "elapsed_ms": round((time.monotonic() - t_start) * 1000, 1)
            })
            yield sse("complete", {
                "recommended_chart": "table_only",
                "chart_justification": "",
                "confidence_score": 1.0,
                "confidence_label": "High",
                "total_ms": round((time.monotonic() - t_start) * 1000, 1),
            })
            return

        # ── Stage 2: SQL Generation ────────────────────────────────────────────
        yield sse("stage_update", {"stage": "generating_sql", "message": "Generating SQL query…"})

        query_key = make_query_key(payload.user_query, schema_key, conn_params.get("database_type", "mysql"))
        cached_sql = sql_result_cache.get(query_key)

        try:
            if cached_sql:
                sql = cached_sql["sql"]
                yield sse("sql_ready", {"sql": sql, "cached": True, "elapsed_ms": round((time.monotonic() - t_start) * 1000, 1)})
            else:
                generator = SQLGenerator(ai_model=_SQL_FAST_MODEL)
                gen_result = await loop.run_in_executor(
                    _executor,
                    lambda: generator.generate_sql(payload.user_query, schema, dialect=conn_params.get("database_type", "mysql")),
                )
                if not gen_result.get("success"):
                    yield sse("error", {"message": gen_result.get("error", "SQL generation failed")})
                    return
                sql = gen_result["sql"]
                sql_result_cache.set(query_key, {"sql": sql})
                yield sse("sql_ready", {"sql": sql, "cached": False, "elapsed_ms": round((time.monotonic() - t_start) * 1000, 1)})
        except Exception as exc:
            yield sse("error", {"message": f"SQL generation failed: {exc}"})
            return

        # ── Stage 3: Execute SQL (with execution-error retry) ─────────────────
        yield sse("stage_update", {"stage": "executing", "message": "Executing query against database…"})
        _MAX_SSE_RETRIES = 2
        exec_result = None
        columns: List[str] = []
        rows: List[Dict[str, Any]] = []

        for _sse_attempt in range(1 + _MAX_SSE_RETRIES):
            try:
                exec_result = await loop.run_in_executor(
                    _executor,
                    lambda _sql=sql: execute_query(engine, _sql, row_limit=payload.row_limit, timeout=30, user_query=payload.user_query),
                )
                columns = exec_result.get("columns", [])
                rows    = exec_result.get("rows", [])
                break  # success
            except InvalidSQLException as exc:
                logger.warning("SQL validation blocked execution in stream_analyze: %s", exc)
                yield sse("intent_conversation", {
                    "response": "Sorry, I cannot modify or delete database data. DataPilot AI is a read-only analytics platform designed for querying and analyzing data only."
                })
                yield sse("complete", {
                    "recommended_chart": "table_only",
                    "chart_justification": "",
                    "confidence_score": 1.0,
                    "confidence_label": "High",
                    "total_ms": round((time.monotonic() - t_start) * 1000, 1),
                })
                return
            except QueryTimeoutError as exc:
                yield sse("error", {"message": str(exc), "sql": sql})
                return
            except Exception as exc:
                sse_exec_err = str(exc)
                logger.warning("SSE SQL execution failed (attempt %d): %s", _sse_attempt + 1, sse_exec_err)
                if _sse_attempt >= _MAX_SSE_RETRIES:
                    yield sse("error", {"message": f"Database execution failed: {sse_exec_err}", "sql": sql})
                    return
                # Regenerate SQL with error hint
                yield sse("stage_update", {"stage": "correcting_sql", "message": "Correcting SQL based on database error…"})
                regen_gen = SQLGenerator(ai_model=_SQL_FAST_MODEL)
                regen_res = await loop.run_in_executor(
                    _executor,
                    lambda _err=sse_exec_err: regen_gen.generate_sql(
                        payload.user_query + f"\n\n[PREVIOUS SQL FAILED WITH: {_err}. Fix the SQL to avoid this error.]",
                        schema,
                        dialect=conn_params.get("database_type", "mysql"),
                    ),
                )
                if regen_res.get("success") and regen_res.get("sql"):
                    sql = regen_res["sql"]
                    yield sse("sql_ready", {"sql": sql, "cached": False, "corrected": True,
                                            "elapsed_ms": round((time.monotonic() - t_start) * 1000, 1)})
                else:
                    yield sse("error", {"message": f"Database execution failed and SQL correction also failed: {sse_exec_err}", "sql": sql})
                    return

        yield sse("data_ready", {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "execution_duration": exec_result.get("execution_duration", 0.0),
            "elapsed_ms": round((time.monotonic() - t_start) * 1000, 1),
        })

        # ── Stage 4: Progressive background tasks ──────────────────────────────
        yield sse("stage_update", {"stage": "analyzing", "message": "Preparing instant chart & cards…"})

        # 1. Fast path: Heuristic Chart Recommendation (< 1ms)
        chart_raw = await loop.run_in_executor(
            _executor,
            lambda: _run_chart(columns, len(rows), payload.user_query, sql),
        )
        yield sse("chart_ready", {
            "recommended_chart":   chart_raw.get("chart_type", "table_only"),
            "chart_justification": chart_raw.get("justification", ""),
            "elapsed_ms": round((time.monotonic() - t_start) * 1000, 1),
        })

        # 2. Launch explanation LLM (Groq primary, Gemini fallback)
        exp_fut = None
        if payload.explanation_mode != "None":
            yield sse("stage_update", {"stage": "analyzing", "message": "AI explanation generating…"})
            exp_fut = loop.run_in_executor(
                _executor,
                lambda: _run_explanation(sql, payload.user_query, payload.explanation_mode, EXPLANATION_FAST_MODEL),
            )

        # 3. Await explanation — tight timeout: Groq is fast (<2s), fallback still bounded.
        explanation = ""
        if exp_fut:
            _exp_timeout = 8.0 if payload.explanation_mode == "Detailed" else 4.0
            try:
                explanation = await asyncio.wait_for(exp_fut, timeout=_exp_timeout)
                yield sse("explanation_ready", {
                    "explanation": explanation,
                    "elapsed_ms": round((time.monotonic() - t_start) * 1000, 1),
                })
            except asyncio.TimeoutError:
                logger.warning("Explanation timed out after %.0fs — using rule-based fallback.", _exp_timeout)
                from app.services.ai.explanation_service import ExplanationService
                fallback_exp = ExplanationService()._generate_fallback(sql, payload.user_query)
                yield sse("explanation_ready", {
                    "explanation": fallback_exp,
                    "elapsed_ms": round((time.monotonic() - t_start) * 1000, 1),
                })
            except Exception as exc:
                logger.warning("Streaming explanation failed: %s", exc)

        # 4. Complete
        word_count = len(payload.user_query.split())
        conf_score = round(min(0.95, 0.5 + word_count * 0.04), 2)
        yield sse("complete", {
            "recommended_chart":   chart_raw.get("chart_type", "table_only"),
            "chart_justification": chart_raw.get("justification", ""),
            "confidence_score":    conf_score,
            "confidence_label":    "High" if conf_score >= 0.75 else "Medium",
            "total_ms": round((time.monotonic() - t_start) * 1000, 1),
        })

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ─── Cache stats ──────────────────────────────────────────────────────────────

@router.get(
    "/cache-stats",
    summary="Performance cache statistics",
    tags=[TAG_QUERY],
)
async def cache_stats(current_user: User = Depends(get_current_user)):
    """Return live cache statistics for all performance caches."""
    return {"success": True, "caches": get_all_cache_stats()}
