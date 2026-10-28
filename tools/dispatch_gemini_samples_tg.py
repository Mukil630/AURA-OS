import os
import sys
import time
from pathlib import Path
import requests

JARVIS_DIR = Path(r"C:\Users\mukil\jarvis-core")
if str(JARVIS_DIR) not in sys.path:
    sys.path.insert(0, str(JARVIS_DIR))

import config

SAMPLES_DIR = JARVIS_DIR / "storage" / "voice_samples" / "gemini_pack"

AUDITION_PROMPTS = [
    {
        "id": "gemini_02_deep_jarvis",
        "caption": "🔥 Option 2: Deep Authoritative Cinematic JARVIS\n'வணக்கம் முகில். ஆல் சிஸ்டம்ஸ் ஆன்லைன். SGC கலெக்ஷன்ஸ் பில்லிங் ரேடார் ஆக்டிவா இருக்கு பாஸ்!'"
    },
    {
        "id": "gemini_03_gym_beast",
        "caption": "🔥 Option 3: Gym Motivation Beast Mode\n'ஒர்க்கவுட் டைம் பாஸ்! இன்னைக்கு புல் டே மாப்ள. லேட் புல்டவுன் பைசெப்ஸ் போட்டு தூள் கெளப்பலாம்!'"
    },
    {
        "id": "gemini_04_caring_friend",
        "caption": "🔥 Option 4: Caring Kongu/Karur Best Friend\n'மாப்ள, வெளில பைக்ல போறப்ப சன்கிளாஸ் மாட்டிக்கோங்க! நல்லா தண்ணி குடிங்க மாப்ள!'"
    },
    {
        "id": "gemini_05_business_partner",
        "caption": "🔥 Option 5: Sharp Business Co-Founder (SGC Cash Radar)\n'பாஸ், கையா சஸ்டைனபிள் பில் நம்பர் 7 ₹1,575 கலெக்ஷன் ரெடி. மணி அண்ணன் இன்ட்ரெஸ்ட் ட்ராக் பண்றேன்!'"
    }
]

def dispatch_remaining():
    token = config.TELEGRAM_BOT_TOKEN
    chat_id = config.AUTHORIZED_TELEGRAM_USERS[0]
    tg_url = f"https://api.telegram.org/bot{token}/sendVoice"

    for item in AUDITION_PROMPTS:
        file_path = SAMPLES_DIR / f"{item['id']}.wav"
        if not file_path.exists():
            print(f"[!] File not found: {file_path}")
            continue

        sent = False
        for attempt in range(1, 4):
            try:
                print(f"[*] Dispatching {item['id']}.wav (Attempt {attempt})...")
                with open(file_path, "rb") as f:
                    r = requests.post(
                        tg_url,
                        data={"chat_id": chat_id, "caption": item["caption"]},
                        files={"voice": f},
                        timeout=90
                    )
                res = r.json()
                if res.get("ok"):
                    print(f"[+] Sent {item['id']}: True (Msg ID: {res.get('result', {}).get('message_id')})")
                    sent = True
                    break
                else:
                    print(f"[-] Telegram returned: {res}")
            except Exception as e:
                print(f"[!] Attempt {attempt} failed: {e}")
                time.sleep(3)

        if not sent:
            print(f"[X] Failed to send {item['id']} after 3 attempts.")
        time.sleep(2)

    print("[*] Dispatch process complete!")

if __name__ == "__main__":
    dispatch_remaining()
