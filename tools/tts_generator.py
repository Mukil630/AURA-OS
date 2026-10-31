"""
JARVIS Autonomous Speech Generator
tools/tts_generator.py
Powered by Google Gemini Native Audio (gemini-3.8-flash-lite-tts / gemini-3.8-flash-tts) with Edge-TTS Fallback.
Calibrated Personas:
1. MORNING_WAKEUP   -> Warm, brotherly Tony Stark Kongu/Karur slang (Default)
2. CINEMATIC_JARVIS -> Deep, authoritative Stark executive AI partner
3. WORKOUT_BEAST    -> High-Energy Tamil Gym Coach
4. BUSINESS_FINANCE -> Sharp Confident SGC Co-Founder
5. CARING_FRIEND    -> Affectionate, caring Kongu Tamil best friend
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
    "CINEMATIC_JARVIS": "Speak in a deep, crisp, authoritative, cinematic executive AI partner tone: ",
    "JARVIS": "Speak in a deep, crisp, authoritative, cinematic executive AI partner tone: ",
    "WORKOUT_BEAST": "Speak in an energetic, pumped-up workout motivation coach tone in Tamil slang: ",
    "BUSINESS_FINANCE": "Speak in a confident, sharp business executive partner tone in Tamil: ",
    "CARING_FRIEND": "Speak in a caring, affectionate, friendly Kongu Tamil spoken tone: ",
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


async def generate_voice_audio(
    text: str,
    custom_voice: Optional[str] = None,
    persona: Optional[str] = None
) -> str:
    """
    Generates high-fidelity authentic voice note.
    Primary: Google Gemini Native Audio (gemini-3.8-flash-lite-tts / gemini-3.8-flash-tts)
             with Tony Stark Brotherly Tamil / Cinematic JARVIS persona.
    Fallback: Microsoft Edge-TTS (ta-IN-ValluvarNeural / en-IN-PrabhatNeural).
    """
    clean_text = clean_text_for_speech(text)
    if not clean_text:
        clean_text = "Task completed successfully, Maapla!"

    active_persona = (persona or DEFAULT_PERSONA).upper()
    directive = PERSONA_PROMPTS.get(active_persona, PERSONA_PROMPTS["MORNING_WAKEUP"])

    temp_dir = tempfile.gettempdir()
    audio_path = os.path.join(temp_dir, f"jarvis_voice_{os.getpid()}_{abs(hash(clean_text)) % 100000}.wav")

    # 1. Primary: Google Gemini Native Audio
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if gemini_key:
        for model_name in [
            "gemini-3.8-flash-lite-tts",
            "gemini-3.8-flash-tts",
            "gemini-3.1-flash-tts-preview"
        ]:
            try:
                from google import genai
                from google.genai import types
                client = genai.Client(api_key=gemini_key)
                prompt = f"{directive}{clean_text}"

                speech_cfg = None
                if custom_voice and custom_voice in ["Puck", "Charon", "Fenrir", "Aoede", "Kore"]:
                    speech_cfg = types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=custom_voice)
                        )
                    )

                config = types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=speech_cfg
                ) if speech_cfg else types.GenerateContentConfig(response_modalities=["AUDIO"])

                res = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=config
                )
                if res.candidates and res.candidates[0].content and res.candidates[0].content.parts:
                    for part in res.candidates[0].content.parts:
                        if getattr(part, 'inline_data', None) and part.inline_data.data:
                            with open(audio_path, "wb") as f:
                                f.write(part.inline_data.data)
                            logger.info(f"Generated voice using Gemini {model_name} ({active_persona})")
                            ogg_file = convert_wav_to_ogg(audio_path)
                            return ogg_file
            except Exception as e:
                logger.warning(f"Gemini {model_name} TTS notice: {e}")
                continue

    # 2. Resilient Fallback: Microsoft Edge-TTS Neural Voice
    selected_voice = "ta-IN-ValluvarNeural" if (custom_voice == "ta-IN-ValluvarNeural" or any('\u0B80' <= c <= '\u0BFF' for c in clean_text) or "mapla" in clean_text.lower() or "bro" in clean_text.lower() or "enna" in clean_text.lower()) else "en-IN-PrabhatNeural"
    audio_path_mp3 = audio_path.replace(".wav", ".mp3")
    try:
        import edge_tts
        communicate = edge_tts.Communicate(clean_text, selected_voice, rate="+6%", pitch="+1Hz")
        await communicate.save(audio_path_mp3)
        logger.info(f"Generated voice using Edge-TTS fallback ({selected_voice})")
        ogg_file = convert_wav_to_ogg(audio_path_mp3)
        return ogg_file
    except Exception as ex:
        logger.error(f"Edge-TTS fallback error: {ex}")

    with open(audio_path_mp3, "wb") as f:
        f.write(b"")
    return audio_path_mp3
