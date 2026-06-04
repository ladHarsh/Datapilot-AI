"""
sql_semantic_checker.py — Detect common analytical SQL anti-patterns.

Used after LLM generation to trigger self-correction retries before execution.
"""
from __future__ import annotations

import re
from typing import List


def check_analytical_sql(sql: str, user_query: str = "") -> List[str]:
    """
    Return human-readable issue strings for known bad patterns.
    Empty list means no semantic issues detected.
    """
    issues: List[str] = []
    if not sql or not sql.strip():
        return ["SQL is empty."]

    q = (user_query or "").lower()
    s = sql
    s_upper = s.upper()

    # ── HAVING MIN >= AVG (always over-filters) ───────────────────────
    if re.search(r"HAVING\s+MIN\s*\([^)]+\)\s*>=\s*AVG\s*\(", s, re.I):
        issues.append(
            "Replace HAVING MIN(order_total) >= AVG(order_total) with "
            "NOT EXISTS on order_totals comparing complete order totals."
        )

    # ── Window functions mixed into customer-only GROUP BY (same SELECT) ─
    for block in re.finditer(
        r"\b(ROW_NUMBER|FIRST_VALUE)\s*\([^)]*\)[\s\S]{0,500}?GROUP\s+BY\s+([^);]+)",
        s,
        re.I,
    ):
        snippet = block.group(0)
        if "category_qty" in snippet.lower() or "category_rank" in snippet.lower():
            continue
        group_cols = block.group(2).lower()
        if "customer_id" in group_cols and "category" not in group_cols:
            if re.search(r"\bSUM\s*\(\s*\w+\.quantity", snippet, re.I):
                issues.append(
                    "Do not use ROW_NUMBER/FIRST_VALUE in the same SELECT that "
                    "GROUP BY customer_id only with SUM(quantity). Pre-aggregate "
                    "per (customer_id, category) in a separate CTE, then window-rank."
                )
                break

    # ── AVG on line-item revenue (not order-level AOV) ─────────────────
    if re.search(
        r"AVG\s*\(\s*\w+\.(?:revenue|Revenue|amount|price|unit_price|line_total)\s*\)",
        s,
        re.I,
    ) and not re.search(r"\border_totals?\b", s, re.I):
        issues.append(
            "avg_order_value must AVG complete order totals from an order_totals "
            "CTE (GROUP BY order_id first), not AVG(line-item revenue)."
        )

    # ── NOT EXISTS on line items vs order average ─────────────────────
    if re.search(r"NOT\s+EXISTS\s*\(", s, re.I) and re.search(
        r"order_items|oi\.", s, re.I
    ):
        if re.search(r"avg_order|average_order|order_total", s, re.I) and not re.search(
            r"order_totals?\s+\w+", s, re.I
        ):
            issues.append(
                "'No order below average' must use NOT EXISTS on order_totals "
                "(one row per order), not individual order_items rows."
            )

    # ── Top product filter in WHERE before GROUP BY ─────────────────────
    # Only flag if the WHERE EXISTS top_product is in the SAME block as a GROUP BY.
    # The previous regex searched the entire string and falsely flagged CTE-based queries.
    for block in re.finditer(r"SELECT\b[\s\S]+?(?=SELECT\b|$)", s, re.I):
        b_str = block.group(0)
        if re.search(r"WHERE\s+EXISTS\s*\([^)]*(max_product|top_product)", b_str, re.I):
            if re.search(r"JOIN\s+order_items", b_str, re.I) and re.search(r"GROUP\s+BY\s+[^;]*customer", b_str, re.I):
                issues.append(
                    "Move 'purchased top revenue product' check to HAVING/EXISTS "
                    "after full customer aggregation, not WHERE on joined line items."
                )
                break

    # ── Missing customer_name when requested ───────────────────────────
    wants_name = any(
        kw in q
        for kw in (
            "customer_name",
            "customer name",
            "customers who",
            "customer business",
            "business intelligence report",
        )
    )
    if wants_name and not re.search(
        r"\bcustomer_name\b|AS\s+customer_name\b|\bc\.name\s+AS",
        s,
        re.I,
    ):
        issues.append(
            "Final SELECT must include customer_name (join customers table)."
        )

    # ── CTE alias shadows column name ─────────────────────────────────
    if re.search(r"\bWITH\s+customer_id\s+AS\s*\(", s, re.I):
        issues.append("Rename CTE customer_id to customer_metrics_cte.")

    return issues
