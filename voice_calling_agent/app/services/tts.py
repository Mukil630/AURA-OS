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
    """Generates audio (Google Gemini 3.8 Flash Native Audio primary, Edge-TTS fallback) and returns base64."""
    clean_text = clean_text_for_speech(text)
    if not clean_text:
        clean_text = "Task executed successfully Boss!"

    # 1. Primary: Google Gemini 3.8 Flash Native Audio (Authentic Tony Stark Brotherly Slang)
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if gemini_key:
        try:
            from google import genai
            client = genai.Client(api_key=gemini_key)
            prompt = f"Speak in a warm, natural, brotherly Tamil slang like Tony Stark talking to his best friend Mukil: {clean_text}"
            res = client.models.generate_content(
                model="gemini-3.8-flash-tts",
                contents=prompt
            )
            for part in res.candidates[0].content.parts:
                if part.inline_data and part.inline_data.data:
                    return base64.b64encode(part.inline_data.data).decode("utf-8")
        except Exception:
            pass

    # 2. Secondary: Edge-TTS Fallback
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
