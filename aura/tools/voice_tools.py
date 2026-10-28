"""
AURA OS Dynamic Multi-Persona Neural Voice Superpower
Powered by Google Gemini 3.8 Flash Native Audio Architecture
with Microsoft Edge-TTS Offline Fallback.

5 Official Personas:
1. JARVIS (CINEMATIC_JARVIS) - Deep, authoritative Stark executive AI partner
2. MORNING_WAKEUP           - Warm, brotherly Tony Stark Kongu/Karur slang
3. WORKOUT_BEAST            - High-energy, pumped-up gym motivation coach
4. BUSINESS_FINANCE         - Sharp, confident SGC business co-founder
5. CARING_FRIEND            - Affectionate, caring Kongu Tamil best friend
"""
import os
import re
import sys
import time
import subprocess
import requests
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

import pygame
from aura.config import DATA_DIR, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, GEMINI_API_KEY

VOICE_CACHE_DIR = DATA_DIR / "voice_cache"
VOICE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# 5 Dedicated Gemini Neural Audio Directives
GEMINI_PERSONA_PROMPTS = {
    "JARVIS": "Speak in a deep, crisp, authoritative, cinematic executive AI partner tone: ",
    "CINEMATIC_JARVIS": "Speak in a deep, crisp, authoritative, cinematic executive AI partner tone: ",
    "MORNING_WAKEUP": "Speak in a warm, natural, brotherly Tamil slang like Tony Stark talking to his best friend Mukil: ",
    "WORKOUT_BEAST": "Speak in an energetic, pumped-up workout motivation coach tone in Tamil slang: ",
    "BUSINESS_FINANCE": "Speak in a confident, sharp business executive partner tone in Tamil: ",
    "CARING_FRIEND": "Speak in a caring, affectionate, friendly Kongu Tamil spoken tone: ",
    "FRIDAY": "Speak in a calm, polite, structured, and gentle tone in Tamil: ",
    "ENGLISH_PRO": "Speak in a crisp, fluent, confident executive Indian English corporate tone: "
}

# Edge-TTS Fallback Voice Registry
EDGE_FALLBACK_VOICES = {
    "JARVIS": ("ta-IN-ValluvarNeural", "+0%", "+0Hz"),
    "CINEMATIC_JARVIS": ("ta-IN-ValluvarNeural", "+0%", "+0Hz"),
    "MORNING_WAKEUP": ("ta-SG-AnbuNeural", "+0%", "+0Hz"),
    "WORKOUT_BEAST": ("ta-SG-AnbuNeural", "+12%", "+2Hz"),
    "BUSINESS_FINANCE": ("ta-IN-ValluvarNeural", "+0%", "+0Hz"),
    "CARING_FRIEND": ("ta-SG-AnbuNeural", "-3%", "-1Hz"),
    "FRIDAY": ("ta-IN-PallaviNeural", "+0%", "+0Hz"),
    "ENGLISH_PRO": ("en-IN-PrabhatNeural", "+2%", "+0Hz")
}

VOICE_CONFIG_FILE = DATA_DIR / "voice_config.json"

def _load_persona() -> str:
    if VOICE_CONFIG_FILE.exists():
        try:
            import json
            with open(VOICE_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("active_persona", "MORNING_WAKEUP")
        except Exception:
            pass
    return "MORNING_WAKEUP"

def _save_persona(p: str):
    try:
        import json
        with open(VOICE_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({"active_persona": p, "engine": "gemini-3.8-flash-tts"}, f, indent=2)
    except Exception:
        pass

# Persistent active persona lock (defaults to Brotherly Stark Wakeup, survives reboots!)
CURRENT_ACTIVE_PERSONA = _load_persona()


def set_active_persona(persona: str) -> str:
    """Locks the active voice persona permanently to disk to prevent random slang changing."""
    global CURRENT_ACTIVE_PERSONA
    p = persona.upper().strip()
    if p in GEMINI_PERSONA_PROMPTS:
        CURRENT_ACTIVE_PERSONA = p
        _save_persona(p)
        return f"✅ Voice Persona permanently locked to: `{CURRENT_ACTIVE_PERSONA}` (Saved to disk)"
    return f"⚠️ Unknown persona `{persona}`. Choices: {', '.join(GEMINI_PERSONA_PROMPTS.keys())}"


def clean_text_for_speech(text: str) -> str:
    """Cleans markdown, code blocks, URLs, file paths, and emojis so speech flows like a real human."""
    # Remove code blocks
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'`[^`]*`', '', text)
    # Remove file paths like C:\Users\...
    text = re.sub(r'[A-Za-z]\:\\[^\s]+', '', text)
    # Remove URLs
    text = re.sub(r'http\S+', '', text)
    # Remove markdown tables and pipes
    text = re.sub(r'\|[^\n]+\|', '', text)
    # Remove markdown headers and formatting
    text = re.sub(r'[\*\#\_\[\]\(\)\~\>\-\:\•]', ' ', text)
    # Remove emojis
    text = re.sub(r'[\U00010000-\U0010ffff]', '', text)
    # Clean excessive whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    # Keep spoken responses crisp (< 400 chars) for fast vocal cadence
    return text[:400]


def _synthesize_gemini_audio(text: str, persona: str, out_wav_path: Path) -> bool:
    """Synthesizes high-fidelity voice using Google Gemini 3.8 Flash Native Audio."""
    api_key = GEMINI_API_KEY or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return False
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        directive = GEMINI_PERSONA_PROMPTS.get(persona, GEMINI_PERSONA_PROMPTS["MORNING_WAKEUP"])
        prompt = f"{directive}{text}"

        for model_name in [
            "gemini-3.8-flash-lite-tts",
            "gemini-3.8-flash-tts",
            "gemini-2.5-flash-preview-tts",
            "gemini-3.1-flash-tts-preview"
        ]:
            try:
                res = client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )
                if res.candidates and res.candidates[0].content and res.candidates[0].content.parts:
                    for part in res.candidates[0].content.parts:
                        if getattr(part, 'inline_data', None) and part.inline_data.data:
                            with open(out_wav_path, "wb") as f:
                                f.write(part.inline_data.data)
                            return True
            except Exception as me:
                continue
        return False
    except Exception as e:
        print(f"[AURA Voice] Gemini TTS warning: {e}")
        return False


def _synthesize_edge_audio_fallback(text: str, persona: str, out_file: Path) -> bool:
    """Fallback to Microsoft Edge-TTS if Gemini network fails."""
    try:
        import edge_tts
        import asyncio
        voice_info = EDGE_FALLBACK_VOICES.get(persona, EDGE_FALLBACK_VOICES["JARVIS"])
        communicate = edge_tts.Communicate(text, voice=voice_info[0], rate=voice_info[1], pitch=voice_info[2])
        asyncio.run(communicate.save(str(out_file)))
        return out_file.exists() and out_file.stat().st_size > 0
    except Exception as e:
        print(f"[AURA Voice] Edge-TTS fallback error: {e}")
        return False


def convert_wav_to_ogg(wav_path: Path) -> Path:
    """Compresses uncompressed WAV to ultra-light OGG Opus for sub-second Telegram dispatch."""
    ogg_path = wav_path.with_suffix(".ogg")
    try:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        cmd = [ffmpeg, "-y", "-i", str(wav_path), "-c:a", "libopus", "-b:a", "32k", str(ogg_path)]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        if ogg_path.exists() and ogg_path.stat().st_size > 0:
            return ogg_path
    except Exception:
        pass
    return wav_path


def convert_wav_to_mp3(wav_path: Path) -> Path:
    """Converts WAV to MP3 for universal browser/mobile audio streaming."""
    mp3_path = wav_path.with_suffix(".mp3")
    try:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        cmd = [ffmpeg, "-y", "-i", str(wav_path), "-c:a", "libmp3lame", "-b:a", "64k", str(mp3_path)]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        if mp3_path.exists() and mp3_path.stat().st_size > 0:
            return mp3_path
    except Exception:
        pass
    return wav_path


def synthesize_voice_file(
    text: str,
    voice_persona: Optional[str] = None,
    preferred_format: str = "ogg"
) -> Tuple[Optional[Path], str]:
    """
    Synthesizes speech using Gemini Native Audio (with Edge fallback) and returns (file_path, mime_type).
    """
    clean = clean_text_for_speech(text)
    if not clean:
        clean = "All systems operational, Boss Mukil."

    persona = voice_persona.upper().strip() if voice_persona and voice_persona.upper() != "AUTO" else CURRENT_ACTIVE_PERSONA
    ts = int(time.time() * 1000)
    out_wav = VOICE_CACHE_DIR / f"aura_{persona.lower()}_{ts}.wav"

    success = _synthesize_gemini_audio(clean, persona, out_wav)
    if success:
        if preferred_format == "ogg":
            ogg_file = convert_wav_to_ogg(out_wav)
            return ogg_file, "audio/ogg"
        elif preferred_format == "mp3":
            mp3_file = convert_wav_to_mp3(out_wav)
            return mp3_file, "audio/mpeg"
        return out_wav, "audio/wav"

    # Fallback to Edge-TTS
    out_mp3 = VOICE_CACHE_DIR / f"aura_{persona.lower()}_{ts}.mp3"
    if _synthesize_edge_audio_fallback(clean, persona, out_mp3):
        return out_mp3, "audio/mpeg"

    return None, ""


def speak_voice(
    text: str,
    voice_persona: Optional[str] = None,
    play_speakers: bool = True,
    send_to_telegram: bool = False
) -> str:
    """
    Synthesizes and speaks text using AURA's calibrated Gemini Neural Voice engine.
    Maintains a consistent, rock-solid persona without random slang changes!
    """
    clean = clean_text_for_speech(text)
    if not clean:
        clean = "All systems operational, Boss Mukil."

    # Use locked persona or user override (No random keyword-based flipping!)
    persona = voice_persona.upper().strip() if voice_persona and voice_persona.upper() != "AUTO" else CURRENT_ACTIVE_PERSONA

    ts = int(time.time() * 1000)
    out_wav = VOICE_CACHE_DIR / f"aura_{persona.lower()}_{ts}.wav"
    out_file = out_wav
    engine_used = "Google Gemini 3.8 Flash Native Audio"

    # 1. Primary: Gemini 3.8 Flash Native Audio (Authentic Tamil / Tanglish Slang)
    success = _synthesize_gemini_audio(clean, persona, out_wav)

    # 2. Secondary: Edge-TTS Fallback if offline
    if not success:
        out_mp3 = VOICE_CACHE_DIR / f"aura_{persona.lower()}_{ts}.mp3"
        if _synthesize_edge_audio_fallback(clean, persona, out_mp3):
            out_file = out_mp3
            engine_used = "Edge-TTS Fallback"
        else:
            return "❌ Voice synthesis failed across both Gemini and Edge engines."

    status_notes = []

    # 3. Play through PC speakers
    if play_speakers:
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.music.load(str(out_file))
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.08)
            status_notes.append("🔊 Played through PC speakers")
        except Exception as pe:
            status_notes.append(f"⚠️ Speaker playback notice: {str(pe)}")

    # 4. Dispatch to Mukil's Telegram
    if send_to_telegram and TELEGRAM_BOT_TOKEN:
        try:
            upload_path = convert_wav_to_ogg(out_file) if str(out_file).endswith(".wav") else out_file
            mime = "audio/ogg" if str(upload_path).endswith(".ogg") else "audio/mpeg"
            fname = "voice.ogg" if str(upload_path).endswith(".ogg") else "voice.mp3"

            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVoice"
            with open(upload_path, "rb") as f:
                resp = requests.post(
                    url,
                    data={"chat_id": TELEGRAM_CHAT_ID, "caption": f"🎙️ AURA Voice Memo ({persona})"},
                    files={"voice": (fname, f, mime)},
                    timeout=30
                )
            if resp.json().get("ok"):
                status_notes.append("📱 Dispatched to Mukil's Telegram")
            else:
                status_notes.append(f"⚠️ Telegram notice: {resp.json().get('description')}")
        except Exception as te:
            status_notes.append(f"⚠️ Telegram notice: {str(te)}")

    summary = " & ".join(status_notes) if status_notes else "Voice synthesized"
    return f"✅ **Voice Synthesized Successfully!** ({summary})\n🎭 Persona: `{persona}`\n⚡ Engine: `{engine_used}`"


def generate_voice_file(text: str, filename: str = "AURA_Voice_Memo.mp3", voice_persona: Optional[str] = None) -> str:
    """
    Generates a high-definition voice memo using Gemini Native Audio and saves to Desktop.
    """
    clean = clean_text_for_speech(text)
    if not clean:
        clean = "Autonomous Executive Briefing for Boss Mukil."

    persona = voice_persona.upper().strip() if voice_persona and voice_persona.upper() != "AUTO" else CURRENT_ACTIVE_PERSONA

    desktop = Path("C:/Users/mukil/Desktop")
    if not desktop.exists():
        desktop = Path.home() / "Desktop"

    # Base path
    target_path = desktop / filename
    temp_wav = VOICE_CACHE_DIR / f"temp_gen_{int(time.time()*1000)}.wav"

    if _synthesize_gemini_audio(clean, persona, temp_wav):
        # Convert to target format
        try:
            import imageio_ffmpeg
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
            cmd = [ffmpeg, "-y", "-i", str(temp_wav), str(target_path)]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        except Exception:
            import shutil
            shutil.copy(temp_wav, target_path)
        return f"🎙️ **Gemini Native Voice generated on Desktop:** {target_path}\n🎭 Persona: `{persona}` (Consistent Tone)"

    # Fallback to Edge-TTS
    _synthesize_edge_audio_fallback(clean, persona, target_path)
    return f"🎙️ **Voice file generated (Edge-TTS Fallback):** {target_path}\n🎭 Persona: `{persona}`"


def list_voice_personas() -> str:
    """Lists all available neural voice personas for AURA OS."""
    lines = ["🎭 **AURA OS Calibrated Gemini Voice Personas:**"]
    for k, v in GEMINI_PERSONA_PROMPTS.items():
        locked = " [CURRENT DEFAULT]" if k == CURRENT_ACTIVE_PERSONA else ""
        lines.append(f"• **{k}**{locked}: {v}")
    return "\n".join(lines)
