"""
Confidence Service — SQL AI Analytics Platform.

Calculates a multidimensional confidence score for generated SQL queries.

Checks:
- Schema Integrity (Tables/Columns exist)
- Relationship Validity (Joins follow FKs)
- Safety (No destructive operations)
- Intent Alignment (Ambiguity detection)
- Result Predictability (Filter presence)

Author : Member 2 — AI/LLM Engineer
"""

from __future__ import annotations

import re
import logging
from typing import Any, Dict, List, Set

import sqlparse
from sqlparse.sql import Where, Identifier, IdentifierList
from sqlparse.tokens import Keyword, Name

logger = logging.getLogger(__name__)


class ConfidenceService:
    """Validator for AI-generated SQL queries.

    Provides a deterministic score (0-100) based on how well the SQL matches
     the physical database schema and the perceived intent.
    """

    def __init__(self) -> None:
        pass

    def calculate_confidence(
        self,
        sql_query: str,
        schema: Dict[str, Any],
        original_query: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyse SQL and return a structured confidence report.

        Parameters
        ----------
        sql_query : str
            The generated SQL.
        schema : dict
            The database schema.
        original_query : str, optional
            The user's NL question (to check for keyword alignment).

        Returns
        -------
        dict
            ``{score, label, checks, warnings}``
        """
        warnings: List[str] = []
        checks = {
            "tables_valid":  False,
            "columns_valid": False,
            "joins_valid":   False,
            "safe_query":    False,
            "has_filter":    False,
            "intent_match":  False,
        }

        # ── 1. Safety Check ───────────────────────────────────────────
        destructive = r"\b(DROP|DELETE|INSERT|UPDATE|TRUNCATE|ALTER|CREATE|GRANT|REVOKE)\b"
        if re.search(destructive, sql_query.upper()):
            warnings.append("Security Alert: Query contains potentially destructive keywords.")
            checks["safe_query"] = False
        else:
            checks["safe_query"] = True

        # ── 2. Parse Query ────────────────────────────────────────────
        try:
            parsed = sqlparse.parse(sql_query)
            if not parsed:
                raise ValueError("SQL could not be parsed.")
            stmt = parsed[0]
        except Exception as exc:
            return {
                "score": 0,
                "label": "Low",
                "checks": checks,
                "warnings": [f"Parsing failed: {exc}"]
            }

        # ── 3. Schema Validation ──────────────────────────────────────
        tables_used = self._extract_tables(stmt)
        schema_tables = {t["name"].lower() for t in schema.get("tables", [])}
        
        if not tables_used:
            checks["tables_valid"] = True # E.g. SELECT 1
        else:
            missing_tables = tables_used - schema_tables
            if missing_tables:
                warnings.append(f"Tables not in schema: {', '.join(missing_tables)}")
                checks["tables_valid"] = False
            else:
                checks["tables_valid"] = True

        # Check Columns
        if checks["tables_valid"] and tables_used:
            cols_used = self._extract_columns(stmt, tables_used)
            schema_cols = set()
            for t in schema["tables"]:
                if t["name"].lower() in tables_used:
                    schema_cols.update(c["name"].lower() for c in t["columns"])
            
            # Filter out standard SQL functions/aliases
            missing_cols = {c for c in cols_used if c not in schema_cols and c not in {"*", "count", "sum", "avg", "min", "max", "as", "id"}}
            if missing_cols:
                warnings.append(f"Columns not in schema: {', '.join(missing_cols)}")
                checks["columns_valid"] = False
            else:
                checks["columns_valid"] = True
        else:
            checks["columns_valid"] = checks["tables_valid"]

        # ── 4. Join Validation ────────────────────────────────────────
        checks["joins_valid"] = self._validate_joins(sql_query, schema, warnings)

        # ── 5. Intent & Filtering ──────────────────────────────────────
        checks["has_filter"] = any(isinstance(t, Where) for t in stmt.tokens)
        
        # Simple intent match: check if key nouns from NL are in SQL
        if original_query:
            checks["intent_match"] = self._check_intent(original_query, sql_query)
        else:
            checks["intent_match"] = True

        # ── 6. Final Score Calculation ────────────────────────────────
        score = self._compute_score(checks)
        
        return {
            "score":    score,
            "label":    "High" if score >= 80 else ("Medium" if score >= 50 else "Low"),
            "checks":   checks,
            "warnings": warnings
        }

    # ------------------------------------------------------------------
    # Private Utilities
    # ------------------------------------------------------------------

    def _extract_tables(self, stmt) -> Set[str]:
        tables = set()
        for token in stmt.tokens:
            if token.ttype is Keyword and token.value.upper() in ("FROM", "JOIN"):
                idx = stmt.token_index(token)
                res = stmt.token_next(idx, skip_ws=True)
                if not res: continue
                next_tok = res[1] # token_next returns (index, token)
                if isinstance(next_tok, Identifier):
                    tables.add(next_tok.get_real_name().lower())
                elif isinstance(next_tok, IdentifierList):
                    for iden in next_tok.get_identifiers():
                        tables.add(iden.get_real_name().lower())
        return {t for t in tables if t}

    def _extract_columns(self, stmt, tables) -> Set[str]:
        cols = set()
        for token in stmt.flatten():
            if token.ttype is Name or isinstance(token, Identifier):
                val = token.value.lower()
                if val not in tables and len(val) > 1:
                    cols.add(val)
        return cols

    def _validate_joins(self, sql: str, schema: dict, warnings: list) -> bool:
        if "JOIN" not in sql.upper():
            return True
        
        # Regex to find join conditions e.g. a.id = b.user_id
        matches = re.findall(r"(\w+)\.(\w+)\s*=\s*(\w+)\.(\w+)", sql, re.I)
        if not matches:
            return True # couldn't detect, be optimistic
            
        all_valid = True
        for t1, c1, t2, c2 in matches:
            t1, c1, t2, c2 = t1.lower(), c1.lower(), t2.lower(), c2.lower()
            # Check if this FK relationship exists in schema
            found = False
            for tbl in schema.get("tables", []):
                if tbl["name"].lower() == t1:
                    for fk in tbl.get("foreign_keys", []):
                        if fk["column"].lower() == c1 and fk["references_table"].lower() == t2:
                            found = True; break
                if not found and tbl["name"].lower() == t2:
                     for fk in tbl.get("foreign_keys", []):
                        if fk["column"].lower() == c2 and fk["references_table"].lower() == t1:
                            found = True; break
            if not found:
                warnings.append(f"Relationship {t1}.{c1} = {t2}.{c2} not defined in schema.")
                all_valid = False
        return all_valid

    def _check_intent(self, nl: str, sql: str) -> bool:
        # Very simple: if NL mentions "revenue" but SQL doesn't have "SUM", score down
        nl_lower = nl.lower()
        sql_upper = sql.upper()
        if "total" in nl_lower or "sum" in nl_lower or "revenue" in nl_lower:
            if "SUM" not in sql_upper: return False
        if "average" in nl_lower or "mean" in nl_lower:
            if "AVG" not in sql_upper: return False
        return True

    def _compute_score(self, checks: dict) -> int:
        score = 0
        if checks["tables_valid"]: score += 30
        if checks["columns_valid"]: score += 30
        if checks["joins_valid"]: score += 15
        if checks["safe_query"]: score += 10
        if checks["has_filter"]: score += 10
        if checks["intent_match"]: score += 5
        
        if not checks["safe_query"]: score = 0  # Unsafe queries get 0
        elif not checks["tables_valid"]: score = min(score, 40) # Hard cap if tables wrong
        return score
