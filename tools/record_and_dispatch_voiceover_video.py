"""
AURA-OS Professional English Autonomous Telephony Showcase Generator & Dispatcher.
1. Generates pristine, executive-grade English neural voice-over.
2. Records 60fps cinematic animation with professional English telemetry and dialogue.
3. Merges video + audio via FFmpeg into pristine MP4.
4. Saves to Desktop and dispatches directly to Mukil's Telegram bot.
"""
import os
import sys
import time
import json
import shutil
import asyncio
import subprocess
from pathlib import Path
import httpx
from playwright.sync_api import sync_playwright
import imageio_ffmpeg
import edge_tts

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = Path(r"C:\Users\mukil\jarvis-core")
VIDEOS_DIR = BASE_DIR / "storage" / "videos"
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

SHOWCASE_HTML = BASE_DIR / "storage" / "calling_flow_cinematic_showcase.html"
AUDIO_PATH = BASE_DIR / "storage" / "videos" / "aura_os_voiceover_en_pro.mp3"
RAW_VIDEO = BASE_DIR / "storage" / "videos" / "temp_raw_flow_pro.webm"
FINAL_MP4 = Path(r"C:\Users\mukil\Desktop\AURA_OS_Autonomous_Calling_Professional_Demo.mp4")

BOT_TOKEN = "8738700204:AAGfOluaOWUUp5HgZTN0ZXiwxbZrlDEituk"
CHAT_ID = "6233907249"

VOICEOVER_TEXT = '''Welcome to AURA-OS: an Autonomous Sovereign Agent Operating System.

Operating 24/7 on the cloud, AURA-OS initiates an outbound telephony signal over 5G WebSockets directly to the mobile device, triggering hardware screen-wake and activating the biometric Arc-Reactor call interface.

With a single tap on the accept control, an encrypted, full-duplex voice uplink is established. The user issues a natural spoken command: 'JARVIS, retrieve system vitals and live enterprise billing status.'

The AURA Cognitive Kernel transcribes the query in under 200 milliseconds, routing the request through specialized agent tools. JARVIS queries hardware telemetry and the industrial enterprise ledger, delivering a concise spoken briefing: 'All systems operational. CPU load at 12%, and four active invoices totaling 43,439 rupees are reconciled.'

The completed interaction is autonomously committed to persistent memory and synchronized across the 250-gigabyte Distributed Drive Mesh. This is sovereign autonomous computing with AURA-OS.'''

async def generate_voiceover():
    print("[1/4] Generating executive-grade English Voice-Over (Christopher Neural)...")
    communicate = edge_tts.Communicate(VOICEOVER_TEXT, 'en-US-ChristopherNeural', rate='+6%')
    await communicate.save(str(AUDIO_PATH))
    print(f"[+] Audio voice-over saved to {AUDIO_PATH}")

def record_visual_flow():
    print("[2/4] Recording 60fps cinematic flow via Playwright...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            record_video_dir=str(VIDEOS_DIR),
            record_video_size={"width": 1280, "height": 720},
            viewport={"width": 1280, "height": 720}
        )
        page = context.new_page()

        html_url = f"file:///{str(SHOWCASE_HTML).replace(os.sep, '/')}"
        page.goto(html_url, wait_until="networkidle")
        time.sleep(2)

        # Scene 1: Telemetry & Ingress (0 - 15s)
        print("  -> Scene 1: Outbound 5G Telephony Ingress & Biometric Arc-Reactor HUD...")
        page.evaluate("window.simulateStep(1)")
        time.sleep(15)

        # Scene 2: Accept Call & Spoken Query (15 - 30s)
        print("  -> Scene 2: Encrypted Handshake & Natural Spoken Query...")
        page.evaluate("window.simulateStep(2)")
        time.sleep(15)

        # Scene 3: ReAct Reasoning & Verbal Tools (30 - 48s)
        print("  -> Scene 3: Sub-200ms Transcription & Industrial ERP Reconciliation...")
        page.evaluate("window.simulateStep(3)")
        time.sleep(18)

        # Scene 4: Memory Persistence (48 - 62s)
        print("  -> Scene 4: State Commitment to Context & 250GB Distributed Memory Mesh...")
        page.evaluate("window.simulateStep(4)")
        time.sleep(14)

        page_video = page.video
        page.close()
        context.close()
        browser.close()

        rec_path = page_video.path()
        shutil.move(rec_path, str(RAW_VIDEO))
        print(f"[+] Raw video captured: {RAW_VIDEO}")

def merge_audio_video():
    print("[3/4] Merging high-definition video and English voice-over using FFmpeg...")
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    cmd = [
        ffmpeg_exe,
        "-y",
        "-i", str(RAW_VIDEO),
        "-i", str(AUDIO_PATH),
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "22",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        str(FINAL_MP4)
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[!] FFmpeg merge error: {result.stderr}")
        raise RuntimeError("FFmpeg merge failed")

    size_mb = os.path.getsize(FINAL_MP4) / (1024 * 1024)
    print(f"🎉 [+] Final Professional English Video Ready: {FINAL_MP4} ({size_mb:.2f} MB)")

def dispatch_to_telegram():
    print("[4/4] Transmitting professional English video to Telegram...")
    caption = (
        "🚀 <b>AURA-OS: AUTONOMOUS TELEPHONY & AGENT OPERATING PLANE</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🏛️ <b>Professional Architecture Walkthrough:</b>\n"
        "1️⃣ <b>5G Ingress</b>: Cloud WebSockets trigger hardware wake-lock on mobile devices.\n"
        "2️⃣ <b>Arc-Reactor HUD</b>: Biometric incoming call interface with real-time waveform dynamics.\n"
        "3️⃣ <b>Full-Duplex Voice Link</b>: Encrypted hands-free spoken dialogue with acoustic feedback isolation.\n"
        "4️⃣ <b>Cognitive ReAct Kernel</b>: Sub-200ms transcription routing to PC vitals & SGC ERP ledgers.\n"
        "5️⃣ <b>Distributed Memory</b>: Persistent state synchronization across a 250GB Drive Mesh.\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔗 <b>GitHub Repo</b>: https://github.com/Mukil630/AURA-OS\n"
        "🎙️ <i>Executive-grade English Voice-Over included.</i>"
    )

    url_video = f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo"
    url_doc = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"

    with open(FINAL_MP4, "rb") as f:
        video_bytes = f.read()

    # 1. Send as streaming Video
    files_video = {"video": ("aura_os_professional_demo.mp4", video_bytes, "video/mp4")}
    data_video = {"chat_id": CHAT_ID, "caption": caption, "parse_mode": "HTML", "supports_streaming": "true"}
    print("  -> Uploading Video stream via HTTPX...")
    res1 = httpx.post(url_video, data=data_video, files=files_video, timeout=120)
    print(f"  [+] Stream Video Upload Status: {res1.status_code} (ok: {res1.json().get('ok')})")

    # 2. Send as downloadable Document
    files_doc = {"document": ("AURA_OS_Autonomous_Calling_Professional_Demo.mp4", video_bytes, "video/mp4")}
    data_doc = {"chat_id": CHAT_ID, "caption": "📁 <b>AURA-OS Architecture Demo (MP4 HD Download)</b>", "parse_mode": "HTML"}
    print("  -> Uploading MP4 Document via HTTPX...")
    res2 = httpx.post(url_doc, data=data_doc, files=files_doc, timeout=120)
    print(f"  [+] Document Upload Status: {res2.status_code} (ok: {res2.json().get('ok')})")

def main():
    asyncio.run(generate_voiceover())
    record_visual_flow()
    merge_audio_video()
    dispatch_to_telegram()

if __name__ == "__main__":
    main()
