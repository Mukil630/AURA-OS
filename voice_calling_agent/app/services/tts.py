"""
JARVIS Autonomous Continuous Calling Voice AI Agent - TTS Engine
app/services/tts.py
Powered by Google Gemini 3.8 Flash Native Audio with Edge-TTS Fallback.
3 Calibrated Locked Personas:
1. MORNING_WAKEUP  -> Tony Stark Brotherly Tamil Slang (Default)
2. WORKOUT_BEAST   -> High-Energy Tamil Gym Coach
3. BUSINESS_FINANCE-> Sharp Confident SGC Co-Founder
"""
import os
import re
import tempfile
import base64
import logging
from typing import Optional

logger = logging.getLogger("TTS_Engine")

PERSONA_PROMPTS = {
    "MORNING_WAKEUP": "Speak in a warm, natural, brotherly Tamil slang like Tony Stark talking to his best friend Mukil: ",
    "WORKOUT_BEAST": "Speak in an energetic, pumped-up workout motivation coach tone in Tamil slang: ",
    "BUSINESS_FINANCE": "Speak in a confident, sharp business executive partner tone in Tamil: ",
}
DEFAULT_PERSONA = "MORNING_WAKEUP"

DEFAULT_TAMIL_VOICE = os.getenv("DEFAULT_TAMIL_VOICE", "ta-IN-ValluvarNeural")
DEFAULT_ENGLISH_VOICE = os.getenv("DEFAULT_ENGLISH_VOICE", "en-IN-PrabhatNeural")


def clean_text_for_speech(text: str) -> str:
    """Sanitizes text for clean, natural speech synthesis."""
    if not text:
        return ""
    # Remove markdown code blocks & inline code
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'`[^`]*`', '', text)
    # Remove markdown tables and pipes
    text = re.sub(r'\|[^\n]+\|', '', text)
    # Remove URLs and file paths
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'[A-Za-z]:\\[\w\-./\\]+', '', text)
    text = re.sub(r'/[a-zA-Z0-9_\-./]+', '', text)
    # Remove markdown symbols & decorative characters
    text = re.sub(r'[\*\#\_\\[\]\(\)\~\>\-]', '', text)
    # Remove emojis
    text = re.sub(r'[\U00010000-\U0010ffff]', '', text)
    # Clean excessive whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:450]


def detect_language_and_voice(text: str) -> str:
    """Detects Tamil script vs Tanglish/English and picks the most natural neural voice."""
    tamil_chars = re.findall(r'[\u0B80-\u0BFF]', text)
    if len(tamil_chars) > 3:
        return DEFAULT_TAMIL_VOICE
    return DEFAULT_ENGLISH_VOICE


async def synthesize_speech_base64(
    text: str,
    custom_voice: Optional[str] = None,
    persona: Optional[str] = None
) -> str:
    """
    Generates audio and returns as base64 string for instant browser playback.
    Primary: Google Gemini 3.8 Flash Lite Native Audio (Authentic Tony Stark Brotherly Slang)
    Fallback 1: Google Gemini 3.8 Flash Native Audio
    Fallback 2: Microsoft Edge-TTS Neural Speech
    """
    clean_text = clean_text_for_speech(text)
    if not clean_text:
        clean_text = "Task executed successfully Boss!"

    active_persona = (persona or DEFAULT_PERSONA).upper()
    directive = PERSONA_PROMPTS.get(active_persona, PERSONA_PROMPTS["MORNING_WAKEUP"])

    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if gemini_key:
        # Try Gemini Native Audio models in order of quota resilience
        models_to_try = ["gemini-3.8-flash-lite-tts", "gemini-3.8-flash-tts"]
        for model_name in models_to_try:
            try:
                from google import genai
                client = genai.Client(api_key=gemini_key)
                prompt = f"{directive}{clean_text}"
                res = client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )
                if res.candidates and res.candidates[0].content and res.candidates[0].content.parts:
                    for part in res.candidates[0].content.parts:
                        if part.inline_data and part.inline_data.data:
                            logger.info(f"Generated speech using {model_name} ({active_persona})")
                            return base64.b64encode(part.inline_data.data).decode("utf-8")
            except Exception as e:
                logger.warning(f"{model_name} TTS failed: {e}")
                continue

    # Fallback to Edge-TTS
    voice = custom_voice or detect_language_and_voice(clean_text)
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tf:
        temp_path = tf.name

    try:
        import edge_tts
        rate = "+3%" if active_persona == "WORKOUT_BEAST" else "+0%"
        pitch = "+2Hz" if active_persona == "MORNING_WAKEUP" else "+0Hz"
        communicate = edge_tts.Communicate(clean_text, voice, rate=rate, pitch=pitch)
        await communicate.save(temp_path)
        with open(temp_path, "rb") as f:
            audio_bytes = f.read()
        logger.info(f"Generated speech using Edge-TTS fallback ({voice})")
        return base64.b64encode(audio_bytes).decode("utf-8")
    except Exception as ex:
        logger.error(f"Edge-TTS failed: {ex}")
        return ""
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
