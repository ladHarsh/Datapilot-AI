"""
core/model_config.py
─────────────────────
Centralized model assignment for the layered multi-model AI architecture.

Layer 1 — Fast Operational AI (default user flow):
    Primary: Groq Llama 3.3 70B
    All real-time pipeline tasks use this model.

Layer 2 — Gemini Fallback:
    Used ONLY when Groq fails or rate-limits.
    Never primary in the default pipeline.

Layer 3 — Deep Reasoning (on-demand):
    Nemotron 120B via NVIDIA/OpenRouter.
    User-triggered only (✨ Optimize Query).

Layer 4 — Long-Form Reports (on-demand):
    GPT-OSS 120B via OpenRouter.
    User-triggered only (📄 Generate Business Report).
"""

# ─── Layer 1: Fast Operational AI ─────────────────────────────────────────────
# Groq Llama 3.3 70B: ~350 tokens/s, ~1-2s per task.
# Used for ALL default pipeline tasks.

SQL_FAST_MODEL         = "llama-3.3-70b-versatile"   # SQL generation
EXPLANATION_FAST_MODEL = "llama-3.3-70b-versatile"   # Query explanation
INSIGHTS_FAST_MODEL    = "llama-3.3-70b-versatile"   # Business insight narrative
VOICE_FAST_MODEL       = "llama-3.3-70b-versatile"   # Voice query normalization
INTENT_FAST_MODEL      = "llama-3.3-70b-versatile"   # Intent detection

# Chart recommendation: rule-based only — no LLM needed, instant.
CHART_USE_LLM          = False

# ─── Layer 2: Fallback Model ──────────────────────────────────────────────────
# Used when Groq fails/rate-limits. Not primary.

FALLBACK_MODEL         = "gemini-2.5-flash"

# ─── Layer 3: Deep Reasoning (on-demand only) ─────────────────────────────────
# Nemotron 120B: used only for ✨ Optimize Query.
# NOT in the default fast pipeline.

QUERY_OPTIMIZER_MODEL  = "nvidia/nemotron-3-super-120b-a12b"

# ─── Layer 4: Long-Form Reports (on-demand only) ──────────────────────────────
# GPT-OSS 120B: used only for 📄 Generate Business Report.
# NOT in the default fast pipeline.

REPORT_MODEL           = "openai/gpt-oss-120b:free"

# ─── Retry Configuration ──────────────────────────────────────────────────────
# Fast, flat retry delays — fail and fallback in ≤1.5s instead of ≤19s.

MAX_RETRIES_FAST       = 2        # Down from 3
FAST_RETRY_DELAY_S     = 0.5     # Flat 0.5s between retries (was 2^attempt: 2s, 4s)
