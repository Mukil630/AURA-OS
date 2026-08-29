"""Stage 1: Intent Classification & Compound Intent Splitter."""
import enum
import json
import logging
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("IntentClassifier")


class IntentType(str, enum.Enum):
    CONVERSATION = "CONVERSATION"
    TASK = "TASK"
    AMBIGUOUS = "AMBIGUOUS"


class SubIntent(BaseModel):
    intent_type: IntentType
    raw_query: str
    target_action: Optional[str] = None
    confidence: float = 1.0


class ParsedIntent(BaseModel):
    primary_intent: IntentType
    confidence: float = 1.0
    sub_intents: List[SubIntent] = Field(default_factory=list)
    raw_text: str


class IntentClassifier:
    """Classifies user input into CONVERSATION vs TASK, splits compound intents, and computes confidence."""

    # Heuristic triggers for deterministic task detection
    TASK_KEYWORDS = {
        "open", "launch", "run", "start", "stop", "kill", "close",
        "scrape", "fetch", "download", "upload", "sync", "backup",
        "remind", "reminder", "timer", "schedule", "alarm",
        "bill", "invoice", "calculate", "process", "analyze",
        "check battery", "battery", "status", "screenshot", "exec",
        "apply", "job", "resume", "test", "compile", "git",
        "delete", "remove", "drop", "wipe", "format", "clean"
    }

    CONVERSATION_STARTERS = {
        "hi", "hello", "hey", "vanakkam", "mapla", "maapla", "boss",
        "how are you", "what is", "explain", "tell me about",
        "who are you", "ennoda", "enna", "epdi", "puriyala", "doubt"
    }

    def __init__(self, llm_client: Optional[Any] = None):
        self.llm_client = llm_client

    def classify(self, user_input: str) -> ParsedIntent:
        """Classifies the given input string using rule heuristics + fallback."""
        clean = (user_input or "").strip()
        if not clean:
            return ParsedIntent(
                primary_intent=IntentType.CONVERSATION,
                confidence=1.0,
                sub_intents=[SubIntent(intent_type=IntentType.CONVERSATION, raw_query="", confidence=1.0)],
                raw_text=clean,
            )

        lower = clean.lower()

        # Check for compound sentence splitters (e.g. "Hi, also open youtube", "Hello, scrape this site")
        sub_intents = self._split_compound_intents(clean)
        
        # Determine primary intent based on sub-intents
        has_task = any(si.intent_type == IntentType.TASK for si in sub_intents)
        has_convo = any(si.intent_type == IntentType.CONVERSATION for si in sub_intents)

        if has_task:
            primary = IntentType.TASK
            confidence = 0.95
        elif has_convo:
            primary = IntentType.CONVERSATION
            confidence = 0.95
        else:
            primary = IntentType.AMBIGUOUS
            confidence = 0.5

        return ParsedIntent(
            primary_intent=primary,
            confidence=confidence,
            sub_intents=sub_intents,
            raw_text=clean,
        )

    def _split_compound_intents(self, text: str) -> List[SubIntent]:
        """Splits multi-clause queries into separate sub-intents."""
        # Split on sentence boundaries and conjunctions like 'and', 'also', 'plus', 'next'
        clauses = re.split(r"(?<=[.!?])\s+|\s+(?:and\s+also|also|and\s+then|then|aprom)\s+", text, flags=re.IGNORECASE)
        results = []

        for clause in clauses:
            c = clause.strip().rstrip(".,!?")
            if not c:
                continue

            c_lower = c.lower()
            # Check if this clause is a task
            is_task = any(re.search(r"\b" + re.escape(kw) + r"\b", c_lower) for kw in self.TASK_KEYWORDS)
            
            if is_task:
                results.append(SubIntent(
                    intent_type=IntentType.TASK,
                    raw_query=c,
                    target_action=self._extract_action(c_lower),
                    confidence=0.95,
                ))
            else:
                results.append(SubIntent(
                    intent_type=IntentType.CONVERSATION,
                    raw_query=c,
                    confidence=0.90,
                ))

        if not results:
            results.append(SubIntent(
                intent_type=IntentType.CONVERSATION,
                raw_query=text,
                confidence=0.8,
            ))

        return results

    def _extract_action(self, text: str) -> str:
        for kw in self.TASK_KEYWORDS:
            if kw in text:
                return kw
        return "generic_task"
