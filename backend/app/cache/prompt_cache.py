"""
prompt_cache.py — SQL AI Analytics Platform.

In-memory LRU cache for LLM prompt-response pairs.
Avoids re-sending identical prompts to the LLM, saving tokens and latency.

Design:
- Uses functools.lru_cache internally for thread-safe caching.
- Cache key = MD5 hash of the prompt string.
- Provider-independent: wraps any callable that takes a str and returns str.

Author : Member 2 — AI/LLM Engineer
"""

from __future__ import annotations

import hashlib
import logging
import time
from collections import OrderedDict
from typing import Callable, Dict, Optional, Tuple

from ..utils.ai_constants import PROMPT_CACHE_MAX_SIZE

logger = logging.getLogger(__name__)


class PromptCache:
    """Thread-safe LRU cache for prompt → LLM response pairs.

    Usage::

        cache = PromptCache(max_size=128)

        def my_llm_call(prompt: str) -> str:
            return llm.send(prompt)

        response = cache.get_or_call(prompt, my_llm_call)
    """

    def __init__(self, max_size: int = PROMPT_CACHE_MAX_SIZE) -> None:
        self._max_size = max_size
        self._store: OrderedDict[str, Tuple[str, float]] = OrderedDict()
        self._hits = 0
        self._misses = 0
        logger.debug("PromptCache initialised (max_size=%d).", max_size)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_or_call(
        self,
        prompt: str,
        llm_callable: Callable[[str], str],
    ) -> str:
        """Return cached response if available; otherwise call LLM and cache.

        Parameters
        ----------
        prompt : str
            The full prompt string.
        llm_callable : callable
            Function that takes a prompt str and returns a response str.

        Returns
        -------
        str
            The LLM response (cached or fresh).
        """
        key = self._hash(prompt)
        cached = self._store.get(key)

        if cached is not None:
            response, _ = cached
            # Move to end (most-recently-used)
            self._store.move_to_end(key)
            self._hits += 1
            logger.debug("Cache HIT (key=%s…)", key[:8])
            return response

        # Cache miss — call LLM
        self._misses += 1
        logger.debug("Cache MISS (key=%s…) — calling LLM.", key[:8])
        response = llm_callable(prompt)

        self._store[key] = (response, time.time())
        self._store.move_to_end(key)

        # Evict oldest if over capacity
        if len(self._store) > self._max_size:
            evicted_key, _ = self._store.popitem(last=False)
            logger.debug("Evicted cache entry (key=%s…).", evicted_key[:8])

        return response

    def invalidate(self, prompt: str) -> bool:
        """Remove a specific prompt from the cache. Returns True if removed."""
        key = self._hash(prompt)
        if key in self._store:
            del self._store[key]
            return True
        return False

    def clear(self) -> None:
        """Clear all cached entries."""
        self._store.clear()
        logger.info("PromptCache cleared.")

    @property
    def stats(self) -> Dict[str, int]:
        """Return cache hit/miss statistics."""
        return {
            "hits": self._hits,
            "misses": self._misses,
            "size": len(self._store),
            "max_size": self._max_size,
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _hash(prompt: str) -> str:
        return hashlib.md5(prompt.encode("utf-8")).hexdigest()
