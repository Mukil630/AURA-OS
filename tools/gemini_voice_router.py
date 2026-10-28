"""
========================================================================================
AURA-OS — DYNAMIC MULTI-PERSONA GEMINI VOICE ROUTER (gemini_voice_router.py)
----------------------------------------------------------------------------------------
Orchestrates Dynamic Context-Aware Voice Personas for Mukil:
1. MORNING_WAKEUP     -> Casual Brotherly Stark Wakeup Tone
2. WORKOUT_BEAST      -> High-Energy Gym Motivation Coach
3. BUSINESS_FINANCE   -> Sharp Confident SGC Co-Founder
4. CINEMATIC_JARVIS   -> Deep Authoritative Executive Commander
5. CARING_FRIEND      -> Affectionate Kongu/Karur Protective Friend
========================================================================================
"""

import os
import sys
import time
import logging
from pathlib import Path
from typing import Optional, Tuple
import requests

JARVIS_DIR = Path(__file__).resolve().parent.parent
if str(JARVIS_DIR) not in sys.path:
    sys.path.insert(0, str(JARVIS_DIR))

import config
from google import genai

logger = logging.getLogger("gemini_voice_router")
VOICE_OUTPUT_DIR = JARVIS_DIR / "storage" / "voice_samples" / "active_cache"
VOICE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 5 Dedicated Persona Directives for Gemini 3.8 Flash Native Audio
PERSONA_DIRECTIVES = {
    "MORNING_WAKEUP": "Speak in a warm, natural, brotherly Tamil slang like Tony Stark talking to his best friend Mukil: ",
    "WORKOUT_BEAST": "Speak in an energetic, pumped-up workout motivation coach tone in Tamil slang: ",
    "BUSINESS_FINANCE": "Speak in a confident, sharp business executive partner tone in Tamil: ",
    "CINEMATIC_JARVIS": "Speak in a deep, crisp, authoritative, cinematic executive AI partner tone: ",
    "CARING_FRIEND": "Speak in a caring, affectionate, friendly Kongu Tamil spoken tone: "
}


def auto_detect_persona(text: str) -> str:
    """Detects the best persona based on text content if not explicitly specified."""
    lower = text.lower()
    if any(k in lower for k in ["workout", "gym", "புல் டே", "புஷ் டே", "bench", "curls", "squats"]):
        return "WORKOUT_BEAST"
    if any(k in lower for k in ["bill", "sgc", "கலெக்ஷன்", "பில்", "interest", "இன்ட்ரெஸ்ட்", "turnover", "ரூபாய்"]):
        return "BUSINESS_FINANCE"
    if any(k in lower for k in ["hello boss", "good morning", "வெயில்", "weather", "காலை"]):
        return "MORNING_WAKEUP"
    if any(k in lower for k in ["ஆல் சிஸ்டம்ஸ்", "system", "online", "drive", "mesh"]):
        return "CINEMATIC_JARVIS"
    return "CARING_FRIEND"


def synthesize_persona_voice(
    text: str,
    persona_type: str = "AUTO",
    output_filename: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Synthesizes speech using Gemini 3.8 Flash Native Audio mapped to the requested persona.
    Returns: (success: bool, audio_file_path: str)
    """
    selected_persona = persona_type.upper() if persona_type != "AUTO" else auto_detect_persona(text)
    directive = PERSONA_DIRECTIVES.get(selected_persona, PERSONA_DIRECTIVES["MORNING_WAKEUP"])
    
    full_prompt = f"{directive}{text}"
    fname = output_filename or f"gemini_voice_{selected_persona.lower()}_{int(time.time())}.wav"
    out_path = VOICE_OUTPUT_DIR / fname

    logger.info(f"[VoiceRouter] Synthesizing via Persona '{selected_persona}'...")

    try:
        client = genai.Client(api_key=config.GEMINI_API_KEY)
        for model_name in ["gemini-3.8-flash-lite-tts", "gemini-3.8-flash-tts"]:
            try:
                res = client.models.generate_content(
                    model=model_name,
                    contents=full_prompt
                )
                if res.candidates and res.candidates[0].content and res.candidates[0].content.parts:
                    for part in res.candidates[0].content.parts:
                        if part.inline_data:
                            with open(out_path, "wb") as f:
                                f.write(part.inline_data.data)
                            logger.info(f"[VoiceRouter] Successfully generated {out_path} using {model_name}")
                            return True, str(out_path)
            except Exception as me:
                logger.warning(f"[VoiceRouter] Model {model_name} failed: {me}")
                continue
        return False, "No audio inline data returned from Gemini TTS models"
    except Exception as e:
        logger.error(f"[VoiceRouter] Gemini TTS failed: {e}")
        return False, str(e)


def send_voice_to_telegram(audio_path: str, caption: str) -> bool:
    """Dispatches generated voice note to Mukil's Telegram (auto-converts WAV to OGG Opus for sub-second upload)."""
    token = getattr(config, "TELEGRAM_BOT_TOKEN", None)
    chat_id = getattr(config, "AUTHORIZED_TELEGRAM_USERS", [6233907249])[0]
    if not token or not os.path.exists(audio_path):
        return False

    upload_path = audio_path
    filename = "voice.ogg"
    mime_type = "audio/ogg"

    # Convert uncompressed WAV to ultra-light OGG Opus (30KB) for instant Telegram delivery
    if audio_path.lower().endswith(".wav"):
        try:
            import subprocess
            import imageio_ffmpeg
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
            ogg_path = str(Path(audio_path).with_suffix(".ogg"))
            cmd = [ffmpeg, "-y", "-i", audio_path, "-c:a", "libopus", "-b:a", "32k", ogg_path]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
            if os.path.exists(ogg_path) and os.path.getsize(ogg_path) > 0:
                upload_path = ogg_path
        except Exception as e:
            logger.warning(f"Audio conversion fallback: {e}")
            filename = "voice.wav"
            mime_type = "audio/wav"

    url = f"https://api.telegram.org/bot{token}/sendVoice"
    try:
        with open(upload_path, "rb") as f:
            r = requests.post(
                url,
                data={"chat_id": chat_id, "caption": caption},
                files={"voice": (filename, f, mime_type)},
                timeout=45
            )
            return r.json().get("ok", False)
    except Exception as e:
        logger.error(f"Telegram dispatch failed: {e}")
        return False


if __name__ == "__main__":
    test_text = "ஒர்க்கவுட் டைம் பாஸ்! இன்னைக்கு லேட் புல்டவுன் பைசெப்ஸ் போட்டு தெறிக்க விடலாம்!"
    print(f"[*] Testing Voice Router with Workout text...")
    ok, path = synthesize_persona_voice(test_text, persona_type="WORKOUT_BEAST")
    print(f"Result: {ok} -> {path}")
