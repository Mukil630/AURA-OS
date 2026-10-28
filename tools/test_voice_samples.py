"""
========================================================================================
JARVIS VOICE STUDIO — VOICE COMPARISON & AUDITION SAMPLER (test_voice_samples.py)
----------------------------------------------------------------------------------------
Generates audio samples for Mukil's morning briefing using top Neural voices:
1. ta-IN-ValluvarNeural (Male Tamil - JARVIS / Tony Stark vibe)
2. ta-IN-PallaviNeural  (Female Tamil - FRIDAY vibe)
3. ta-SG-AnbuNeural     (Male Tamil - Youthful brotherly vibe)
========================================================================================
"""

import os
import sys
import asyncio
from pathlib import Path
import edge_tts

JARVIS_DIR = Path(__file__).resolve().parent.parent
SAMPLES_DIR = JARVIS_DIR / "storage" / "voice_samples"
SAMPLES_DIR.mkdir(parents=True, exist_ok=True)

# Mukil's exact morning greeting text
SAMPLE_TEXT = (
    "Hello Boss! Good morning! கரூர்ல இன்னைக்கு 31 டிகிரி நல்ல வெயில் மாப்ள, "
    "மழை வர வாய்ப்பு zero percent. SGC yarn காய வைக்க சரியான நாள்! "
    "வெளில போறப்ப மறக்காம sunglasses போட்டுக்கோங்க, நல்லா தண்ணி குடிங்க!"
)

VOICES = {
    "valluvar_male": ("ta-IN-ValluvarNeural", "JARVIS Male (Tamil India)"),
    "pallavi_female": ("ta-IN-PallaviNeural", "FRIDAY Female (Tamil India)"),
    "anbu_male": ("ta-SG-AnbuNeural", "Brotherly Male (Tamil Youth)")
}


async def generate_samples():
    results = {}
    for key, (voice_id, desc) in VOICES.items():
        out_file = SAMPLES_DIR / f"{key}.mp3"
        print(f"[*] Synthesizing with {voice_id} ({desc})...")
        communicate = edge_tts.Communicate(SAMPLE_TEXT, voice_id)
        await communicate.save(str(out_file))
        results[key] = {
            "name": desc,
            "voice_id": voice_id,
            "file": str(out_file),
            "size_kb": round(out_file.stat().st_size / 1024, 2)
        }
    return results


if __name__ == "__main__":
    res = asyncio.run(generate_samples())
    for k, v in res.items():
        print(f"[+] Generated: {v['name']} -> {v['file']} ({v['size_kb']} KB)")
