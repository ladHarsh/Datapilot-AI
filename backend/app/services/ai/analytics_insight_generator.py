"""
Analytics Insight Generator — SQL AI Analytics Platform.

Converts raw SQL query results (rows + columns) into human-readable
business insight statements suitable for dashboard insight cards.

Supports:
* Trend detection  (up / down / flat)
* Top-performer identification
* Anomaly flagging
* Summary statistics
* LLM-augmented narrative (optional)

Author : Member 2 — AI/LLM Engineer
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Threshold constants (tweak as required)
# ---------------------------------------------------------------------------
_TREND_UP_THRESHOLD    = 0.05   # 5 % increase counts as upward trend
_TREND_DOWN_THRESHOLD  = -0.05  # 5 % decrease counts as downward trend
_ANOMALY_STD_FACTOR    = 2.0    # values > mean + 2σ are flagged


class AnalyticsInsightGenerator:
    """Generate business insight statements from SQL query results.

    The generator works in two modes:

    1. **Rule-based** (always available) — inspects numeric columns for
       trends, anomalies, and top performers using statistical heuristics.
    2. **LLM-augmented** (optional) — passes a result summary to the LLM
       and asks for a professional narrative.  Requires a live LLMService.

    Usage::

        gen = AnalyticsInsightGenerator()
        insights = gen.generate(
            columns=["month", "revenue"],
            rows=[["Jan", 50000], ["Feb", 55000], ["Mar", 52000]],
            user_query="show monthly revenue",
        )
        # insights["insights"] → ["Revenue increased 10% from Jan to Feb.", ...]
    """

    def __init__(self, llm_service: Optional[Any] = None) -> None:
        """Initialise the generator.

        Parameters
        ----------
        llm_service : LLMService, optional
            If supplied, LLM-augmented narrative is also generated.
        """
        self._llm = llm_service
        logger.debug("AnalyticsInsightGenerator initialised (llm=%s).", bool(llm_service))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        columns: List[str],
        rows: List[List[Any]],
        user_query: str = "",
        query_sql: str = "",
    ) -> Dict[str, Any]:
        """Generate insights from query result data.

        Parameters
        ----------
        columns : list[str]
            Column names in the result set.
        rows : list[list]
            Result rows (each row is a list of values aligned with columns).
        user_query : str
            Original natural-language question for context.
        query_sql : str
            Generated SQL for additional context in LLM narrative.

        Returns
        -------
        dict
            ``{insights, summary_stats, trends, top_performers,
               anomalies, narrative, row_count, column_count}``
        """
        if not rows:
            return {
                "success":        True,
                "insights":       ["No data returned for this query."],
                "summary_stats":  {},
                "trends":         [],
                "top_performers": [],
                "anomalies":      [],
                "narrative":      "The query returned no results.",
                "row_count":      0,
                "column_count":   len(columns),
            }

        col_lower = [c.lower() for c in columns]
        numeric_cols = self._identify_numeric_columns(columns, rows)

        insights: List[str]      = []
        trends: List[str]        = []
        top_performers: List[str] = []
        anomalies: List[str]     = []

        # -- Row / column summary
        insights.append(
            f"Query returned {len(rows)} row{'s' if len(rows) != 1 else ''} "
            f"across {len(columns)} column{'s' if len(columns) != 1 else ''}."
        )

        # -- Numeric analysis
        for col_name, col_idx in numeric_cols.items():
            values = self._extract_numeric_values(rows, col_idx)
            if len(values) < 2:
                continue

            stats     = self._summary_stats(values)
            trend     = self._detect_trend(values)
            top       = self._top_performer(columns, rows, col_idx)
            anoms     = self._detect_anomalies(values, col_name, columns, rows, col_idx)

            # Trend insights
            if trend["direction"] == "up":
                change_pct = abs(trend["change_pct"])
                trends.append(
                    f"{col_name.capitalize()} shows an upward trend "
                    f"(+{change_pct:.1f}% from first to last record)."
                )
            elif trend["direction"] == "down":
                change_pct = abs(trend["change_pct"])
                trends.append(
                    f"{col_name.capitalize()} shows a downward trend "
                    f"(-{change_pct:.1f}% from first to last record)."
                )
            else:
                trends.append(f"{col_name.capitalize()} remains relatively stable.")

            # Top performer
            if top:
                top_performers.append(top)

            # Anomalies
            anomalies.extend(anoms)

            # Stats insight
            insights.append(
                f"{col_name.capitalize()}: min={stats['min']:.2f}, "
                f"max={stats['max']:.2f}, avg={stats['mean']:.2f}."
            )

        # Combine into single insight list
        all_insights = insights + trends + top_performers + anomalies

        # Summary stats dict
        summary_stats: Dict[str, Dict[str, float]] = {}
        for col_name, col_idx in numeric_cols.items():
            vals = self._extract_numeric_values(rows, col_idx)
            if vals:
                summary_stats[col_name] = self._summary_stats(vals)

        # Optional LLM narrative
        narrative = self._build_narrative(
            user_query, all_insights, summary_stats
        )

        return {
            "success":        True,
            "insights":       all_insights,
            "summary_stats":  summary_stats,
            "trends":         trends,
            "top_performers": top_performers,
            "anomalies":      anomalies,
            "narrative":      narrative,
            "row_count":      len(rows),
            "column_count":   len(columns),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _identify_numeric_columns(
        columns: List[str], rows: List[List[Any]]
    ) -> Dict[str, int]:
        """Return a dict of {col_name: col_index} for numeric columns."""
        numeric: Dict[str, int] = {}
        for idx, col in enumerate(columns):
            # Check first non-None value
            for row in rows:
                val = row[idx] if idx < len(row) else None
                if val is None:
                    continue
                try:
                    float(val)
                    numeric[col] = idx
                    break
                except (ValueError, TypeError):
                    break
        return numeric

    @staticmethod
    def _extract_numeric_values(
        rows: List[List[Any]], col_idx: int
    ) -> List[float]:
        """Extract floats from a column, skipping None / non-numeric."""
        values: List[float] = []
        for row in rows:
            val = row[col_idx] if col_idx < len(row) else None
            if val is None:
                continue
            try:
                values.append(float(val))
            except (ValueError, TypeError):
                continue
        return values

    @staticmethod
    def _summary_stats(values: List[float]) -> Dict[str, float]:
        """Basic descriptive statistics."""
        n    = len(values)
        mean = sum(values) / n
        variance = sum((v - mean) ** 2 for v in values) / n if n > 1 else 0.0
        std  = variance ** 0.5
        return {
            "count": float(n),
            "min":   min(values),
            "max":   max(values),
            "mean":  mean,
            "std":   std,
        }

    @staticmethod
    def _detect_trend(values: List[float]) -> Dict[str, Any]:
        """Detect overall trend direction using first vs last value."""
        first, last = values[0], values[-1]
        if first == 0:
            return {"direction": "flat", "change_pct": 0.0}
        change_pct = (last - first) / abs(first) * 100
        if change_pct > _TREND_UP_THRESHOLD * 100:
            direction = "up"
        elif change_pct < _TREND_DOWN_THRESHOLD * 100:
            direction = "down"
        else:
            direction = "flat"
        return {"direction": direction, "change_pct": change_pct}

    @staticmethod
    def _top_performer(
        columns: List[str],
        rows: List[List[Any]],
        metric_col_idx: int,
    ) -> Optional[str]:
        """Identify the row with the highest value in the metric column."""
        best_row = None
        best_val = None
        for row in rows:
            val = row[metric_col_idx] if metric_col_idx < len(row) else None
            if val is None:
                continue
            try:
                fval = float(val)
                if best_val is None or fval > best_val:
                    best_val = fval
                    best_row = row
            except (ValueError, TypeError):
                continue

        if best_row is None:
            return None

        # Use first non-numeric column as label
        label = None
        for idx, col in enumerate(columns):
            if idx != metric_col_idx:
                cell = best_row[idx] if idx < len(best_row) else None
                if cell is not None:
                    try:
                        float(cell)
                    except (ValueError, TypeError):
                        label = str(cell)
                        break

        metric_name = columns[metric_col_idx]
        if label:
            return (
                f"Top performer: '{label}' with highest "
                f"{metric_name} of {best_val:,.2f}."
            )
        return f"Highest {metric_name}: {best_val:,.2f}."

    def _detect_anomalies(
        self,
        values: List[float],
        col_name: str,
        columns: List[str],
        rows: List[List[Any]],
        col_idx: int,
    ) -> List[str]:
        """Flag values that deviate > _ANOMALY_STD_FACTOR standard deviations."""
        anomalies: List[str] = []
        if len(values) < 3:
            return anomalies

        stats = self._summary_stats(values)
        threshold = stats["mean"] + _ANOMALY_STD_FACTOR * stats["std"]
        low_threshold = stats["mean"] - _ANOMALY_STD_FACTOR * stats["std"]

        for row, val in zip(rows, values):
            if val > threshold:
                anomalies.append(
                    f"Anomaly detected: {col_name} value {val:,.2f} is "
                    f"unusually high (>{_ANOMALY_STD_FACTOR:.0f}σ above mean)."
                )
            elif val < low_threshold:
                anomalies.append(
                    f"Anomaly detected: {col_name} value {val:,.2f} is "
                    f"unusually low (>{_ANOMALY_STD_FACTOR:.0f}σ below mean)."
                )
        return anomalies[:3]  # cap to 3 anomaly alerts

    def _build_narrative(
        self,
        user_query: str,
        insights: List[str],
        summary_stats: Dict[str, Dict[str, float]],
    ) -> str:
        """Build a short human-readable narrative from the insights."""
        if self._llm:
            try:
                from .prompt_builder import PromptBuilder
                pb = PromptBuilder()
                prompt = pb.build_analytics_prompt(
                    user_query=user_query,
                    insights=insights,
                    summary_stats=summary_stats,
                )
                return self._llm.send_prompt(prompt).strip()
            except Exception as exc:
                logger.warning("LLM narrative failed, using rule-based: %s", exc)

        # Rule-based fallback narrative
        if not insights:
            return "No significant patterns detected."
        return " ".join(insights[:4])  # first 4 insights as a paragraph
