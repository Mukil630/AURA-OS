# 📞 JARVIS Autonomous Continuous Calling Voice AI Agent

An autonomous full-duplex conversational voice calling engine and executive partner for **Mukil's JARVIS Ecosystem**.

Built with **FastAPI**, **Groq LPU (`openai/gpt-oss-120b`)**, **Microsoft Edge-TTS Neural Speech**, **Web STT**, and **PWA Mobile App** support.

---

## ⚡ Architecture Overview

```
               [JARVIS Autonomous Voice Calling Brain]
                                │
       ┌────────────────────────┼────────────────────────┐
       ▼                        ▼                        ▼
[Groq LPU Engine]       [11 Ecosystem Tools]     [Microsoft Edge-TTS]
openai/gpt-oss-120b     ├── Live Web Search       ├── ta-IN-ValluvarNeural
Sub-second latency (<0.4s)├── SGC Billing & Ledger └── en-IN-PrabhatNeural
                        ├── Mill Web Scraper     
                        ├── Telegram Alert Push   
                        ├── Drive Mesh Vault     
                        ├── Turso Cloud Tasks    
                        └── PC Hardware Vitals   
```

---

## 🌟 Key Capabilities
1. **Full-Duplex Hands-Free Voice**: Real-time voice call loop with sub-second response times (< 0.5s latency).
2. **Authentic Executive Tanglish**: Custom prompt engine calibrated for Mukil's brotherly dynamic ("Mapla / Boss"), placement strategy, and SGC textile empire.
3. **PWA Mobile App (Installable)**: Fullscreen phone call HUD with ARC Reactor pulsing animation, ringtone, and vibration.
4. **11 Agentic Tools & Function Calling**:
   - 🌐 **Live Web Search**: Real-time news, weather, stock, market data.
   - ☁️ **Drive Vault Search**: 250GB Distributed Drive Mesh & Bills Search.
   - 🎯 **Career & Placement Intel**: Amazon VCS prep, STAR format, GD strategy, ATS tips.
   - 🧾 **SGC Financial Overview**: Total invoices turnover & gross revenue.
   - ⚠️ **SGC Overdue Radar**: Unpaid bills & customer payment radar.
   - 📊 **SGC Customer Ledger**: Specific customer ledger details.
   - 🏭 **Spinning Mill Leads Scraper**: Real live B2B Tamil Nadu spinning mill scraper.
   - 📱 **Telegram Mobile Alert**: Instant high-priority push to Mukil's phone.
   - ⏰ **Turso Reminders**: Active tasks and cloud alarm retrieval.
   - ➕ **Add Turso Reminder**: Schedule new cloud tasks with natural time (e.g. `10m`, `1h`).
   - 💻 **PC Vitals**: CPU load, RAM usage, Battery %.

---

## 🚀 Quick Start (Local Run)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment (`.env`)
```dotenv
HOST=0.0.0.0
PORT=8765
GROQ_API_KEY=your_groq_api_key
GEMINI_API_KEY=your_gemini_api_key
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
```

### 3. Start Server
```bash
python run.py
```
Open `http://localhost:8765` on PC or `http://<LAN_IP>:8765` on Mobile browser.

---

## ☁️ 1-Click Render Cloud Deployment
This project includes pre-configured `render.yaml` and `Procfile`.
1. Fork or push this repository to GitHub.
2. In [Render Dashboard](https://dashboard.render.com), create a new **Web Service**.
3. Select this repository.
4. Set Environment Variables: `GROQ_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
5. Deploy! Render assigns a permanent HTTPS URL with working mobile microphone permissions.
