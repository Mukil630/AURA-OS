"""
Record Cinematic Stark HUD Animation of JARVIS 9:00 AM Job Apply Strike.
Dispatches directly to Mukil's Telegram!
"""

import os
import sys
import time
import json
from pathlib import Path
import urllib.request
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent.parent
VIDEOS_DIR = BASE_DIR / "storage" / "videos"
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = "6233907249"

HTML_PATH = BASE_DIR / "storage" / "creative_jarvis_job_apply.html"

print(f"[*] Starting Cinematic HUD Recording from: {HTML_PATH}")

OUTPUT_VIDEO = None

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        record_video_dir=str(VIDEOS_DIR),
        record_video_size={"width": 1280, "height": 720},
        viewport={"width": 1280, "height": 720}
    )
    page = context.new_page()
    page.goto(f"file:///{str(HTML_PATH).replace(os.sep, '/')}", wait_until="load")
    time.sleep(1)

    # Phase 1: 09:00 AM Cron Strike
    print("[1/4] Phase 1: 09:00 AM Cron Strike...")
    page.evaluate("window.setPhase(1)")
    time.sleep(3)

    # Phase 2: Global Tech Radar Scan
    print("[2/4] Phase 2: Global Tech Radar Scan & ATS Matching...")
    page.evaluate("window.setPhase(2)")
    time.sleep(3.5)

    # Phase 3: BrowserPilot Form Solver
    print("[3/4] Phase 3: BrowserPilot Form Solver & Resume Injection...")
    page.evaluate("window.setPhase(3)")
    time.sleep(3.5)

    # Phase 4: Mission Accomplished & Telegram Dispatch
    print("[4/4] Phase 4: Verified Submission & Telegram Dispatch...")
    page.evaluate("window.setPhase(4)")
    time.sleep(4)

    page_video = page.video
    page.close()
    context.close()
    browser.close()

    OUTPUT_VIDEO = page_video.path()

print(f"\n[+] Cinematic HUD Video Recorded! File: {OUTPUT_VIDEO}")
print(f"Size: {os.path.getsize(OUTPUT_VIDEO)} bytes")

caption = (
    "⚡ <b>JARVIS 9:00 AM AUTONOMOUS CAREER STRIKE // HUD FLOW</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "🚀 <b>Stark Cybernetic Execution:</b>\n"
    "1️⃣ <b>09:00:00 AM Cron Lock</b>: Windows Task Scheduler awakens JARVIS Placement Daemon.\n"
    "2️⃣ <b>Global Tech Radar Scan</b>: 360° radar sweep detects 59 openings (GitLab 98%, Canonical 94%, Datadog 90%).\n"
    "3️⃣ <b>BrowserPilot Strike</b>: Headless Playwright + Gemini 3.6 Flash auto-fills form & selects dropdowns.\n"
    "4️⃣ <b>Drive Vault & Telegram Alert</b>: Instant proof screenshot sent to your phone with zero human touch.\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "✅ <i>Mapla, Stark HUD style creative automation video unga phone-ku vanthachu!</i> 🔥"
)

def send_video(token, chat_id, vid_path, caption):
    url = f"https://api.telegram.org/bot{token}/sendVideo"
    boundary = "----WebKitFormBoundaryCyberHUD88"
    with open(vid_path, "rb") as f:
        vid_bytes = f.read()

    body = bytearray()
    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(f'Content-Disposition: form-data; name="chat_id"\r\n\r\n{chat_id}\r\n'.encode("utf-8"))
    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(f'Content-Disposition: form-data; name="caption"\r\n\r\n{caption}\r\n'.encode("utf-8"))
    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(f'Content-Disposition: form-data; name="parse_mode"\r\n\r\nHTML\r\n'.encode("utf-8"))
    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(f'Content-Disposition: form-data; name="video"; filename="jarvis_cyber_job_apply_flow.webm"\r\n'.encode("utf-8"))
    body.extend(b'Content-Type: video/webm\r\n\r\n')
    body.extend(vid_bytes)
    body.extend(b'\r\n')
    body.extend(f"--{boundary}--\r\n".encode("utf-8"))

    req = urllib.request.Request(
        url,
        data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=45) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        print("[+] Telegram sendVideo result:", res.get("ok"))

send_video(BOT_TOKEN, CHAT_ID, OUTPUT_VIDEO, caption)
