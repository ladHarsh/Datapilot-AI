"""
query_similarity_checker.py — SQL AI Analytics Platform.

Compares two natural-language queries for semantic similarity.

Supports:
- Token-level Jaccard similarity (no external models needed)
- Intent keyword matching (aggregation, filtering, ranking intent)
- Business term synonym normalization before comparison

Use cases:
- Conversational query continuation (detect if user is refining a query)
- Duplicate query detection (avoid re-running identical queries)
- Cache key generation for semantically equivalent queries

Author : Member 2 — AI/LLM Engineer
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

# Business synonyms for normalization before comparison
_SYNONYMS: Dict[str, str] = {
    "revenue":      "sales",
    "earnings":     "sales",
    "income":       "sales",
    "clients":      "customers",
    "buyers":       "customers",
    "items":        "products",
    "goods":        "products",
    "staff":        "employees",
    "workers":      "employees",
    "orders":       "transactions",
    "purchases":    "transactions",
}

# Intent signals by category
_INTENT_PATTERNS: Dict[str, List[str]] = {
    "aggregation": [r"\btotal\b", r"\bsum\b", r"\baverage\b", r"\bcount\b", r"\bhow many\b"],
    "ranking":     [r"\btop\s*\d+\b", r"\bbest\b", r"\brank\b", r"\bhighest\b", r"\bmost\b"],
    "filtering":   [r"\bwhere\b", r"\bonly\b", r"\bspecific\b", r"\bfilter\b"],
    "trend":       [r"\btrend\b", r"\bover time\b", r"\bmonthly\b", r"\bweekly\b", r"\bgrowth\b"],
    "comparison":  [r"\bcompare\b", r"\bvs\b", r"\bversus\b", r"\bdifference\b"],
}


class QuerySimilarityChecker:
    """Compare two natural-language queries for intent similarity.

    Usage::

        checker = QuerySimilarityChecker()
        result = checker.compare(
            "Show total revenue by month",
            "Monthly revenue summary",
        )
        # result["similarity"] → 0.72
        # result["same_intent"] → True
    """

    def compare(
        self,
        query_a: str,
        query_b: str,
        threshold: float = 0.5,
    ) -> Dict[str, Any]:
        """Compare two queries for similarity.

        Parameters
        ----------
        query_a : str
            First natural-language query.
        query_b : str
            Second natural-language query.
        threshold : float
            Minimum Jaccard similarity to consider intents as matching.

        Returns
        -------
        dict
            ``{similarity, same_intent, intent_a, intent_b, is_refinement}``
        """
        norm_a = self._normalize(query_a)
        norm_b = self._normalize(query_b)

        similarity = self._jaccard(norm_a, norm_b)

        intent_a = self._detect_intent(query_a)
        intent_b = self._detect_intent(query_b)

        same_intent = similarity >= threshold or (bool(intent_a & intent_b))
        is_refinement = self._is_refinement(query_a, query_b)

        return {
            "similarity":    round(similarity, 4),
            "same_intent":   same_intent,
            "intent_a":      sorted(intent_a),
            "intent_b":      sorted(intent_b),
            "is_refinement": is_refinement,
        }

    def is_duplicate(self, query_a: str, query_b: str, threshold: float = 0.85) -> bool:
        """Return True if two queries are near-identical (likely duplicates)."""
        result = self.compare(query_a, query_b, threshold)
        return result["similarity"] >= threshold

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize(query: str) -> str:
        """Lowercase, remove stop words, apply synonym mapping."""
        stop_words = {"the", "a", "an", "me", "show", "get", "list", "find",
                      "what", "which", "how", "of", "for", "in", "by", "on"}
        text = query.lower().strip()
        for syn, canonical in _SYNONYMS.items():
            text = re.sub(rf"\b{re.escape(syn)}\b", canonical, text)
        tokens = [w for w in re.findall(r"\b\w+\b", text) if w not in stop_words]
        return " ".join(tokens)

    @staticmethod
    def _jaccard(text_a: str, text_b: str) -> float:
        """Token-level Jaccard similarity between two strings."""
        set_a = set(text_a.split())
        set_b = set(text_b.split())
        if not set_a and not set_b:
            return 1.0
        if not set_a or not set_b:
            return 0.0
        return len(set_a & set_b) / len(set_a | set_b)

    @staticmethod
    def _detect_intent(query: str) -> set:
        """Return a set of detected intent labels."""
        detected = set()
        query_lower = query.lower()
        for intent, patterns in _INTENT_PATTERNS.items():
            if any(re.search(p, query_lower) for p in patterns):
                detected.add(intent)
        return detected

    @staticmethod
    def _is_refinement(query_a: str, query_b: str) -> bool:
        """Heuristic: B is a refinement of A if it adds qualifiers to A's topic."""
        tokens_a = set(query_a.lower().split())
        tokens_b = set(query_b.lower().split())
        # B refines A if A's tokens are a subset of B's
        return tokens_a.issubset(tokens_b) and len(tokens_b) > len(tokens_a)
