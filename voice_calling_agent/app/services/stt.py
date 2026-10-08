import os
from typing import Optional
from app.core.config import GROQ_API_KEY

def transcribe_audio_groq(audio_bytes: bytes, filename: str = "audio.ogg") -> Optional[str]:
    """Transcribes audio using Groq Whisper Large V3 Turbo for ultra-fast latency."""
    if not GROQ_API_KEY:
        return None
    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        transcription = client.audio.transcriptions.create(
            file=(filename, audio_bytes),
            model="whisper-large-v3-turbo",
            prompt="Tanglish, Tamil, English spoken dialogue with JARVIS AI",
            response_format="text"
        )
        return str(transcription).strip()
    except Exception as e:
        print(f"[STT Error] Groq Whisper transcription failed: {e}")
        return None
