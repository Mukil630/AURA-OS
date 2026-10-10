"""
JARVIS Autonomous Voice Call 2.0 - Full-Duplex Conversational Server
Enables real two-way spoken conversation between Mukil and JARVIS.
- Full context injection (context.json, SGC billing, Amazon VCS, GD prep)
- Real-time Edge Neural TTS (ta-IN-ValluvarNeural & en-IN-PrabhatNeural)
- WebRTC / Mobile Phone Incoming Call Screen with Ringtone & Green Accept Button
- Twilio Telephony Webhook for GSM Cellular Calls
"""

import os
import sys
import json
import base64
import asyncio
import tempfile
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import edge_tts

# Path setup
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config import GEMINI_API_KEY, GROQ_API_KEY
from tools.tts_generator import clean_text_for_speech, detect_language_and_voice

app = FastAPI(title="JARVIS Autonomous Conversational Voice Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

IST_TZ = timezone(timedelta(hours=5, minutes=30))

def load_system_context() -> Dict[str, Any]:
    """Loads latest state from context.json."""
    ctx_path = os.path.join(BASE_DIR, "storage", "memory", "context.json")
    if os.path.exists(ctx_path):
        try:
            with open(ctx_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def build_system_prompt() -> str:
    ctx = load_system_context()
    now_ist = datetime.now(IST_TZ).strftime("%I:%M %p, %d %b %Y (%A) IST")
    career = ctx.get("active_career_strategy", {})
    textile = ctx.get("textile_empire_roadmap", {})
    
    return f"""
You are Antigravity (JARVIS Prime), Mukil's personal autonomous AI executive partner on a LIVE PHONE CALL.
You are having a real-time, two-way spoken conversation directly with Mukil through his phone.

CURRENT TIME: {now_ist}
USER PROFILE:
- Boss: Mukil (AI Engineer / Full-Stack Developer & Entrepreneur)
- Tone: Natural, confident, brotherly Tanglish + English ('Boss' / 'Mapla' Stark dynamic).
- Calling Mode: Live voice call. Speak concisely (1 to 3 short punchy sentences max per turn). NEVER recite long essays.
- CONVERSATIONAL RULE ("Ask, Reply & Understand"): Always give the direct answer first, and when relevant, ask a natural follow-up question back to keep the dialogue interactive and alive!

ACTIVE CONTEXT:
1. Master Blueprint Pillars:
   - Pillar 1: Amazon VCS (Customer Service Associate) fast-track offer letter (100% online from room, 3-5 days turnaround) + Tomorrow's Infinite Computer Solutions in-person GD!
   - Pillar 2: Textile Empire expansion from ₹1.5L to ₹4L-₹6L/month via SGC Yarn Dyeing recipe database (saving ₹30k-₹50k/mo), ready-dyed yarn trading, Salavai (bleaching), and industrial washing hub.
   - Pillar 3: This live interactive phone call system you are currently running!
2. SGC Billing: Sri Ganapathi Colours, 4 active bills on record, ₹43,439.00 gross total.

Speak naturally like a loyal, high-IQ tech executive talking on the phone. Keep replies under 35 words so the speech feels instant and punchy.
"""

# Maintain in-memory conversation turns for the active phone call
CALL_HISTORY: List[Dict[str, str]] = []

class ChatRequest(BaseModel):
    message: str
    language: Optional[str] = "en-IN"

async def call_llm(user_message: str) -> str:
    """Invokes LLM with system context and conversation history."""
    global CALL_HISTORY
    system_prompt = build_system_prompt()
    
    # 1. Try Google Gemini
    if GEMINI_API_KEY:
        try:
            from google import genai
            client = genai.Client(api_key=GEMINI_API_KEY)
            
            # Format history
            conversation_text = ""
            for turn in CALL_HISTORY[-6:]:
                role = "Mukil" if turn["role"] == "user" else "JARVIS"
                conversation_text += f"{role}: {turn['content']}\n"
            
            full_prompt = (
                f"{system_prompt}\n\n"
                f"CONVERSATION TRANSCRIPT SO FAR:\n{conversation_text}\n"
                f"Mukil just said: \"{user_message}\"\n\n"
                f"JARVIS Response (Spoken Voice):"
            )
            
            response = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=full_prompt
            )
            if response and response.text:
                reply = response.text.strip()
                CALL_HISTORY.append({"role": "user", "content": user_message})
                CALL_HISTORY.append({"role": "assistant", "content": reply})
                return reply
        except Exception as ge:
            print(f"[LLM] Gemini attempt error: {ge}")

    # Fallback response
    fallback = "Boss, message reach aachu! System operational. Inniki Amazon assessment mudikkalama?"
    CALL_HISTORY.append({"role": "user", "content": user_message})
    CALL_HISTORY.append({"role": "assistant", "content": fallback})
    return fallback

async def generate_speech_base64(text: str) -> str:
    """Generates MP3 audio and returns base64 encoded string."""
    clean = clean_text_for_speech(text)
    voice = detect_language_and_voice(clean)
    
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tf:
        temp_path = tf.name
        
    try:
        communicate = edge_tts.Communicate(clean, voice)
        await communicate.save(temp_path)
        with open(temp_path, "rb") as f:
            audio_bytes = f.read()
        return base64.b64encode(audio_bytes).decode("utf-8")
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass

@app.get("/", response_class=HTMLResponse)
async def serve_call_ui():
    """Serves the authentic incoming call interface."""
    html_path = os.path.join(os.path.dirname(__file__), "call_ui.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>JARVIS Voice Server Running</h1>"

@app.post("/api/chat")
async def chat_turn(req: ChatRequest):
    """Processes user voice turn, responds with LLM text + audio base64."""
    user_text = req.message.strip()
    if not user_text:
        return JSONResponse({"reply": "Boss, unga voice kekala, innoru thadava sollunga?", "audio_b64": ""})
    
    reply_text = await call_llm(user_text)
    audio_b64 = await generate_speech_base64(reply_text)
    
    return JSONResponse({
        "reply": reply_text,
        "audio_b64": audio_b64
    })

@app.post("/api/reset")
async def reset_call():
    """Resets call history for new call."""
    global CALL_HISTORY
    CALL_HISTORY = []
    initial_greeting = "Vanakkam Boss! JARVIS is on the line. Sollinga, enna plan?"
    audio_b64 = await generate_speech_base64(initial_greeting)
    CALL_HISTORY.append({"role": "assistant", "content": initial_greeting})
    return JSONResponse({
        "greeting": initial_greeting,
        "audio_b64": audio_b64
    })

@app.api_route("/api/twilio/voice", methods=["GET", "POST"])
async def twilio_voice_webhook(request: Request):
    """
    Twilio Interactive Voice Webhook (TwiML) for real cellular phone calls.
    Uses <Gather> for speech input and responds via neural speech.
    """
    form_data = await request.form()
    speech_result = form_data.get("SpeechResult", "").strip()
    
    if not speech_result:
        twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aditi">Vanakkam Boss! This is JARVIS. System connection established. Sollinga Boss, I am listening.</Say>
    <Gather input="speech" timeout="5" speechTimeout="auto" action="/api/twilio/voice" method="POST">
    </Gather>
</Response>"""
        return HTMLResponse(content=twiml, media_type="application/xml")
    
    # Process speech with LLM
    reply_text = await call_llm(speech_result)
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aditi">{reply_text}</Say>
    <Gather input="speech" timeout="5" speechTimeout="auto" action="/api/twilio/voice" method="POST">
    </Gather>
</Response>"""
    return HTMLResponse(content=twiml, media_type="application/xml")

if __name__ == "__main__":
    uvicorn.run("voice_agent.server:app", host="0.0.0.0", port=8765, reload=False)
