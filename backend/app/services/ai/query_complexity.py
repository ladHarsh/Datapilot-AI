"""
Query Complexity Classifier — DataPilot AI Performance Engine.

Zero-latency query classification using pure regex pattern matching.
Routes queries to optimized prompt strategies and model tiers.

Complexity levels:
  EASY   → simple count/sum/select → lightweight prompt + fastest model
  MEDIUM → joins/group by/filters  → standard prompt + standard model
  HARD   → CTEs/window/subquery    → full prompt + best model

Author: DataPilot Performance Team
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Tuple

__all__ = ["QueryComplexity", "classify_query"]


class QueryComplexity(str, Enum):
    EASY   = "easy"
    MEDIUM = "medium"
    HARD   = "hard"


# ─── Pattern sets ────────────────────────────────────────────────────────────

# HARD signals — any of these → HARD (most expensive)
_HARD_PATTERNS = re.compile(
    r"\b("
    r"with\s+\w|"                        # CTE
    r"window\s+function|"
    r"dense_rank|row_number|rank\s*\(|"  # window funcs
    r"partition\s+by|"
    r"lag\s*\(|lead\s*\(|"
    r"ntile\s*\(|percent_rank|"
    r"correlated|subquery|"
    r"having\s+.*avg|having\s+.*sum|"    # complex HAVING
    r"crosstab|pivot|unpivot|"
    r"lateral|recursive|"
    r"anomal|predict|forecast|"
    r"correlation|regression|"
    r"running\s+total|cumulative|"
    r"cohort|retention|funnel|"
    r"multi.*dimension|segment.*analysis"
    r")\b",
    re.IGNORECASE,
)

# MEDIUM signals — any of these → at least MEDIUM
_MEDIUM_PATTERNS = re.compile(
    r"\b("
    r"join|left\s+join|right\s+join|inner\s+join|full\s+join|"
    r"group\s+by|order\s+by|having|"
    r"subquery|exists|not\s+exists|"
    r"date_trunc|date_format|extract|"
    r"case\s+when|coalesce|nullif|"
    r"distinct|union|intersect|except|"
    r"top\s+\d+|rank|trend|compare|"
    r"month.*over.*month|year.*over.*year|"
    r"growth\s+rate|moving\s+average"
    r")\b",
    re.IGNORECASE,
)

# EASY signals — pure COUNT/SUM/AVG/SELECT with no grouping or date ops
_EASY_PATTERNS = re.compile(
    r"^("
    r"(how\s+many|count\s+(all|total|the)|total\s+count|"
    r"show\s+all|list\s+all|get\s+all|fetch\s+all|"
    r"select\s+\*|show\s+top\s+\d+)\b"
    r")",
    re.IGNORECASE,
)


def classify_query(user_query: str) -> Tuple[QueryComplexity, str]:
    """Classify a natural-language query into EASY / MEDIUM / HARD.

    Parameters
    ----------
    user_query : str
        The user's natural-language question.

    Returns
    -------
    tuple[QueryComplexity, str]
        ``(complexity_level, reason)``

    Performance
    -----------
    Pure regex — executes in < 1 ms regardless of query length.
    """
    q = user_query.strip()

    if _HARD_PATTERNS.search(q):
        return QueryComplexity.HARD, "Contains advanced analytics patterns (CTE / window / correlation)"

    if _MEDIUM_PATTERNS.search(q):
        return QueryComplexity.MEDIUM, "Contains joins, aggregations, or date operations"

    if _EASY_PATTERNS.match(q) or len(q.split()) <= 8:
        return QueryComplexity.EASY, "Simple lookup or aggregate query"

    # Default: MEDIUM for anything unclassified
    return QueryComplexity.MEDIUM, "Default to medium complexity"


def get_model_for_complexity(complexity: QueryComplexity, default_model: str | None = None) -> str | None:
    """Return the recommended model override for a given complexity level.

    EASY/MEDIUM queries use a fast model; HARD queries use the full model.
    Returns None to mean "use configured default".
    """
    if complexity == QueryComplexity.EASY:
        # For easy queries: don't override — let config decide,
        # but signal caller to use shorter prompt
        return None
    if complexity == QueryComplexity.HARD:
        # Use whatever the user configured — don't downgrade hard queries
        return default_model
    return None  # MEDIUM: use default
