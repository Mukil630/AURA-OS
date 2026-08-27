"""Request Normalization Subsystem for multi-channel user inputs."""
import re
from typing import Any, Dict, List
from pydantic import BaseModel, Field

from app.core.enums import ChannelType


class NormalizedRequestPayload(BaseModel):
    """Cleaned, standardized request representation ready for intent classification."""
    cleaned_text: str = Field(..., description="Sanitized, filler-stripped instruction")
    detected_language: str = Field(default="en", description="Language tag: 'en', 'ta', 'en-ta'")
    original_raw: str = Field(..., description="Original raw unmodified input")
    channel: ChannelType = Field(default=ChannelType.API, description="Source input channel")
    client_context: Dict[str, Any] = Field(default_factory=dict, description="Client device metadata")


class RequestNormalizer:
    """
    Sanitizes voice transcriptions, Telegram messages, and web queries into uniform format.
    Removes wake-word artifacts, conversational fillers, and normalizes date/time shorthand.
    """

    # Common voice wake-words and conversational openers
    WAKE_PREFIXES: List[str] = [
        r"^hey\s+jarvis[,\s]*",
        r"^hi\s+jarvis[,\s]*",
        r"^ok\s+jarvis[,\s]*",
        r"^jarvis[,\s]*",
        r"^maapla[,\s]*",
        r"^mapla[,\s]*",
        r"^maplaa[,\s]*",
        r"^please\s+",
        r"^pls\s+",
        r"^can\s+you\s+",
        r"^could\s+you\s+",
        r"^would\s+you\s+",
    ]

    # Conversational filler words
    FILLER_WORDS: List[str] = [
        r"\buh+\b",
        r"\bum+\b",
        r"\ber+\b",
        r"\bah+\b",
    ]

    # Tanglish / Tamil lexical markers
    TANGLISH_MARKERS: List[str] = [
        "maapla", "mapla", "irukku", "panni", "pannu", "kudu", "sollu",
        "paaru", "epdi", "enna", "aachu", "mudiyuma", "podu", "eduthu",
        "parunga", "venum", "nalla", "seiyya",
    ]

    def normalize(
        self,
        raw_input: str,
        channel: ChannelType = ChannelType.API,
        client_context: Dict[str, Any] | None = None,
    ) -> NormalizedRequestPayload:
        """Sanitize raw text and produce a NormalizedRequestPayload."""
        if not raw_input or not raw_input.strip():
            return NormalizedRequestPayload(
                cleaned_text="",
                detected_language="en",
                original_raw=raw_input or "",
                channel=channel,
                client_context=client_context or {},
            )

        text = raw_input.strip()

        # 1. Detect Language (Tamil Script or Tanglish markers)
        detected_lang = self._detect_language(text)

        # 2. Strip Wake Prefixes (e.g. "Jarvis, check my CI" -> "check my CI")
        cleaned = text
        for pattern in self.WAKE_PREFIXES:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()

        # 3. Strip Filler Words (e.g. "uh remind me um to study" -> "remind me to study")
        for filler in self.FILLER_WORDS:
            cleaned = re.sub(filler, "", cleaned, flags=re.IGNORECASE).strip()

        # 4. Normalize Whitespace & Punctuation
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        # If stripping emptied the text (e.g. user just said "Jarvis"), keep original stripped text
        if not cleaned:
            cleaned = text

        return NormalizedRequestPayload(
            cleaned_text=cleaned,
            detected_language=detected_lang,
            original_raw=raw_input,
            channel=channel,
            client_context=client_context or {},
        )

    def _detect_language(self, text: str) -> str:
        """Detect whether input is pure Tamil, Tanglish, or English."""
        # Check for Tamil Unicode range (U+0B80 - U+0BFF)
        if any("\u0b80" <= char <= "\u0bff" for char in text):
            return "ta"

        # Check for Tanglish romanized markers
        lowered = text.lower()
        if any(re.search(rf"\b{re.escape(marker)}\b", lowered) for marker in self.TANGLISH_MARKERS):
            return "en-ta"

        return "en"
