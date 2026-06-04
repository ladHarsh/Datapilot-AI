"""
Query Complexity Checker Module
================================
Analyzes SQL query complexity to prevent database overload.
Detects excessive JOINs, nested subqueries, full table scans,
and applies configurable limits for safe execution.
"""

import re
import logging
from dataclasses import dataclass
from typing import List, Dict

import sqlparse
from sqlparse.sql import Statement

logger = logging.getLogger(__name__)


# ─── Configurable complexity limits ──────────────────────────────────────────
class ComplexityLimits:
    MAX_JOINS: int = 5
    MAX_SUBQUERY_DEPTH: int = 3
    MAX_QUERY_LENGTH: int = 5000          # characters
    MAX_UNION_COUNT: int = 3
    MAX_AGGREGATE_FUNCTIONS: int = 10
    EXECUTION_TIMEOUT_SECONDS: int = 30
    MAX_RESULT_ROWS: int = 10_000


@dataclass
class ComplexityResult:
    """Structured result from complexity analysis."""
    is_acceptable: bool
    complexity_score: int               # 0–100 (higher = more complex)
    complexity_level: str               # low / medium / high / critical
    join_count: int
    subquery_depth: int
    union_count: int
    has_full_table_scan_risk: bool
    query_length: int
    violations: List[str]
    warnings: List[str]
    recommended_timeout: int
    message: str

    def to_dict(self) -> dict:
        return {
            "is_acceptable": self.is_acceptable,
            "complexity_score": self.complexity_score,
            "complexity_level": self.complexity_level,
            "join_count": self.join_count,
            "subquery_depth": self.subquery_depth,
            "union_count": self.union_count,
            "has_full_table_scan_risk": self.has_full_table_scan_risk,
            "query_length": self.query_length,
            "violations": self.violations,
            "warnings": self.warnings,
            "recommended_timeout": self.recommended_timeout,
            "message": self.message,
        }


class ComplexityChecker:
    """
    Analyzes SQL queries for structural complexity that could overload the database.

    Scoring:
    - Each violation adds points to the complexity score (0–100).
    - Queries scoring >= 80 are rejected outright (critical).
    - Queries scoring 50–79 are flagged as high complexity (allowed with warning).
    - Queries scoring 20–49 are medium complexity.
    - Queries scoring < 20 are low complexity.
    """

    def __init__(self, limits: ComplexityLimits = None):
        self.limits = limits or ComplexityLimits()

        # Patterns
        self._join_pattern = re.compile(
            r"\b(INNER\s+JOIN|LEFT\s+JOIN|RIGHT\s+JOIN|FULL\s+OUTER\s+JOIN|CROSS\s+JOIN|JOIN)\b",
            re.IGNORECASE,
        )
        self._union_pattern = re.compile(r"\bUNION(\s+ALL)?\b", re.IGNORECASE)
        self._subquery_pattern = re.compile(r"\bSELECT\b", re.IGNORECASE)
        self._full_scan_patterns = [
            re.compile(r"\bSELECT\s+\*\s+FROM\b", re.IGNORECASE),
            re.compile(r"\bWHERE\s+1\s*=\s*1\b", re.IGNORECASE),
            re.compile(r"\bFROM\b(?!\s*\()", re.IGNORECASE),   # FROM without subquery = possible scan
        ]
        self._no_where_pattern = re.compile(
            r"\bSELECT\b(?:(?!\bWHERE\b).)*$", re.IGNORECASE | re.DOTALL
        )
        self._aggregate_pattern = re.compile(
            r"\b(COUNT|SUM|AVG|MIN|MAX|GROUP_CONCAT|ARRAY_AGG|STRING_AGG)\s*\(",
            re.IGNORECASE,
        )
        self._order_by_no_limit_pattern = re.compile(
            r"\bORDER\s+BY\b(?:(?!\bLIMIT\b).)*$", re.IGNORECASE | re.DOTALL
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def check(self, sql: str) -> ComplexityResult:
        """
        Analyze the complexity of a SQL query.

        Args:
            sql: The SQL query string.

        Returns:
            ComplexityResult with score, level, and violation details.
        """
        logger.info("ComplexityChecker: starting analysis.")

        violations: List[str] = []
        warnings: List[str] = []
        score = 0

        # 1. Query length
        query_length = len(sql)
        if query_length > self.limits.MAX_QUERY_LENGTH:
            violations.append(
                f"Query length ({query_length}) exceeds limit ({self.limits.MAX_QUERY_LENGTH} chars)."
            )
            score += 25
        elif query_length > self.limits.MAX_QUERY_LENGTH * 0.7:
            warnings.append(f"Query length ({query_length}) is approaching the limit.")
            score += 10

        # 2. JOIN count
        join_count = len(self._join_pattern.findall(sql))
        if join_count > self.limits.MAX_JOINS:
            violations.append(
                f"Excessive JOINs ({join_count}). Maximum allowed: {self.limits.MAX_JOINS}."
            )
            score += min(30, (join_count - self.limits.MAX_JOINS) * 6)
        elif join_count >= self.limits.MAX_JOINS:
            warnings.append(f"JOIN count ({join_count}) is at the maximum threshold.")
            score += 10

        # 3. UNION count
        union_count = len(self._union_pattern.findall(sql))
        if union_count > self.limits.MAX_UNION_COUNT:
            violations.append(
                f"Excessive UNION operations ({union_count}). Maximum allowed: {self.limits.MAX_UNION_COUNT}."
            )
            score += 15

        # 4. Subquery depth (count of nested SELECT keywords)
        select_count = len(self._subquery_pattern.findall(sql))
        subquery_depth = max(0, select_count - 1)  # first SELECT is the main query
        if subquery_depth > self.limits.MAX_SUBQUERY_DEPTH:
            violations.append(
                f"Nested subquery depth ({subquery_depth}) exceeds limit ({self.limits.MAX_SUBQUERY_DEPTH})."
            )
            score += min(25, subquery_depth * 5)
        elif subquery_depth > 1:
            warnings.append(f"Query contains {subquery_depth} levels of subquery nesting.")
            score += subquery_depth * 3

        # 5. Full table scan risk
        has_full_scan = self._detect_full_scan_risk(sql)
        if has_full_scan:
            warnings.append("Potential full table scan detected (SELECT * or missing WHERE clause).")
            score += 15

        # 6. Aggregate function overuse
        agg_count = len(self._aggregate_pattern.findall(sql))
        if agg_count > self.limits.MAX_AGGREGATE_FUNCTIONS:
            warnings.append(
                f"High number of aggregate functions ({agg_count}). Consider optimizing."
            )
            score += 10

        # 7. ORDER BY without LIMIT (dangerous at scale)
        if re.search(r"\bORDER\s+BY\b", sql, re.IGNORECASE) and not re.search(r"\bLIMIT\b", sql, re.IGNORECASE):
            warnings.append("ORDER BY used without LIMIT — may cause full result-set sort.")
            score += 10

        # Cap score
        score = min(score, 100)

        # Determine complexity level and acceptability
        complexity_level, is_acceptable = self._classify(score)
        if violations:
            is_acceptable = False
            complexity_level = "critical"
            score = max(score, 80)

        # Compute recommended timeout (scale with complexity)
        recommended_timeout = min(
            self.limits.EXECUTION_TIMEOUT_SECONDS,
            max(5, int(self.limits.EXECUTION_TIMEOUT_SECONDS * (score / 100) + 5)),
        )

        if is_acceptable:
            message = f"Query complexity is {complexity_level} (score={score}). Execution permitted."
        else:
            message = (
                f"Query complexity is CRITICAL (score={score}). Execution blocked to protect the database. "
                f"Violations: {'; '.join(violations)}"
            )

        logger.info(
            "ComplexityChecker: score=%d level=%s acceptable=%s joins=%d subqueries=%d",
            score, complexity_level, is_acceptable, join_count, subquery_depth,
        )

        return ComplexityResult(
            is_acceptable=is_acceptable,
            complexity_score=score,
            complexity_level=complexity_level,
            join_count=join_count,
            subquery_depth=subquery_depth,
            union_count=union_count,
            has_full_table_scan_risk=has_full_scan,
            query_length=query_length,
            violations=violations,
            warnings=warnings,
            recommended_timeout=recommended_timeout,
            message=message,
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    def _detect_full_scan_risk(self, sql: str) -> bool:
        """Heuristic check for potential full table scan."""
        has_select_star = bool(re.search(r"\bSELECT\s+\*", sql, re.IGNORECASE))
        has_where = bool(re.search(r"\bWHERE\b", sql, re.IGNORECASE))
        has_limit = bool(re.search(r"\bLIMIT\b", sql, re.IGNORECASE))

        # Flag if: SELECT * without LIMIT, or no WHERE clause without LIMIT
        if has_select_star and not has_limit:
            return True
        if not has_where and not has_limit:
            return True
        return False

    def _classify(self, score: int) -> tuple:
        """Map numeric score to complexity level and acceptability."""
        if score >= 80:
            return "critical", False
        elif score >= 50:
            return "high", True   # allowed but warned
        elif score >= 20:
            return "medium", True
        else:
            return "low", True


# ── Module-level convenience function ─────────────────────────────────────────

def check_complexity(sql: str) -> dict:
    """
    Convenience function for complexity checking.

    Args:
        sql: SQL query string.

    Returns:
        dict with complexity analysis result.
    """
    checker = ComplexityChecker()
    return checker.check(sql).to_dict()
