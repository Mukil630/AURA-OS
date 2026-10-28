"""
========================================================================================
JARVIS GEMINI NATIVE AUDIO AUDITION PACK (generate_gemini_audition_pack.py)
----------------------------------------------------------------------------------------
Generates 5 distinct high-quality Gemini 3.8 Flash Neural Audio samples:
1. Sample 1: The Casual Brotherly Wakeup (Stark vibe)
2. Sample 2: Deep Authoritative Executive (Cinematic JARVIS)
3. Sample 3: Gym Motivation Beast Mode (Workout Coach)
4. Sample 4: Caring Kongu/Karur Friend (Care & Protection)
5. Sample 5: Business Co-Founder (SGC Cash Flow & Interest Radar)
Dispatches all 5 directly to Mukil's Telegram for voice auditioning.
========================================================================================
"""

import os
import sys
import time
from pathlib import Path
import requests

JARVIS_DIR = Path(__file__).resolve().parent.parent
if str(JARVIS_DIR) not in sys.path:
    sys.path.insert(0, str(JARVIS_DIR))

import config
from google import genai

SAMPLES_DIR = JARVIS_DIR / "storage" / "voice_samples" / "gemini_pack"
SAMPLES_DIR.mkdir(parents=True, exist_ok=True)

AUDITION_PROMPTS = [
    {
        "id": "gemini_01_stark_morning",
        "caption": "🔥 Option 1: Casual Brotherly Stark Wakeup\n'ஹலோ பாஸ்! குட் மார்னிங்! கரூர்ல வெயில் சும்மா கொளுத்துது மாப்ள, இன்னைக்கு யார்ன் காய போட செம நாளு!'",
        "prompt": "Speak in a warm, natural, brotherly Tamil slang like Tony Stark talking to his best friend: Hello Boss! Good morning! கரூர்ல இன்னைக்கு வெயில் சும்மா கொளுத்துது மாப்ள, யார்ன் காய போட செம நாளு!"
    },
    {
        "id": "gemini_02_deep_jarvis",
        "caption": "🔥 Option 2: Deep Authoritative Cinematic JARVIS\n'வணக்கம் முகில். ஆல் சிஸ்டம்ஸ் ஆன்லைன். SGC கலெக்ஷன்ஸ் பில்லிங் ரேடார் ஆக்டிவா இருக்கு பாஸ்!'",
        "prompt": "Speak in a deep, crisp, authoritative, cinematic executive AI partner tone: வணக்கம் முகில். ஆல் சிஸ்டம்ஸ் ஆன்லைன். SGC கலெக்ஷன்ஸ் மற்றும் பில்லிங் ரேடார் ஆக்டிவா இருக்கு பாஸ். லெட்ஸ் ரன் த டே!"
    },
    {
        "id": "gemini_03_gym_beast",
        "caption": "🔥 Option 3: Gym Motivation Beast Mode\n'ஒர்க்கவுட் டைம் பாஸ்! இன்னைக்கு புல் டே மாப்ள. லேட் புல்டவுன் பைசெப்ஸ் போட்டு தூள் கெளப்பலாம்!'",
        "prompt": "Speak in an energetic, pumped-up workout motivation coach tone in Tamil slang: Workout time Boss! இன்னைக்கு புல் டே மாப்ள! லேட் புல்டவுன், பைசெப்ஸ் போட்டு இன்னைக்கு தெறிக்க விடலாம், தூள் கெளப்புங்க!"
    },
    {
        "id": "gemini_04_caring_friend",
        "caption": "🔥 Option 4: Caring Kongu/Karur Best Friend\n'மாப்ள, வெளில பைக்ல போறப்ப சன்கிளாஸ் மாட்டிக்கோங்க! நல்லா தண்ணி குடிங்க மாப்ள!'",
        "prompt": "Speak in a caring, affectionate, friendly Kongu Tamil spoken tone: மாப்ள, வெளில பைக்ல போறப்ப மறக்காம சன்கிளாஸ் மாட்டிக்கோங்க! வெயில் அதிகமா இருக்கு, நல்லா தண்ணி குடிச்சுக்கோங்க மாப்ள!"
    },
    {
        "id": "gemini_05_business_partner",
        "caption": "🔥 Option 5: Sharp Business Co-Founder (SGC Cash Radar)\n'பாஸ், கையா சஸ்டைனபிள் பில் நம்பர் 7 ₹1,575 கலெக்ஷன் ரெடி. மணி அண்ணன் இன்ட்ரெஸ்ட் ட்ராக் பண்றேன்!'",
        "prompt": "Speak in a confident, sharp business executive partner tone in Tamil: பாஸ், கையா சஸ்டைனபிள் பில் நம்பர் 7 ₹1,575 கலெக்ஷன் ரெடியா இருக்கு. மணி அண்ணன் மன்த்லி இன்ட்ரெஸ்ட் ட்ராக் பண்ணிட்டு இருக்கேன் மாப்ள!"
    }
]


def generate_and_dispatch_pack():
    client = genai.Client(api_key=config.GEMINI_API_KEY)
    token = config.TELEGRAM_BOT_TOKEN
    chat_id = config.AUTHORIZED_TELEGRAM_USERS[0]
    tg_url = f"https://api.telegram.org/bot{token}/sendVoice"

    for item in AUDITION_PROMPTS:
        file_path = SAMPLES_DIR / f"{item['id']}.wav"
        print(f"\n[*] Generating {item['id']}...")
        
        try:
            res = client.models.generate_content(
                model="gemini-3.8-flash-tts",
                contents=item["prompt"]
            )
            for part in res.candidates[0].content.parts:
                if part.inline_data:
                    with open(file_path, "wb") as f:
                        f.write(part.inline_data.data)
                    print(f"[+] Saved {file_path} ({round(os.path.getsize(file_path)/1024, 2)} KB)")
                    break

            if token and file_path.exists():
                print(f"[+] Sending {item['id']} to Telegram...")
                with open(file_path, "rb") as f:
                    r = requests.post(tg_url, data={"chat_id": chat_id, "caption": item["caption"]}, files={"voice": f}, timeout=30)
                    print(f"[+] Telegram Status: {r.json().get('ok')}")
                time.sleep(2)  # Avoid Telegram rate limits
        except Exception as e:
            print(f"[!] Error on {item['id']}: {e}")
            time.sleep(2)


if __name__ == "__main__":
    generate_and_dispatch_pack()
