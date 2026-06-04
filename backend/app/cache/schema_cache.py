"""
schema_cache.py — SQL AI Analytics Platform.

TTL-based cache for parsed and formatted schema contexts.

Schema processing (building context strings, filtering tables, computing
column maps) is CPU-only but expensive when called on every request.
This cache stores the formatted output and invalidates it after a
configurable TTL so changes to the live DB schema are eventually reflected.

Author : Member 2 — AI/LLM Engineer
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Any, Callable, Dict, Optional, Tuple

from ..utils.ai_constants import SCHEMA_CACHE_TTL_SECONDS

logger = logging.getLogger(__name__)


class SchemaCache:
    """TTL cache for schema context strings and derived structures.

    Usage::

        cache = SchemaCache(ttl=300)

        context_str = cache.get_or_build(
            schema_dict=raw_schema,
            builder_fn=schema_context_builder.build_context,
        )
    """

    def __init__(self, ttl: int = SCHEMA_CACHE_TTL_SECONDS) -> None:
        self._ttl = ttl
        # key → (value, expiry_timestamp)
        self._store: Dict[str, Tuple[Any, float]] = {}
        self._hits = 0
        self._misses = 0
        logger.debug("SchemaCache initialised (ttl=%ds).", ttl)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_or_build(
        self,
        schema: Dict[str, Any],
        builder_fn: Callable[[Dict[str, Any]], Any],
        cache_key: Optional[str] = None,
    ) -> Any:
        """Return cached schema context or build fresh and cache it.

        Parameters
        ----------
        schema : dict
            The raw schema dictionary.
        builder_fn : callable
            Function that accepts the schema dict and returns the context.
        cache_key : str, optional
            Override the auto-generated key (useful for partial schemas).

        Returns
        -------
        Any
            The output of builder_fn (usually a string or dict).
        """
        key = cache_key or self._hash_schema(schema)
        cached = self._store.get(key)

        if cached is not None:
            value, expiry = cached
            if time.time() < expiry:
                self._hits += 1
                logger.debug("SchemaCache HIT (key=%s…).", key[:8])
                return value
            else:
                logger.debug("SchemaCache EXPIRED (key=%s…).", key[:8])
                del self._store[key]

        # Miss — build fresh
        self._misses += 1
        logger.debug("SchemaCache MISS (key=%s…) — rebuilding.", key[:8])
        value = builder_fn(schema)
        self._store[key] = (value, time.time() + self._ttl)
        return value

    def invalidate(self, schema: Dict[str, Any]) -> bool:
        """Force-remove a schema entry. Returns True if it existed."""
        key = self._hash_schema(schema)
        if key in self._store:
            del self._store[key]
            logger.info("SchemaCache invalidated (key=%s…).", key[:8])
            return True
        return False

    def clear(self) -> None:
        """Purge all cached schema entries."""
        self._store.clear()
        logger.info("SchemaCache cleared.")

    def purge_expired(self) -> int:
        """Remove all expired entries. Returns count of removed entries."""
        now = time.time()
        expired_keys = [k for k, (_, exp) in self._store.items() if now >= exp]
        for k in expired_keys:
            del self._store[k]
        if expired_keys:
            logger.info("SchemaCache purged %d expired entries.", len(expired_keys))
        return len(expired_keys)

    @property
    def stats(self) -> Dict[str, Any]:
        """Return cache statistics."""
        return {
            "hits":   self._hits,
            "misses": self._misses,
            "size":   len(self._store),
            "ttl_s":  self._ttl,
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _hash_schema(schema: Dict[str, Any]) -> str:
        """Create a deterministic hash of the schema dict."""
        import json
        schema_str = json.dumps(schema, sort_keys=True)
        return hashlib.md5(schema_str.encode()).hexdigest()
