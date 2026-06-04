"""
LLM Service Module — Multi-Provider Version
AI-powered SQL Database Analysis Tool

Supports: OpenRouter (Default), OpenAI, DeepSeek, and Gemini.
"""

from __future__ import annotations

import logging
import os
import re
import time
import requests
from typing import Optional

from dotenv import load_dotenv

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

# ---------------------------------------------------------
# Environment & Logging
# ---------------------------------------------------------

load_dotenv(override=True)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# Constants
# ---------------------------------------------------------

DEFAULT_TEMPERATURE = 0.1
DEFAULT_MAX_TOKENS = 8192   # Increased: complex multi-CTE queries can exceed 4096 tokens
MAX_RETRIES = 2             # Reduced from 3 → 2: fail-fast, fallback quickly
FAST_RETRY_DELAY = 0.5      # Flat 0.5s between retries (was 2^attempt: 2s, 4s)

# ---------------------------------------------------------
# Custom Exception
# ---------------------------------------------------------


class LLMServiceError(Exception):
    """Custom exception for LLM services."""
    def __init__(self, message: str, is_permanent: bool = False) -> None:
        super().__init__(message)
        self.is_permanent = is_permanent



# ---------------------------------------------------------
# LLM Service
# ---------------------------------------------------------


class LLMService:
    """
    Multi-provider LLM Service for SQL generation.

    Supported providers: openrouter, openai, deepseek, gemini, groq.
    The provider is auto-detected from environment variables when not
    explicitly specified.
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        model_override: Optional[str] = None,
    ) -> None:
        self.temperature = temperature
        self.max_tokens = max_tokens

        # Handle UI-driven model overrides
        if model_override:
            mo = model_override.lower()
            if "gemini" in mo:
                provider = "gemini"
                model = model_override
            elif "groq" in mo or "llama" in mo or "mixtral" in mo:
                provider = "groq"
                model = model_override
            elif "gpt" in mo or "openai" in mo:
                provider = "openai"
                model = model_override
            elif "nvidia" in mo or "nemotron" in mo:
                provider = "nvidia"
                model = model_override
            else:
                provider = "openrouter"
                model = model_override

        # ── Provider selection ──────────────────────────────────────────
        # Priority: explicit arg > LLM_PROVIDER env > first key found
        env_provider = os.getenv("LLM_PROVIDER", "").lower().strip()
        if provider:
            sel_provider = provider.lower()
        elif env_provider:
            sel_provider = env_provider
        elif os.getenv("OPENROUTER_API_KEY"):
            sel_provider = "openrouter"
        elif os.getenv("GEMINI_API_KEY"):
            sel_provider = "gemini"
        elif os.getenv("GROQ_API_KEY"):
            sel_provider = "groq"
        elif os.getenv("OPENAI_API_KEY"):
            sel_provider = "openai"
        elif os.getenv("NVIDIA_API_KEY"):
            sel_provider = "nvidia"
        else:
            sel_provider = "openrouter"  # last-resort default

        self._configure_provider(provider=sel_provider, model=model, api_key=api_key)

        if not self.api_key:
            # Look for any other active, configured keys in the environment for zero-downtime fallback!
            fallback_providers = [
                ("gemini", "GEMINI_API_KEY", "gemini-2.5-flash"),
                ("groq", "GROQ_API_KEY", "llama-3.3-70b-versatile"),
                ("openai", "OPENAI_API_KEY", os.getenv("OPENAI_MODEL", "google/gemini-2.5-flash")),
                ("nvidia", "NVIDIA_API_KEY", os.getenv("NVIDIA_MODEL", "nvidia/nemotron-3-super-120b-a12b")),
                ("openrouter", "OPENROUTER_API_KEY", "google/gemini-2.5-flash-001"),
            ]
            found_fallback = False
            for p, env_var, default_m in fallback_providers:
                p_key = os.getenv(env_var, "").strip()
                if p_key:
                    logger.warning(
                        "API key for provider '%s' not found. "
                        "Seamlessly falling back to active provider '%s' with default model...",
                        self.provider, p
                    )
                    self._configure_provider(provider=p, model=default_m, api_key=p_key)
                    found_fallback = True
                    break
            
            if not found_fallback:
                raise LLMServiceError(
                    f"API key for provider '{self.provider}' not found, and no other LLM "
                    f"keys are configured. Set the corresponding environment variable."
                )

        logger.info(
            "LLMService ready — provider=%s, model=%s",
            self.provider,
            self.model,
        )

    def _configure_provider(self, provider: str, model: Optional[str] = None, api_key: Optional[str] = None) -> None:
        """Configure the endpoints, keys, and model names for the selected provider."""
        self.provider = provider.lower()
        
        # ── Default model per provider ──────────────────────────────────
        if model:
            self.model = model
        elif self.provider == "openrouter":
            self.model = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash-001")
        elif self.provider == "openai":
            self.model = os.getenv("OPENAI_MODEL", "google/gemini-2.5-flash")
        elif self.provider == "groq":
            self.model = os.getenv("GROQ_MODEL", "llama3-70b-8192")
        elif self.provider == "gemini":
            self.model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        elif self.provider == "nvidia":
            self.model = os.getenv("NVIDIA_MODEL", "nvidia/nemotron-3-super-120b-a12b")
        else:
            self.model = "google/gemini-2.5-flash-001"

        # ── API key & base URL per provider ────────────────────────────
        if self.provider == "openrouter":
            self.api_key = api_key or os.getenv("OPENROUTER_API_KEY", "")
            self.base_url = "https://openrouter.ai/api/v1/chat/completions"

        elif self.provider == "openai":
            self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
            self.base_url = "https://api.openai.com/v1/chat/completions"

        elif self.provider == "groq":
            self.api_key = api_key or os.getenv("GROQ_API_KEY", "")
            self.base_url = "https://api.groq.com/openai/v1/chat/completions"

        elif self.provider == "gemini":
            self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")

        elif self.provider == "nvidia":
            self.api_key = api_key or os.getenv("NVIDIA_API_KEY", "")
            self.base_url = "https://integrate.api.nvidia.com/v1/chat/completions"

        else:
            raise LLMServiceError(f"Unsupported provider: '{self.provider}'")

        # ── Global Smart Routing for OpenRouter ─────────────────────────
        if self.api_key and self.api_key.startswith("sk-or-") and self.provider != "openrouter":
            logger.warning(
                "Detected OpenRouter API key inside %s config. "
                "Automatically routing request through OpenRouter completions endpoint...",
                self.provider.upper()
            )
            self.provider = "openrouter"
            self.base_url = "https://openrouter.ai/api/v1/chat/completions"

    # ---------------------------------------------------------
    # Main Prompt Method
    # ---------------------------------------------------------

    def send_prompt(self, prompt: str) -> str:
        """Send prompt to the selected LLM provider and return cleaned response."""
        if not prompt.strip():
            raise LLMServiceError("Prompt cannot be empty.")

        # Keep track of tried providers (resolved, after aliasing) to avoid infinite retry loops
        tried_providers: set = set()
        # Hard cap: at most 5 provider switches before we give up entirely
        MAX_PROVIDER_SWITCHES = 5
        switches = 0

        while switches < MAX_PROVIDER_SWITCHES:
            # The actual provider after rerouting (e.g. openai key → openrouter)
            current_provider = self.provider
            tried_providers.add(current_provider)
            switches += 1

            last_exc: Optional[Exception] = None
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    logger.info(
                        "Sending request to %s (Attempt %d/%d)",
                        self.provider, attempt, MAX_RETRIES,
                    )

                    if self.provider == "gemini":
                        content = self._call_gemini(prompt)
                    else:
                        content = self._call_openai_compatible(prompt)

                    if not content:
                        raise LLMServiceError(f"Empty response from {self.provider}.")

                    cleaned = self._strip_code_fences(content)
                    logger.info("%s responded successfully.", self.provider)
                    return cleaned

                except Exception as exc:
                    last_exc = exc
                    err_str = str(exc)
                    logger.error(
                        "%s request failed (Attempt %d/%d): %s",
                        self.provider, attempt, MAX_RETRIES, err_str,
                    )

                    # Permanent errors (auth, quota, rate limits) — skip remaining retries
                    is_fatal = (
                        "401" in err_str or 
                        "402" in err_str or
                        "User not found" in err_str or 
                        "Unauthorized" in err_str or
                        "429" in err_str or
                        "Quota exceeded" in err_str or
                        "Rate limit" in err_str or
                        "ResourceExhausted" in err_str or
                        "Insufficient credits" in err_str or
                        "Payment Required" in err_str
                    )
                    if is_fatal:
                        logger.warning(
                            "Permanent or rate-limit error from '%s' — skipping remaining retries for this provider.",
                            self.provider,
                        )
                        break  # Skip to fallback immediately

                    if attempt < MAX_RETRIES:
                        time.sleep(FAST_RETRY_DELAY)

            # All attempts for current_provider exhausted — try next provider
            # Fallback order: Groq (fast) → Gemini (capable) → OpenRouter (last resort)
            fallback_providers = [
                ("groq",       "GROQ_API_KEY",     "llama-3.3-70b-versatile"),
                ("gemini",     "GEMINI_API_KEY",   "gemini-2.5-flash"),
                ("openai",     "OPENAI_API_KEY",   os.getenv("OPENAI_MODEL", "openai/gpt-oss-120b:free")),
                ("nvidia",     "NVIDIA_API_KEY",   os.getenv("NVIDIA_MODEL", "nvidia/nemotron-3-super-120b-a12b")),
                ("openrouter", "OPENROUTER_API_KEY", "google/gemini-2.5-flash-001"),
            ]

            found_fallback = False
            for p, env_var, default_m in fallback_providers:
                p_key = os.getenv(env_var, "").strip()
                if not p_key:
                    continue

                # Determine the resolved provider name (OpenRouter key in OPENAI_API_KEY → "openrouter")
                resolved_p = "openrouter" if (p_key.startswith("sk-or-") and p != "openrouter") else p

                if resolved_p in tried_providers:
                    continue  # Already tried this physical endpoint

                logger.warning(
                    "Active provider '%s' failed. Seamlessly falling back to configured provider '%s'...",
                    current_provider, p
                )
                self._configure_provider(provider=p, model=default_m, api_key=p_key)
                found_fallback = True
                break

            if not found_fallback:
                last_err_str = str(last_exc) if last_exc else ""
                is_perm = any(sig in last_err_str for sig in [
                    "401", "402", "User not found", "Unauthorized", "429",
                    "Quota exceeded", "Rate limit", "ResourceExhausted",
                    "Insufficient credits", "Payment Required"
                ])
                raise LLMServiceError(
                    f"LLM request failed after attempting all configured providers. Last error: {last_exc}",
                    is_permanent=is_perm
                )
            # Continue outer while loop with new provider

        raise LLMServiceError(
            f"LLM request failed after {switches} provider switches — "
            "all configured providers exhausted.",
            is_permanent=True
        )

    # ---------------------------------------------------------
    # Provider-Specific Calls
    # ---------------------------------------------------------

    def _call_gemini(self, prompt: str) -> str:
        """Call Google Gemini via the official Python SDK."""
        # Lazy init so @patch("...llm_service.genai") works in tests.
        if genai is None or types is None:
            raise LLMServiceError(
                "google-genai is not installed. "
                "Run: pip install google-genai"
            )
        client = genai.Client(api_key=self.api_key)
        response = client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=self.temperature,
                max_output_tokens=self.max_tokens,
            ),
        )
        return response.text

    def _call_openai_compatible(self, prompt: str) -> str:
        """Call any OpenAI-compatible REST API (OpenRouter, OpenAI, DeepSeek, Groq)."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.provider == "openrouter":
            headers["HTTP-Referer"] = "https://github.com/ladHarsh/SQL-Database-Analysis-Tool"
            headers["X-Title"] = "SQL Database Analysis Tool"

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an expert SQL generator and business analyst. "
                        "You MUST handle: broken English, voice typing errors, spelling mistakes, "
                        "wrong column names, wrong table names, and incomplete questions. "
                        "Intelligently detect the correct table/column from the schema using "
                        "semantic understanding and fuzzy matching. "
                        "NEVER fail because of a spelling mistake — always correct it and generate valid SQL. "
                        "Support multi-table JOINs, time-series analysis, ranking, trend, distribution, "
                        "and complex aggregation queries. "
                        "When the user query is ambiguous, make a reasonable assumption and generate the best SQL."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": self.temperature,
            "max_tokens":  self.max_tokens,
        }

        resp = requests.post(self.base_url, headers=headers, json=payload, timeout=30)
        if resp.status_code != 200:
            raise LLMServiceError(f"HTTP {resp.status_code}: {resp.text[:300]}")

        return resp.json()["choices"][0]["message"]["content"]

    # ---------------------------------------------------------
    # Utility
    # ---------------------------------------------------------

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        """Remove markdown code fences from LLM output."""
        cleaned = re.sub(r"```\w*\n?", "", text)
        cleaned = re.sub(r"```", "", cleaned)
        return cleaned.strip()


# ---------------------------------------------------------
# Smoke Test
# ---------------------------------------------------------

if __name__ == "__main__":
    try:
        service = LLMService()
        result = service.send_prompt("SELECT 1;")
        print(f"\nResult:\n{result}")
    except Exception as e:
        print(f"Error: {e}")