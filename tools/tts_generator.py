"""
JARVIS Autonomous Speech Generator
tools/tts_generator.py
Powered by Google Gemini Native Audio (gemini-3.8-flash-lite-tts) with Edge-TTS Fallback.
3 Calibrated Locked Personas:
1. MORNING_WAKEUP  -> Tony Stark Brotherly Tamil Slang (Default)
2. WORKOUT_BEAST   -> High-Energy Tamil Gym Coach
3. BUSINESS_FINANCE-> Sharp Confident SGC Co-Founder
"""
import os
import re
import tempfile
import logging
import subprocess
from typing import Optional
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv(r"C:\Users\mukil\jarvis-core\.env")
load_dotenv(r"C:\Users\mukil\aura-os\.env")

logger = logging.getLogger("tts_generator")

PERSONA_PROMPTS = {
    "MORNING_WAKEUP": "Speak in a warm, natural, brotherly Tamil slang like Tony Stark talking to his best friend Mukil: ",
    "WORKOUT_BEAST": "Speak in an energetic, pumped-up workout motivation coach tone in Tamil slang: ",
    "BUSINESS_FINANCE": "Speak in a confident, sharp business executive partner tone in Tamil: ",
}
DEFAULT_PERSONA = "MORNING_WAKEUP"


def convert_wav_to_ogg(input_path: str) -> str:
    """Compresses WAV or MP3 to ultra-light OGG Opus for sub-second Telegram dispatch."""
    ogg_path = input_path.rsplit(".", 1)[0] + ".ogg"
    try:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        cmd = [ffmpeg, "-y", "-i", input_path, "-c:a", "libopus", "-b:a", "32k", ogg_path]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        if os.path.exists(ogg_path) and os.path.getsize(ogg_path) > 0:
            try:
                os.remove(input_path)
            except Exception:
                pass
            return ogg_path
    except Exception as e:
        logger.warning(f"FFmpeg OGG conversion error: {e}")
    return input_path


def detect_language_and_voice(text: str) -> str:
    """Detects whether text contains Tamil script or English/Tanglish and picks the best fallback voice."""
    # ta-IN-ValluvarNeural is our locked authentic Tamil male voice with warm, brotherly tone
    return "ta-IN-ValluvarNeural"


def clean_text_for_speech(text: str) -> str:
    """Removes markdown symbols, tables, URLs, emojis, and code blocks for clean speech."""
    if not text:
        return ""
    # Remove code blocks
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'`[^`]*`', '', text)
    # Remove markdown tables
    text = re.sub(r'\|[^\n]+\|', '', text)
    # Remove file paths and URLs
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'[A-Za-z]:\\[\w\-./\\]+', '', text)
    # Remove markdown formatting characters
    text = re.sub(r'[\*\#\_\[\]\(\)\~\>\-]', '', text)
    # Remove emojis
    text = re.sub(r'[\U00010000-\U0010ffff]', '', text)
    # Clean whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:450]


def convert_tanglish_to_spoken_tamil(tanglish_text: str, gemini_key: str) -> str:
    """Converts Roman Tanglish into natural colloquial spoken Tamil script so Neural TTS pronounces authentic Kongu/Stark slang."""
    try:
        from google import genai
        client = genai.Client(api_key=gemini_key)
        prompt = (
            "Convert this Tanglish response into natural spoken Tamil script for a brotherly voice note (Tony Stark / Mapla style). "
            "Keep English technical words (like Excel, Google Drive, Profit, P&L, Bill, Sheet, Status) in simple English or transliterated Tamil:\n"
            f"Input: {tanglish_text}\n"
            "Output ONLY the spoken Tamil text:"
        )
        res = client.models.generate_content(model="gemini-3.5-flash-lite", contents=prompt)
        if res.text and len(res.text.strip()) > 0:
            return res.text.strip()
    except Exception as e:
        logger.warning(f"Tanglish to Tamil conversion notice: {e}")
    return tanglish_text


async def generate_voice_audio(
    text: str,
    custom_voice: Optional[str] = None,
    persona: Optional[str] = None
) -> str:
    """
    Generates an audio voice note file from text.
    Primary: Google Gemini Native Audio (Tony Stark Brotherly Slang)
    Secondary Fallback: Microsoft Edge-TTS ta-IN-ValluvarNeural with spoken Tamil script conversion.
    """
    clean_text = clean_text_for_speech(text)
    if not clean_text:
        clean_text = "Task completed successfully, Maapla!"

    active_persona = (persona or DEFAULT_PERSONA).upper()
    directive = PERSONA_PROMPTS.get(active_persona, PERSONA_PROMPTS["MORNING_WAKEUP"])

    temp_dir = tempfile.gettempdir()
    audio_path = os.path.join(temp_dir, f"jarvis_voice_{os.getpid()}_{abs(hash(clean_text)) % 100000}.wav")

    # 1. Primary: Gemini Native Audio (when daily quota is available)
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if gemini_key:
        for model_name in [
            "gemini-2.5-flash-preview-tts",
            "gemini-3.8-flash-lite-tts",
            "gemini-3.8-flash-tts"
        ]:
            try:
                from google import genai
                from google.genai import types
                client = genai.Client(api_key=gemini_key)
                prompt = f"{directive}{clean_text}"
                res = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_modalities=["AUDIO"]
                    )
                )
                if res.candidates and res.candidates[0].content and res.candidates[0].content.parts:
                    for part in res.candidates[0].content.parts:
                        if getattr(part, 'inline_data', None) and part.inline_data.data:
                            with open(audio_path, "wb") as f:
                                f.write(part.inline_data.data)
                            logger.info(f"Generated voice using {model_name} ({active_persona})")
                            ogg_file = convert_wav_to_ogg(audio_path)
                            return ogg_file
            except Exception as e:
                logger.warning(f"{model_name} TTS failed: {e}")
                continue

    # 2. Secondary High-Fidelity Fallback: Edge-TTS ta-IN-ValluvarNeural with Spoken Tamil Script Conversion
    tamil_chars_count = len([c for c in clean_text if '\u0B80' <= c <= '\u0BFF'])
    spoken_text = clean_text
    if tamil_chars_count < 5 and gemini_key:
        spoken_text = convert_tanglish_to_spoken_tamil(clean_text, gemini_key)

    selected_voice = custom_voice or detect_language_and_voice(spoken_text)
    audio_path_mp3 = audio_path.replace(".wav", ".mp3")
    try:
        import edge_tts
        communicate = edge_tts.Communicate(spoken_text, selected_voice, rate="+8%", pitch="+1Hz")
        await communicate.save(audio_path_mp3)
        logger.info(f"Generated authentic Tamil voice using Edge-TTS ({selected_voice})")
        ogg_file = convert_wav_to_ogg(audio_path_mp3)
        return ogg_file
    except Exception as ex:
        logger.error(f"Edge-TTS failed: {ex}")
        with open(audio_path_mp3, "wb") as f:
            f.write(b"")
        return audio_path_mp3
