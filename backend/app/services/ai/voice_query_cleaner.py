"""
Voice Query Cleaner — SQL AI Analytics Platform.

Pre-processes speech-to-text output before it enters the SQL generation
pipeline.  Speech recognition produces noisy text (filler words, broken
sentence structure, duplicated tokens).  This module cleans that noise
and normalises the text so the LLM generates accurate SQL.

Pipeline:
    Voice Input  →  Speech-to-Text  →  VoiceQueryCleaner  →  SQL Generation

Author : Member 2 — AI/LLM Engineer
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Filler word catalogue — extend freely
# ---------------------------------------------------------------------------
_FILLER_WORDS: List[str] = [
    "um", "uh", "er", "ah", "hmm", "hm", "eh",
    "like", "you know", "you see", "i mean", "sort of", "kind of",
    "basically", "literally", "actually", "essentially",
    "so", "well", "right", "okay", "ok", "yeah", "yes",
    "please", "could you", "can you", "would you",
    "just", "simply", "merely",
]

# Common spoken → written normalisation
_SPOKEN_TO_WRITTEN: Dict[str, str] = {
    "gimme":    "give me",
    "gonna":    "going to",
    "wanna":    "want to",
    "gotta":    "got to",
    "lemme":    "let me",
    "kinda":    "kind of",
    "sorta":    "sort of",
    "dunno":    "do not know",
    "y'all":    "all",
    "ain't":    "is not",
    "won't":    "will not",
    "can't":    "cannot",
    "doesn't":  "does not",
    "don't":    "do not",
    "isn't":    "is not",
    "aren't":   "are not",
    "wasn't":   "was not",
    "weren't":  "were not",
    "hasn't":   "has not",
    "haven't":  "have not",
    "hadn't":   "had not",
    "wouldn't": "would not",
    "couldn't": "could not",
    "shouldn't": "should not",
    "i'd":      "i would",
    "i've":     "i have",
    "i'm":      "i am",
    "i'll":     "i will",
    "it's":     "it is",
    "that's":   "that is",
    "what's":   "what is",
    "where's":  "where is",
    "how's":    "how is",
    "there's":  "there is",
    "who's":    "who is",
}

# Business domain synonyms common in voice queries
_BUSINESS_SYNONYMS: Dict[str, str] = {
    "revenue":         "total sales",
    "earnings":        "revenue",
    "turnover":        "revenue",
    "profit":          "revenue",
    "income":          "revenue",
    "clients":         "customers",
    "buyers":          "customers",
    "purchasers":      "customers",
    "items":           "products",
    "goods":           "products",
    "merchandise":     "products",
    "purchases":       "orders",
    "transactions":    "orders",
    "invoices":        "orders",
    "staff":           "employees",
    "workers":         "employees",
    "team members":    "employees",
    "personnel":       "employees",
}


class VoiceQueryCleaner:
    """Clean and normalise speech-to-text output for SQL generation.

    Steps applied in order:
    1. Expand spoken contractions / abbreviations.
    2. Strip filler words.
    3. Remove duplicate consecutive words (common in ASR output).
    4. Fix whitespace.
    5. Optionally normalise business synonyms.

    Usage::

        cleaner = VoiceQueryCleaner()
        result  = cleaner.clean("um show me uh the top customers")
        # result["cleaned_query"] == "show me the top customers"
    """

    def __init__(self, normalise_business_terms: bool = False) -> None:
        """Initialise the cleaner.

        Parameters
        ----------
        normalise_business_terms : bool
            Whether to apply the business synonym map.  Default ``True``.
        """
        self.normalise_business_terms = normalise_business_terms

        # Pre-compile filler pattern (whole-word match, case-insensitive)
        escaped = sorted(
            (_FILLER_WORDS),
            key=len,
            reverse=True,  # match longer phrases first
        )
        pattern = r"\b(?:" + "|".join(re.escape(w) for w in escaped) + r")\b"
        self._filler_re = re.compile(pattern, re.IGNORECASE)

        logger.debug("VoiceQueryCleaner initialised.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def clean(self, raw_voice_text: str) -> Dict[str, object]:
        """Clean a single speech-to-text string.

        Parameters
        ----------
        raw_voice_text : str
            Raw text from a speech-to-text engine.

        Returns
        -------
        dict
            ``{cleaned_query, original_query, changes_made, confidence}``
            where *confidence* is ``"high" | "medium" | "low"`` based on
            how much the text changed.
        """
        if not raw_voice_text or not raw_voice_text.strip():
            return {
                "cleaned_query": "",
                "original_query": raw_voice_text,
                "changes_made": [],
                "confidence": "low",
                "error": "Empty voice input received.",
            }

        original = raw_voice_text.strip()
        text = original
        changes: List[str] = []

        # Step 1 — expand contractions / abbreviations
        text, step_changes = self._expand_spoken_forms(text)
        changes.extend(step_changes)

        # Step 2 — strip filler words
        before = text
        text = self._filler_re.sub(" ", text)
        if text != before:
            changes.append("Removed filler words.")

        # Step 3 — remove duplicate consecutive words (ASR stutters)
        before = text
        text = re.sub(r"\b(\w+)( \1\b)+", r"\1", text, flags=re.IGNORECASE)
        if text != before:
            changes.append("Removed duplicate words.")

        # Step 4 — normalise whitespace
        text = " ".join(text.split())

        # Step 5 — business synonym normalisation (optional)
        if self.normalise_business_terms:
            text, syn_changes = self._normalise_synonyms(text)
            changes.extend(syn_changes)

        # Determine confidence based on edit ratio
        original_words = len(original.split())
        cleaned_words  = len(text.split())
        diff_ratio = abs(original_words - cleaned_words) / max(original_words, 1)

        if diff_ratio < 0.15:
            confidence = "high"
        elif diff_ratio < 0.40:
            confidence = "medium"
        else:
            confidence = "low"

        logger.info(
            "Voice cleaned: '%s' → '%s' | changes=%d | confidence=%s",
            original[:60],
            text[:60],
            len(changes),
            confidence,
        )

        return {
            "success": True,
            "cleaned_query": text,
            "original_query": original,
            "changes_made": changes,
            "confidence": confidence,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _expand_spoken_forms(text: str) -> tuple[str, List[str]]:
        """Replace spoken contractions with written equivalents."""
        changes: List[str] = []
        result = text
        for spoken, written in _SPOKEN_TO_WRITTEN.items():
            pattern = re.compile(rf"\b{re.escape(spoken)}\b", re.IGNORECASE)
            new = pattern.sub(written, result)
            if new != result:
                changes.append(f"Expanded '{spoken}' → '{written}'.")
                result = new
        return result, changes

    @staticmethod
    def _normalise_synonyms(text: str) -> tuple[str, List[str]]:
        """Replace common business synonyms with canonical terms."""
        changes: List[str] = []
        result = text
        for synonym, canonical in _BUSINESS_SYNONYMS.items():
            pattern = re.compile(rf"\b{re.escape(synonym)}\b", re.IGNORECASE)
            new = pattern.sub(canonical, result)
            if new != result:
                changes.append(f"Normalised '{synonym}' → '{canonical}'.")
                result = new
        return result, changes
