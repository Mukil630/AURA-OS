"""
Record 1080p Ultra-HD 60FPS Cinematic JARVIS Prime Autonomous Career Strike.
Delivers directly to Mukil's Telegram!
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

BOT_TOKEN = "8738700204:AAGfOluaOWUUp5HgZTN0ZXiwxbZrlDEituk"
CHAT_ID = "6233907249"

HTML_PATH = BASE_DIR / "storage" / "jarvis_advanced_cinema.html"

print(f"[*] Starting 1080p 60FPS Cinematic HUD Recording from: {HTML_PATH}")

OUTPUT_VIDEO = None

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        record_video_dir=str(VIDEOS_DIR),
        record_video_size={"width": 1920, "height": 1080},
        viewport={"width": 1920, "height": 1080}
    )
    page = context.new_page()
    page.goto(f"file:///{str(HTML_PATH).replace(os.sep, '/')}", wait_until="load")
    time.sleep(1)

    # Phase 1: 09:00:00 AM Cron Engaged
    print("[1/4] Phase 1: 09:00:00 AM Cron Engaged...")
    page.evaluate("window.setPhase(1)")
    time.sleep(3.5)

    # Phase 2: Radar Scan & 3D Globe Pings
    print("[2/4] Phase 2: Radar Scan & Global 3D Wireframe Pings...")
    page.evaluate("window.setPhase(2)")
    time.sleep(4)

    # Phase 3: CodeAct Live Execution
    print("[3/4] Phase 3: CodeAct Neural Live Execution...")
    page.evaluate("window.setPhase(3)")
    time.sleep(4)

    # Phase 4: Verified Submission & Telegram Receipt
    print("[4/4] Phase 4: Application 100% Verified & Telegram Dispatched...")
    page.evaluate("window.setPhase(4)")
    time.sleep(4.5)

    page_video = page.video
    page.close()
    context.close()
    browser.close()

    OUTPUT_VIDEO = page_video.path()

print(f"\n[+] 1080p Cinematic Video Recorded! File: {OUTPUT_VIDEO}")
print(f"Size: {os.path.getsize(OUTPUT_VIDEO)} bytes")

caption = (
    "⚡ <b>JARVIS PRIME // 1080p 60FPS ADVANCED CAREER STRIKE</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "🌐 <b>Stark Industries Advanced Cognitive Flow:</b>\n"
    "1️⃣ <b>3D Holographic Wireframe Globe</b>: Rotating latitude/longitude rings with orbital satellites & real-time pings.\n"
    "2️⃣ <b>Autonomous Swarm Registry</b>: 👑 Antigravity Prime, 🤖 BrowserPilot, 🎯 PlacementHunter, ☁️ MemoryVault.\n"
    "3️⃣ <b>Live ATS Radar</b>: GitLab AI Engineer (98%), Canonical Python (94%), Canonical Go (92%).\n"
    "4️⃣ <b>CodeAct Stream</b>: Headless Playwright DOM injection + Gemini 3.6 Flash screening solver.\n"
    "5️⃣ <b>Telegram Verification Receipt</b>: Direct dispatch to your phone with zero human touch.\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "✅ <i>Mapla, ultra-crisp 1080p JARVIS cinema style video unga phone-ku vanthachu!</i> 🔥"
)

def send_video(token, chat_id, vid_path, caption):
    url = f"https://api.telegram.org/bot{token}/sendVideo"
    boundary = "----WebKitFormBoundaryCinema1080p99"
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
    body.extend(f'Content-Disposition: form-data; name="video"; filename="jarvis_prime_1080p_career_strike.webm"\r\n'.encode("utf-8"))
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

    with urllib.request.urlopen(req, timeout=60) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        print("[+] Telegram sendVideo result:", res.get("ok"))

send_video(BOT_TOKEN, CHAT_ID, OUTPUT_VIDEO, caption)
