"""Neural Voice Synthesizer using Edge-TTS with Multi-Voice Profiles.
Supports 3 Distinct Persona Voices:
1. Male (ta-IN-ValluvarNeural / en-IN-PrabhatNeural)
2. Female (ta-IN-PallaviNeural / en-IN-NeerjaNeural)
3. Robotic JARVIS (en-GB-RyanNeural / Stark Edition)
"""
import asyncio
from enum import Enum
import logging
import os
import tempfile
from typing import Dict, Optional, Tuple
import edge_tts

logger = logging.getLogger("TTSEngine")


class VoiceMode(str, Enum):
    MALE = "male"
    FEMALE = "female"
    JARVIS = "jarvis"


VOICE_CONFIGS: Dict[VoiceMode, Dict[str, str]] = {
    VoiceMode.MALE: {
        "name": "👨 Male Voice (Valluvar / Prabhat)",
        "tamil": "ta-IN-ValluvarNeural",
        "english": "en-IN-PrabhatNeural",
        "rate": "+0%",
        "pitch": "+0Hz",
    },
    VoiceMode.FEMALE: {
        "name": "👩 Female Voice (Pallavi / Neerja)",
        "tamil": "ta-IN-PallaviNeural",
        "english": "en-IN-NeerjaNeural",
        "rate": "+0%",
        "pitch": "+0Hz",
    },
    VoiceMode.JARVIS: {
        "name": "🤖 Robotic JARVIS (Stark AI Edition)",
        "tamil": "ta-IN-ValluvarNeural",
        "english": "en-GB-RyanNeural",
        "rate": "+5%",
        "pitch": "-2Hz",
    },
}


class JARVISVoiceEngine:
    """
    Synthesizes fluent Tamil or English audio notes from text across 3 distinct persona voices.
    """

    def __init__(self, default_mode: VoiceMode = VoiceMode.MALE):
        self.current_mode: VoiceMode = default_mode

    def set_voice_mode(self, mode: str) -> Tuple[bool, str]:
        """Switch voice persona mode."""
        clean_mode = mode.lower().strip()
        if clean_mode in ("male", "1", "valluvar"):
            self.current_mode = VoiceMode.MALE
        elif clean_mode in ("female", "2", "pallavi", "friday"):
            self.current_mode = VoiceMode.FEMALE
        elif clean_mode in ("jarvis", "robot", "robotic", "3", "stark"):
            self.current_mode = VoiceMode.JARVIS
        else:
            return False, f"Unknown voice mode '{mode}'. Available modes: `male`, `female`, `jarvis`."

        cfg = VOICE_CONFIGS[self.current_mode]
        return True, f"Voice switched to *{cfg['name']}*."

    def get_current_mode_info(self) -> Dict[str, str]:
        """Returns details about currently active voice."""
        return VOICE_CONFIGS[self.current_mode]

    def _resolve_voice(self, text: str, voice_override: Optional[str] = None) -> Tuple[str, str, str]:
        """Resolves target voice, rate, and pitch."""
        if voice_override:
            return voice_override, "+0%", "+0Hz"

        cfg = VOICE_CONFIGS[self.current_mode]
        is_tamil = any('\u0b80' <= char <= '\u0bff' for char in text)

        # For robotic JARVIS mode on English text, use crisp British Stark voice
        if self.current_mode == VoiceMode.JARVIS and not is_tamil:
            return cfg["english"], cfg["rate"], cfg["pitch"]

        target_voice = cfg["tamil"] if is_tamil else cfg["english"]
        return target_voice, cfg["rate"], cfg["pitch"]

    async def generate_voice_bytes(self, text: str, voice: Optional[str] = None) -> bytes:
        """Asynchronously generates audio bytes from text."""
        if not text or not text.strip():
            raise ValueError("TTS text cannot be empty.")

        selected_voice, rate, pitch = self._resolve_voice(text, voice)
        logger.info(f"Synthesizing voice with {selected_voice} (rate={rate}, pitch={pitch}) for: '{text[:40]}...'")

        communicate = edge_tts.Communicate(text, selected_voice, rate=rate, pitch=pitch)
        audio_chunks = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_chunks.append(chunk["data"])

        return b"".join(audio_chunks)

    async def save_voice_file(self, text: str, output_path: str, voice: Optional[str] = None) -> str:
        """Synthesizes voice and saves to specified file path."""
        selected_voice, rate, pitch = self._resolve_voice(text, voice)
        communicate = edge_tts.Communicate(text, selected_voice, rate=rate, pitch=pitch)
        await communicate.save(output_path)
        return output_path

