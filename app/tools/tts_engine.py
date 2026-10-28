"""
Neural Voice Synthesizer using Google Gemini 3.8 Flash Native Audio with Edge-TTS Fallback.
3 Calibrated Locked Personas:
1. MORNING_WAKEUP  -> Tony Stark Brotherly Tamil Slang (Default, Mapla bond)
2. WORKOUT_BEAST   -> High-Energy Tamil Gym Motivation Coach
3. BUSINESS_FINANCE-> Sharp Confident SGC Co-Founder & Executive Partner
"""
import os
import re
import asyncio
from enum import Enum
import logging
import tempfile
from typing import Dict, Optional, Tuple

logger = logging.getLogger("TTSEngine")


class VoiceMode(str, Enum):
    MORNING_WAKEUP = "morning_wakeup"
    WORKOUT_BEAST = "workout_beast"
    BUSINESS_FINANCE = "business_finance"
    MALE = "morning_wakeup"
    FEMALE = "female"
    JARVIS = "business_finance"


PERSONA_DIRECTIVES: Dict[str, str] = {
    "MORNING_WAKEUP": "Speak in a warm, natural, brotherly Tamil slang like Tony Stark talking to his best friend Mukil: ",
    "WORKOUT_BEAST": "Speak in an energetic, pumped-up workout motivation coach tone in Tamil slang: ",
    "BUSINESS_FINANCE": "Speak in a confident, sharp business executive partner tone in Tamil: ",
    "FEMALE": "Speak in a sweet, clear, encouraging female assistant tone in Tamil: ",
}

VOICE_CONFIGS: Dict[str, Dict[str, str]] = {
    "MORNING_WAKEUP": {
        "name": "🤖 Tony Stark Brotherly Voice (Gemini Native Audio)",
        "tamil": "ta-IN-ValluvarNeural",
        "english": "en-IN-PrabhatNeural",
        "rate": "+2%",
        "pitch": "+1Hz",
    },
    "WORKOUT_BEAST": {
        "name": "🔥 Workout Beast Motivator (Gemini Native Audio)",
        "tamil": "ta-IN-ValluvarNeural",
        "english": "en-IN-PrabhatNeural",
        "rate": "+5%",
        "pitch": "+2Hz",
    },
    "BUSINESS_FINANCE": {
        "name": "💼 SGC Business Executive (Gemini Native Audio)",
        "tamil": "ta-IN-ValluvarNeural",
        "english": "en-IN-PrabhatNeural",
        "rate": "+0%",
        "pitch": "+0Hz",
    },
    "FEMALE": {
        "name": "👩 FRIDAY AI (Soft & Friendly Tone)",
        "tamil": "ta-IN-PallaviNeural",
        "english": "en-US-JennyNeural",
        "rate": "+2%",
        "pitch": "+3Hz",
    },
}


def sanitize_text_for_speech(text: str) -> str:
    """Sanitizes text for clean, natural speech synthesis, stripping markdown, code, and noise."""
    if not text:
        return ""
    # Strip markdown code blocks & inline code
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'`[^`]*`', '', text)
    # Strip markdown tables
    text = re.sub(r'\|[^\n]+\|', '', text)
    # Strip URLs and absolute filesystem paths
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'[A-Za-z]:\\[\w\-./\\]+', '', text)
    text = re.sub(r'/[a-zA-Z0-9_\-./]+', '', text)
    # Strip markdown symbols & formatting noise
    text = re.sub(r'[\*\#\_\\[\]\(\)\~\>\-]', '', text)
    # Strip emojis
    text = re.sub(r'[\U00010000-\U0010ffff]', '', text)
    # Clean whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:450]


class JARVISVoiceEngine:
    """
    Synthesizes fluent Tamil/English audio notes using Google Gemini 3.8 Flash Native Audio
    with robust fallback to Microsoft Edge-TTS.
    """

    def __init__(self, default_mode: str = "MORNING_WAKEUP"):
        self.current_mode: str = default_mode.upper()
        if self.current_mode not in PERSONA_DIRECTIVES:
            self.current_mode = "MORNING_WAKEUP"

    def set_voice_mode(self, mode: str) -> Tuple[bool, str]:
        """Switch voice persona mode."""
        clean = mode.lower().strip()
        if clean in ("morning_wakeup", "male", "1", "valluvar", "stark"):
            self.current_mode = "MORNING_WAKEUP"
        elif clean in ("workout_beast", "workout", "gym", "beast", "2"):
            self.current_mode = "WORKOUT_BEAST"
        elif clean in ("business_finance", "business", "sgc", "jarvis", "robot", "3"):
            self.current_mode = "BUSINESS_FINANCE"
        elif clean in ("female", "pallavi", "friday"):
            self.current_mode = "FEMALE"
        else:
            return False, f"Unknown voice mode '{mode}'. Available: `morning_wakeup`, `workout_beast`, `business_finance`, `female`."

        cfg = VOICE_CONFIGS.get(self.current_mode, VOICE_CONFIGS["MORNING_WAKEUP"])
        return True, f"Voice switched to *{cfg['name']}*."

    def get_current_mode_info(self) -> Dict[str, str]:
        """Returns details about currently active voice."""
        return VOICE_CONFIGS.get(self.current_mode, VOICE_CONFIGS["MORNING_WAKEUP"])

    async def _generate_gemini_audio(self, text: str) -> Optional[bytes]:
        """Synthesizes speech using Google Gemini Native Audio."""
        gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not gemini_key:
            return None

        directive = PERSONA_DIRECTIVES.get(self.current_mode, PERSONA_DIRECTIVES["MORNING_WAKEUP"])
        prompt = f"{directive}{text}"

        for model_name in ["gemini-3.8-flash-lite-tts", "gemini-3.8-flash-tts"]:
            try:
                from google import genai
                client = genai.Client(api_key=gemini_key)
                res = await asyncio.to_thread(
                    client.models.generate_content,
                    model=model_name,
                    contents=prompt
                )
                if res.candidates and res.candidates[0].content and res.candidates[0].content.parts:
                    for part in res.candidates[0].content.parts:
                        if part.inline_data and part.inline_data.data:
                            logger.info(f"Gemini TTS succeeded using {model_name} ({self.current_mode})")
                            return part.inline_data.data
            except Exception as e:
                logger.warning(f"Gemini TTS with {model_name} failed: {e}")
                continue
        return None

    async def generate_voice_bytes(self, text: str, voice: Optional[str] = None) -> bytes:
        """Asynchronously generates audio bytes from text."""
        clean_text = sanitize_text_for_speech(text)
        if not clean_text:
            clean_text = "Task executed successfully Boss!"

        # 1. Primary: Gemini Native Audio
        gemini_bytes = await self._generate_gemini_audio(clean_text)
        if gemini_bytes:
            return gemini_bytes

        # 2. Fallback: Edge-TTS
        cfg = VOICE_CONFIGS.get(self.current_mode, VOICE_CONFIGS["MORNING_WAKEUP"])
        is_tamil = any('\u0b80' <= c <= '\u0bff' for c in clean_text)
        target_voice = voice or (cfg["tamil"] if is_tamil else cfg["english"])

        logger.info(f"Synthesizing voice with Edge-TTS {target_voice} for: '{clean_text[:40]}...'")
        try:
            import edge_tts
            communicate = edge_tts.Communicate(clean_text, target_voice, rate=cfg.get("rate", "+0%"), pitch=cfg.get("pitch", "+0Hz"))
            audio_chunks = []
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_chunks.append(chunk["data"])
            return b"".join(audio_chunks)
        except Exception as ex:
            logger.error(f"Edge-TTS failed: {ex}")
            return b""

    async def save_voice_file(self, text: str, output_path: str, voice: Optional[str] = None) -> str:
        """Synthesizes voice and saves to specified file path."""
        clean_text = sanitize_text_for_speech(text)
        if not clean_text:
            clean_text = "Task executed successfully Boss!"

        # 1. Primary: Gemini Native Audio
        gemini_bytes = await self._generate_gemini_audio(clean_text)
        if gemini_bytes:
            with open(output_path, "wb") as f:
                f.write(gemini_bytes)
            logger.info(f"Saved Gemini Native Audio to {output_path}")
            return output_path

        # 2. Fallback: Edge-TTS
        cfg = VOICE_CONFIGS.get(self.current_mode, VOICE_CONFIGS["MORNING_WAKEUP"])
        is_tamil = any('\u0b80' <= c <= '\u0bff' for c in clean_text)
        target_voice = voice or (cfg["tamil"] if is_tamil else cfg["english"])

        try:
            import edge_tts
            communicate = edge_tts.Communicate(clean_text, target_voice, rate=cfg.get("rate", "+0%"), pitch=cfg.get("pitch", "+0Hz"))
            await communicate.save(output_path)
            logger.info(f"Saved Edge-TTS audio to {output_path}")
            return output_path
        except Exception as ex:
            logger.error(f"Edge-TTS save failed: {ex}")
            # Ensure an empty file exists so downstream doesn't throw FileNotFound
            with open(output_path, "wb") as f:
                f.write(b"")
            return output_path
