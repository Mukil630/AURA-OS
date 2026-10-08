import os
import re
import tempfile
import base64
import edge_tts
from app.core.config import DEFAULT_TAMIL_VOICE, DEFAULT_ENGLISH_VOICE

def detect_language_and_voice(text: str) -> str:
    """Detects Tamil script vs Tanglish/English and picks the most natural neural voice."""
    tamil_chars = re.findall(r'[\u0B80-\u0BFF]', text)
    if len(tamil_chars) > 3:
        return DEFAULT_TAMIL_VOICE
    return DEFAULT_ENGLISH_VOICE

def clean_text_for_speech(text: str) -> str:
    """Sanitizes text for clean, natural speech synthesis."""
    # Remove code blocks and inline code
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'`[^`]*`', '', text)
    # Remove markdown formatting
    text = re.sub(r'[\*\#\_\\[\]\(\)\~\>\-]', '', text)
    # Remove URLs
    text = re.sub(r'http\S+', '', text)
    # Remove emojis
    text = re.sub(r'[\U00010000-\U0010ffff]', '', text)
    # Clean whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:400]

async def synthesize_speech_base64(text: str, custom_voice: str = None) -> str:
    """Generates MP3 audio and returns as base64 string for instant browser playback."""
    clean_text = clean_text_for_speech(text)
    if not clean_text:
        clean_text = "Task executed successfully Boss!"

    voice = custom_voice or detect_language_and_voice(clean_text)

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tf:
        temp_path = tf.name

    try:
        communicate = edge_tts.Communicate(clean_text, voice)
        await communicate.save(temp_path)
        with open(temp_path, "rb") as f:
            audio_bytes = f.read()
        return base64.b64encode(audio_bytes).decode("utf-8")
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
