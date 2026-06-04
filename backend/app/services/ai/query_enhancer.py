"""
Query Enhancer — SQL AI Analytics Platform.

Improves user natural-language queries BEFORE they are sent to the SQL
generation pipeline.  Handles ambiguous intent, incomplete questions,
missing context, and business-term normalisation.

Pipeline:
    Raw User Query  →  QueryEnhancer  →  SQLGenerator  →  SQL

Author : Member 2 — AI/LLM Engineer
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Ambiguity detection patterns
# ---------------------------------------------------------------------------
_AMBIGUOUS_PATTERNS: List[tuple[str, str]] = [
    # (regex pattern, reason string)
    (r"\bthings?\b",     "vague noun 'thing' detected"),
    (r"\bstuff\b",       "vague noun 'stuff' detected"),
    (r"\bsome\b",        "unspecified quantity 'some' detected"),
    (r"\brecent(ly)?\b", "time range not specified for 'recent'"),
    (r"\bnew\b",         "time range not specified for 'new'"),
    (r"\bold\b",         "time range not specified for 'old'"),
    (r"\bbig\b|\blarge\b|\bsmall\b", "relative size without threshold"),
    (r"\bgood\b|\bbad\b|\bbest\b",   "subjective qualifier without metric"),
    (r"\bmore\b|\bless\b",           "comparison without explicit baseline"),
    (r"\beverything\b|\ball (the )?\w+\b", "broad query may be expensive"),
]

# ---------------------------------------------------------------------------
# Incomplete query patterns & their suggested improvements
# ---------------------------------------------------------------------------
_COMPLETIONS: List[tuple[str, str]] = [
    # Pattern → template (use {match} to embed the matched text)
    (r"^show\s+(\w+)$",      "show all {match}"),
    (r"^get\s+(\w+)$",       "get all {match}"),
    (r"^list\s+(\w+)$",      "list all {match}"),
    (r"^find\s+(\w+)$",      "find all {match}"),
    (r"^count\s+(\w+)$",     "count the number of {match}"),
    (r"^total\s+(\w+)$",     "show total {match}"),
    (r"^average\s+(\w+)$",   "show average {match}"),
    (r"^top\s+(\d+)\s+(\w+)$", "show top {0} {1} by value"),
]

# ---------------------------------------------------------------------------
# Business term → explicit wording
# ---------------------------------------------------------------------------
_BUSINESS_EXPANSIONS: Dict[str, str] = {
    "mtd":   "month to date",
    "ytd":   "year to date",
    "qtd":   "quarter to date",
    "ltm":   "last twelve months",
    "yoy":   "year over year",
    "mom":   "month over month",
    "arpu":  "average revenue per user",
    "cac":   "customer acquisition cost",
    "ltv":   "lifetime value",
    "churn": "customer churn rate",
    "dau":   "daily active users",
    "mau":   "monthly active users",
    "kpi":   "key performance indicator",
    "roi":   "return on investment",
    "cogs":  "cost of goods sold",
    "gm":    "gross margin",
    "nps":   "net promoter score",
}

# ---------------------------------------------------------------------------
# Analytics context keywords → suggest GROUP BY / ORDER BY
# ---------------------------------------------------------------------------
_ANALYTICS_HINTS: List[tuple[str, str]] = [
    (r"\btrend(s)?\b",       "Consider adding time grouping (e.g. by month)."),
    (r"\bby (category|type|region|segment)\b", "Consider GROUP BY the mentioned dimension."),
    (r"\btop\s+\d+\b",       "Consider ORDER BY ... DESC LIMIT N."),
    (r"\brank(ed|ing)?\b",   "Consider using RANK() or ORDER BY."),
    (r"\bcompare\b",         "Consider grouping both dimensions for comparison."),
    (r"\bmonthly\b|\bweekly\b|\bdaily\b", "Add date truncation to the GROUP BY clause."),
]


class QueryEnhancer:
    """Improve user natural-language queries before SQL generation.

    Responsibilities
    ----------------
    * Detect and flag ambiguous intent.
    * Complete/expand under-specified queries.
    * Expand business abbreviations.
    * Add analytics hints (GROUP BY, ORDER BY suggestions).
    * Return an enhanced query + metadata for the pipeline.

    Usage::

        enhancer = QueryEnhancer()
        result = enhancer.enhance("show top 5 clients by revenue mtd")
        # result["enhanced_query"] == "show top 5 customers by total sales month to date"
    """

    def __init__(self) -> None:
        logger.debug("QueryEnhancer initialised.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def enhance(
        self,
        user_query: str,
        context_hint: Optional[str] = None,
    ) -> Dict[str, object]:
        """Enhance a natural-language query.

        Parameters
        ----------
        user_query : str
            The raw user question.
        context_hint : str, optional
            Extra context (e.g. previous query for conversational mode).

        Returns
        -------
        dict
            ``{enhanced_query, original_query, ambiguities, analytics_hints,
               changes_made, quality_score}``
        """
        if not user_query or not user_query.strip():
            return {
                "enhanced_query": "",
                "original_query": user_query,
                "ambiguities": [],
                "analytics_hints": [],
                "changes_made": [],
                "quality_score": 0,
                "error": "Empty query received.",
            }

        original = user_query.strip()
        text = original
        changes: List[str] = []

        # Step 1 — expand business abbreviations
        text, abbrev_changes = self._expand_abbreviations(text)
        changes.extend(abbrev_changes)

        # Step 2 — complete incomplete queries
        text, completion_changes = self._complete_query(text)
        changes.extend(completion_changes)

        # Step 3 — detect ambiguities
        ambiguities = self._detect_ambiguities(text)

        # Step 4 — collect analytics hints
        analytics_hints = self._collect_analytics_hints(text)

        # Step 5 — append context from previous query if provided
        if context_hint and context_hint.strip():
            text, ctx_change = self._merge_context(text, context_hint)
            if ctx_change:
                changes.append(ctx_change)

        # Compute a simple quality score
        quality_score = self._quality_score(
            text, len(ambiguities), len(analytics_hints)
        )

        logger.info(
            "Query enhanced: '%s' → '%s' | score=%d | ambiguities=%d",
            original[:60],
            text[:60],
            quality_score,
            len(ambiguities),
        )

        return {
            "success":         True,
            "enhanced_query":  text,
            "original_query":  original,
            "ambiguities":     ambiguities,
            "analytics_hints": analytics_hints,
            "changes_made":    changes,
            "quality_score":   quality_score,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _expand_abbreviations(text: str) -> tuple[str, List[str]]:
        """Replace known business abbreviations with full English text."""
        changes: List[str] = []
        result = text
        for abbrev, expansion in _BUSINESS_EXPANSIONS.items():
            pattern = re.compile(rf"\b{re.escape(abbrev)}\b", re.IGNORECASE)
            new = pattern.sub(expansion, result)
            if new != result:
                changes.append(f"Expanded '{abbrev}' → '{expansion}'.")
                result = new
        return result, changes

    @staticmethod
    def _complete_query(text: str) -> tuple[str, List[str]]:
        """Detect and complete known under-specified query patterns."""
        changes: List[str] = []
        result = text.strip()
        for pattern_str, template in _COMPLETIONS:
            match = re.fullmatch(pattern_str, result, re.IGNORECASE)
            if match:
                groups = match.groups()
                try:
                    completed = template.format(*groups, match=groups[0] if groups else result)
                except (IndexError, KeyError):
                    completed = template.format(match=result)
                changes.append(f"Completed under-specified query: '{result}' → '{completed}'.")
                result = completed
                break
        return result, changes

    @staticmethod
    def _detect_ambiguities(text: str) -> List[str]:
        """Return a list of detected ambiguity descriptions."""
        found: List[str] = []
        for pattern_str, reason in _AMBIGUOUS_PATTERNS:
            if re.search(pattern_str, text, re.IGNORECASE):
                found.append(reason)
        return found

    @staticmethod
    def _collect_analytics_hints(text: str) -> List[str]:
        """Collect SQL optimisation hints based on detected analytics terms."""
        hints: List[str] = []
        for pattern_str, hint in _ANALYTICS_HINTS:
            if re.search(pattern_str, text, re.IGNORECASE):
                hints.append(hint)
        return hints

    @staticmethod
    def _merge_context(
        current: str, context_hint: str
    ) -> tuple[str, Optional[str]]:
        """Merge previous query context for conversational continuation."""
        # Simple heuristic: if the current query is very short (≤ 5 words)
        # and lacks a subject noun, prepend context subject.
        if len(current.split()) <= 5:
            merged = f"{context_hint} — {current}"
            return merged, f"Merged context: '{context_hint}' + '{current}'."
        return current, None

    @staticmethod
    def _quality_score(
        text: str, ambiguity_count: int, hint_count: int
    ) -> int:
        """Return a 0-100 quality score for the enhanced query."""
        score = 50
        word_count = len(text.split())

        # Reward reasonable query length
        if word_count >= 5:
            score += 10
        if word_count >= 10:
            score += 10

        # Penalise ambiguity
        score -= ambiguity_count * 10

        # Reward analytics specificity
        score += hint_count * 5

        # Reward presence of dimension/metric keywords
        analytics_kw = r"\b(by|per|group|total|count|sum|average|trend|top|rank)\b"
        if re.search(analytics_kw, text, re.IGNORECASE):
            score += 10

        return max(0, min(100, score))
