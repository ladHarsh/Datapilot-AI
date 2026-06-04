"""
token_counter.py — SQL AI Analytics Platform.

Estimates token usage for prompts before sending to the LLM.
Prevents prompt overflow and helps with cost management.

Uses a simple character-ratio approximation (no external tokenizer needed),
with an optional tiktoken integration when available.

Author : Member 2 — AI/LLM Engineer
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .ai_constants import CHARS_PER_TOKEN, PROMPT_TOKEN_BUDGET, DEFAULT_MAX_TOKENS

logger = logging.getLogger(__name__)

# Try to use tiktoken for accurate OpenAI-compatible counting
try:
    import tiktoken
    _tiktoken_available = True
    _encoder = tiktoken.get_encoding("cl100k_base")
    logger.debug("tiktoken available — using accurate token counting.")
except ImportError:
    _tiktoken_available = False
    _encoder = None
    logger.debug("tiktoken not installed — using char-ratio approximation.")


def count_tokens(text: str) -> int:
    """Estimate token count for a text string.

    Uses tiktoken if installed, otherwise falls back to char/4 approximation.
    """
    if not text:
        return 0
    if _tiktoken_available and _encoder:
        try:
            return len(_encoder.encode(text))
        except Exception:
            pass
    # Fallback: approximation
    return max(1, len(text) // CHARS_PER_TOKEN)


def fits_in_budget(text: str, budget: int = PROMPT_TOKEN_BUDGET) -> bool:
    """Return True if the text fits within the token budget."""
    return count_tokens(text) <= budget


def truncate_to_budget(text: str, budget: int = PROMPT_TOKEN_BUDGET) -> str:
    """Truncate text to fit within the given token budget.

    Truncation is done at character boundaries to preserve word integrity.
    """
    if fits_in_budget(text, budget):
        return text

    # Estimate target char count
    target_chars = budget * CHARS_PER_TOKEN
    truncated = text[:target_chars]

    # Try to cut at last complete sentence
    last_period = truncated.rfind(".")
    if last_period > target_chars // 2:
        truncated = truncated[:last_period + 1]

    logger.info(
        "Prompt truncated: %d tokens → ~%d tokens",
        count_tokens(text),
        count_tokens(truncated),
    )
    return truncated


def token_budget_report(components: Dict[str, str]) -> Dict[str, Any]:
    """Generate a token usage report for multiple prompt components.

    Parameters
    ----------
    components : dict
        Mapping of label → text, e.g. {"schema": ..., "query": ..., "examples": ...}

    Returns
    -------
    dict
        {label: token_count, "total": int, "within_budget": bool}
    """
    report: Dict[str, Any] = {}
    total = 0
    for label, text in components.items():
        count = count_tokens(text)
        report[label] = count
        total += count
    report["total"] = total
    report["within_budget"] = total <= PROMPT_TOKEN_BUDGET
    report["budget"] = PROMPT_TOKEN_BUDGET
    return report
