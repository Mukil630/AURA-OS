import sys
import time
import requests
from pathlib import Path

JARVIS_DIR = Path(r"C:\Users\mukil\jarvis-core")
if str(JARVIS_DIR) not in sys.path:
    sys.path.insert(0, str(JARVIS_DIR))

import config

token = config.TELEGRAM_BOT_TOKEN
chat_id = config.AUTHORIZED_TELEGRAM_USERS[0]

report_text = """🚀 *JARVIS PRIME // MORNING ROUTINE TOUCHPOINTS 1-3 HOSTED & ACTIVE*

Mapla, neenga sonna andha *First 3 Core Touchpoints*-ah successfully implement panni, 24/7 background scheduler-la host panniten! 

━━━━━━━━━━━━━━━━━━━━━━━━━━━
🌅 *SCHEDULED MORNING PIPELINE (24/7 AUTONOMOUS)*
━━━━━━━━━━━━━━━━━━━━━━━━━━━

⏰ *1. 06:00 AM (Daily)* ➔ *Option 1: MORNING_WAKEUP*
• *Voice:* Brotherly Tony Stark (Kongu/Karur Slang)
• *Actions:* Live Karur Weather Radar, Sky condition & SGC Yarn drying viability check.
• *Care:* Sunglasses & Hydration brotherly reminder.

⏰ *2. 06:05 AM (Daily)* ➔ *Option 3: WORKOUT_BEAST*
• *Voice:* High-Energy Tamil Gym Motivation Coach
• *Actions:* Daily split matrix check (Push/Pull/Legs/Arms).
• *Today (Wednesday):* Legs & Core (Squats, Leg Press, Deadlift).

⏰ *3. 07:00 AM (Monthly 1st)* ➔ *Option 5: BUSINESS_FINANCE*
• *Voice:* Sharp SGC Co-Founder
• *Actions:* SGC Previous Month 5% GST Audit, Net Turnover calculation, and CA-ready Branded Infographic image generation to phone.

━━━━━━━━━━━━━━━━━━━━━━━━━━━
🛡️ *HOSTING & SYSTEM ARCHITECTURE*
━━━━━━━━━━━━━━━━━━━━━━━━━━━
• *Scheduler Status:* 🟢 ACTIVE & RUNNING (24/7 Daemon)
• *Autostart:* Windows Startup VBS persistent across reboots (`launch_morning_routine.vbs`).
• *Audio Pipeline:* Gemini 3.8 Flash Neural Audio + OGG Opus auto-compression (<1s delivery).
• *Next Steps:* Ready to wire 11:00 AM SGC Collections, 02:00 PM Mill Leads, and 10:00 PM Bedtime!

_All 3 touchpoints are locked, loaded, and standing by for tomorrow 06:00 AM sharp, Boss!_ 🔥"""

url = f"https://api.telegram.org/bot{token}/sendMessage"

for attempt in range(1, 5):
    try:
        print(f"[*] Attempt {attempt} to dispatch to Telegram...")
        r = requests.post(url, json={
            "chat_id": chat_id,
            "text": report_text,
            "parse_mode": "Markdown"
        }, timeout=25)
        res = r.json()
        if res.get("ok"):
            print(f"[+] Success! Message ID: {res.get('result', {}).get('message_id')}")
            sys.exit(0)
        else:
            print(f"[-] Telegram returned error: {res}")
    except Exception as e:
        print(f"[!] Attempt {attempt} failed: {e}")
        time.sleep(3)

print("[X] All attempts failed.")
sys.exit(1)
