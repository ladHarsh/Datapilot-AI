"""
SQL Injection Checker Module
============================
Analyzes SQL queries for injection patterns and sanitizes unsafe inputs.
Detects: OR 1=1, UNION SELECT, comment injections, semicolon injection,
         multiple statements, stacked queries, and time-based attacks.
"""

import re
import logging
from dataclasses import dataclass, field
from typing import List

logger = logging.getLogger(__name__)


@dataclass
class InjectionCheckResult:
    """Structured result from injection analysis."""
    is_safe: bool
    detected_patterns: List[str]
    risk_indicators: List[str]
    sanitized_query: str
    message: str
    injection_score: int  # 0 = clean, 100 = definitely injected

    def to_dict(self) -> dict:
        return {
            "is_safe": self.is_safe,
            "detected_patterns": self.detected_patterns,
            "risk_indicators": self.risk_indicators,
            "sanitized_query": self.sanitized_query,
            "message": self.message,
            "injection_score": self.injection_score,
        }


# ─── Injection pattern registry ──────────────────────────────────────────────
# Each entry: (pattern_name, compiled_regex, severity_score)
_INJECTION_PATTERNS = [
    # Tautology attacks
    ("tautology_or_1_eq_1",        re.compile(r"\bOR\s+1\s*=\s*1\b", re.IGNORECASE), 40),
    ("tautology_or_true",          re.compile(r"\bOR\s+['\"]?\s*true\s*['\"]?\b", re.IGNORECASE), 35),
    ("tautology_or_a_eq_a",        re.compile(r"\bOR\s+['\"]?\w+['\"]?\s*=\s*['\"]?\w+['\"]?\b", re.IGNORECASE), 20),
    ("tautology_and_1_eq_1",       re.compile(r"\bAND\s+1\s*=\s*1\b", re.IGNORECASE), 35),

    # UNION-based injection
    ("union_select",               re.compile(r"\bUNION\s+(ALL\s+)?SELECT\b", re.IGNORECASE), 50),
    ("union_all",                  re.compile(r"\bUNION\s+ALL\b", re.IGNORECASE), 30),

    # Stacked / semicolon injection
    ("semicolon_injection",        re.compile(r";\s*\w+", re.IGNORECASE), 45),
    ("multiple_statements",        re.compile(r";\s*(SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|EXEC|EXECUTE|CALL)\b", re.IGNORECASE), 50),

    # Comment injection
    ("inline_comment",             re.compile(r"--.*$", re.MULTILINE), 25),
    ("block_comment",              re.compile(r"/\*.*?\*/", re.DOTALL | re.IGNORECASE), 25),
    ("hash_comment",               re.compile(r"#.*$", re.MULTILINE), 20),

    # Stored procedure / exec injection
    ("exec_sp",                    re.compile(r"\b(EXEC|EXECUTE|CALL|SP_)\b", re.IGNORECASE), 40),
    ("xp_cmdshell",                re.compile(r"\bxp_cmdshell\b", re.IGNORECASE), 100),
    ("sys_tables",                 re.compile(r"\b(sysobjects|syscolumns|information_schema|sys\.tables|sys\.columns)\b", re.IGNORECASE), 30),

    # Time-based blind injection
    ("time_based_sleep",           re.compile(r"\b(SLEEP\s*\(|BENCHMARK\s*\(|WAITFOR\s+DELAY\b)", re.IGNORECASE), 60),

    # Error-based injection
    ("error_based_convert",        re.compile(r"\bCONVERT\s*\(.*?\bINT\b.*?\bSELECT\b", re.IGNORECASE), 35),
    ("extractvalue",               re.compile(r"\b(EXTRACTVALUE|UPDATEXML)\s*\(", re.IGNORECASE), 40),

    # Boolean-based injection helpers
    ("char_concat",                re.compile(r"\bCHAR\s*\(\s*\d+\s*\)", re.IGNORECASE), 20),
    ("hex_encoded",                re.compile(r"0x[0-9a-fA-F]{4,}", re.IGNORECASE), 20),

    # Out-of-band / DNS injection
    ("load_file",                  re.compile(r"\b(LOAD_FILE|INTO\s+OUTFILE|INTO\s+DUMPFILE)\b", re.IGNORECASE), 80),

    # Piggyback injection
    ("always_true_number",         re.compile(r"(['\"]?)\b(\w+)\b\1\s*=\s*(['\"]?)\b\2\b\3"), 30),
    ("quoted_string_escape",       re.compile(r"['\"][\s;]*(OR|AND)\b", re.IGNORECASE), 35),

    # Advanced / Evasion patterns
    ("mysql_executable_comment",   re.compile(r"/\*![0-9]*\s*.*?\*/", re.DOTALL), 45),
    ("boolean_blind_logic",        re.compile(r"\b(IF|CASE|WHEN|COALESCE)\s*\(.*?\b(SELECT|OR|AND|1=1)\b", re.IGNORECASE), 40),
    ("pg_sleep_blind",             re.compile(r"\bpg_sleep\s*\(", re.IGNORECASE), 60),
    ("db_info_leak",               re.compile(r"\b(VERSION|USER|DATABASE|SCHEMA|SESSION_USER|CURRENT_USER)\s*\(", re.IGNORECASE), 25),
    ("string_concat_trick",        re.compile(r"(\"|\')\s*(\+|\s*\|\|\s*)\s*(\"|\')", re.IGNORECASE), 30),
]

# Score threshold above which a query is considered injected
_INJECTION_THRESHOLD = 40


class InjectionChecker:
    """
    Detects SQL injection patterns in AI-generated or user-provided SQL queries.

    Uses a pattern-matching approach with severity scoring.
    Queries exceeding the threshold are flagged as unsafe.
    """

    def check(self, sql: str) -> InjectionCheckResult:
        """
        Analyze a SQL string for injection patterns.

        Args:
            sql: The SQL query string to analyze.

        Returns:
            InjectionCheckResult with detection details.
        """
        logger.info("InjectionChecker: analyzing query.")

        if not sql or not sql.strip():
            return InjectionCheckResult(
                is_safe=False,
                detected_patterns=[],
                risk_indicators=["empty_query"],
                sanitized_query="",
                message="Empty query provided.",
                injection_score=0,
            )

        detected: List[str] = []
        risk_indicators: List[str] = []
        total_score = 0

        for pattern_name, pattern_regex, severity in _INJECTION_PATTERNS:
            if pattern_regex.search(sql):
                detected.append(pattern_name)
                risk_indicators.append(f"{pattern_name} (severity={severity})")
                total_score += severity
                logger.warning("InjectionChecker: pattern detected — %s (score+%d)", pattern_name, severity)

        # Cap score at 100
        total_score = min(total_score, 100)

        is_safe = total_score < _INJECTION_THRESHOLD and len(detected) == 0

        # Sanitize the query regardless of result
        sanitized = self._sanitize(sql)

        if is_safe:
            message = "No SQL injection patterns detected. Query appears clean."
        else:
            message = (
                f"SQL injection risk detected. Score: {total_score}/100. "
                f"Patterns found: {', '.join(detected)}. Query blocked."
            )
            logger.error("InjectionChecker: UNSAFE query — score=%d patterns=%s", total_score, detected)

        return InjectionCheckResult(
            is_safe=is_safe,
            detected_patterns=detected,
            risk_indicators=risk_indicators,
            sanitized_query=sanitized,
            message=message,
            injection_score=total_score,
        )

    # ── Sanitization ──────────────────────────────────────────────────────────

    def _sanitize(self, sql: str) -> str:
        """
        Perform best-effort sanitization by stripping common injection vectors.
        This is NOT a substitute for parameterized queries but provides a
        defense-in-depth layer for AI-generated SQL.
        """
        sanitized = sql

        # Remove inline comments
        sanitized = re.sub(r"--[^\n]*", " ", sanitized)

        # Remove block comments
        sanitized = re.sub(r"/\*.*?\*/", " ", sanitized, flags=re.DOTALL)

        # Remove hash comments
        sanitized = re.sub(r"#[^\n]*", " ", sanitized)

        # Remove dangerous functions
        dangerous_funcs = [
            r"\bxp_cmdshell\b",
            r"\bSLEEP\s*\(",
            r"\bWAITFOR\s+DELAY\b",
            r"\bBENCHMARK\s*\(",
            r"\bLOAD_FILE\s*\(",
            r"\bINTO\s+OUTFILE\b",
            r"\bINTO\s+DUMPFILE\b",
        ]
        for func_pattern in dangerous_funcs:
            sanitized = re.sub(func_pattern, "/* BLOCKED */", sanitized, flags=re.IGNORECASE)

        # Collapse excess whitespace
        sanitized = " ".join(sanitized.split()).strip()

        return sanitized


# ── Module-level convenience function ─────────────────────────────────────────

def check_injection(sql: str) -> dict:
    """
    Convenience function for injection checking.

    Args:
        sql: SQL query string.

    Returns:
        dict with injection analysis result.
    """
    checker = InjectionChecker()
    return checker.check(sql).to_dict()
