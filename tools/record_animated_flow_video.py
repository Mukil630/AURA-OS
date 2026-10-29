"""
Create a 100% self-contained, smooth, cinematic 4-stage Animated Video Flow of SGC Billing v6.0.
Zero external library dependencies (no unpkg, no react CDN, no loading screen).
Pure HTML5 + CSS3 + Canvas animation.
Records directly to 60fps MP4/WebM via Playwright and delivers to Telegram!
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

ANIMATION_HTML = BASE_DIR / "storage" / "sgc_animated_flow.html"

html_code = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>SGC Billing Automation Flow</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body {
    background: #07090e;
    color: #ede5d0;
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    width: 100vw;
    height: 100vh;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }
  .header {
    height: 60px;
    background: #0d111a;
    border-bottom: 1.5px solid rgba(255,200,74,0.25);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 32px;
  }
  .title {
    font-size: 18px;
    font-weight: 800;
    letter-spacing: 1px;
    color: #ffc84a;
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .badge {
    background: rgba(34,197,94,0.15);
    border: 1px solid #22c55e;
    color: #4ade80;
    font-size: 11px;
    font-weight: 700;
    padding: 4px 12px;
    border-radius: 20px;
  }
  .stage-container {
    flex: 1;
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 20px;
    padding: 32px;
    align-items: stretch;
  }
  .step-card {
    background: rgba(15,23,42,0.6);
    border: 1.5px solid rgba(255,255,255,0.1);
    border-radius: 16px;
    padding: 24px;
    display: flex;
    flex-direction: column;
    position: relative;
    transition: all 0.6s cubic-bezier(0.16, 1, 0.3, 1);
    opacity: 0.35;
    transform: translateY(12px);
  }
  .step-card.active {
    opacity: 1;
    transform: translateY(0);
    border-color: #ffc84a;
    box-shadow: 0 0 30px rgba(255,200,74,0.25);
    background: rgba(20,29,50,0.85);
  }
  .step-num {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: rgba(255,255,255,0.1);
    color: #aaa;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 800;
    font-size: 14px;
    margin-bottom: 16px;
    transition: all 0.4s;
  }
  .step-card.active .step-num {
    background: #ffc84a;
    color: #111;
  }
  .step-title {
    font-size: 15px;
    font-weight: 800;
    color: #fff;
    margin-bottom: 8px;
    letter-spacing: 0.5px;
  }
  .step-desc {
    font-size: 12px;
    color: #94a3b8;
    line-height: 1.5;
    margin-bottom: 18px;
  }
  .step-preview {
    flex: 1;
    background: #090c14;
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px;
    padding: 14px;
    font-size: 11.5px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    overflow: hidden;
  }
  .highlight-row {
    display: flex;
    justify-content: space-between;
    padding: 6px 8px;
    background: rgba(255,255,255,0.03);
    border-radius: 6px;
  }
  .pill {
    display: inline-block;
    padding: 3px 8px;
    border-radius: 4px;
    font-size: 10px;
    font-weight: 700;
  }
  .pill-blue { background: rgba(59,130,246,0.2); color: #60a5fa; }
  .pill-gold { background: rgba(255,200,74,0.2); color: #ffc84a; }
  .pill-green { background: rgba(34,197,94,0.2); color: #4ade80; }
  
  .connector-arrow {
    position: absolute;
    right: -14px;
    top: 50%;
    transform: translateY(-50%);
    font-size: 18px;
    color: #ffc84a;
    z-index: 10;
    opacity: 0.4;
    transition: opacity 0.5s;
  }
  .step-card.active .connector-arrow {
    opacity: 1;
    text-shadow: 0 0 10px #ffc84a;
  }
  .footer-status {
    height: 48px;
    background: #0a0d14;
    border-top: 1px solid rgba(255,255,255,0.08);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 32px;
    font-size: 12px;
    color: #888;
  }
</style>
</head>
<body>

<div class="header">
  <div class="title">
    <span>⚡</span> SRI GANAPATHI COLOURS — AUTOMATION PIPELINE FLOW
  </div>
  <div class="badge">LIVE ENTERPRISE ARCHITECTURE</div>
</div>

<div class="stage-container">
  
  <!-- Step 1: Invoice Creation -->
  <div class="step-card" id="step1">
    <div class="step-num">1</div>
    <div class="step-title">Invoice Creation & GST Math</div>
    <div class="step-desc">User enters yarn variety & weight. Real-time engine computes CGST & SGST instantly.</div>
    <div class="step-preview">
      <div class="highlight-row">
        <span>Party:</span>
        <strong style="color:#fff;">SRI GANAPATHI COLOURS</strong>
      </div>
      <div class="highlight-row">
        <span>Variety:</span>
        <span style="color:#60a5fa;">Red 2/10s Cotton</span>
      </div>
      <div class="highlight-row">
        <span>Subtotal:</span>
        <strong style="color:#ffc84a;">₹7,600.00</strong>
      </div>
      <div class="highlight-row">
        <span>CGST (2.5%):</span>
        <span style="color:#60a5fa;">₹190.00</span>
      </div>
      <div class="highlight-row">
        <span>SGST (2.5%):</span>
        <span style="color:#38bdf8;">₹190.00</span>
      </div>
      <div class="highlight-row" style="background:rgba(34,197,94,0.1); border:1px solid rgba(34,197,94,0.3);">
        <span>Net Total:</span>
        <strong style="color:#4ade80;">₹7,980.00</strong>
      </div>
    </div>
    <div class="connector-arrow">➔</div>
  </div>

  <!-- Step 2: Autonomous Cloud Sorting -->
  <div class="step-card" id="step2">
    <div class="step-num">2</div>
    <div class="step-title">Drive Month Allocation</div>
    <div class="step-desc">Google Drive API dynamically inspects the bill date & routes PDF into dedicated month subfolders.</div>
    <div class="step-preview">
      <div style="font-size:11px; color:#888;">📁 Master Bills Vault (<code>11KMBP...</code>)</div>
      <div class="highlight-row">
        <span>📂 2026-05</span>
        <span class="pill pill-blue">1 Bill</span>
      </div>
      <div class="highlight-row">
        <span>📂 2026-07</span>
        <span class="pill pill-blue">5 Bills</span>
      </div>
      <div class="highlight-row">
        <span>📂 2026-08</span>
        <span class="pill pill-blue">2 Bills</span>
      </div>
      <div class="highlight-row" style="background:rgba(255,200,74,0.15); border:1px solid #ffc84a;">
        <span>📂 2026-09 (Sep)</span>
        <span class="pill pill-gold">Active Upload</span>
      </div>
      <div style="font-size:10px; color:#4ade80; text-align:center; margin-top:4px;">
        ✔ Zero local disk waste • 100% Cloud Mesh
      </div>
    </div>
    <div class="connector-arrow">➔</div>
  </div>

  <!-- Step 3: Monthly GST Radar -->
  <div class="step-card" id="step3">
    <div class="step-num">3</div>
    <div class="step-title">Monthly GST Radar</div>
    <div class="step-desc">Month-end totalizer aggregates all CGST & SGST across bills and formats for CA / Auditor filing.</div>
    <div class="step-preview">
      <div class="highlight-row">
        <span>Period:</span>
        <strong style="color:#fff;">September 2026</strong>
      </div>
      <div class="highlight-row">
        <span>Total Bills:</span>
        <span>2 Invoices (#9, #10)</span>
      </div>
      <div class="highlight-row">
        <span>Total CGST:</span>
        <strong style="color:#60a5fa;">₹380.00</strong>
      </div>
      <div class="highlight-row">
        <span>Total SGST:</span>
        <strong style="color:#38bdf8;">₹380.00</strong>
      </div>
      <div class="highlight-row" style="background:rgba(255,200,74,0.15); border:1px solid #ffc84a;">
        <span>TOTAL GST:</span>
        <strong style="color:#ffc84a;">₹760.00</strong>
      </div>
      <div style="display:flex; gap:6px; margin-top:4px;">
        <span class="pill pill-green">📄 GSTR-1 CSV</span>
        <span class="pill pill-gold">📋 CA Copy</span>
      </div>
    </div>
    <div class="connector-arrow">➔</div>
  </div>

  <!-- Step 4: Mobile Auditor Access -->
  <div class="step-card" id="step4">
    <div class="step-num">4</div>
    <div class="step-title">Telegram Mobile Control</div>
    <div class="step-desc">Control everything from mobile. Query /gst, export CSV, and forward summaries to Auditor with 1 click.</div>
    <div class="step-preview">
      <div style="background:#182533; border-radius:8px; padding:8px; font-size:11px;">
        <span style="color:#60a5fa; font-weight:700;">/gst</span> ➔ <i>Instant Response</i><br>
        <span style="color:#4ade80;">CGST: ₹380 | SGST: ₹380</span><br>
        <strong style="color:#ffc84a;">Total Tax: ₹760.00</strong>
      </div>
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:4px; margin-top:4px;">
        <div style="background:rgba(0,136,204,0.2); border:1px solid rgba(0,136,204,0.4); text-align:center; padding:4px; border-radius:4px; font-size:10px; color:#38bdf8;">
          📅 Last Month
        </div>
        <div style="background:rgba(0,136,204,0.2); border:1px solid rgba(0,136,204,0.4); text-align:center; padding:4px; border-radius:4px; font-size:10px; color:#38bdf8;">
          📄 Send CSV
        </div>
      </div>
      <div style="background:#25d366; color:#fff; text-align:center; padding:5px; border-radius:6px; font-weight:700; font-size:10px; margin-top:4px;">
        💬 1-Click WhatsApp CA Forward
      </div>
    </div>
  </div>

</div>

<div class="footer-status">
  <div>⚡ SGC BILLING V6.0 ENTERPRISE AUTOMATION ENGINE</div>
  <div style="color:#ffc84a;">POWERED BY ANTIGRAVITY JARVIS CORE</div>
</div>

<script>
  // Progressive lighting animation
  function activateStep(n) {
    document.querySelectorAll('.step-card').forEach((el, idx) => {
      if (idx < n) {
        el.classList.add('active');
      } else {
        el.classList.remove('active');
      }
    });
  }
  window.activateStep = activateStep;
</script>
</body>
</html>
"""

with open(ANIMATION_HTML, "w", encoding="utf-8") as f:
    f.write(html_code)

print(f"[+] Written self-contained animated flow HTML: {ANIMATION_HTML}")

OUTPUT_VIDEO = None

print("[*] Recording 60fps cinematic flow video with Playwright...")
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        record_video_dir=str(VIDEOS_DIR),
        record_video_size={"width": 1280, "height": 720},
        viewport={"width": 1280, "height": 720}
    )
    page = context.new_page()
    page.goto(f"file:///{str(ANIMATION_HTML).replace(os.sep, '/')}", wait_until="load")
    time.sleep(1)

    # Step 1: Activate Step 1
    print("[1/4] Activating Stage 1: Invoice Creation...")
    page.evaluate("window.activateStep(1)")
    time.sleep(2.5)

    # Step 2: Activate Step 2
    print("[2/4] Activating Stage 2: Drive Month Allocation...")
    page.evaluate("window.activateStep(2)")
    time.sleep(2.5)

    # Step 3: Activate Step 3
    print("[3/4] Activating Stage 3: Monthly GST Radar...")
    page.evaluate("window.activateStep(3)")
    time.sleep(2.5)

    # Step 4: Activate Step 4
    print("[4/4] Activating Stage 4: Telegram Mobile Control...")
    page.evaluate("window.activateStep(4)")
    time.sleep(4)

    page_video = page.video
    page.close()
    context.close()
    browser.close()

    OUTPUT_VIDEO = page_video.path()

print(f"\n[+] Video Flow Recorded! File: {OUTPUT_VIDEO}")
print(f"Size: {os.path.getsize(OUTPUT_VIDEO)} bytes")

# Send Video to Telegram
caption = (
    "🎥 <b>SGC BILLING v6.0 — ANIMATED 4-STAGE AUTOMATION FLOW VIDEO</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "⚡ <b>The 4 Automated Stages:</b>\n"
    "1️⃣ <b>Invoice Creation & Dynamic GST</b>: Instant CGST 2.5% & SGST 2.5% math.\n"
    "2️⃣ <b>Autonomous Cloud Sorting</b>: Auto-sorted into Google Drive month folders (<code>2026-05</code>, <code>2026-07</code>, <code>2026-08</code>, <code>2026-09</code>).\n"
    "3️⃣ <b>Monthly GST Radar</b>: Tax totalizer with GSTR-1 CSV export.\n"
    "4️⃣ <b>Telegram Mobile Control</b>: <code>/gst</code> command + 1-click WhatsApp CA forward.\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "✅ <i>Mapla, animated automation flow video unga phone-ku vanthachu!</i> 🔥"
)

def send_video(token, chat_id, vid_path, caption):
    url = f"https://api.telegram.org/bot{token}/sendVideo"
    boundary = "----WebKitFormBoundaryAnimFlow8899"
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
    body.extend(f'Content-Disposition: form-data; name="video"; filename="sgc_automation_flow_demo.webm"\r\n'.encode("utf-8"))
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
