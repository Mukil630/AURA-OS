# 🌌 AURA — Autonomous Unified Response Assistant
> **A 24/7 Persistent, Multi-Device Autonomous AI Operating System & Executive Partner**  
> *Engineered by Mukil | Official Birthday Launch: September 3, 2026*

---

## 🏛️ System Overview

**AURA** (*Autonomous Unified Response Assistant*) is a next-generation personal AI operating system designed to automate software engineering, campus placement preparation, family business modernization, and cross-device hardware control (Phone ↔ Cloud ↔ PC).

Unlike static rule-based chatbots, **AURA** employs a **Dynamic CodeAct & State Engine** that dynamically plans, generates on-demand scripts, self-heals errors, and adapts schedules contextually without hardcoded limitations.

```
                  ┌─────────────────────────────────────┐
                  │          🗣️ MUKIL (Master)          │
                  └──────────────────┬──────────────────┘
                                     │
           ┌─────────────────────────┴─────────────────────────┐
           │                                                   │
  📲 Phone PWA / Voice                               💻 PC Desktop Dashboard
           │                                                   │
           └─────────────────────────┬─────────────────────────┘
                                     ▼
                   ┌───────────────────────────────────┐
                   │     🚪 AURA 24/7 CLOUD GATEWAY    │
                   │     FastAPI + Secret Auth Token   │
                   └─────────────────┬─────────────────┘
                                     ▼
                   ┌───────────────────────────────────┐
                   │    🧠 LANGGRAPH CENTRAL BRAIN     │
                   │    Intent Router & Dynamic CodeAct│
                   └─────────────────┬─────────────────┘
                                     ▼
     ┌───────────────────────┬───────┴───────┬───────────────────────┐
     ▼                       ▼               ▼                       ▼
☕ Study & Sprints     🤖 Placement Hunter  📧 24/7 Gmail Radar    💼 Business Engine
 (Adaptive Revert)     (Indeed / ATS Match)  (Interview Alerts)     (SGC Billing Sync)
     │                       │               │                       │
     └───────────────────────┼───────────────┼───────────────────────┘
                             ▼               ▼
                 🗄️ PostgreSQL / Supabase   🌐 5TB Google Drive Vault
```

---

## ⚡ Core Architectural Superpowers

1. **🧠 Universal Dynamic CodeAct Engine**:
   - Zero hardcoded tool limitations. When given arbitrary complex tasks, AURA writes, debugs, and executes Python/PowerShell scripts on the fly.
2. **📅 Adaptive Sprints with Auto-Reversion**:
   - Normal daily routines (Java, Python, Apti) dynamically switch into 7-day high-intensity placement drive sprints and automatically restore baseline habits upon deadline completion.
3. **📱 24/7 Cloud Brain (Never Sleeps)**:
   - Hosted in the cloud (Railway / Render). Operates autonomously even when the local laptop is shut down.
4. **🔒 Military-Grade Security & Stark Passcode Protocol**:
   - Secret key header pairing (`x-jarvis-token`), destructive command firewalls, and biometric voice passcode activation (`AURA Protocol Stark 55`).
5. **🌐 5TB Google Drive Master Vault Sync**:
   - Direct integration with Google Drive (`1nGZG5-eIcxmkgQxBtZ7tjGTUoWWNY4m1`) & dual SGC billing vaults (`155Eq...` & `1a9VJ...`).

---

## 📁 Repository Structure

```text
aura-core/
├── api/                   # 🚪 24/7 Authenticated Mobile Voice Gateway
│   └── voice_webhook.py   # FastAPI server with Token pairing & guardrails
├── brain/                 # 🧠 Core Reasoning & Intent Classification
│   ├── agent_brain.py     # ReAct reasoning loop & tool executor
│   └── intent_router.py   # Convo vs Action vs Process 3-way triage
├── memory/                # 💾 Memory Management Layer
│   └── memory_manager.py  # Persistent state reader & updater
├── storage/               # 🗄️ Local state & Applied jobs database
│   ├── memory/            # context.json, user_profile.json, system_blueprint.json
│   └── applied_jobs.json  # Live log of automated job applications
├── tools/                 # 🛠️ System Tools & Cloud Bridges
│   ├── pc_tools.py        # Windows OS hardware execution
│   ├── telegram_bridge.py # 2-Way Voice Telegram bot with Whisper & Neural TTS
│   ├── drive_manager.py   # 5TB Google Drive sync engine
│   └── cloudflared.exe    # Encrypted Cloudflare Tunnel bridge
└── start_jarvis_tunnel.bat# 🚀 1-Click Server & Tunnel Launcher
```

---

## 🚀 Quick Start (Local & Remote Mobile Pairing)

### 1. Launch Server & Secure Tunnel
```bash
start_jarvis_tunnel.bat
```

### 2. Mobile Voice Webhook Trigger
Send an authenticated `POST` request from Android HTTP Shortcuts or Google Assistant:
```bash
curl -X POST "https://your-tunnel.trycloudflare.com/api/voice" \
     -H "x-jarvis-token: mukil-jarvis-vault-key-9080030538" \
     -H "Content-Type: application/json" \
     -d '{"query": "Check screen brightness and today study schedule"}'
```

---

## 👑 Roadmap & Milestones (8-Day Birthday Sprint)
- [x] **Day 1 (Aug 25)**: Core Brain Refactor, Intent Router & Secure Cloud Tunnel.
- [ ] **Day 2 (Aug 26)**: Google Calendar Native Sync & Adaptive 7-Day Sprint Overrides.
- [ ] **Day 3 (Aug 27)**: 24/7 Gmail Interview Radar & Placement Fresher Job Hunter.
- [ ] **Day 4 (Aug 28)**: Family Business (SGC Billing) Overdue Radar & 5TB Drive Indexer.
- [ ] **Day 5 (Aug 29)**: Stark Voice Passcode Protocol & Encrypted Secret Vault.
- [ ] **Day 6 (Aug 30)**: Mobile PWA App & Iron-Man UI Dashboard.
- [ ] **Day 7 (Aug 31)**: 24/7 Cloud Deployment (Railway + Supabase).
- [ ] **Day 8 (Sep 1-2)**: End-to-End Master Polish & Official Launch!
- [ ] **🎂 Sep 3, 2026**: **Happy Birthday Mukil — AURA is Live!**
