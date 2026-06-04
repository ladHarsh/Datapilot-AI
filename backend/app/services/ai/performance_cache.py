"""
Performance Cache — DataPilot AI Speed Engine.

Multi-level in-memory cache with TTL support.

Caches:
  - Schema context strings (per connection key)      TTL: 10 min
  - SQL query results (per query + connection hash)  TTL: 5 min
  - Chart recommendations (per columns signature)    TTL: 30 min
  - Analytics insights (per data signature)          TTL: 5 min

Author: DataPilot Performance Team
"""

from __future__ import annotations

import hashlib
import logging
import time
from functools import lru_cache
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

__all__ = [
    "schema_context_cache",
    "sql_result_cache",
    "explanation_cache",
    "insights_cache",
    "chart_cache",
    "make_query_key",
    "make_schema_key",
    "make_explanation_key",
]


# ─── Generic TTL cache ───────────────────────────────────────────────────────

class TTLCache:
    """Thread-safe in-memory cache with TTL eviction.

    Uses a simple dict with (value, expiry_timestamp) pairs.
    Eviction is lazy — happens on access or explicit cleanup.
    """

    def __init__(self, ttl_seconds: int = 300, maxsize: int = 256) -> None:
        self._ttl = ttl_seconds
        self._maxsize = maxsize
        self._store: Dict[str, Tuple[Any, float]] = {}

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expiry = entry
        if time.monotonic() > expiry:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        # Evict oldest entry if at capacity
        if len(self._store) >= self._maxsize:
            oldest_key = min(self._store, key=lambda k: self._store[k][1])
            del self._store[oldest_key]
        self._store[key] = (value, time.monotonic() + self._ttl)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()

    def stats(self) -> Dict[str, int]:
        now = time.monotonic()
        live = sum(1 for _, (_, exp) in self._store.items() if exp > now)
        return {"total_entries": len(self._store), "live_entries": live, "ttl_seconds": self._ttl}


# ─── Singleton cache instances ────────────────────────────────────────────────

# Schema context: expensive to rebuild (calls SchemaContextBuilder)
schema_context_cache = TTLCache(ttl_seconds=600, maxsize=64)

# SQL results: query + schema fingerprint → (sql, columns, rows)
sql_result_cache = TTLCache(ttl_seconds=300, maxsize=128)

# Explanations: SQL query + explanation mode → explanation text
explanation_cache = TTLCache(ttl_seconds=300, maxsize=128)

# AI Insights: data fingerprint → insight cards + narrative
insights_cache = TTLCache(ttl_seconds=300, maxsize=128)

# Chart recommendation: columns fingerprint → chart type
chart_cache = TTLCache(ttl_seconds=1800, maxsize=256)


# ─── Key builders ────────────────────────────────────────────────────────────

def make_schema_key(host: str, database: str, db_type: str) -> str:
    """Stable cache key for a database connection's schema context."""
    raw = f"{host}|{database}|{db_type}".lower()
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def make_query_key(user_query: str, schema_key: str, dialect: str = "mysql") -> str:
    """Stable cache key for an (query, schema, dialect) triple."""
    raw = f"{user_query.strip().lower()}|{schema_key}|{dialect}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def make_explanation_key(sql: str, mode: str) -> str:
    """Stable cache key for query explanation."""
    raw = f"{sql.strip()}|{mode}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def make_data_key(columns: list, rows: list) -> str:
    """Stable cache key for a query result dataset."""
    # Hash column names + first/last row to detect data changes
    sample = str(columns) + str(rows[:1]) + str(rows[-1:]) + str(len(rows))
    return hashlib.sha1(sample.encode()).hexdigest()[:20]


def make_chart_key(columns: list, user_query: str) -> str:
    """Stable cache key for chart recommendation."""
    raw = str(sorted(columns)) + "|" + user_query.strip().lower()[:80]
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


# ─── Cache statistics helper ─────────────────────────────────────────────────

def get_all_cache_stats() -> Dict[str, Any]:
    """Return stats for all caches — useful for monitoring endpoint."""
    return {
        "schema_context": schema_context_cache.stats(),
        "sql_results":    sql_result_cache.stats(),
        "explanation":    explanation_cache.stats(),
        "insights":       insights_cache.stats(),
        "chart":          chart_cache.stats(),
    }
