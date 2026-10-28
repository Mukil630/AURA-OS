import os
import sys
import subprocess
import requests
import time
from pathlib import Path
import imageio_ffmpeg

sys.path.insert(0, r"C:\Users\mukil\jarvis-core")
import config

ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
pack_dir = Path(r"C:\Users\mukil\jarvis-core\storage\voice_samples\gemini_pack")
token = config.TELEGRAM_BOT_TOKEN
chat_id = config.AUTHORIZED_TELEGRAM_USERS[0]
tg_url = f"https://api.telegram.org/bot{token}/sendVoice"

samples = [
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

def run():
    print(f"[*] Using ffmpeg: {ffmpeg}")
    for s in samples:
        wav_path = pack_dir / f"{s['id']}.wav"
        ogg_path = pack_dir / f"{s['id']}.ogg"
        
        # Convert WAV to OGG Opus
        cmd = [ffmpeg, "-y", "-i", str(wav_path), "-c:a", "libopus", "-b:a", "32k", str(ogg_path)]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        orig_sz = wav_path.stat().st_size
        new_sz = ogg_path.stat().st_size
        print(f"[+] Compressed {s['id']}: {new_sz} bytes (from {orig_sz} bytes - {round(new_sz/orig_sz*100, 1)}%)")
        
        # Send to Telegram
        with open(ogg_path, "rb") as f:
            r = requests.post(
                tg_url,
                data={"chat_id": chat_id, "caption": s["caption"]},
                files={"voice": ("voice.ogg", f, "audio/ogg")},
                timeout=30
            )
            res = r.json()
            ok = res.get("ok")
            msg_id = res.get("result", {}).get("message_id")
            print(f"[+] Sent {s['id']}: {ok} (Msg ID: {msg_id})")
        time.sleep(1)

    print("[*] All remaining samples dispatched successfully!")

if __name__ == "__main__":
    run()
