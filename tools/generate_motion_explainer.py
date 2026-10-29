"""
AURA-OS Clean 2D Motion Graphics Explainer Video Generator.
ByteByteGo / Stripe / Fireship style modern visual storytelling.
Synchronized 60fps Playwright capture + Edge-TTS Christopher Neural voice.
"""

import os
import sys
import time
import shutil
import asyncio
import subprocess
from pathlib import Path
import httpx
from playwright.sync_api import sync_playwright
import imageio_ffmpeg

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = Path(r"C:\Users\mukil\jarvis-core")
VIDEOS_DIR = BASE_DIR / "storage" / "videos"
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

HTML_PATH = BASE_DIR / "storage" / "motion_explainer.html"
AUDIO_PATH = VIDEOS_DIR / "motion_vo.mp3"
RAW_VIDEO = VIDEOS_DIR / "temp_motion_raw.webm"
FINAL_MP4 = Path(r"C:\Users\mukil\Desktop\AURA_OS_2D_Motion_Graphics_Explainer.mp4")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = "6233907249"

HTML_CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>AURA-OS 2D Motion Graphics Explainer</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body {
    background: #080c14;
    color: #f1f5f9;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    width: 1280px;
    height: 720px;
    overflow: hidden;
    position: relative;
    user-select: none;
  }

  /* Ambient Geometric Background */
  .bg-canvas {
    position: absolute;
    inset: 0;
    z-index: 1;
    background: radial-gradient(circle at 50% 50%, rgba(20, 35, 65, 0.5) 0%, rgba(8, 12, 20, 1) 75%);
  }

  /* Header Branding */
  .top-nav {
    position: absolute;
    top: 24px;
    left: 40px;
    right: 40px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    z-index: 10;
  }
  .brand-group {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .brand-icon {
    width: 36px;
    height: 36px;
    border-radius: 10px;
    background: linear-gradient(135deg, #00e5ff, #3b82f6);
    display: flex;
    align-items: center;
    justify-content: center;
    color: #080c14;
    font-weight: 900;
    font-size: 16px;
    box-shadow: 0 0 20px rgba(0, 229, 255, 0.4);
  }
  .brand-text {
    font-size: 18px;
    font-weight: 800;
    letter-spacing: 0.5px;
    color: #ffffff;
  }
  .brand-tag {
    font-size: 11px;
    font-weight: 700;
    color: #38bdf8;
    background: rgba(56, 189, 248, 0.12);
    border: 1px solid rgba(56, 189, 248, 0.3);
    padding: 4px 12px;
    border-radius: 20px;
    text-transform: uppercase;
    letter-spacing: 1px;
  }

  /* Scene Container */
  .stage-viewport {
    position: absolute;
    inset: 80px 40px 40px 40px;
    z-index: 5;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .scene {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    opacity: 0;
    transform: scale(0.95) translateY(20px);
    transition: all 0.7s cubic-bezier(0.16, 1, 0.3, 1);
    pointer-events: none;
  }
  .scene.active {
    opacity: 1;
    transform: scale(1) translateY(0);
    pointer-events: auto;
  }

  /* Titles */
  .scene-pill {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    font-weight: 800;
    color: #00e5ff;
    background: rgba(0, 229, 255, 0.1);
    border: 1px solid rgba(0, 229, 255, 0.3);
    padding: 6px 16px;
    border-radius: 30px;
    margin-bottom: 14px;
    text-transform: uppercase;
    letter-spacing: 1.5px;
  }
  .scene-headline {
    font-size: 34px;
    font-weight: 800;
    color: #ffffff;
    margin-bottom: 30px;
    text-align: center;
    letter-spacing: -0.5px;
  }

  /* SCENE 1: Phone & Speech */
  .phone-mockup {
    width: 240px;
    height: 380px;
    background: #0f172a;
    border: 3px solid rgba(255, 255, 255, 0.2);
    border-radius: 36px;
    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7), 0 0 30px rgba(0, 229, 255, 0.2);
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 20px 16px;
    position: relative;
    animation: floatPhone 4s ease-in-out infinite alternate;
  }
  @keyframes floatPhone {
    0% { transform: translateY(0); }
    100% { transform: translateY(-10px); }
  }
  .phone-speaker {
    width: 50px;
    height: 4px;
    background: rgba(255, 255, 255, 0.3);
    border-radius: 4px;
    margin-bottom: 24px;
  }
  .waveform-container {
    display: flex;
    align-items: center;
    gap: 4px;
    height: 40px;
    margin-bottom: 20px;
  }
  .wave-bar {
    width: 4px;
    background: #00e5ff;
    border-radius: 4px;
    animation: waveAnim 1s ease-in-out infinite alternate;
  }
  .wave-bar:nth-child(1) { height: 12px; animation-delay: 0.1s; }
  .wave-bar:nth-child(2) { height: 26px; animation-delay: 0.3s; }
  .wave-bar:nth-child(3) { height: 38px; animation-delay: 0.2s; }
  .wave-bar:nth-child(4) { height: 18px; animation-delay: 0.4s; }
  .wave-bar:nth-child(5) { height: 32px; animation-delay: 0.15s; }
  .wave-bar:nth-child(6) { height: 14px; animation-delay: 0.25s; }
  @keyframes waveAnim {
    0% { transform: scaleY(0.4); opacity: 0.4; }
    100% { transform: scaleY(1.2); opacity: 1; }
  }

  .speech-card {
    position: absolute;
    right: -240px;
    top: 90px;
    width: 290px;
    background: rgba(30, 41, 59, 0.95);
    border: 1.5px solid rgba(0, 229, 255, 0.4);
    border-radius: 18px;
    padding: 16px;
    box-shadow: 0 15px 30px rgba(0, 0, 0, 0.5);
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .speech-tag {
    font-size: 10px;
    font-weight: 800;
    color: #38bdf8;
    text-transform: uppercase;
    letter-spacing: 1px;
  }
  .speech-text {
    font-size: 13px;
    font-weight: 600;
    color: #ffffff;
    line-height: 1.45;
  }

  /* SCENE 2: The Data Envelope & Bus */
  .packet-flow-container {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 860px;
    position: relative;
  }
  .circuit-cable {
    position: absolute;
    top: 50%;
    left: 40px;
    right: 40px;
    height: 4px;
    background: rgba(255, 255, 255, 0.1);
    transform: translateY(-50%);
    z-index: 1;
  }
  .circuit-cable-active {
    position: absolute;
    top: 50%;
    left: 40px;
    width: 60%;
    height: 4px;
    background: linear-gradient(90deg, #00e5ff, #facc15);
    transform: translateY(-50%);
    z-index: 2;
    box-shadow: 0 0 15px #00e5ff;
  }
  .packet-box {
    background: rgba(15, 23, 42, 0.95);
    border: 2px solid #facc15;
    border-radius: 16px;
    padding: 18px 24px;
    box-shadow: 0 0 30px rgba(250, 204, 21, 0.35);
    z-index: 5;
    display: flex;
    align-items: center;
    gap: 16px;
    animation: glideIn 2s ease-in-out infinite alternate;
  }
  @keyframes glideIn {
    0% { transform: translateY(-4px); }
    100% { transform: translateY(4px); }
  }
  .envelope-icon {
    font-size: 32px;
  }
  .envelope-details {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .env-title { font-size: 14px; font-weight: 800; color: #fff; }
  .env-badges {
    display: flex;
    gap: 6px;
  }
  .mini-badge {
    font-size: 9px;
    font-weight: 700;
    padding: 2px 6px;
    border-radius: 6px;
    background: rgba(34, 197, 94, 0.2);
    border: 1px solid #22c55e;
    color: #4ade80;
  }

  /* SCENE 3: Brain Cognitive Core */
  .brain-center {
    width: 130px;
    height: 130px;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(168, 85, 247, 0.3) 0%, rgba(15, 23, 42, 0.9) 70%);
    border: 2px solid #a855f7;
    box-shadow: 0 0 40px rgba(168, 85, 247, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 54px;
    margin-bottom: 24px;
    position: relative;
    animation: pulseBrain 2.5s infinite alternate;
  }
  @keyframes pulseBrain {
    0% { transform: scale(0.96); box-shadow: 0 0 25px rgba(168, 85, 247, 0.4); }
    100% { transform: scale(1.05); box-shadow: 0 0 50px rgba(168, 85, 247, 0.8); }
  }
  .brain-cards-row {
    display: flex;
    gap: 24px;
    width: 780px;
  }
  .glass-card {
    flex: 1;
    background: rgba(15, 23, 42, 0.85);
    border: 1.5px solid rgba(255, 255, 255, 0.12);
    border-radius: 16px;
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 10px;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
  }
  .gc-header {
    font-size: 13px;
    font-weight: 800;
    color: #facc15;
    display: flex;
    align-items: center;
    gap: 8px;
    text-transform: uppercase;
  }
  .gc-body {
    font-size: 13px;
    color: #cbd5e1;
    line-height: 1.5;
  }

  /* SCENE 4: Split Dual Execution */
  .split-execution-row {
    display: flex;
    gap: 36px;
    width: 900px;
  }
  .dest-card {
    flex: 1;
    background: rgba(15, 23, 42, 0.9);
    border: 2px solid rgba(255, 255, 255, 0.12);
    border-radius: 20px;
    padding: 24px;
    display: flex;
    flex-direction: column;
    box-shadow: 0 20px 40px rgba(0, 0, 0, 0.5);
    position: relative;
    overflow: hidden;
  }
  .dest-card.github { border-color: rgba(34, 197, 94, 0.5); }
  .dest-card.linkedin { border-color: rgba(59, 130, 246, 0.5); }
  
  .card-top {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 16px;
  }
  .card-icon-box {
    width: 44px;
    height: 44px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 22px;
  }
  .card-icon-box.gh { background: #24292e; color: #fff; }
  .card-icon-box.li { background: #0077b5; color: #fff; }
  .card-head-text { font-size: 16px; font-weight: 800; color: #fff; }

  .dest-terminal {
    background: #030712;
    border: 1px solid #1e293b;
    border-radius: 10px;
    padding: 12px;
    font-family: 'Consolas', monospace;
    font-size: 12px;
    color: #38bdf8;
    line-height: 1.5;
    margin-bottom: 16px;
  }
  .check-banner {
    background: rgba(34, 197, 94, 0.15);
    border: 1.5px solid #22c55e;
    color: #4ade80;
    font-size: 12px;
    font-weight: 800;
    padding: 8px 14px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: auto;
  }

  /* SCENE 5: Observation Loop */
  .observation-box {
    width: 720px;
    background: rgba(15, 23, 42, 0.95);
    border: 2px solid #22c55e;
    border-radius: 20px;
    padding: 28px;
    box-shadow: 0 0 50px rgba(34, 197, 94, 0.25);
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
  }
  .shield-icon {
    font-size: 50px;
    margin-bottom: 12px;
  }
  .obs-title {
    font-size: 22px;
    font-weight: 800;
    color: #4ade80;
    margin-bottom: 8px;
  }
  .obs-desc {
    font-size: 14px;
    color: #94a3b8;
    margin-bottom: 20px;
    max-width: 500px;
  }
  .obs-checklist {
    display: flex;
    gap: 16px;
    width: 100%;
  }
  .obs-pill {
    flex: 1;
    background: rgba(30, 41, 59, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.1);
    padding: 10px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 700;
    color: #e2e8f0;
  }

  /* SCENE 6: Notification Ding */
  .phone-alert-card {
    width: 320px;
    background: rgba(15, 23, 42, 0.95);
    border: 2px solid #00e5ff;
    border-radius: 20px;
    padding: 20px;
    box-shadow: 0 0 40px rgba(0, 229, 255, 0.4);
    display: flex;
    flex-direction: column;
    gap: 10px;
    animation: popDing 0.5s cubic-bezier(0.175, 0.885, 0.32, 1.275);
  }
  @keyframes popDing {
    0% { transform: scale(0.8); opacity: 0; }
    100% { transform: scale(1); opacity: 1; }
  }
  .notif-top {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .notif-app { font-size: 13px; font-weight: 800; color: #00e5ff; }
  .notif-msg { font-size: 14px; font-weight: 600; color: #fff; line-height: 1.4; }

</style>
</head>
<body>

<div class="bg-canvas"></div>

<!-- Top Branding -->
<div class="top-nav">
  <div class="brand-group">
    <div class="brand-icon">&#9670;</div>
    <div class="brand-text">AURA-OS <span style="font-weight:300; color:#00e5ff;">EXPLAINER</span></div>
  </div>
  <div class="brand-tag">Autonomous Agent Data-Flow</div>
</div>

<!-- Main Animated Stages -->
<div class="stage-viewport">

  <!-- SCENE 1: The Trigger (0s - 13s) -->
  <div class="scene" id="scene-0">
    <div class="scene-pill">&#128241; Stage 1: Ingress &amp; Voice Trigger</div>
    <div class="scene-headline">It Starts With a Natural Spoken Command</div>
    
    <div class="phone-mockup">
      <div class="phone-speaker"></div>
      <div style="font-size: 28px; margin-bottom: 8px;">&#127897;&#65039;</div>
      <div style="font-size: 12px; color: #94a3b8; font-weight: 700; margin-bottom: 16px;">LISTENING...</div>
      
      <div class="waveform-container">
        <div class="wave-bar"></div>
        <div class="wave-bar"></div>
        <div class="wave-bar"></div>
        <div class="wave-bar"></div>
        <div class="wave-bar"></div>
        <div class="wave-bar"></div>
      </div>

      <div class="speech-card">
        <div class="speech-tag">MUKIL (VOICE NOTE)</div>
        <div class="speech-text">"Jarvis, push our new billing fix to GitHub, and share the update on LinkedIn."</div>
      </div>
    </div>
  </div>

  <!-- SCENE 2: The Data Envelope (13s - 27s) -->
  <div class="scene" id="scene-1">
    <div class="scene-pill">&#9881;&#65039; Stage 2: Context Hydration</div>
    <div class="scene-headline">Audio Transcribed &amp; Packaged with Memory</div>

    <div class="packet-flow-container">
      <div class="circuit-cable"></div>
      <div class="circuit-cable-active"></div>

      <div class="packet-box" style="margin: 0 auto;">
        <div class="envelope-icon">&#9993;&#65039;</div>
        <div class="envelope-details">
          <div class="env-title">NORMALIZED DATA ENVELOPE</div>
          <div style="font-size: 11px; color: #94a3b8;">User Payload + System Profile + Tool Schemas</div>
          <div class="env-badges">
            <span class="mini-badge">Whisper STT &lt; 190ms</span>
            <span class="mini-badge">Profile.json Hydrated</span>
            <span class="mini-badge">Turso Cloud Synced</span>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- SCENE 3: The Brain (27s - 43s) -->
  <div class="scene" id="scene-2">
    <div class="scene-pill">&#129504; Stage 3: The Cognitive Core</div>
    <div class="scene-headline">Evaluating Intent &amp; Selecting Tools</div>

    <div class="brain-center">&#129504;</div>

    <div class="brain-cards-row">
      <div class="glass-card">
        <div class="gc-header">&#128161; 1. Intent Recognition</div>
        <div class="gc-body">The model does NOT guess text. It analyzes the goal: <b>Code Deployment + Social Announcement</b>.</div>
      </div>
      <div class="glass-card" style="border-color: rgba(250, 204, 21, 0.4);">
        <div class="gc-header" style="color:#00e5ff;">&#128260; 2. Tool Selection</div>
        <div class="gc-body">Evaluates OpenAPI tool definitions. Selects <b>git_cli_push</b> and <b>linkedin_rest_api</b>.</div>
      </div>
    </div>
  </div>

  <!-- SCENE 4: Split Dual Execution (43s - 63s) -->
  <div class="scene" id="scene-3">
    <div class="scene-pill">&#9889; Stage 4: Dual Execution Pipeline</div>
    <div class="scene-headline">Parallel Execution on GitHub &amp; LinkedIn</div>

    <div class="split-execution-row">
      <!-- GitHub -->
      <div class="dest-card github">
        <div class="card-top">
          <div class="card-icon-box gh">&#128025;</div>
          <div class="card-head-text">GitHub Engine</div>
        </div>
        <div class="dest-terminal">
$ git add .
$ git commit -m "fix(billing): unify SGC access"
$ git push origin main
        </div>
        <div class="check-banner">&#10004; PUSHED TO REPO (Commit 9f3a1b0)</div>
      </div>

      <!-- LinkedIn -->
      <div class="dest-card linkedin">
        <div class="card-top">
          <div class="card-icon-box li">in</div>
          <div class="card-head-text">LinkedIn Agent</div>
        </div>
        <div class="dest-terminal" style="color: #cbd5e1; font-size:11px;">
POST /v2/ugcPosts (Status: 201)
"🚀 Shipped a core billing fix! #Python #DevOps"
        </div>
        <div class="check-banner" style="border-color:#3b82f6; color:#60a5fa; background:rgba(59,130,246,0.15);">&#10004; PUBLISHED LIVE VIA API</div>
      </div>
    </div>
  </div>

  <!-- SCENE 5: The Observation Feedback Loop (63s - 75s) -->
  <div class="scene" id="scene-4">
    <div class="scene-pill">&#128260; Stage 5: Observation Loop</div>
    <div class="scene-headline">Real Execution Results Return to Brain</div>

    <div class="observation-box">
      <div class="shield-icon">&#128737;&#65039;</div>
      <div class="obs-title">ZERO-HALLUCINATION VERIFICATION</div>
      <div class="obs-desc">The real terminal stdout and HTTP status codes are injected back into the LLM context window to confirm success before answering.</div>
      <div class="obs-checklist">
        <div class="obs-pill">&#10004; Git Remote: 200 OK</div>
        <div class="obs-pill">&#10004; LinkedIn Post: 201 Created</div>
        <div class="obs-pill">&#10004; 250GB Mesh: Synced</div>
      </div>
    </div>
  </div>

  <!-- SCENE 6: Final Phone Alert (75s - 85s) -->
  <div class="scene" id="scene-5">
    <div class="scene-pill">&#128276; Stage 6: Completion</div>
    <div class="scene-headline">Verified Telemetry Delivered to Phone</div>

    <div class="phone-alert-card">
      <div class="notif-top">
        <div style="font-size:20px;">&#129302;</div>
        <div class="notif-app">JARVIS Prime &bull; Just now</div>
      </div>
      <div class="notif-msg">
        "Mission accomplished, Boss! 🔥<br>Code pushed to GitHub (9f3a1b0) &amp; update is live on LinkedIn."
      </div>
      <div style="font-size: 11px; color:#4ade80; font-weight:700;">
        &#10004; State committed to memory.
      </div>
    </div>
  </div>

</div>

<script>
  window.goToScene = function(idx) {
    for (let i = 0; i <= 5; i++) {
      const el = document.getElementById('scene-' + i);
      if (el) {
        if (i === idx) el.classList.add('active');
        else el.classList.remove('active');
      }
    }
  };
  // Default to initial scene
  window.goToScene(0);
</script>
</body>
</html>
"""

def write_html():
    print("[1/4] Writing clean 2D motion graphics HTML explainer...")
    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(HTML_CONTENT)
    print(f"  [+] HTML saved to {HTML_PATH}")

def record_motion():
    print("[2/4] Recording 60fps clean motion graphics with Playwright...")
    # Narration duration: ~84.6 seconds
    # Scene 0: 0s - 13s (13s)
    # Scene 1: 13s - 27s (14s)
    # Scene 2: 27s - 43s (16s)
    # Scene 3: 43s - 63s (20s)
    # Scene 4: 63s - 75s (12s)
    # Scene 5: 75s - 85s (10s)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            record_video_dir=str(VIDEOS_DIR),
            record_video_size={"width": 1280, "height": 720},
            viewport={"width": 1280, "height": 720}
        )
        page = context.new_page()
        page.goto(f"file:///{str(HTML_PATH).replace(os.sep, '/')}", wait_until="networkidle")
        time.sleep(1)

        print("    -> Scene 0: Phone & Voice Trigger (13s)...")
        page.evaluate("window.goToScene(0)")
        time.sleep(13)

        print("    -> Scene 1: Data Envelope & Context Hydration (14s)...")
        page.evaluate("window.goToScene(1)")
        time.sleep(14)

        print("    -> Scene 2: Cognitive Brain Reasoning (16s)...")
        page.evaluate("window.goToScene(2)")
        time.sleep(16)

        print("    -> Scene 3: Dual Execution: GitHub & LinkedIn (20s)...")
        page.evaluate("window.goToScene(3)")
        time.sleep(20)

        print("    -> Scene 4: Observation Feedback Loop (12s)...")
        page.evaluate("window.goToScene(4)")
        time.sleep(12)

        print("    -> Scene 5: Verified Phone Notification (10s)...")
        page.evaluate("window.goToScene(5)")
        time.sleep(10)

        context.close()
        video_path = page.video.path()
        browser.close()

    print(f"  [+] Raw video saved: {video_path}")
    if os.path.exists(RAW_VIDEO):
        os.remove(RAW_VIDEO)
    shutil.move(video_path, str(RAW_VIDEO))

def merge_video_audio():
    print("[3/4] Merging 2D motion video + voiceover with FFmpeg into MP4...")
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    if os.path.exists(FINAL_MP4):
        try:
            os.remove(FINAL_MP4)
        except Exception:
            pass

    cmd = [
        ffmpeg_exe,
        "-y",
        "-i", str(RAW_VIDEO),
        "-i", str(AUDIO_PATH),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "fast",
        "-crf", "18",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        str(FINAL_MP4)
    ]
    subprocess.run(cmd, check=True)
    print(f"  [+] FINAL MP4 CREATED: {FINAL_MP4} ({os.path.getsize(FINAL_MP4) / (1024*1024):.2f} MB)")

def dispatch_telegram():
    print("[4/4] Sending completed 2D Motion Graphics explainer to Mukil's Telegram...")
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo"
    caption = (
        "🎨 *AURA-OS | 2D MOTION GRAPHICS EXPLAINER VIDEO READY!*\n\n"
        "✨ *Style*: ByteByteGo / Stripe Clean 2D Visual Storytelling\n"
        "📱 *Scene Flow*:\n"
        "1. Spoken Voice Command from Phone\n"
        "2. Data Packetization & Memory Hydration\n"
        "3. Cognitive Brain: Intent & Tool Selection\n"
        "4. Parallel Execution: GitHub Commit & LinkedIn Post\n"
        "5. Observation Feedback Loop (Zero-Hallucination)\n"
        "6. Verified Phone Alert: 'Mission accomplished, Boss!'\n\n"
        "📁 Saved to Desktop: `AURA_OS_2D_Motion_Graphics_Explainer.mp4`"
    )
    with open(FINAL_MP4, "rb") as f:
        resp = httpx.post(url, data={"chat_id": CHAT_ID, "caption": caption, "parse_mode": "Markdown"}, files={"video": (FINAL_MP4.name, f, "video/mp4")}, timeout=120.0)
        print("  [+] Telegram Dispatch Status:", resp.status_code)

def main():
    start = time.time()
    write_html()
    record_motion()
    merge_video_audio()
    dispatch_telegram()
    elapsed = time.time() - start
    print(f"\n==========================================")
    print(f"🔥 MOTION EXPLAINER COMPLETE IN {elapsed:.1f} SECONDS!")
    print(f"Available on Desktop: {FINAL_MP4}")
    print(f"==========================================")

if __name__ == "__main__":
    main()
