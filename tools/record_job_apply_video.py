"""
Cinematic Video Generator for JARVIS 9:00 AM Fresher Tech Job Auto-Apply Pipeline.
Visualizes the 4-stage automated execution:
1. 09:00 AM Cron & Windows Task Scheduler Trigger
2. Live Tech Boards Scan & ATS Matching (>90% Score)
3. Autonomous BrowserPilot Execution (Playwright form-filling, dropdowns, Gemini solver)
4. Proof Screenshot Capture, Google Drive Vault Upload & Telegram Alert Dispatch
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

SHOWCASE_HTML = BASE_DIR / "storage" / "job_auto_apply_showcase.html"

html_code = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>JARVIS 9:00 AM Job Auto-Apply Flow</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    background: #06080e;
    color: #ede5d0;
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    width: 100vw;
    height: 100vh;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }
  .header {
    height: 64px;
    background: #0b0f19;
    border-bottom: 1.5px solid rgba(255,200,74,0.3);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 36px;
  }
  .brand {
    display: flex;
    align-items: center;
    gap: 14px;
  }
  .brand-logo {
    width: 38px;
    height: 38px;
    border-radius: 10px;
    background: linear-gradient(135deg, #f59e0b, #d97706);
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 900;
    color: #111;
    font-size: 18px;
    box-shadow: 0 0 15px rgba(245,158,11,0.5);
  }
  .brand-title {
    font-size: 17px;
    font-weight: 800;
    color: #ffc84a;
    letter-spacing: 0.5px;
  }
  .cron-timer {
    display: flex;
    align-items: center;
    gap: 10px;
    background: rgba(16,185,129,0.15);
    border: 1px solid rgba(16,185,129,0.4);
    padding: 6px 16px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 700;
    color: #34d399;
  }
  .clock-pulse {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #34d399;
    box-shadow: 0 0 10px #34d399;
    animation: pulse 1s infinite alternate;
  }
  @keyframes pulse {
    from { opacity: 0.4; transform: scale(0.8); }
    to { opacity: 1; transform: scale(1.3); }
  }

  /* 4-Stage Grid */
  .grid-container {
    flex: 1;
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 20px;
    padding: 28px 36px;
    align-items: stretch;
  }
  .stage-card {
    background: rgba(15,23,42,0.65);
    border: 1.5px solid rgba(255,255,255,0.08);
    border-radius: 18px;
    padding: 22px;
    display: flex;
    flex-direction: column;
    position: relative;
    transition: all 0.6s cubic-bezier(0.16, 1, 0.3, 1);
    opacity: 0.3;
    transform: translateY(14px);
  }
  .stage-card.active {
    opacity: 1;
    transform: translateY(0);
    border-color: #ffc84a;
    background: rgba(18,27,48,0.95);
    box-shadow: 0 0 35px rgba(255,200,74,0.22);
  }
  .stage-card.completed {
    opacity: 0.85;
    border-color: #10b981;
    box-shadow: 0 0 20px rgba(16,185,129,0.15);
  }
  .stage-header {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 14px;
  }
  .stage-badge {
    width: 30px;
    height: 30px;
    border-radius: 50%;
    background: rgba(255,255,255,0.1);
    color: #aaa;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 13px;
    font-weight: 800;
    transition: all 0.4s;
  }
  .stage-card.active .stage-badge {
    background: #ffc84a;
    color: #111;
  }
  .stage-card.completed .stage-badge {
    background: #10b981;
    color: #111;
  }
  .stage-title {
    font-size: 15px;
    font-weight: 800;
    color: #fff;
    letter-spacing: 0.3px;
  }
  .stage-desc {
    font-size: 11.5px;
    color: #94a3b8;
    line-height: 1.5;
    margin-bottom: 16px;
  }
  .stage-body {
    flex: 1;
    background: #0a0d16;
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px;
    padding: 14px;
    font-size: 11px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    overflow: hidden;
  }
  .data-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 6px 8px;
    background: rgba(255,255,255,0.03);
    border-radius: 6px;
  }
  .tag {
    padding: 2px 7px;
    border-radius: 4px;
    font-size: 9.5px;
    font-weight: 700;
  }
  .tag-cyan { background: rgba(56,189,248,0.2); color: #38bdf8; border: 1px solid rgba(56,189,248,0.4); }
  .tag-gold { background: rgba(255,200,74,0.2); color: #ffc84a; border: 1px solid rgba(255,200,74,0.4); }
  .tag-green { background: rgba(34,197,94,0.2); color: #4ade80; border: 1px solid rgba(34,197,94,0.4); }

  .connector-arrow {
    position: absolute;
    right: -14px;
    top: 50%;
    transform: translateY(-50%);
    font-size: 16px;
    color: #ffc84a;
    z-index: 10;
    opacity: 0.3;
    transition: opacity 0.5s;
  }
  .stage-card.active .connector-arrow {
    opacity: 1;
    text-shadow: 0 0 10px #ffc84a;
  }
  .footer {
    height: 48px;
    background: #090c14;
    border-top: 1px solid rgba(255,255,255,0.08);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 36px;
    font-size: 11.5px;
    color: #888;
  }
</style>
</head>
<body>

<div class="header">
  <div class="brand">
    <div class="brand-logo">J</div>
    <div class="brand-title">JARVIS 9:00 AM AUTONOMOUS CAREER & JOB-APPLY PIPELINE</div>
  </div>
  <div class="cron-timer">
    <div class="clock-pulse"></div>
    <span>⏰ SCHEDULED DAILY: 09:00:00 AM (WIN CRON)</span>
  </div>
</div>

<div class="grid-container">

  <!-- STAGE 1: 9:00 AM CRON TRIGGER -->
  <div class="stage-card" id="stage1">
    <div class="stage-header">
      <div class="stage-badge">1</div>
      <div class="stage-title">9:00 AM Auto-Trigger</div>
    </div>
    <div class="stage-desc">Windows Task Scheduler executes <code>daily_fresher_job_dispatcher.py</code> automatically every morning.</div>
    <div class="stage-body">
      <div class="data-row">
        <span>Trigger Source:</span>
        <span class="tag tag-gold">Windows Task Scheduler</span>
      </div>
      <div class="data-row">
        <span>Target Time:</span>
        <strong style="color:#fff;">09:00:00 AM IST</strong>
      </div>
      <div class="data-row">
        <span>Greenhouse Boards:</span>
        <span class="tag tag-cyan">Canonical, GitLab, Datadog...</span>
      </div>
      <div class="data-row">
        <span>Lever Boards:</span>
        <span class="tag tag-cyan">Postman, Razorpay, BrowserStack</span>
      </div>
      <div class="data-row" style="background:rgba(34,197,94,0.12); border:1px solid rgba(34,197,94,0.3);">
        <span>Fresh Openings:</span>
        <strong style="color:#4ade80;">59 Matches Found</strong>
      </div>
    </div>
    <div class="connector-arrow">➔</div>
  </div>

  <!-- STAGE 2: ATS MATCHING & RESUME SYNC -->
  <div class="stage-card" id="stage2">
    <div class="stage-header">
      <div class="stage-badge">2</div>
      <div class="stage-title">ATS Radar & Ranking</div>
    </div>
    <div class="stage-desc">Ranks openings against Mukil's skills (Python, Docker, FastAPI, LLMs) and syncs Master Resume from Drive.</div>
    <div class="stage-body">
      <div class="data-row">
        <span>Candidate:</span>
        <strong style="color:#fff;">Mukil (AI / Full-Stack)</strong>
      </div>
      <div class="data-row">
        <span>Canonical Python:</span>
        <span class="tag tag-gold">⭐ 94% ATS Match</span>
      </div>
      <div class="data-row">
        <span>GitLab AI Engineer:</span>
        <span class="tag tag-green">⭐ 98% ATS Match</span>
      </div>
      <div class="data-row">
        <span>Canonical Go Containers:</span>
        <span class="tag tag-gold">⭐ 92% ATS Match</span>
      </div>
      <div class="data-row" style="background:rgba(59,130,246,0.12); border:1px solid rgba(59,130,246,0.3);">
        <span>Master Resume:</span>
        <strong style="color:#60a5fa;">Synced from Drive Vault</strong>
      </div>
    </div>
    <div class="connector-arrow">➔</div>
  </div>

  <!-- STAGE 3: AUTONOMOUS BROWSERPILOT (PLAYWRIGHT) -->
  <div class="stage-card" id="stage3">
    <div class="stage-header">
      <div class="stage-badge">3</div>
      <div class="stage-title">Autonomous Form Pilot</div>
    </div>
    <div class="stage-desc">Headless Playwright fills fields, solves questions via Gemini 3.6 Flash & selects React-Select dropdowns.</div>
    <div class="stage-body">
      <div class="data-row">
        <span>Browser Engine:</span>
        <span class="tag tag-cyan">Playwright Chromium</span>
      </div>
      <div class="data-row">
        <span>Personal Details:</span>
        <span style="color:#fff;">Mukilarasu S • 9080030538</span>
      </div>
      <div class="data-row">
        <span>Screening Solver:</span>
        <span class="tag tag-gold">Gemini 3.6 Flash</span>
      </div>
      <div class="data-row">
        <span>Dropdowns Handled:</span>
        <span style="color:#4ade80;">Country, Sponsorship, EEOC</span>
      </div>
      <div class="data-row" style="background:rgba(16,185,129,0.12); border:1px solid rgba(16,185,129,0.3);">
        <span>Resume Injected:</span>
        <strong style="color:#34d399;">Mukil_Master_Resume.pdf</strong>
      </div>
    </div>
    <div class="connector-arrow">➔</div>
  </div>

  <!-- STAGE 4: PROOF, CLOUD VAULT & TELEGRAM ALERT -->
  <div class="stage-card" id="stage4">
    <div class="stage-header">
      <div class="stage-badge">4</div>
      <div class="stage-title">Cloud Vault & Telegram</div>
    </div>
    <div class="stage-desc">Captures full-page proof screenshot, saves to Google Drive Master Vault & delivers photo receipt to Telegram.</div>
    <div class="stage-body">
      <div class="data-row">
        <span>Screenshot Receipt:</span>
        <span class="tag tag-cyan">Full-Page PNG Proof</span>
      </div>
      <div class="data-row">
        <span>Drive Master Vault:</span>
        <span style="color:#60a5fa;">Node 05 (05_Media_Proofs)</span>
      </div>
      <div class="data-row">
        <span>Telegram Alert:</span>
        <span class="tag tag-green">@mukil_jarvis_executive_bot</span>
      </div>
      <div class="data-row">
        <span>Photo Proof Sent:</span>
        <strong style="color:#fff;">Chat ID: 6233907249</strong>
      </div>
      <div class="data-row" style="background:rgba(245,158,11,0.15); border:1px solid #f59e0b;">
        <span>Application Status:</span>
        <strong style="color:#ffc84a;">100% SUBMITTED & VERIFIED</strong>
      </div>
    </div>
  </div>

</div>

<div class="footer">
  <div>⚡ FULLY AUTONOMOUS PLACEMENT PIPELINE • ZERO HUMAN TOUCH</div>
  <div style="color:#ffc84a;">POWERED BY ANTIGRAVITY JARVIS CORE</div>
</div>

<script>
  function activateStage(n) {
    for (let i = 1; i <= 4; i++) {
      const el = document.getElementById('stage' + i);
      if (i < n) {
        el.className = 'stage-card completed';
      } else if (i === n) {
        el.className = 'stage-card active';
      } else {
        el.className = 'stage-card';
      }
    }
  }
  window.activateStage = activateStage;
</script>
</body>
</html>
"""

with open(SHOWCASE_HTML, "w", encoding="utf-8") as f:
    f.write(html_code)

print(f"[+] Written showcase HTML: {SHOWCASE_HTML}")

OUTPUT_VIDEO = None

print("[*] Launching Playwright to record 60fps automated pipeline video...")
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        record_video_dir=str(VIDEOS_DIR),
        record_video_size={"width": 1280, "height": 720},
        viewport={"width": 1280, "height": 720}
    )
    page = context.new_page()
    page.goto(f"file:///{str(SHOWCASE_HTML).replace(os.sep, '/')}", wait_until="load")
    time.sleep(1)

    # Step 1: 9:00 AM Cron Trigger
    print("[1/4] Activating Stage 1: 09:00 AM Cron Trigger & Board Scanning...")
    page.evaluate("window.activateStage(1)")
    time.sleep(3)

    # Step 2: ATS Radar & Resume Sync
    print("[2/4] Activating Stage 2: ATS Matching & Resume Sync...")
    page.evaluate("window.activateStage(2)")
    time.sleep(3)

    # Step 3: Autonomous Form Pilot
    print("[3/4] Activating Stage 3: Autonomous BrowserPilot (Playwright + Gemini)...")
    page.evaluate("window.activateStage(3)")
    time.sleep(3.5)

    # Step 4: Verification Receipt, Cloud Vault & Telegram Alert
    print("[4/4] Activating Stage 4: Cloud Vault Sync & Telegram Delivery...")
    page.evaluate("window.activateStage(4)")
    time.sleep(4)

    page_video = page.video
    page.close()
    context.close()
    browser.close()

    OUTPUT_VIDEO = page_video.path()

print(f"\n[+] Video Flow Recorded! File: {OUTPUT_VIDEO}")
print(f"Size: {os.path.getsize(OUTPUT_VIDEO)} bytes")

# Dispatch to Telegram Chat
caption = (
    "🎥 <b>JARVIS 9:00 AM JOB AUTO-APPLY PIPELINE FLOW</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "⚡ <b>The 4 Automated Stages:</b>\n"
    "1️⃣ <b>09:00 AM Cron Trigger</b>: Windows Task Scheduler triggers <code>daily_fresher_job_dispatcher.py</code> automatically.\n"
    "2️⃣ <b>ATS Radar & Resume Sync</b>: Evaluates 50+ openings against Mukil's profile (>90% ATS) & syncs Master Resume from Drive.\n"
    "3️⃣ <b>Autonomous BrowserPilot</b>: Headless Playwright fills fields, solves screening questions via Gemini 3.6 Flash & selects dropdowns.\n"
    "4️⃣ <b>Cloud Vault & Telegram Alert</b>: Captures full-page proof screenshot, uploads to Drive Master Vault & pushes live receipt to your phone.\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "✅ <i>Mapla, daily 9:00 AM job apply automation video unga phone-ku vanthachu!</i> 🔥"
)

def send_video(token, chat_id, vid_path, caption):
    url = f"https://api.telegram.org/bot{token}/sendVideo"
    boundary = "----WebKitFormBoundaryJobFlow9999"
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
    body.extend(f'Content-Disposition: form-data; name="video"; filename="jarvis_9am_job_auto_apply_flow.webm"\r\n'.encode("utf-8"))
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
