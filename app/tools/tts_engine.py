"""Neural Voice Synthesizer using Edge-TTS with Fluent Tamil and Indian English.
Generates natural-sounding voice notes for JARVIS Telegram responses.
"""
import asyncio
import logging
import os
import tempfile
from typing import Optional
import edge_tts

logger = logging.getLogger("TTSEngine")

TAMIL_VOICE = "ta-IN-ValluvarNeural"
ENGLISH_VOICE = "en-IN-PrabhatNeural"
FEMALE_TAMIL_VOICE = "ta-IN-PallaviNeural"


class JARVISVoiceEngine:
    """
    Synthesizes fluent Tamil or English audio notes from text.
    Uses edge-tts with zero cloud API cost and zero credentials needed.
    """

    def __init__(self, default_voice: str = TAMIL_VOICE):
        self.default_voice = default_voice

    def _detect_script(self, text: str) -> str:
        """Determines if text contains Tamil Unicode characters."""
        for char in text:
            if '\u0b80' <= char <= '\u0bff':
                return TAMIL_VOICE
        return ENGLISH_VOICE

    async def generate_voice_bytes(self, text: str, voice: Optional[str] = None) -> bytes:
        """Asynchronously generates audio bytes from text."""
        if not text or not text.strip():
            raise ValueError("TTS text cannot be empty.")

        selected_voice = voice or self._detect_script(text)
        logger.info(f"Synthesizing voice note with {selected_voice} for text: '{text[:50]}...'")

        communicate = edge_tts.Communicate(text, selected_voice)
        audio_chunks = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_chunks.append(chunk["data"])

        return b"".join(audio_chunks)

    async def save_voice_file(self, text: str, output_path: str, voice: Optional[str] = None) -> str:
        """Synthesizes voice and saves to specified file path."""
        selected_voice = voice or self._detect_script(text)
        communicate = edge_tts.Communicate(text, selected_voice)
        await communicate.save(output_path)
        return output_path
