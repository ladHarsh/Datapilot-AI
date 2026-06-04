"""
Explanation Service — SQL AI Analytics Platform.

Translates technical SQL queries into professional, business-friendly English
explanations that clearly describe what the data represents.

Designed for SPEED:
  - Hard token caps per mode (Brief=80, Detailed=800)
  - Timeout scales with mode: Detailed=25s, Brief=8s
  - Zero style-guide bloat in the prompt
  - Instant rule-based fallback on any failure

Author : Member 2 — AI/LLM Engineer
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .llm_service import LLMService, LLMServiceError
from .prompt_builder import PromptBuilder

logger = logging.getLogger(__name__)


class ExplanationService:
    """Service to bridge the gap between technical SQL and business users.

    Produces concise summaries of what a SQL query is doing, what filters are
    applied, and what the final output represents in business terms.
    """

    # Token budgets — primary speed lever.
    # Detailed was 220 (forced 1-line output). Now 800 to allow 3-5 paragraphs.
    _TOKENS: Dict[str, int] = {"Detailed": 800, "Brief": 80, "Short": 80}

    # Timeout budget per mode (seconds).
    # Groq responds in ~2s. Give 6s headroom for Detailed, 2s for Brief.
    # These are much tighter than before (was 25s/8s) because Gemini is no longer primary.
    _TIMEOUTS: Dict[str, int] = {"Detailed": 8, "Brief": 4, "Short": 4}

    def __init__(self, ai_model: Optional[str] = None) -> None:
        self._ai_model = ai_model
        self.prompt_builder = PromptBuilder()

    def _make_fast_llm(self, max_tokens: int) -> LLMService:
        """Instantiate a purpose-built LLM with a strict output cap."""
        svc = LLMService(model_override=self._ai_model) if self._ai_model else LLMService()
        svc.max_tokens = max_tokens
        return svc

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def explain_query(
        self,
        sql_query: str,
        user_query: str,
        context_hint: Optional[str] = None,
        explanation_mode: str = "Detailed Explanation",
    ) -> Dict[str, Any]:
        """Generate a professional explanation for an SQL query.

        Parameters
        ----------
        sql_query : str
            The generated SQL statement.
        user_query : str
            The original natural-language question.
        context_hint : str, optional
            Ignored (kept for backward compatibility).
        explanation_mode : str, optional
            "Detailed Explanation", "Brief Summary", or "No Explanation".

        Returns
        -------
        dict
            ``{success, explanation, error}``
        """
        if not sql_query or not sql_query.strip():
            return {"success": False, "explanation": "No query provided.", "error": "Empty SQL."}

        # ── Determine mode, token budget, and timeout ─────────────────
        if "Detailed" in explanation_mode:
            mode = "Detailed"
            instruction = (
                "In 3-5 short paragraphs explain: (1) what this query does, "
                "(2) which tables/columns it uses, (3) what business question it answers. "
                "Be concise. No code. No markdown headers."
            )
        else:
            mode = "Brief"
            instruction = (
                "In exactly 1-2 sentences explain what this SQL query does "
                "and what result it returns. No code. Be direct."
            )

        max_tokens = self._TOKENS.get(mode, 80)
        # FIX: timeout is resolved here and captured by the closure below,
        # not hardcoded inside _fast_post. This is the correct way to make
        # the timeout mode-aware — the original code could not access `mode`
        # inside the nested function.
        timeout_seconds = self._TIMEOUTS.get(mode, 8)

        # ── Build a lean prompt ───────────────────────────────────────
        base_prompt = self.prompt_builder.build_explanation_prompt(sql_query, user_query)
        prompt = f"{base_prompt}\n\nInstruction: {instruction}"

        # ── Apply mode-aware timeout via monkey-patch ─────────────────
        import requests as _req

        _orig_post = _req.post

        def _fast_post(url, **kwargs):
            """Cap timeout to the mode-appropriate value.

            `timeout_seconds` is captured from the enclosing scope above —
            this is what makes the timeout mode-aware without passing extra
            arguments through the LLM service layer.
            """
            kwargs["timeout"] = min(kwargs.get("timeout", 30), timeout_seconds)
            return _orig_post(url, **kwargs)

        try:
            fast_llm = self._make_fast_llm(max_tokens)
            _req.post = _fast_post
            try:
                response = fast_llm.send_prompt(prompt)
            finally:
                _req.post = _orig_post

            explanation = self._post_process(response.strip())
            return {"success": True, "explanation": explanation, "error": None}

        except Exception as exc:
            _req.post = _orig_post
            logger.warning(
                "Explanation LLM failed (%s). Using rule-based fallback.", exc
            )
            fallback = self._generate_fallback(sql_query, user_query)
            return {"success": False, "explanation": fallback, "error": str(exc)}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _post_process(text: str) -> str:
        """Minimal post-processing — de-AI-ify language."""
        text = text.replace("This SQL query", "This report")
        text = text.replace("The query", "The analysis")
        return text

    def _generate_fallback(self, sql: str, nl: str) -> str:
        """Deterministic rule-based explanation when AI is offline or timed out."""
        sql_upper = sql.upper()
        features = []
        if "JOIN" in sql_upper:
            features.append("combines information from multiple tables")
        if "GROUP BY" in sql_upper:
            features.append("aggregates and summarizes the data")
        if "ORDER BY" in sql_upper:
            features.append("ranks the results")
        if "SUM" in sql_upper or "AVG" in sql_upper:
            features.append("calculates key financial metrics")
        if "WHERE" in sql_upper:
            features.append("filters for specific criteria")

        if not features:
            return f"This report retrieves information based on your request: '{nl}'."

        feature_str = ", ".join(features[:-1]) + (
            f" and {features[-1]}" if len(features) > 1 else features[0]
        )
        return f"This analysis {feature_str} to answer your question: '{nl}'."
