# 🎙️ JARVIS AUTONOMOUS FULL-DUPLEX VOICE CALL SYSTEM 2.0

> **Real-Time Two-Way Spoken Conversation Engine**  
> *"Ask, Reply & Understand" — Continuous Live Spoken Dialogue with Tanglish Fluency.*

---

## 🚀 ARCHITECTURE OVERVIEW

Unlike simple one-way audio alerts or walkie-talkie bots, this system implements a **continuous, interactive full-duplex conversational voice loop**:

```
                 [ Mukil Speaks into Phone / Mic ]
                                ↓
       [ Web Speech Recognition / Groq Streaming Whisper ]
                                ↓
        [ Context-Injected Gemini 3.8 Flash Brain ]
     (Reads context.json: SGC Bills, Amazon VCS, GD Prep)
                                ↓
    [ Dynamic Response: Direct Answer + Follow-Up Question ]
                                ↓
      [ Edge Neural TTS: ta-IN-Valluvar / en-IN-Prabhat ]
                                ↓
        [ Audio Stream Plays on Speaker / Earpiece ]
                                ↓
           [ Microphone Resumes Listening Instantly ]
```

---

## 📱 DUAL ACCESS CHANNELS

### 1. WebRTC / Mobile Phone Screen Link (Zero Cost, ₹0)
* **Local PC / Network URL**: `http://localhost:8765`
* **Mobile Access on Same Wi-Fi / Hotspot**: `http://<YOUR_PC_IP>:8765`
* **Features**:
  * Realistic telephone dual-tone incoming call ringtone (440Hz + 480Hz pulses synthesized via Web Audio API).
  * Device vibration pulse (`navigator.vibrate`).
  * Stark Industries ARC-Reactor pulsing HUD.
  * **Pulsing Green "Accept" Button** & **Red "Decline" Button**.
  * Dynamic audio waveform reaction.
  * Real-time conversational turn transcript.
  * Completely hands-free continuous dialogue.

### 2. Twilio GSM Cellular Phone Call (Real Mobile Number Ring)
* Endpoint configured at: `/api/twilio/voice`
* Compatible with Twilio `<Gather input="speech">` and Twilio Media Streams (`<Stream url="wss://...">`).
* Twilio calls your actual SIM number (`+918072044874`), standard mobile ringtone rings, and you speak over the GSM network.

---

## 🛠️ HOW TO RUN

### Instant Desktop Launcher:
Double-click:
`C:\Users\mukil\Desktop\Launch_JARVIS_Voice_Call.bat`

### Manual Terminal Command:
```powershell
cd C:\Users\mukil\jarvis-core
python -m uvicorn voice_agent.server:app --host 0.0.0.0 --port 8765
```

---

## 🧠 CONVERSATIONAL INTELLIGENCE RULES
1. **Direct Answer First**: States exact real data from `context.json` (no fluff).
2. **Interactive Probe**: Always attaches an intelligent follow-up question or recommendation to keep the dialogue active.
3. **Low Latency**: Generates responses under 35 words per turn for sub-second vocal cadence.
4. **Hands-Free**: Automatically turns on microphone after finishing speech.
