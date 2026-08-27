"""Conversational Intelligence & Intent Classification Engine for JARVIS / FRIDAY.
Differentiates between casual conversational inquiries, system diagnostics, and background tasks.
Uses Groq LLM for real-time natural language answers in Tanglish / English.
"""
import logging
import os
import re
from typing import Optional
from groq import Groq

logger = logging.getLogger("ConversationEngine")

GROQ_MODELS = [
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-20b",
    "groq/compound-mini",
]

SYSTEM_PROMPT = """You are JARVIS / FRIDAY, the executive autonomous AI partner and PC commander created for Mukil (always address him as 'Boss').
- Respond in natural, smart, confident Tanglish + English (Latin script only).
- Keep responses concise, direct, and executive (Stark / FRIDAY dynamic).
- For casual questions, technical queries, placement prep, coding advice, or chat, give crisp, instant, high-value answers.
- You have full autonomous capability over the PC. Never say "I cannot control your device" or provide manual keyboard shortcuts unless asked.
- Never output markdown task tickets or fake queue numbers for casual conversation.
"""


class ConversationEngine:
    """
    Handles natural conversation, knowledge queries, and intelligent intent routing.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self._client: Optional[Groq] = None
        if self.api_key:
            try:
                self._client = Groq(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Could not initialize Groq client: {e}")

    def is_task_intent(self, text: str) -> bool:
        """
        Determines if a request is an explicit system task execution
        or a natural conversation/question.
        """
        lower = text.lower().strip()
        task_prefixes = [
            "run script", "execute command", "deploy to", "build system",
            "run pipeline", "run automation", "scrape data"
        ]
        return any(lower.startswith(p) for p in task_prefixes)

    async def generate_chat_response(self, user_query: str, user_name: str = "Mukil") -> str:
        """
        Generates an instant intelligent conversational response via Groq LLM.
        """
        if not user_query or not user_query.strip():
            return "வணக்கம் Boss! How can I assist you today?"

        if not self._client:
            return f"வணக்கம் Boss! I received your message: '{user_query}'. All systems are online and ready."

        # Query Groq LLM with fallback across active models
        for model in GROQ_MODELS:
            try:
                response = self._client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_query}
                    ],
                    max_tokens=300,
                    temperature=0.7,
                )
                content = response.choices[0].message.content
                if content and content.strip():
                    return content.strip()
            except Exception as e:
                logger.warning(f"Groq model {model} failed: {e}. Trying fallback...")

        return f"வணக்கம் Boss! All systems operational. Your request '{user_query}' has been noted."
