"""
AURA OS Cloud Server & Web/PWA Gateway
FastAPI + WebSockets + Dual-Modal Voice & Text Interface (OLED Dark Stark Theme)
"""
import sys
import os
import json
import asyncio
from pathlib import Path
from typing import Set, Dict, Any, Optional
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests

from aura.tools.voice_tools import (
    synthesize_voice_file,
    VOICE_CACHE_DIR,
    clean_text_for_speech,
    CURRENT_ACTIVE_PERSONA
)
from aura.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, GEMINI_API_KEY

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from aura.kernel.agent import AuraAgent
from aura.tools.registry import registry
from aura.tools.reminders import get_and_purge_due_reminders, complete_task, list_active_reminders, get_daily_completed_tasks

IST = timezone(timedelta(hours=5, minutes=30))

active_websockets: Set[WebSocket] = set()
scheduler_running = False

async def background_scheduler():
    """
    Autonomous Proactive Scheduler Loop.
    Polls Turso Cloud DB for due reminders, auto-purges completed ones (0 MB bloat),
    broadcasts alarms to connected Web/Mobile clients, and dispatches:
    1. 06:00 AM / 09:00 AM Wakeup Briefing
    2. 02:00 PM Midday Nudge
    3. 10:00 PM EOD Retrospective
    """
    global scheduler_running
    scheduler_running = True
    print("[AURA SCHEDULER] ⏰ Autonomous Background Scheduler Loop STARTED (3-Stage Daily Routines + Push).")
    last_briefing_date = None
    last_midday_date = None
    last_eod_date = None

    while scheduler_running:
        try:
            now = datetime.now(IST)
            now_time = now.strftime("%H:%M")
            today_str = now.strftime("%Y-%m-%d")

            # 1. Check and fire due reminders from Turso Cloud
            due_items = get_and_purge_due_reminders()
            for r in due_items:
                alert_text = f"Mapla! Reminder alarm: {r['title']} (#{r['id']})"
                print(f"[AURA SCHEDULER] 🔔 ALARM TRIGGERED: #{r['id']} - {r['title']}")
                for ws in list(active_websockets):
                    try:
                        await ws.send_json({
                            "type": "alarm",
                            "title": "AURA EXECUTIVE ALARM",
                            "id": r["id"],
                            "content": f"⏰ **{r['title']}**\n\n• Trigger Time: `{r['remind_at']} IST`\n• Auto-purged from Turso Cloud (0 MB bloat)."
                        })
                    except Exception:
                        pass

            # 2. Daily 06:00 AM / 09:00 AM IST Morning Wakeup Call & Briefing Pilot
            if now_time in ["06:00", "09:00"] and last_briefing_date != today_str:
                last_briefing_date = today_str
                print(f"[AURA SCHEDULER] 🌅 Firing Autonomous Morning Pilot for {today_str} ({now_time} IST)...")
                try:
                    from aura.kernel.morning_intel_pilot import MorningIntelPilot
                    pilot = MorningIntelPilot()
                    res = await pilot.run_proactive_cycle()
                    briefing_script = res.get("script", "")
                    for ws in list(active_websockets):
                        try:
                            await ws.send_json({
                                "type": "alarm",
                                "title": "06:00 AM AUTONOMOUS WAKEUP BRIEFING",
                                "content": f"🌅 **Good Morning Boss Mukil!**\n\n{briefing_script}"
                            })
                        except Exception:
                            pass
                except Exception as ex:
                    print(f"[AURA SCHEDULER] Morning pilot error: {ex}")

            # 3. Daily 02:00 PM IST Midday Nudge (Progress on Morning Priorities)
            if now_time == "14:00" and last_midday_date != today_str:
                last_midday_date = today_str
                print(f"[AURA SCHEDULER] ☀️ Firing 02:00 PM Midday Nudge for {today_str}...")
                try:
                    from aura.kernel.morning_intel_pilot import MorningIntelPilot
                    pilot = MorningIntelPilot()
                    res = await pilot.run_midday_cycle()
                    midday_script = res.get("script", "")
                    for ws in list(active_websockets):
                        try:
                            await ws.send_json({
                                "type": "alarm",
                                "title": "02:00 PM MIDDAY PROGRESS CHECK",
                                "content": f"⚡ **Midday Status Check, Mapla!**\n\n{midday_script}"
                            })
                        except Exception:
                            pass
                except Exception as ex:
                    print(f"[AURA SCHEDULER] Midday pilot error: {ex}")

            # 4. Daily 10:00 PM IST EOD Retrospective (Day Wrap-Up & Storage Commit)
            if now_time == "22:00" and last_eod_date != today_str:
                last_eod_date = today_str
                print(f"[AURA SCHEDULER] 🌙 Firing 10:00 PM EOD Retrospective for {today_str}...")
                try:
                    from aura.kernel.morning_intel_pilot import MorningIntelPilot
                    pilot = MorningIntelPilot()
                    res = await pilot.run_eod_cycle()
                    eod_script = res.get("script", "")
                    for ws in list(active_websockets):
                        try:
                            await ws.send_json({
                                "type": "alarm",
                                "title": "10:00 PM EOD RETROSPECTIVE",
                                "content": f"🌙 **Day Wrap-Up, Boss Mukil!**\n\n{eod_script}"
                            })
                        except Exception:
                            pass
                except Exception as ex:
                    print(f"[AURA SCHEDULER] EOD retrospective error: {ex}")

        except Exception as e:
            print(f"[AURA SCHEDULER] Error in loop: {e}")

        await asyncio.sleep(15)

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(background_scheduler())
    yield
    global scheduler_running
    scheduler_running = False
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    print("[AURA SCHEDULER] 🛑 Scheduler loop stopped safely.")

app = FastAPI(title="AURA OS Cloud Gateway", version="3.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Cloud Mobile Calling Hub
from aura.kernel.call_hub import router as call_router
app.include_router(call_router)

class ChatRequest(BaseModel):
    prompt: str

@app.get("/health")
def health_check():
    return {
        "status": "ONLINE_24_7",
        "system": "AURA OS v3 // JARVIS Prime",
        "registered_tools_count": len(registry.get_schemas()),
        "tools": [s["function"]["name"] for s in registry.get_schemas()]
    }

@app.post("/api/chat")
def chat_endpoint(req: ChatRequest):
    agent = AuraAgent()
    events = []
    final_text = ""
    for event_type, content in agent.chat_stream(req.prompt):
        if event_type == "token":
            final_text += content
        else:
            events.append({"type": event_type, "content": content})
    return {"response": final_text, "events": events}

class TaskCompleteRequest(BaseModel):
    query: str

class PilotTriggerRequest(BaseModel):
    cycle: Optional[str] = "morning"  # "morning", "midday", "eod"

@app.get("/api/tasks/active")
def get_active_tasks_endpoint():
    return {"raw": list_active_reminders()}

@app.get("/api/tasks/completed")
def get_completed_tasks_endpoint():
    return {"completed": get_daily_completed_tasks()}

@app.post("/api/tasks/complete")
def complete_task_endpoint(req: TaskCompleteRequest):
    result = complete_task(req.query)
    return {"result": result}

@app.post("/api/pilot/trigger")
async def trigger_pilot_endpoint(req: PilotTriggerRequest):
    from aura.kernel.morning_intel_pilot import MorningIntelPilot
    pilot = MorningIntelPilot()
    cycle = (req.cycle or "morning").lower()
    if cycle == "midday":
        res = await pilot.run_midday_cycle()
    elif cycle == "eod":
        res = await pilot.run_eod_cycle()
    else:
        res = await pilot.run_proactive_cycle()
    return {"status": "SUCCESS", "cycle": cycle, "result": res}

class VoiceSynthesizeRequest(BaseModel):
    text: str
    persona: Optional[str] = "MORNING_WAKEUP"
    format: Optional[str] = "ogg"

@app.post("/api/voice/synthesize")
def synthesize_voice_endpoint(req: VoiceSynthesizeRequest):
    """Generates Gemini Native Audio (with brotherly Tony Stark Kongu dialect) for Web & Mobile."""
    out_file, mime = synthesize_voice_file(req.text, voice_persona=req.persona, preferred_format=req.format or "ogg")
    if out_file and out_file.exists():
        return {
            "status": "success",
            "filename": out_file.name,
            "audio_url": f"/api/voice/stream/{out_file.name}",
            "mime_type": mime,
            "size_bytes": out_file.stat().st_size
        }
    return JSONResponse(status_code=500, content={"status": "error", "message": "Voice synthesis failed."})

@app.get("/api/voice/stream/{filename}")
def stream_voice_endpoint(filename: str):
    """Streams cached voice audio to mobile devices and browsers."""
    file_path = VOICE_CACHE_DIR / filename
    if not file_path.exists():
        return JSONResponse(status_code=404, content={"error": "Audio file not found."})
    mime = "audio/ogg" if filename.endswith(".ogg") else ("audio/mpeg" if filename.endswith(".mp3") else "audio/wav")
    return FileResponse(file_path, media_type=mime)

class OrchestratorRequest(BaseModel):
    message: str
    user_id: Optional[str] = "mukil"
    channel: Optional[str] = "ANDROID_APP"

@app.post("/api/v1/orchestrator/process")
def process_orchestrator_endpoint(req: OrchestratorRequest):
    """
    Central Cognitive Orchestrator Endpoint for the Android VoiceAssistantApp.
    Executes AuraAgent, synthesizes Gemini Native Voice, and returns full structured response.
    """
    agent = AuraAgent()
    events = []
    final_text = ""
    for event_type, content in agent.chat_stream(req.message):
        if event_type == "token":
            final_text += content
        else:
            events.append({"type": event_type, "content": content})
    
    clean_reply = final_text.strip()
    speech_reply = clean_text_for_speech(clean_reply)
    
    # Generate Gemini Native Audio for phone playback
    out_file, _ = synthesize_voice_file(speech_reply, preferred_format="ogg")
    audio_url = f"/api/voice/stream/{out_file.name}" if out_file and out_file.exists() else None
    
    return {
        "success": True,
        "reply": clean_reply,
        "speech_reply": speech_reply,
        "audio_url": audio_url,
        "task_id": f"task_{int(datetime.now().timestamp()*1000)}",
        "intent": "CONVERSATIONAL_EXECUTIVE",
        "events": events
    }

@app.post("/api/v1/vision/analyze")
async def analyze_vision_endpoint(
    file: UploadFile = File(...),
    query: str = Form("Inspect this image and provide key insights."),
    channel: str = Form("ANDROID_CAMERA")
):
    """Multimodal Live Vision Endpoint for Android camera frames & documents."""
    try:
        contents = await file.read()
        from google import genai
        from google.genai import types
        
        client = genai.Client(api_key=GEMINI_API_KEY)
        res = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Part.from_bytes(data=contents, mime_type=file.content_type or "image/jpeg"),
                f"You are AURA OS Vision Copilot. Address Mukil in brotherly Tanglish/English. Analyze this image: {query}"
            ]
        )
        analysis_text = res.text or "Analysis completed successfully."
        speech_text = clean_text_for_speech(analysis_text)
        out_file, _ = synthesize_voice_file(speech_text, preferred_format="ogg")
        audio_url = f"/api/voice/stream/{out_file.name}" if out_file and out_file.exists() else None
        
        return {
            "success": True,
            "analysis": analysis_text,
            "speech_reply": speech_text,
            "audio_url": audio_url,
            "task_id": f"vis_{int(datetime.now().timestamp()*1000)}"
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "analysis": f"Vision error: {str(e)}", "speech_reply": "Vision error vandhuchu mapla."})

@app.get("/apk", tags=["APK"])
@app.get("/download-apk", tags=["APK"])
async def get_apk():
    candidates = [
        Path(__file__).parent.parent / "data" / "AURA_OS_VoiceAssistant.apk",
        Path("C:/Users/mukil/Desktop/AURA_OS_VoiceAssistant_Update.apk"),
        Path("C:/Users/mukil/Desktop/AURA-OS-VoiceAssistant-v2.2.apk"),
        Path("C:/Users/mukil/AndroidProjects/VoiceAssistantApp/app/build/outputs/apk/debug/app-debug.apk")
    ]
    for p in candidates:
        if p.exists():
            return FileResponse(str(p), media_type="application/vnd.android.package-archive", filename="AURA_OS_VoiceAssistant.apk")
    return HTMLResponse("<h1>APK not found on host</h1>", status_code=404)

@app.post("/api/telegram/webhook")
async def telegram_webhook_endpoint(request: Request):
    """
    24/7 Render Cloud Telegram Webhook for Mukil.
    Receives all Telegram requests, queries AuraAgent, sends text reply,
    and guarantees spoken Gemini Voice Note replay for EVERY message!
    """
    try:
        data = await request.json()
        message = data.get("message") or data.get("edited_message")
        if not message:
            return {"ok": True}
        
        chat_id = message.get("chat", {}).get("id")
        user_text = message.get("text", "")
        if not user_text:
            return {"ok": True}
        
        # Immediate voice recording indicator
        if TELEGRAM_BOT_TOKEN and chat_id:
            try:
                requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendChatAction",
                    json={"chat_id": chat_id, "action": "record_voice"},
                    timeout=5
                )
            except Exception:
                pass
        
        # Execute query through AuraAgent
        agent = AuraAgent()
        reply_text = ""
        for event_type, content in agent.chat_stream(user_text):
            if event_type == "token":
                reply_text += content
        
        if not reply_text:
            reply_text = "All systems operational, Boss Mukil."
        
        # 1. Send text reply
        if TELEGRAM_BOT_TOKEN and chat_id:
            try:
                requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                    json={"chat_id": chat_id, "text": reply_text, "parse_mode": "Markdown"},
                    timeout=15
                )
            except Exception:
                try:
                    requests.post(
                        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                        json={"chat_id": chat_id, "text": reply_text},
                        timeout=15
                    )
                except Exception:
                    pass
        
        # 2. Guaranteed Gemini Native Voice replay back to Mukil
        speech_text = clean_text_for_speech(reply_text)
        out_file, mime = synthesize_voice_file(speech_text, preferred_format="ogg")
        if out_file and out_file.exists() and TELEGRAM_BOT_TOKEN and chat_id:
            try:
                with open(out_file, "rb") as vf:
                    requests.post(
                        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVoice",
                        data={"chat_id": chat_id, "caption": "🎙️ AURA Spoken Voice"},
                        files={"voice": ("voice.ogg", vf, "audio/ogg")},
                        timeout=30
                    )
            except Exception as ve:
                print(f"[Telegram Webhook Voice Error] {ve}")
        
        return {"ok": True}
    except Exception as e:
        print(f"[Telegram Webhook Error] {e}")
        return {"ok": False, "error": str(e)}

@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    active_websockets.add(websocket)
    agent = AuraAgent()
    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            prompt = payload.get("prompt", "")
            if not prompt:
                continue
                
            for event_type, content in agent.chat_stream(prompt):
                await websocket.send_json({"type": event_type, "content": content})
            await websocket.send_json({"type": "done", "content": ""})
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "content": str(e)})
        except Exception:
            pass
    finally:
        active_websockets.discard(websocket)

@app.get("/", response_class=HTMLResponse)
def index_page():
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>AURA OS // Autonomous Executive Partner</title>
    <meta name="theme-color" content="#030712">
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Outfit:wght@300;400;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #030712;
            --surface: #0B132B;
            --surface-border: #1C2541;
            --cyan: #00F0FF;
            --cyan-glow: rgba(0, 240, 255, 0.35);
            --blue: #3A86FF;
            --amber: #FFB703;
            --green: #10B981;
            --pink: #F43F5E;
            --text-main: #F8FAFC;
            --text-muted: #94A3B8;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }
        body {
            background: var(--bg);
            color: var(--text-main);
            font-family: 'Outfit', -apple-system, sans-serif;
            height: 100vh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        header {
            padding: 14px 20px;
            background: rgba(11, 19, 43, 0.85);
            backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--surface-border);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .brand {
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .arc-mini {
            width: 30px;
            height: 30px;
            border-radius: 50%;
            border: 2px solid var(--cyan);
            box-shadow: 0 0 14px var(--cyan-glow);
            position: relative;
            animation: pulse-mini 2.5s infinite ease-in-out;
            cursor: pointer;
        }
        .arc-mini::after {
            content: '';
            position: absolute;
            inset: 7px;
            background: var(--cyan);
            border-radius: 50%;
            box-shadow: 0 0 8px var(--cyan);
        }
        @keyframes pulse-mini {
            0%, 100% { transform: scale(1); box-shadow: 0 0 12px var(--cyan-glow); }
            50% { transform: scale(1.08); box-shadow: 0 0 20px rgba(0, 240, 255, 0.6); }
        }
        .title h1 { font-size: 1.15rem; font-weight: 700; letter-spacing: 1px; color: var(--cyan); }
        .title p { font-size: 0.72rem; color: var(--text-muted); font-family: 'JetBrains Mono', monospace; }
        .header-controls {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .btn-toggle {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.7rem;
            padding: 5px 10px;
            border-radius: 20px;
            background: rgba(28, 37, 65, 0.8);
            color: var(--text-muted);
            border: 1px solid var(--surface-border);
            cursor: pointer;
            transition: all 0.2s;
        }
        .btn-toggle.active {
            background: rgba(0, 240, 255, 0.15);
            color: var(--cyan);
            border-color: var(--cyan);
            box-shadow: 0 0 10px var(--cyan-glow);
        }
        .badge {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.7rem;
            padding: 5px 10px;
            border-radius: 20px;
            background: rgba(16, 185, 129, 0.12);
            color: var(--green);
            border: 1px solid rgba(16, 185, 129, 0.35);
        }
        #chat-canvas {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 16px;
        }
        .msg {
            max-width: 88%;
            padding: 14px 18px;
            border-radius: 16px;
            font-size: 0.95rem;
            line-height: 1.55;
            word-wrap: break-word;
        }
        .msg.user {
            align-self: flex-end;
            background: linear-gradient(135deg, #1E3A8A, #2563EB);
            color: #FFFFFF;
            border-bottom-right-radius: 4px;
            box-shadow: 0 4px 14px rgba(37, 99, 235, 0.25);
        }
        .msg.agent {
            align-self: flex-start;
            background: var(--surface);
            border: 1px solid var(--surface-border);
            border-bottom-left-radius: 4px;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
        }
        .tool-banner {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.78rem;
            background: rgba(255, 183, 3, 0.08);
            border: 1px solid rgba(255, 183, 3, 0.35);
            color: var(--amber);
            padding: 8px 14px;
            border-radius: 8px;
            display: inline-block;
            margin-bottom: 6px;
            animation: fadeIn 0.3s ease;
        }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(-4px); } to { opacity: 1; transform: translateY(0); } }
        .action-chips {
            display: flex;
            gap: 8px;
            padding: 8px 20px;
            overflow-x: auto;
            scrollbar-width: none;
        }
        .action-chips::-webkit-scrollbar { display: none; }
        .chip {
            background: rgba(28, 37, 65, 0.7);
            border: 1px solid var(--surface-border);
            color: var(--text-muted);
            font-size: 0.8rem;
            padding: 6px 14px;
            border-radius: 20px;
            white-space: nowrap;
            cursor: pointer;
            transition: all 0.2s;
        }
        .chip:hover {
            color: var(--cyan);
            border-color: var(--cyan);
            background: rgba(0, 240, 255, 0.08);
        }
        footer {
            padding: 12px 20px 20px;
            background: rgba(11, 19, 43, 0.9);
            backdrop-filter: blur(14px);
            border-top: 1px solid var(--surface-border);
            display: flex;
            gap: 10px;
            align-items: center;
        }
        .input-box {
            flex: 1;
            background: rgba(3, 7, 18, 0.85);
            border: 1px solid var(--surface-border);
            border-radius: 24px;
            padding: 12px 20px;
            color: #FFF;
            font-family: 'Outfit', sans-serif;
            font-size: 0.95rem;
            outline: none;
            transition: all 0.2s;
        }
        .input-box:focus { border-color: var(--cyan); box-shadow: 0 0 12px var(--cyan-glow); }
        .btn-circle {
            width: 44px;
            height: 44px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            font-weight: 700;
            border: none;
            transition: transform 0.15s, box-shadow 0.2s;
        }
        .btn-circle:active { transform: scale(0.92); }
        .mic-btn {
            background: rgba(28, 37, 65, 0.9);
            color: var(--cyan);
            border: 1px solid var(--cyan);
            font-size: 1.1rem;
        }
        .mic-btn.recording {
            background: var(--pink);
            color: #FFF;
            border-color: var(--pink);
            box-shadow: 0 0 18px rgba(244, 63, 94, 0.7);
            animation: pulse-mic 1s infinite alternate;
        }
        @keyframes pulse-mic {
            0% { transform: scale(1); }
            100% { transform: scale(1.1); }
        }
        .send-btn {
            background: var(--cyan);
            color: #030712;
            box-shadow: 0 0 14px var(--cyan-glow);
            font-size: 1.1rem;
        }
        table {
            border-collapse: collapse;
            width: 100%;
            margin: 12px 0;
            font-size: 0.88rem;
        }
        th, td {
            border: 1px solid var(--surface-border);
            padding: 8px 12px;
            text-align: left;
        }
        th { background: rgba(0, 240, 255, 0.08); color: var(--cyan); }
        pre, code {
            font-family: 'JetBrains Mono', monospace;
            background: rgba(0,0,0,0.4);
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.85em;
        }
    </style>
</head>
<body>
    <header>
        <div class="brand">
            <div class="arc-mini" title="AURA Core"></div>
            <div class="title">
                <h1>AURA OS</h1>
                <p>MUKIL // JARVIS PRIME v3.1</p>
            </div>
        </div>
        <div class="header-controls">
            <button id="tts-toggle" class="btn-toggle" onclick="toggleTTS()">🔊 Audio: OFF</button>
            <div class="badge">ONLINE 24/7</div>
        </div>
    </header>

    <div id="chat-canvas">
        <div class="msg agent">
            Vaa mapla! 🤝 AURA OS Cognitive Engine live-ah ready-ah irukku.<br>
            Text mode-la prompt tharalaam, illana mic tap panni voice command kudukalaam! Enna task pannanum sollu, let's crack it! 🚀
        </div>
    </div>

    <div class="action-chips">
        <div class="chip" onclick="sendQuick('SGC pending bills evlo mapla?')">🧾 SGC Pending Bills</div>
        <div class="chip" onclick="sendQuick('This month October GST total evlo?')">📊 SGC GST Radar</div>
        <div class="chip" onclick="sendQuick('Master resume link eduthu kudu')">📄 Master Resume</div>
        <div class="chip" onclick="sendQuick('250GB Drive mesh status kaattu')">🌐 250GB Drive Mesh</div>
        <div class="chip" onclick="sendQuick('Enna custom tools create pannirukom list pannu')">⚡ List Custom Superpowers</div>
    </div>

    <footer>
        <input type="text" id="prompt-input" class="input-box" placeholder="Message AURA in Tanglish or English (or click mic)..." onkeypress="handleKey(event)">
        <button id="mic-btn" class="btn-circle mic-btn" title="Toggle Voice Recognition" onclick="toggleMic()">🎙️</button>
        <button class="btn-circle send-btn" title="Send" onclick="sendMessage()">➤</button>
    </footer>

    <script>
        const canvas = document.getElementById('chat-canvas');
        const input = document.getElementById('prompt-input');
        const micBtn = document.getElementById('mic-btn');
        const ttsBtn = document.getElementById('tts-toggle');
        
        let ttsEnabled = false;
        function toggleTTS() {
            ttsEnabled = !ttsEnabled;
            ttsBtn.className = ttsEnabled ? 'btn-toggle active' : 'btn-toggle';
            ttsBtn.innerText = ttsEnabled ? '🔊 Audio: ON' : '🔊 Audio: OFF';
        }

        // Web Speech Recognition setup
        let recognition = null;
        let isRecording = false;
        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
            recognition = new SpeechRec();
            recognition.continuous = false;
            recognition.interimResults = true;
            recognition.lang = 'en-IN';

            recognition.onstart = () => {
                isRecording = true;
                micBtn.classList.add('recording');
                input.placeholder = "Listening mapla... Speak now!";
            };

            recognition.onresult = (event) => {
                let transcript = '';
                for (let i = event.resultIndex; i < event.results.length; ++i) {
                    transcript += event.results[i][0].transcript;
                }
                input.value = transcript;
            };

            recognition.onerror = (e) => {
                console.error("Speech rec error:", e);
                stopMic();
            };

            recognition.onend = () => {
                stopMic();
                if (input.value.trim().length > 0) {
                    sendMessage();
                }
            };
        }

        function toggleMic() {
            if (!recognition) {
                alert("Voice recognition not supported in this browser. Please use Google Chrome or Edge.");
                return;
            }
            if (isRecording) {
                recognition.stop();
            } else {
                recognition.start();
            }
        }

        function stopMic() {
            isRecording = false;
            micBtn.classList.remove('recording');
            input.placeholder = "Message AURA in Tanglish or English (or click mic)...";
        }

        let activeAudio = null;
        async function speakText(txt) {
            if (!ttsEnabled) return;
            try {
                if (activeAudio) {
                    activeAudio.pause();
                    activeAudio = null;
                }
                const res = await fetch('/api/voice/synthesize', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text: txt, persona: 'MORNING_WAKEUP', format: 'ogg' })
                });
                const data = await res.json();
                if (data.status === 'success' && data.audio_url) {
                    activeAudio = new Audio(data.audio_url);
                    activeAudio.play().catch(e => console.log('Autoplay policy note:', e));
                }
            } catch(e) {
                console.error("Gemini voice playback error:", e);
            }
        }

        async function playVoiceClip(txt) {
            try {
                if (activeAudio) {
                    activeAudio.pause();
                    activeAudio = null;
                }
                const res = await fetch('/api/voice/synthesize', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text: txt, persona: 'MORNING_WAKEUP', format: 'ogg' })
                });
                const data = await res.json();
                if (data.status === 'success' && data.audio_url) {
                    activeAudio = new Audio(data.audio_url);
                    activeAudio.play();
                }
            } catch(e) {
                alert('Audio playback error: ' + e);
            }
        }

        let ws;
        let activeAgentDiv = null;
        let activeCurrentText = '';

        function playChime() {
            try {
                const ctx = new (window.AudioContext || window.webkitAudioContext)();
                const osc = ctx.createOscillator();
                const gain = ctx.createGain();
                osc.type = 'sine';
                osc.frequency.setValueAtTime(587.33, ctx.currentTime); // D5
                osc.frequency.setValueAtTime(880, ctx.currentTime + 0.15); // A5
                gain.gain.setValueAtTime(0.3, ctx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.6);
                osc.connect(gain);
                gain.connect(ctx.destination);
                osc.start();
                osc.stop(ctx.currentTime + 0.6);
            } catch(e) {}
        }

        function connectWS() {
            const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${proto}//${window.location.host}/ws/chat`);
            ws.onclose = () => setTimeout(connectWS, 2000);
            
            ws.onmessage = (e) => {
                try {
                    const msg = JSON.parse(e.data);
                    if (msg.type === 'token') {
                        if (activeAgentDiv) {
                            activeCurrentText += msg.content;
                            activeAgentDiv.innerHTML = formatMarkdown(activeCurrentText);
                            canvas.scrollTop = canvas.scrollHeight;
                        }
                    } else if (msg.type === 'tool_call') {
                        if (activeAgentDiv) {
                            const banner = document.createElement('div');
                            banner.className = 'tool-banner';
                            banner.innerText = '⚙️ ' + msg.content;
                            activeAgentDiv.parentNode.insertBefore(banner, activeAgentDiv);
                            canvas.scrollTop = canvas.scrollHeight;
                        }
                    } else if (msg.type === 'done') {
                        if (activeAgentDiv) {
                            speakText(activeCurrentText);
                            activeAgentDiv = null;
                            activeCurrentText = '';
                        }
                    } else if (msg.type === 'alarm' || msg.type === 'notification') {
                        playChime();
                        const alertDiv = document.createElement('div');
                        alertDiv.className = 'msg agent';
                        alertDiv.style.border = '2px solid var(--amber)';
                        alertDiv.style.boxShadow = '0 0 24px rgba(255, 183, 3, 0.45)';
                        alertDiv.style.background = 'rgba(11, 19, 43, 0.95)';
                        alertDiv.innerHTML = `<div style="color:var(--amber); font-weight:700; font-size:0.85rem; letter-spacing:0.5px; margin-bottom:6px;">🚨 ${msg.title || 'AURA EXECUTIVE ALARM'}</div>${formatMarkdown(msg.content)}`;
                        canvas.appendChild(alertDiv);
                        canvas.scrollTop = canvas.scrollHeight;
                        speakText(msg.content);
                    }
                } catch(err) {
                    console.error("WS message parse error:", err);
                }
            };
        }
        connectWS();

        function handleKey(e) {
            if (e.key === 'Enter') sendMessage();
        }

        function sendQuick(txt) {
            input.value = txt;
            sendMessage();
        }

        function formatMarkdown(text) {
            return text
                .replace(/\\n/g, '<br>')
                .replace(/\\*\\*(.*?)\\*\\*/g, '<b>$1</b>')
                .replace(/`([^`]+)`/g, '<code>$1</code>');
        }

        function appendMessage(role, text) {
            const div = document.createElement('div');
            div.className = `msg ${role}`;
            div.innerHTML = formatMarkdown(text);
            canvas.appendChild(div);
            canvas.scrollTop = canvas.scrollHeight;
            return div;
        }

        function sendMessage() {
            const text = input.value.trim();
            if (!text) return;
            appendMessage('user', text);
            input.value = '';

            activeAgentDiv = appendMessage('agent', '');
            activeCurrentText = '';

            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ prompt: text }));
            } else {
                fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ prompt: text })
                })
                .then(r => r.json())
                .then(d => {
                    activeAgentDiv.innerHTML = formatMarkdown(d.response);
                    canvas.scrollTop = canvas.scrollHeight;
                    speakText(d.response);
                    activeAgentDiv = null;
                });
            }
        }
    </script>
</body>
</html>
"""
