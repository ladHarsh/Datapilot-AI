"""
schemas/query_schema.py
────────────────────────
Pydantic schemas for query execution requests and results.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.config import settings
from app.core.constants import DEFAULT_ROW_LIMIT, BLOCKED_SQL_KEYWORDS


# ══════════════════════════════════════════════════════════════════════════════
#  Request schemas
# ══════════════════════════════════════════════════════════════════════════════

class QueryGenerateRequest(BaseModel):
    user_query: str = Field(..., description="Natural-language question from the user.", min_length=1)
    host: Optional[str] = Field(None)
    port: Optional[int] = Field(None, ge=0, lt=65536)
    username: Optional[str] = Field(None)
    password: Optional[str] = Field(None)
    database: Optional[str] = Field(None)
    database_type: Optional[str] = Field(None)
    file_path: Optional[str] = Field(None)
    ai_model: Optional[str] = Field(None, description="The preferred AI model (e.g. Gemini, Groq, GPT, NVIDIA).")
    explanation_mode: Optional[str] = Field(None, description="Mode for SQL explanation (Detailed, Brief, None).")
    row_limit: Optional[int] = Field(None, description="Maximum rows to return.")

class QueryGenerateResponse(BaseModel):
    success: bool
    sql_query: str
    explanation: Optional[str] = None
    error: Optional[str] = None

class QueryExecuteRequest(BaseModel):
    """
    Payload for executing a (potentially AI-generated) SQL query.

    Either ``user_query`` (natural language) or ``sql_query`` (raw SQL) must be
    provided. When both are present, ``sql_query`` takes precedence for execution
    while ``user_query`` is stored for history.
    """

    user_query: Optional[str] = Field(
        None,
        description="Natural-language question from the user.",
        max_length=2048,
        examples=["Show me the top 10 customers by revenue"],
    )
    sql_query: str = Field(
        ...,
        description="SQL SELECT statement to execute.",
        min_length=1,
        examples=["SELECT * FROM customers ORDER BY revenue DESC LIMIT 10"],
    )
    row_limit: int = Field(
        default=DEFAULT_ROW_LIMIT,
        gt=0,
        le=settings.MAX_ROWS,
        description=f"Maximum rows to return. Hard cap: {settings.MAX_ROWS}.",
    )
    timeout: int = Field(
        default=settings.QUERY_TIMEOUT,
        gt=0,
        le=300,
        description="Per-query timeout in seconds.",
    )
    # Connection identity — echoed from the connect step
    # Connection identity — optional if active session exists
    host: Optional[str] = Field(None, description="Target database host.")
    port: Optional[int] = Field(None, ge=0, lt=65536)
    username: Optional[str] = Field(None)
    password: Optional[str] = Field(None)
    database: Optional[str] = Field(None)
    database_type: Optional[str] = Field(None)
    file_path: Optional[str] = Field(None, description="SQLite file path for uploaded databases.")

    @field_validator("sql_query")
    @classmethod
    def strip_query(cls, v: str) -> str:
        return v.strip()

    @field_validator("database_type")
    @classmethod
    def validate_db_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        from app.core.constants import SUPPORTED_DATABASES
        v_lower = v.strip().lower()
        if v_lower not in SUPPORTED_DATABASES:
            raise ValueError(f"Unsupported database_type: {v}")
        return v_lower

    model_config = {"json_schema_extra": {
        "example": {
            "user_query": "Show top 5 products by sales",
            "sql_query": "SELECT product_name, SUM(quantity) AS total_sold FROM order_items GROUP BY product_name ORDER BY total_sold DESC LIMIT 5",
            "row_limit": 100,
            "timeout": 30,
            "host": "localhost",
            "port": 3306,
            "username": "root",
            "password": "secret",
            "database": "shop_db",
            "database_type": "mysql",
        }
    }}


# ══════════════════════════════════════════════════════════════════════════════
#  History replay
# ══════════════════════════════════════════════════════════════════════════════

class QueryReplayRequest(BaseModel):
    """Re-execute a query from history with fresh credentials."""

    history_id: int = Field(..., gt=0, description="ID from query_history table.")
    host: Optional[str] = Field(None)
    port: Optional[int] = Field(None, ge=0, lt=65536)
    username: Optional[str] = Field(None)
    password: Optional[str] = Field(None)
    database: Optional[str] = Field(None)
    database_type: Optional[str] = Field(None)
    file_path: Optional[str] = Field(None)


# ══════════════════════════════════════════════════════════════════════════════
#  Result schemas
# ══════════════════════════════════════════════════════════════════════════════

class QueryResult(BaseModel):
    """Structured result of a single SQL execution."""

    sql_query: str
    user_query: Optional[str] = None
    columns: List[str]
    rows: List[Dict[str, Any]]
    row_count: int
    execution_duration: float = Field(..., description="Seconds taken to execute the query.")
    truncated: bool = Field(False, description="True when the result was capped at row_limit.")
    explanation: Optional[str] = Field(
        None,
        description="Placeholder for AI-generated explanation of the query result.",
    )


class InsightsRequest(BaseModel):
    user_query: str
    columns: List[str]
    rows: List[List[Any]]
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    database: Optional[str] = None
    database_type: Optional[str] = None
    file_path: Optional[str] = None
    ai_model: Optional[str] = Field(None, description="The preferred AI model (e.g. Gemini, Groq, GPT, NVIDIA).")


class InsightsResponse(BaseModel):
    success: bool
    insight_cards: List[Dict[str, str]] = []
    insights: List[str] = []
    narrative: Optional[str] = None
    recommended_chart: Optional[str] = None
    chart_justification: Optional[str] = None
    confidence_score: Optional[float] = None
    confidence_label: Optional[str] = None
    ambiguities: List[str] = []
    warnings: List[str] = []

