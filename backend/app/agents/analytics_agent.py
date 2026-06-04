"""
Analytics Agent — SQL AI Analytics Platform.

Orchestrates AI-powered business insight generation from SQL query results:
    Query Results (columns + rows)
        → AnalyticsInsightGenerator  (trend, top, anomaly detection)
        → LLM Narrative              (professional summary via analytics_prompt.txt)
        → Structured Insight Response (for dashboard cards)

Author : Member 2 — AI/LLM Engineer
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..services.ai.analytics_insight_generator import AnalyticsInsightGenerator
from ..services.ai.llm_service import LLMService, LLMServiceError
from ..services.ai.prompt_builder import PromptBuilder

logger = logging.getLogger(__name__)


class AnalyticsAgent:
    """Generate structured business insights from SQL query results.

    The agent composes two layers:

    1. **Statistical layer** — ``AnalyticsInsightGenerator`` detects
       trends, top performers, and anomalies purely from the data.
    2. **LLM narrative layer** — sends the insight list + summary stats
       to the LLM via ``analytics_prompt.txt`` for a polished executive
       summary.  Gracefully falls back to rule-based narrative if the
       LLM is unavailable.

    Usage::

        agent = AnalyticsAgent()
        result = agent.analyze(
            columns=["month", "revenue"],
            rows=[["Jan", 50000], ["Feb", 55000], ["Mar", 48000]],
            user_query="show monthly revenue trend",
        )
        # result["narrative"] → "Revenue peaked in February..."
    """

    def __init__(self, use_llm: bool = True, ai_model: Optional[str] = None) -> None:
        """Initialise the agent.

        Parameters
        ----------
        use_llm : bool
            Whether to include an LLM-generated narrative.  Default ``True``.
        ai_model : str, optional
            The preferred AI model to use.
        """
        self._prompt_builder = PromptBuilder()
        self._use_llm = use_llm
        self._llm: Optional[LLMService] = None

        if use_llm:
            try:
                self._llm = LLMService(model_override=ai_model) if ai_model else LLMService()
                self._llm.max_tokens = 150  # Hard budget for speed
            except Exception as exc:
                logger.warning("AnalyticsAgent: LLM not available (%s). Using rule-based only.", exc)

        # Pass the LLM into the generator so it can call build_analytics_prompt
        self._generator = AnalyticsInsightGenerator(
            llm_service=self._llm if use_llm else None
        )
        logger.debug("AnalyticsAgent initialised (use_llm=%s, ai_model=%s).", use_llm, ai_model)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(
        self,
        columns: List[str],
        rows: List[List[Any]],
        user_query: str = "",
        query_sql: str = "",
    ) -> Dict[str, Any]:
        """Analyse SQL result data and return structured insights.

        Parameters
        ----------
        columns : list[str]
            Column names from the result set.
        rows : list[list]
            Data rows aligned with *columns*.
        user_query : str
            Original natural-language question.
        query_sql : str
            SQL query that produced the results (for context).

        Returns
        -------
        dict
            ``{success, insights, trends, top_performers, anomalies,
               summary_stats, narrative, row_count, column_count,
               insight_cards}``
        """
        if not columns:
            return {
                "success":       False,
                "insights":      ["No columns in result set."],
                "trends":        [],
                "top_performers": [],
                "anomalies":     [],
                "summary_stats": {},
                "narrative":     "No data available to analyse.",
                "row_count":     0,
                "column_count":  0,
                "insight_cards": [],
            }

        # ── Normalize dict rows to list rows if needed ─────────────────
        normalized_rows = []
        for r in (rows or []):
            if isinstance(r, dict):
                normalized_rows.append([r.get(col) for col in columns])
            else:
                normalized_rows.append(r)
        rows = normalized_rows

        # ── Statistical analysis ───────────────────────────────────────
        gen_result = self._generator.generate(
            columns=columns,
            rows=rows,
            user_query=user_query,
            query_sql=query_sql,
        )

        # ── Build insight cards (frontend-ready) ──────────────────────
        insight_cards = self._build_insight_cards(
            gen_result["trends"],
            gen_result["top_performers"],
            gen_result["anomalies"],
        )

        logger.info(
            "AnalyticsAgent: %d insights generated for query '%s'.",
            len(gen_result["insights"]),
            user_query[:50],
        )

        return {
            "success":        True,
            "insights":       gen_result["insights"],
            "trends":         gen_result["trends"],
            "top_performers": gen_result["top_performers"],
            "anomalies":      gen_result["anomalies"],
            "summary_stats":  gen_result["summary_stats"],
            "narrative":      gen_result["narrative"],
            "row_count":      gen_result["row_count"],
            "column_count":   gen_result["column_count"],
            "insight_cards":  insight_cards,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_insight_cards(
        trends: List[str],
        top_performers: List[str],
        anomalies: List[str],
    ) -> List[Dict[str, str]]:
        """Convert insight lists into structured cards for the frontend.

        Returns
        -------
        list[dict]
            Each card has ``{type, title, body, severity}``.
        """
        cards: List[Dict[str, str]] = []

        for trend in trends:
            severity = "positive" if "upward" in trend.lower() else (
                "negative" if "downward" in trend.lower() else "neutral"
            )
            cards.append({
                "type":     "trend",
                "title":    "Trend Detected",
                "body":     trend,
                "severity": severity,
            })

        for top in top_performers:
            cards.append({
                "type":     "top_performer",
                "title":    "Top Performer",
                "body":     top,
                "severity": "positive",
            })

        for anomaly in anomalies:
            cards.append({
                "type":     "anomaly",
                "title":    "Anomaly Alert",
                "body":     anomaly,
                "severity": "warning",
            })

        return cards
