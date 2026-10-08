# 📞 AURA-OS Autonomous Continuous Calling Agent

An autonomous full-duplex conversational calling engine and mobile uplink bridge for **Mukil's JARVIS / AURA-OS**.

---

## ⚡ Architecture Overview

```
               [AURA-OS Brain & Telephony Engine]
                               │
               ┌───────────────┴───────────────┐
               ▼                               ▼
    [FastAPI & WebSockets]            [ADB / Mobile Bridge]
    Port 8765 (run.py)                (call_mukil.py)
    ├── Groq Whisper STT (<300ms)             │ am start --ez incoming_call true
    ├── Gemini 3.8 Flash Brain                ▼
    ├── Edge Neural Speech (TTS)    [Redmi Note 14 Pro+ 5G]
    └── Stark Hologram Web HUD      com.example.voiceassistantapp
                                    ├── Billa 2007 Beat-Drop Ringtone
                                    ├── Dynamic Animated Wallpaper
                                    └── Full-Screen Calling HUD
```

---

## 🌟 Key Capabilities
1. **Full-Duplex Hands-Free Voice**: Real-time conversation loop with zero robotic delay.
2. **Authentic Executive Tanglish**: Custom prompt engine calibrated for Mukil's brotherly dynamic ("Mapla / Boss"), placement strategy, and SGC textile empire.
3. **Hardware & Mobile Wake Uplink**: Directly triggers incoming call intents on connected Android phones over ADB (`call_mukil.py`).
4. **Agentic Verbal Tools**: Real-time verbal execution for:
   - PC Vitals & Battery Status
   - Sri Ganapathi Colours (SGC) Billing Ledger & Overdue Radar
5. **Stark Holographic Call HUD**: Audio-reactive Arc Reactor ring, interactive waveform equalizer, mute controls, and call timer.

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
Copy `.env.template` to `.env` and provide your API keys:
```bash
copy .env.template .env
```

### 3. Launch Telephony Server
```bash
python run.py
```
Open `http://localhost:8765` on PC or `http://<LAN_IP>:8765` on Mobile browser.

### 4. Trigger Phone Call via ADB
```bash
python call_mukil.py
```

---

## 📁 Module Structure
- `app/api/`: FastAPI endpoints for turn-by-turn chat, audio transcription, and session resets.
- `app/core/`: Configuration, session memory, and dynamic prompt engine with live memory injection.
- `app/services/`: Groq Whisper STT, Gemini 3.8 Flash reasoning, Edge TTS, and verbal tool triggers.
- `static/`: Stark HUD holographic web caller interface with Web Audio synthesis.
- `call_mukil.py`: One-click ADB incoming call intent trigger for Android device.
