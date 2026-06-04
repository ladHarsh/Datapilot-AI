"""
ai_constants.py — SQL AI Analytics Platform.

Central registry of all constants used across the AI layer.
Import from here to avoid magic numbers and string duplication.

Author : Member 2 — AI/LLM Engineer
"""

# ---------------------------------------------------------------------------
# LLM Provider Keys
# ---------------------------------------------------------------------------
PROVIDER_GEMINI     = "gemini"
PROVIDER_OPENROUTER = "openrouter"
PROVIDER_OPENAI     = "openai"
PROVIDER_DEEPSEEK   = "deepseek"

SUPPORTED_PROVIDERS = [PROVIDER_GEMINI, PROVIDER_OPENROUTER, PROVIDER_OPENAI, PROVIDER_DEEPSEEK]

# ---------------------------------------------------------------------------
# Token Limits (conservative safe values per provider)
# ---------------------------------------------------------------------------
MAX_TOKENS_GEMINI     = 8192
MAX_TOKENS_OPENROUTER = 4096
MAX_TOKENS_OPENAI     = 4096
MAX_TOKENS_DEEPSEEK   = 4096
DEFAULT_MAX_TOKENS    = 4096

# Prompt budget: leave headroom for the response
PROMPT_TOKEN_BUDGET = 3000

# Average chars-per-token approximation (English text)
CHARS_PER_TOKEN = 4

# ---------------------------------------------------------------------------
# SQL Generation
# ---------------------------------------------------------------------------
SQL_MAX_RETRIES   = 3
SQL_MAX_ROWS      = 1000           # default LIMIT appended if query has none
SUPPORTED_DIALECTS = ["mysql", "postgresql"]

# Destructive SQL keywords — always blocked
DESTRUCTIVE_KEYWORDS = [
    "DROP", "DELETE", "INSERT", "UPDATE", "TRUNCATE",
    "ALTER", "CREATE", "GRANT", "REVOKE", "EXEC", "EXECUTE",
    "REPLACE", "MERGE", "CALL",
]

# ---------------------------------------------------------------------------
# Confidence Scoring
# ---------------------------------------------------------------------------
CONFIDENCE_HIGH_THRESHOLD   = 80   # score >= this → "High"
CONFIDENCE_MEDIUM_THRESHOLD = 50   # score >= this → "Medium", else "Low"

SCORE_TABLES_VALID  = 30
SCORE_COLUMNS_VALID = 30
SCORE_JOINS_VALID   = 15
SCORE_SAFE_QUERY    = 10
SCORE_HAS_FILTER    = 10
SCORE_INTENT_MATCH  = 5

# ---------------------------------------------------------------------------
# Chart Types
# ---------------------------------------------------------------------------
CHART_BAR        = "bar_chart"
CHART_LINE       = "line_chart"
CHART_PIE        = "pie_chart"
CHART_SCATTER    = "scatter_chart"
CHART_HEATMAP    = "heatmap"
CHART_TABLE_ONLY = "table_only"

SUPPORTED_CHARTS = [CHART_BAR, CHART_LINE, CHART_PIE, CHART_SCATTER, CHART_HEATMAP, CHART_TABLE_ONLY]

# ---------------------------------------------------------------------------
# Analytics Thresholds
# ---------------------------------------------------------------------------
TREND_UP_THRESHOLD    = 5.0    # % increase from first → last row
TREND_DOWN_THRESHOLD  = -5.0   # % decrease
ANOMALY_STD_FACTOR    = 2.0    # standard deviations above/below mean

# ---------------------------------------------------------------------------
# Cache Settings
# ---------------------------------------------------------------------------
SCHEMA_CACHE_TTL_SECONDS = 300   # 5 minutes
PROMPT_CACHE_MAX_SIZE    = 128   # max cached prompt entries (LRU)

# ---------------------------------------------------------------------------
# Response Parsing
# ---------------------------------------------------------------------------
SQL_FENCE_PATTERNS = ["```sql", "```SQL", "```", "~~~"]
MAX_EXPLANATION_SENTENCES = 4
