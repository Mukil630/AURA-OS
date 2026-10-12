# AURA-OS Target Architecture & System Design
**Specification Document:** `docs/AURA_OS_ARCHITECTURE.md`  
**Architect:** Senior AI Systems Architect & Agentic AI Engineer  
**Version:** 2.0.0 (Unified Operating Plane)  
**Budgetary Constraint:** ₹0 / Month  

---

## 1. System Vision & Design Principles

AURA-OS is an autonomous personal AI operating system built for Mukil, providing continuous, proactive executive assistance across business operations (Sri Ganapathi Colours yarn dyeing & industrial washing hub), personal productivity, career development, and computer control.

### Core Architectural Principles
1. **Separation of Responsibilities**:
   - **Reasoning**: Google Gemini (`gemini-2.5-flash`) provides deep multi-step planning and contextual reasoning.
   - **Control**: Central Python Orchestrator manages task state, execution graph, and policy gates.
   - **Domain Ownership**: Specialized Swarm Agents own specific business and operational domains.
   - **Tool Connectivity**: Model Context Protocol (MCP) and strongly-typed function registries bridge the model to real-world systems.
2. **Deterministic Durability at ₹0 Cost**:
   - Free cloud infrastructure (Render) is inherently ephemeral. Durability is achieved via atomic local SQLite persistence backed by continuous cloud snapshots to Google Drive Mesh Node 09 via a permanent Google Cloud Service Account.
3. **Proactive Cognition (Not Just Reactive Chat)**:
   - The system maintains background awareness of deadlines, supplier payment terms, factory machine cycles, and customer receivables, proactively alerting Mukil before deadlines arrive.
4. **Safety-First Authorization Gates**:
   - Read-only operations execute automatically with zero friction.
   - Destructive or financial operations (creating invoices, deleting records, releasing payments) strictly enforce two-step cryptographic verification tokens.

---

## 2. Five-Layer Architecture Blueprint

```
┌────────────────────────────────────────────────────────────────────────┐
│                        USER & COMMAND CHANNELS                         │
│    Telegram Voice/Chat · AURA Mobile Hub (PWA) · Web UI · REST API     │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ LAYER 1: GATEWAY & NORMALIZATION LAYER                                 │
│ • Authentication & Authorization Guard (Authorized Telegram IDs)       │
│ • Channel Input Normalization (Voice STT ➔ GatewayRequest Contract)    │
│ • Session Management & Deduplication Fingerprinting                    │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ LAYER 2: CENTRAL ORCHESTRATOR & COGNITIVE CONTROLLER                   │
│ • Task Manager (Durable SQLite CRUD, State Transitions)                │
│ • Gemini Reasoning Adapter (Intent, Multi-step Planner, Tool Calling)  │
│ • Policy & Approvals Engine (Read-only Auto-Approve vs Token Gates)    │
│ • Workflow State Machine (Checkpoints, Failover, Error Recovery)       │
│                                                                        │
│                       DELEGATES TO SPECIALISTS:                        │
│ ┌───────────────────┬───────────────────┬────────────────────────────┐ │
│ │ SGC Business      │ Business Vault &  │ Industrial Washing         │ │
│ │ Invoicing Agent   │ Payables Agent    │ & Salavai Hub Agent        │ │
│ ├───────────────────┼───────────────────┼────────────────────────────┤ │
│ │ Knowledge & Drive │ Windows System    │ Career & Placement         │ │
│ │ Mesh Agent        │ & PC Bridge Agent │ Hunting Agent              │ │
│ └───────────────────┴───────────────────┴────────────────────────────┘ │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ LAYER 3: UNIFIED TOOL & MCP REGISTRY                                   │
│ • FastMCP Client (sgc-mcp: 14 tools - Invoices, Overdue, Recipes, Swatch)│
│ • Local Python Tool Registry (Pydantic-validated, schema-dereferenced)  │
│ • REST / Webhook Adapters (Google APIs, GitHub, TNEB Portal)           │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ LAYER 4: MULTI-PLANE EXECUTION ENVIRONMENTS                            │
│ • Render Cloud Container (24/7 Linux Web Server & Keep-Alive Daemon)   │
│ • Local Windows PC Worker Bridge (WebSocket WSS ➔ Win32, Screen, Apps) │
│ • SGC Electron Physical Storage & Data Store                           │
│ • Google Drive Distributed Vault (Permanent Service Account Bot)       │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ LAYER 5: SHARED PLATFORM & PERSISTENCE SERVICES                        │
│ • Durable SQLite Database (data/master_agent.db - 7 relational tables) │
│ • Asia/Kolkata Durable Reminder & Alarms Engine (Survives Restarts)    │
│ • 250GB Distributed Drive Mesh Synchronization (10 Dedicated Nodes)    │
│ • Two-Layer Structural & Semantic Verifier                             │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. End-to-End Request & Task Execution Flow

```
User: "Remind me tomorrow at 6 PM that Lakshmi Chemicals ₹25k payment is due"
                          │
                          ▼
┌───────────────────────────────────────────────────────────────────────┐
│ 1. Gateway Normalization                                              │
│    • Checks Telegram user ID against AUTHORIZED_TELEGRAM_USERS.       │
│    • Converts voice note or text into:                                │
│      GatewayRequest(user_id='6233907249', channel='TELEGRAM', text=...)│
└─────────────────────────┬─────────────────────────────────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────────────────────────┐
│ 2. Central Orchestrator & Gemini Reasoning Adapter                    │
│    • Analyzes natural language request:                               │
│      - Intent: SCHEDULE_REMINDER + BUSINESS_PAYABLE_ALERT             │
│      - Entities: Vendor='Lakshmi Chemicals', Amount=25000,            │
│                  Time='2026-10-13 18:00:00 IST'                       │
│    • Generates TaskContract(task_id='tsk_89ab', status='IN_PROGRESS') │
│    • Persists directly to SQLite tasks table.                         │
└─────────────────────────┬─────────────────────────────────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────────────────────────┐
│ 3. Policy & Approval Evaluation                                       │
│    • Action: Scheduled read/alert. Risk level: LOW.                   │
│    • Auto-approved by policy engine (no token gate needed for alerts). │
└─────────────────────────┬─────────────────────────────────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────────────────────────┐
│ 4. Specialist Delegation: BusinessVaultFinanceAgent & Scheduler       │
│    • BusinessVaultFinanceAgent looks up verified bank details:        │
│      A/C: HDFC 50200078129043, IFSC: HDFC0001234.                     │
│    • DurableScheduler inserts job into reminders table:               │
│      trigger_at_ist='2026-10-13 18:00:00', channel='TELEGRAM',        │
│      payload={'speech_text': '...', 'display_text': '...'}            │
└─────────────────────────┬─────────────────────────────────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────────────────────────┐
│ 5. Execution Verification & State Transition                          │
│    • Verifies reminder ID was written to DB and indexed in memory.    │
│    • Updates TaskContract status to 'COMPLETED'.                      │
│    • Logs event to execution_events table.                            │
└─────────────────────────┬─────────────────────────────────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────────────────────────┐
│ 6. Response Synthesis & Delivery                                      │
│    • Generates Tanglish executive confirmation:                       │
│      "Done Boss! Tomorrow 6 PM-ku voice alarm schedule aayiduchu..."   │
│    • Delivers formatted HTML text + audio note to Telegram / Web Hub. │
└───────────────────────────────────────────────────────────────────────┘
```

---

## 4. Disaster Recovery & Zero-Budget Cloud Persistence Strategy

Render Free Web Services discard their ephemeral disk on redeploy and spin down after 15 minutes of inactivity. To guarantee 100% data durability at ₹0 cost:

1. **Keep-Alive Heartbeat**:
   - `app/core/keep_alive.py` continuously pings `https://aura-os-jarvis.onrender.com/health` every 120 seconds to prevent cold shutdowns during working hours.
2. **Permanent Service Account Drive Sync**:
   - The system utilizes `sgc-drive-bot@sgc-billing.iam.gserviceaccount.com` (RSA 2048-bit key) with zero token expiration to sync:
     - `data/master_agent.db` ➔ Node 09 (`1SoZDnh1JPz59NaKxvnR72xtJSYWbL8uU`)
     - `storage/memory/*.json` ➔ Node 01 (`14fGVZomgy2CItfspYo7cVXSImAqJDZZX`)
     - Invoices & Ledgers ➔ Node 05 (`11KMBP0HHa2AFl30zjL8-a_-BQk9MgWM9`)
3. **Cold-Start Self-Healing (Hydration on Startup)**:
   - When the container initializes, if `data/master_agent.db` is empty or missing, it queries Drive Node 09 to download the latest database snapshot before serving traffic.

---

## 5. Security & Permission Gates

| Risk Tier | Operations | Policy Rule | Verification Mechanism |
| :--- | :--- | :--- | :--- |
| **Tier 1 (Read-Only)** | Check turnover, list bills, search Drive, query weather/vitals | **Auto-Approved** | Read query executes immediately. |
| **Tier 2 (Operational)** | Schedule reminder, log new expense, formulate dyeing recipe | **Logged & Validated** | Parameters validated through Pydantic schemas. |
| **Tier 3 (Financial & Write)** | Create quick bill, mark bill paid, mark supplier paid | **Two-Step Confirmation** | Step 1 yields preview + temporary token (`CONFIRM_PAID_...`); Step 2 executes on confirmation. |
| **Tier 4 (Destructive)** | Delete invoice, purge records, lock workstation | **Strict Token Gate** | Irreversible operation blocked without explicit token + biometric/secret verification. |
