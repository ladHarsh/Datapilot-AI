"""
Intent Detector — DataPilot AI Performance Engine.

Classifies user queries into:
1. Conversation: Skip database/SQL pipelines and respond in a friendly conversational manner.
2. Database Query: Proceed with SQL generation.
3. Ambiguous: Generate context-aware suggestions based on schema metadata.

Author: DataPilot Core Team
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from app.services.ai.llm_service import LLMService
from app.core.model_config import INTENT_FAST_MODEL

logger = logging.getLogger(__name__)

# Basic regex for zero-latency conversational greetings and basic chat inputs
_GREETING_REGEX = re.compile(
    r"^(hi|hello|hey|greetings|good\s+morning|good\s+afternoon|good\s+evening|hola|yo|hello\s+there)\b[\s?!.]*$",
    re.IGNORECASE
)

_APPRECIATION_REGEX = re.compile(
    r"^(thanks|thank\s+you|awesome|perfect|great|cool|nice|ok|okay|thx)\b[\s?!.]*$",
    re.IGNORECASE
)

_IDENTITY_REGEX = re.compile(
    r"^(who\s+are\s+you|what\s+is\s+your\s+name|what\s+are\s+you|what\s+do\s+you\s+do)\b[\s?!.]*$",
    re.IGNORECASE
)


class IntentDetector:
    """Detects and routes user query intents."""

    def __init__(self, ai_model: Optional[str] = None) -> None:
        model = ai_model or INTENT_FAST_MODEL
        self.llm_service = LLMService(model_override=model)

    def detect_intent(
        self,
        query: str,
        schema: Optional[Dict[str, Any]] = None,
        dialect: str = "mysql"
    ) -> Dict[str, Any]:
        """Classify user intent as Conversation, Database Query, or Ambiguous.

        Returns:
            Dict: {
                "intent": "Conversation" | "Database Query" | "Ambiguous",
                "response": str (Conversational greeting/reply),
                "suggestions": List[str] (For ambiguous intents)
            }
        """
        trimmed = query.strip()
        if not trimmed:
            return {
                "intent": "Conversation",
                "response": "How can I help you today?",
                "suggestions": []
            }

        # ── Step 1: Zero-Latency Regex Pre-Classifier ─────────────────────────
        if _GREETING_REGEX.match(trimmed):
            return {
                "intent": "Conversation",
                "response": "Hello! I am DataPilot AI, your database assistant. How can I help you analyze your data today?",
                "suggestions": []
            }

        if _APPRECIATION_REGEX.match(trimmed):
            return {
                "intent": "Conversation",
                "response": "You're welcome! Let me know if you have any database questions or need further analysis.",
                "suggestions": []
            }

        if _IDENTITY_REGEX.match(trimmed):
            return {
                "intent": "Conversation",
                "response": "I am DataPilot AI, an intelligent agent designed to help you generate SQL, query your database, analyze records, and visualize results. Try asking me a question about your database schema!",
                "suggestions": []
            }

        # ── Step 2: LLM Classifier (Fast Operational Layer) ────────────────────
        # Format the schema context if available to help build suggestions
        schema_summary = ""
        if schema and "tables" in schema:
            schema_summary += "Available tables and columns in the active database:\n"
            for tbl in schema["tables"]:
                tname = tbl.get("name", "")
                cols = [c.get("name", "") for c in tbl.get("columns", [])]
                schema_summary += f"- Table '{tname}' with columns: {', '.join(cols)}\n"

        prompt = f"""You are the intent routing layer of DataPilot AI, a premium SQL analytics platform.
Analyze the user's message and categorize it into EXACTLY one of three intents:
1. "Conversation": Greetings, conversational questions, pleasantries, humor, identity questions, or generic questions completely unrelated to the database or analytics.
2. "Database Query": A clear question, extraction request, or search query that asks to retrieve, aggregate, filter, join, or visualize records from the database schema.
3. "Ambiguous": A vague, partial keyword, table reference, column reference, or incomplete query that might refer to the database but does not make a clear request (e.g. just typing "customers", "signup_date", "total price").

---
SECURITY RULE:
- If the user request asks to alter, modify, delete, update, truncate, drop, insert, or change database schema/data (destructive/modifying operations, e.g. "delete all customers", "drop table orders", "update age to 30"), you MUST classify it as "Conversation" and in the "response" field, politely reply EXACTLY: "Sorry, I cannot modify or delete database data. DataPilot AI is a read-only analytics platform designed for querying and analyzing data only."

---
DATABASE METADATA:
Database Dialect: {dialect}
{schema_summary}
---
USER REQUEST:
"{trimmed}"

---
INSTRUCTIONS:
- You must output valid, minified JSON ONLY. No explanation or backticks.
- If classification is "Conversation", generate a helpful, premium, natural AI reply in the "response" field. Keep it professional.
- If classification is "Ambiguous", generate EXACTLY 3 highly relevant, premium database query suggestions that the user might have meant based on the provided schema metadata, and place them in the "suggestions" field. If no tables exist or you cannot form a query, suggest generic queries like "Show total tables".
- If classification is "Database Query", return an empty "response" and an empty "suggestions" array.

JSON Schema:
{{
  "intent": "Conversation" | "Database Query" | "Ambiguous",
  "response": "Friendly reply here or empty",
  "suggestions": ["suggested query 1", "suggested query 2", "suggested query 3"]
}}
"""

        try:
            raw_response = self.llm_service.send_prompt(prompt)
            # Find JSON in raw response to be safe
            json_match = re.search(r"\{.*\}", raw_response, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group(0))
                # Validate schema
                intent = parsed.get("intent", "Database Query")
                if intent not in ["Conversation", "Database Query", "Ambiguous"]:
                    intent = "Database Query"
                return {
                    "intent": intent,
                    "response": parsed.get("response", ""),
                    "suggestions": parsed.get("suggestions", [])
                }
        except Exception as exc:
            logger.error("Intent classification failed: %s. Defaulting to Database Query.", exc)

        # Fallback to Database Query if anything fails
        return {
            "intent": "Database Query",
            "response": "",
            "suggestions": []
        }
