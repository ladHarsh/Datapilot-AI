"""
Voice Agent — SQL AI Analytics Platform.

Orchestrates the full voice query processing workflow:
    Speech-to-Text Output
        → VoiceQueryCleaner  (rule-based)
        → LLM Voice Prompt   (optional LLM pass)
        → QueryEnhancer      (analytics improvement)
        → Cleaned + Enhanced Query  (ready for SQLGenerator)

Author : Member 2 — AI/LLM Engineer
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from ..services.ai.voice_query_cleaner import VoiceQueryCleaner
from ..services.ai.query_enhancer import QueryEnhancer
from ..services.ai.prompt_builder import PromptBuilder
from ..services.ai.llm_service import LLMService, LLMServiceError
from app.core.model_config import VOICE_FAST_MODEL

logger = logging.getLogger(__name__)


class VoiceAgent:
    """Process raw speech-to-text query through cleaning and enhancement.

    The agent runs two passes:

    1. **Rule-based** — ``VoiceQueryCleaner`` strips filler words,
       fixes ASR errors, and normalises contractions.
    2. **LLM-based** *(optional)* — sends the rule-cleaned text to the
       LLM via ``voice_prompt.txt`` for a quality second pass.  Falls back
       gracefully if the LLM is unavailable.
    3. **Query Enhancement** — ``QueryEnhancer`` expands abbreviations,
       detects ambiguity, and adds analytics SQL hints.

    Usage::

        agent  = VoiceAgent()
        result = agent.process("um show me uh top clients by revenue mtd")
        # result["final_query"] → "Show top customers by total sales month to date"
    """

    def __init__(self, use_llm: bool = True) -> None:
        """Initialise the agent.

        Parameters
        ----------
        use_llm : bool
            Whether to run the optional LLM cleaning pass.  Default ``True``.
        """
        self._cleaner = VoiceQueryCleaner()
        self._enhancer = QueryEnhancer()
        self._prompt_builder = PromptBuilder()
        self._use_llm = use_llm
        self._llm: Optional[LLMService] = None

        if use_llm:
            try:
                # Always use fast Groq model for voice normalization
                self._llm = LLMService(model_override=VOICE_FAST_MODEL)
            except Exception as exc:
                logger.warning("VoiceAgent: LLM not available (%s). Falling back to rules only.", exc)

        logger.debug("VoiceAgent initialised (use_llm=%s).", use_llm)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process(
        self,
        voice_text: str,
        context_hint: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Process raw voice input into an SQL-generation-ready query.

        Parameters
        ----------
        voice_text : str
            Raw speech-to-text string.
        context_hint : str, optional
            Previous query for conversational continuation.

        Returns
        -------
        dict
            ``{final_query, rule_cleaned, llm_cleaned, enhanced_meta,
               confidence, changes_made, success}``
        """
        if not voice_text or not voice_text.strip():
            return {
                "final_query":  "",
                "rule_cleaned": "",
                "llm_cleaned":  None,
                "enhanced_meta": {},
                "confidence":   "low",
                "changes_made": [],
                "success":      False,
                "error":        "Empty voice input.",
            }

        # ── Stage 1: Rule-based cleaning ───────────────────────────────
        clean_result = self._cleaner.clean(voice_text)
        rule_cleaned = clean_result["cleaned_query"]
        changes = list(clean_result.get("changes_made", []))

        # ── Stage 2: LLM cleaning (optional) ──────────────────────────
        llm_cleaned: Optional[str] = None
        if self._use_llm and self._llm and rule_cleaned:
            try:
                prompt = self._prompt_builder.build_voice_prompt(rule_cleaned)
                llm_cleaned = self._llm.send_prompt(prompt).strip()
                if llm_cleaned:
                    changes.append("LLM voice normalisation applied.")
                else:
                    llm_cleaned = None
            except LLMServiceError as exc:
                logger.warning("VoiceAgent: LLM pass failed (%s). Using rule output.", exc)

        # Best text going into the enhancer
        text_for_enhancer = llm_cleaned if llm_cleaned else rule_cleaned

        # ── Stage 3: Query enhancement ────────────────────────────────
        enhance_result = self._enhancer.enhance(
            text_for_enhancer, context_hint=context_hint
        )
        final_query = enhance_result["enhanced_query"]
        changes.extend(enhance_result.get("changes_made", []))

        # ── Confidence: combine cleaner + enhancer scores ─────────────
        raw_confidence = clean_result.get("confidence", "medium")
        quality_score  = enhance_result.get("quality_score", 50)

        if quality_score >= 70 and raw_confidence == "high":
            confidence = "high"
        elif quality_score <= 30 or raw_confidence == "low":
            confidence = "low"
        else:
            confidence = "medium"

        logger.info(
            "VoiceAgent: '%s' → '%s' | confidence=%s",
            voice_text[:50],
            final_query[:50],
            confidence,
        )

        return {
            "final_query":   final_query,
            "rule_cleaned":  rule_cleaned,
            "llm_cleaned":   llm_cleaned,
            "enhanced_meta": enhance_result,
            "confidence":    confidence,
            "changes_made":  changes,
            "success":       bool(final_query),
        }
