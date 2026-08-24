import re
import json
import logging
from typing import Literal, Optional, Dict, Any
from pydantic import BaseModel, Field
from groq import Groq

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import GROQ_API_KEY

logger = logging.getLogger("intent_router")

class IntentResult(BaseModel):
    category: Literal["CONVERSATION", "SYNC_ACTION", "ASYNC_PROCESS"] = Field(
        description="CONVERSATION for chats/doubts/greetings, SYNC_ACTION for instant PC tools (screenshot, volume, open app), ASYNC_PROCESS for long-running workflows (job applying, scraping, code builds)."
    )
    target_agent: str = Field(
        description="Target specialized agent: 'general_chat', 'study_tutor', 'pc_controller', 'placement_agent', 'browser_agent', 'scheduler'."
    )
    requires_background_task: bool = Field(
        default=False,
        description="True if this task takes > 5 seconds and should run in background without blocking chat."
    )
    confidence: float = Field(default=0.9, description="Confidence score between 0.0 and 1.0")
    reasoning: str = Field(description="Brief 1-line reason for this classification.")


class IntentRouter:
    """
    High-speed Intent Classifier that strictly differentiates between:
    1. CONVERSATION: Casual chat, technical doubts, Java/Python explanations, brainstorming (Zero tool latency).
    2. SYNC_ACTION: Quick instant OS actions (<3s) like screenshot, volume, battery, open URL.
    3. ASYNC_PROCESS: Long-running agentic workflows (Job search & auto-apply, Web scraping, Deep research).
    """

    def __init__(self):
        self.client = Groq(api_key=GROQ_API_KEY)
        self.model = "openai/gpt-oss-120b"

    def classify(self, user_text: str) -> IntentResult:
        text = user_text.strip()

        # Fast-path Rule Heuristics (Zero latency regex checks)
        # 1. Obvious Conversations
        conversational_patterns = [
            r"^(hi|hello|vanakkam|hey|mapla|maapla|machi)\b",
            r"^(what is|explain|how does|why|tell me about|difference between|teach me)",
            r"(purila|sollu|theriyuma|doubt|interview question|quiz)\??$"
        ]
        for pat in conversational_patterns:
            if re.search(pat, text, re.IGNORECASE) and not any(k in text.lower() for k in ["apply", "screenshot", "battery", "volume", "open", "run", "search jobs"]):
                return IntentResult(
                    category="CONVERSATION",
                    target_agent="study_tutor" if any(w in text.lower() for w in ["java", "python", "apti", "sql", "set", "array", "oops"]) else "general_chat",
                    requires_background_task=False,
                    confidence=0.98,
                    reasoning="Matched fast-path conversational / technical explanation pattern."
                )

        # 2. Obvious Async Background Processes
        async_patterns = [
            r"(apply.*jobs?|indeed.*apply|scrape.*leads?|search.*openings?|crawl|auto.*apply)",
            r"(build.*full.*project|generate.*all.*resumes)"
        ]
        for pat in async_patterns:
            if re.search(pat, text, re.IGNORECASE):
                return IntentResult(
                    category="ASYNC_PROCESS",
                    target_agent="placement_agent",
                    requires_background_task=True,
                    confidence=0.95,
                    reasoning="Matched long-running autonomous workflow pattern."
                )

        # 3. LLM Semantic Classification (Structured JSON)
        system_prompt = (
            "You are the Intent Router for JARVIS Personal AI OS.\n"
            "Classify the user message into exactly ONE of three categories:\n\n"
            "1. 'CONVERSATION': Questions, tech doubts (Java, Python, Apti, DSA), casual chat, brainstorming, asking for advice. Needs ONLY text answer.\n"
            "2. 'SYNC_ACTION': Quick instant PC/System actions taking < 3 seconds (e.g. 'take screenshot', 'open YouTube', 'check battery', 'lock PC', 'adjust volume').\n"
            "3. 'ASYNC_PROCESS': Long-running background workflows taking > 5 seconds (e.g. 'apply for 3 jobs on indeed', 'scrape lead emails', 're-schedule my entire week', 'build codebase').\n\n"
            "Return JSON strictly adhering to schema:\n"
            "{\n"
            "  \"category\": \"CONVERSATION\" | \"SYNC_ACTION\" | \"ASYNC_PROCESS\",\n"
            "  \"target_agent\": \"study_tutor\" | \"general_chat\" | \"pc_controller\" | \"placement_agent\" | \"scheduler\",\n"
            "  \"requires_background_task\": true | false,\n"
            "  \"confidence\": 0.95,\n"
            "  \"reasoning\": \"explanation\"\n"
            "}"
        )

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            raw = resp.choices[0].message.content
            parsed = json.loads(raw)
            return IntentResult(**parsed)
        except Exception as e:
            logger.error(f"Classifier error: {e}")
            # Fallback safe default
            return IntentResult(
                category="CONVERSATION",
                target_agent="general_chat",
                requires_background_task=False,
                confidence=0.5,
                reasoning=f"Fallback due to router error: {str(e)}"
            )

if __name__ == "__main__":
    router = IntentRouter()
    test_queries = [
        "What is the difference between HashSet and TreeSet in Java?",
        "Take a screenshot of my PC screen right now",
        "Search and apply for 3 Python Developer fresher jobs on Indeed in background",
        "Tomorrow I have a placement drive, can you adjust my study plan?",
        "Hey maapla epdi irukka?"
    ]
    
    print("[TEST] Testing Intent Router (Process vs Convo):\n" + "="*50)
    for q in test_queries:
        res = router.classify(q)
        print(f"\nQuery: '{q}'")
        print(f"  -> Category: {res.category} | Agent: {res.target_agent} | Background: {res.requires_background_task}")
        print(f"  -> Reason: {res.reasoning}")
