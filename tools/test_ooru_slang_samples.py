"""
========================================================================================
JARVIS NAMMA OORU SLANG AUDIO GENERATOR (test_ooru_slang_samples.py)
----------------------------------------------------------------------------------------
Converts formal Tamil into 100% authentic Karur / Kongu spoken colloquial Tamil (பேச்சுத் தமிழ்):
- Formal 'சரியான நாள்' -> Colloquial 'செம நாளு மாப்ள!'
- Formal 'வாய்ப்பு இல்லை' -> Colloquial 'மழையெல்லாம் ஒன்னும் வராது, sky ஃபுல் க்ளியர்!'
- Formal 'போட்டுக் கொள்ளுங்கள்' -> Colloquial 'வெயில் கொளுத்துது, sunglasses மாட்டிக்கோ மாப்ள!'
- Slightly boosted rate (+6%) for real human brotherly conversational cadence.
========================================================================================
"""

import os
import sys
import asyncio
from pathlib import Path
import edge_tts
import requests

JARVIS_DIR = Path(__file__).resolve().parent.parent
if str(JARVIS_DIR) not in sys.path:
    sys.path.insert(0, str(JARVIS_DIR))

import config

SAMPLES_DIR = JARVIS_DIR / "storage" / "voice_samples"
SAMPLES_DIR.mkdir(parents=True, exist_ok=True)

# 100% Authentic Namma Ooru Spoken Tamil (Colloquial Karur Slang)
OORU_SLANG_TEXT = (
    "Hello Boss! Good morning! கரூர்ல இன்னைக்கு 31 டிகிரி வெயில் சும்மா கொளுத்துது மாப்ள! "
    "மழையெல்லாம் ஒன்னும் வராது, sky ஃபுல் க்ளியர். SGC யார்ன் காய போட இன்னைக்கு செம நாளு! "
    "வெளில பைக்ல போறப்ப மறக்காம sunglasses மாட்டிக்கோங்க, வெயிலுக்கு தண்ணி நெறைய குடிச்சுக்கோங்க மாப்ள!"
)

OORU_WORKOUT_TEXT = (
    "Workout time Boss! இன்னைக்கு செவ்வாய்க்கிழமை, பேக் அண்ட் பைசெப்ஸ் Pull Day மாப்ள! "
    "லேட் புல்டவுன், சீட்டட் ரோவ்ஸ், அப்புறம் hammer curls போட்டு இன்னைக்கு ஜிம்முல தூள் கெளப்பலாம் மாப்ள!"
)


async def generate_and_dispatch():
    voices_to_test = [
        ("ta-IN-ValluvarNeural", "+6%", "valluvar_ooru_slang.mp3", "🎙️ Namma Ooru Slang 1: Valluvar (Natural Karur Tone)"),
        ("ta-SG-AnbuNeural", "+5%", "anbu_ooru_slang.mp3", "🎙️ Namma Ooru Slang 2: Anbu (Casual Friendly Tone)")
    ]

    token = getattr(config, "TELEGRAM_BOT_TOKEN", None)
    chat_id = getattr(config, "AUTHORIZED_TELEGRAM_USERS", [6233907249])[0]
    tg_url = f"https://api.telegram.org/bot{token}/sendVoice"

    for voice_id, rate_val, filename, caption in voices_to_test:
        out_file = SAMPLES_DIR / filename
        print(f"[*] Generating {filename} with {voice_id} at rate {rate_val}...")
        
        # Using rate=+6% for natural human speech flow (eliminates robotic slow reading)
        communicate = edge_tts.Communicate(OORU_SLANG_TEXT, voice_id, rate=rate_val)
        await communicate.save(str(out_file))

        if token and out_file.exists():
            print(f"[+] Sending {filename} to Telegram...")
            with open(out_file, "rb") as f:
                r = requests.post(tg_url, data={"chat_id": chat_id, "caption": caption}, files={"voice": f}, timeout=25)
                print(f"[+] Telegram Status for {filename}: {r.json().get('ok')}")


if __name__ == "__main__":
    asyncio.run(generate_and_dispatch())
