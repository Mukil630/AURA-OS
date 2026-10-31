"""
JARVIS Autonomous Speech Generator
tools/tts_generator.py
Powered by Google Gemini Native Audio Architecture (gemini-3.8-flash-lite-tts / gemini-3.8-flash-tts)
with Edge-TTS Resilient Fallback.

Fixed 3 Official Locked Voices (Mukil Approved):
1. STARK   -> Tony Stark Brotherly Tanglish (Default)
2. CHARON  -> Deep & Cinematic Stark AI Partner
3. FENRIR  -> Strong & Authoritative Executive Tone
"""
import os
import re
import json
import tempfile
import logging
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv(r"C:\Users\mukil\jarvis-core\.env")
load_dotenv(r"C:\Users\mukil\aura-os\.env")

logger = logging.getLogger("tts_generator")

# The 3 Fixed Locked Voices requested by Mukil
LOCKED_VOICES: Dict[str, Dict[str, Any]] = {
    "STARK": {
        "key": "STARK",
        "name": "Tony Stark Brotherly Tanglish",
        "directive": "Speak in a warm, natural, brotherly Tamil slang like Tony Stark talking to his best friend Mukil: ",
        "prebuilt_voice": None,
        "caption": "🎙️ Gemini 3.8 Flash: Tony Stark Brotherly Tanglish",
        "description": "Warm, natural brotherly Kongu/Karur Tanglish slang (Default)"
    },
    "CHARON": {
        "key": "CHARON",
        "name": "Charon (Deep & Cinematic Stark)",
        "directive": "Speak in a deep, crisp, authoritative, cinematic executive AI partner tone: ",
        "prebuilt_voice": "Charon",
        "caption": "🎬 Gemini Voice: Charon (Deep & Cinematic Stark)",
        "description": "Deep, crisp, cinematic executive Stark AI partner"
    },
    "FENRIR": {
        "key": "FENRIR",
        "name": "Fenrir (Strong & Authoritative)",
        "directive": "Speak in a strong, authoritative, commanding executive partner tone: ",
        "prebuilt_voice": "Fenrir",
        "caption": "⚡ Gemini Voice: Fenrir (Strong & Authoritative)",
        "description": "Powerful, confident, commanding executive partner"
    }
}
DEFAULT_VOICE_KEY = "STARK"

# Persona compatibility prompts
PERSONA_PROMPTS = {
    "MORNING_WAKEUP": LOCKED_VOICES["STARK"]["directive"],
    "CINEMATIC_JARVIS": LOCKED_VOICES["CHARON"]["directive"],
    "JARVIS": LOCKED_VOICES["CHARON"]["directive"],
    "WORKOUT_BEAST": "Speak in an energetic, pumped-up workout motivation coach tone in Tamil slang: ",
    "BUSINESS_FINANCE": "Speak in a confident, sharp business executive partner tone in Tamil: ",
    "CARING_FRIEND": "Speak in a caring, affectionate, friendly Kongu Tamil spoken tone: ",
}
DEFAULT_PERSONA = "MORNING_WAKEUP"

# Path for persistent voice preference
def _get_voice_config_path() -> Path:
    candidates = [
        Path(r"C:\Users\mukil\aura-os\storage\memory\voice_config.json"),
        Path(r"C:\Users\mukil\jarvis-core\storage\memory\voice_config.json"),
        Path(os.path.dirname(__file__)) / "voice_config.json",
        Path(tempfile.gettempdir()) / "jarvis_voice_config.json"
    ]
    for p in candidates:
        try:
            if p.parent.exists():
                return p
        except Exception:
            pass
    return Path(tempfile.gettempdir()) / "jarvis_voice_config.json"


def get_active_voice_key() -> str:
    """Returns the persistent active voice key (defaults to STARK)."""
    cfg_path = _get_voice_config_path()
    if cfg_path.exists():
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                key = str(data.get("active_voice", DEFAULT_VOICE_KEY)).upper().strip()
                if key in LOCKED_VOICES:
                    return key
        except Exception:
            pass
    return DEFAULT_VOICE_KEY


def set_active_voice_key(voice_key: str) -> Dict[str, Any]:
    """Persistently locks the active voice key to disk."""
    key = str(voice_key).upper().strip()
    # Support numeric shortcuts: 1 -> STARK, 2 -> CHARON, 3 -> FENRIR
    aliases = {
        "1": "STARK", "STARK": "STARK", "TONY": "STARK", "DEFAULT": "STARK",
        "2": "CHARON", "CHARON": "CHARON",
        "3": "FENRIR", "FENRIR": "FENRIR"
    }
    resolved_key = aliases.get(key, DEFAULT_VOICE_KEY)
    voice_info = LOCKED_VOICES[resolved_key]

    cfg_path = _get_voice_config_path()
    try:
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump({
                "active_voice": resolved_key,
                "name": voice_info["name"],
                "engine": "gemini-3.8-flash-lite-tts",
                "prebuilt_voice": voice_info["prebuilt_voice"],
                "last_updated": "2026-10-31"
            }, f, indent=2)
        logger.info(f"Voice preference locked to: {resolved_key} ({voice_info['name']})")
    except Exception as e:
        logger.warning(f"Could not persist voice config: {e}")

    return voice_info


def get_active_voice_config() -> Dict[str, Any]:
    """Returns full config dictionary of the currently active voice."""
    key = get_active_voice_key()
    return LOCKED_VOICES.get(key, LOCKED_VOICES[DEFAULT_VOICE_KEY])


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
             using Mukil's 3 locked voices:
             - STARK  (Tony Stark Brotherly Tanglish)
             - CHARON (Deep & Cinematic Stark)
             - FENRIR (Strong & Authoritative)
    Fallback: Microsoft Edge-TTS (ta-IN-ValluvarNeural / en-IN-PrabhatNeural).
    """
    clean_text = clean_text_for_speech(text)
    if not clean_text:
        clean_text = "Task completed successfully, Maapla!"

    # Resolve active voice configuration
    if custom_voice and custom_voice.upper() in LOCKED_VOICES:
        voice_cfg = LOCKED_VOICES[custom_voice.upper()]
    elif custom_voice and custom_voice.capitalize() in ["Charon", "Fenrir"]:
        voice_cfg = LOCKED_VOICES.get(custom_voice.upper(), LOCKED_VOICES["STARK"])
    else:
        voice_cfg = get_active_voice_config()

    directive = voice_cfg["directive"]
    if persona and persona.upper() in PERSONA_PROMPTS:
        directive = PERSONA_PROMPTS[persona.upper()]

    temp_dir = tempfile.gettempdir()
    audio_path = os.path.join(temp_dir, f"jarvis_voice_{os.getpid()}_{abs(hash(clean_text)) % 100000}.wav")

    # 1. Primary: Google Gemini Native Audio
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if gemini_key:
        for model_name in [
            "gemini-3.8-flash-tts",
            "gemini-3.8-flash-lite-tts",
            "gemini-3.1-flash-tts-preview"
        ]:
            try:
                from google import genai
                from google.genai import types
                client = genai.Client(api_key=gemini_key)
                prompt = f"{directive}{clean_text}"

                prebuilt = voice_cfg.get("prebuilt_voice")
                speech_cfg = None
                if prebuilt:
                    speech_cfg = types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=prebuilt)
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
                            logger.info(f"Generated voice using Gemini {model_name} [{voice_cfg['name']}]")
                            ogg_file = convert_wav_to_ogg(audio_path)
                            return ogg_file
            except Exception as e:
                logger.warning(f"Gemini {model_name} TTS notice: {e}")
                continue

    # 2. Resilient Fallback: Microsoft Edge-TTS Neural Voice
    selected_voice = "ta-IN-ValluvarNeural" if (any('\u0B80' <= c <= '\u0BFF' for c in clean_text) or "mapla" in clean_text.lower() or "bro" in clean_text.lower() or "enna" in clean_text.lower()) else "en-IN-PrabhatNeural"
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
