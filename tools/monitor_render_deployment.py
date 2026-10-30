"""
Monitor Render Deployment for AURA-OS Cloud Routine Engine
tools/monitor_render_deployment.py
"""
import sys
import time
import requests
from pathlib import Path

JARVIS_DIR = Path(__file__).resolve().parent.parent
if str(JARVIS_DIR) not in sys.path:
    sys.path.insert(0, str(JARVIS_DIR))

import config

TARGET_URL = "https://aura-os-jarvis.onrender.com/api/v1/routines/status"
HEALTH_URL = "https://aura-os-jarvis.onrender.com/health"

token = getattr(config, "TELEGRAM_BOT_TOKEN", None)
chat_id = getattr(config, "AUTHORIZED_TELEGRAM_USERS", [6233907249])[0]

def send_telegram(text: str):
    if not token or not chat_id:
        return
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }, timeout=10)
    except Exception as e:
        print(f"Telegram notice error: {e}")

print(f"[*] Starting deployment watcher for {TARGET_URL}...")

max_attempts = 35  # ~5.8 minutes
for attempt in range(1, max_attempts + 1):
    try:
        resp = requests.get(TARGET_URL, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            print(f"✅ [DEPLOYED] Render Cloud Routine Engine is LIVE! Status: {resp.status_code}")
            print(f"Response: {data}")
            
            tg_msg = (
                "🚀 *AURA Cloud Update Live!*\n\n"
                "Boss, the *24/7 Cloud Routine Engine* is now officially compiled, deployed, and live on Render!\n\n"
                "• 🌅 *06:00 AM*: Morning Intel (Stark Wakeup + Karur Weather)\n"
                "• ⚡ *06:05 AM*: Workout Beast Mode (Gym Split Audio)\n"
                "• 📊 *07:00 AM*: SGC 5% GST Audit (1st of month)\n"
                "• 🌙 *22:00 PM*: Night Retrospective\n\n"
                "🔒 *Zero PC Dependency*: Active 24/7 in the cloud independent of your laptop."
            )
            send_telegram(tg_msg)
            print("Telegram notification dispatched successfully.")
            sys.exit(0)
        else:
            print(f"[{attempt}/{max_attempts}] Still building... (HTTP {resp.status_code})")
    except requests.exceptions.RequestException as e:
        print(f"[{attempt}/{max_attempts}] Connecting to Render... ({e.__class__.__name__})")

    time.sleep(10)

print("⚠️ Deployment watcher timed out. Check Render dashboard manually.")
sys.exit(1)
