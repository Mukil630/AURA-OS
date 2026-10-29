"""
AURA OS Master Knowledge Vault & Operational Flows Tool
aura/tools/knowledge_vault_tools.py
Provides instantaneous, structured ground-truth access to Mukil's master profile,
credentials, accounts payable, VIZRO VERTEX & project dossiers, and core workflow pipelines.
"""
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional

MEMORY_DIR = Path("C:/Users/mukil/jarvis-core/storage/memory")

MASTER_KNOWLEDGE = {
    "profile": {
        "name": "MUKILARASU S (Mukil)",
        "role": "AI Engineer / Full-Stack Developer & Entrepreneur",
        "email": "mukilarasu55@gmail.com",
        "phone": "9080030538",
        "location": "Karur, Tamil Nadu",
        "college": "VSB Engineering College, Karur (B.Tech IT, 2023–2027, 8.1 CGPA)",
        "pan_card": "IQWPM4967A",
        "birthday": "September 3",
        "github": "https://github.com/Mukil630 (Mukil630)",
        "leetcode": "https://leetcode.com/u/Mukil55 (Mukil55)",
        "linkedin": "https://www.linkedin.com/in/mukilarasu-s-333771302",
        "primary_stack": "Next.js, FastAPI, Python, Java, PostgreSQL, LibSQL/Turso, Playwright",
        "master_resume_link": "https://drive.google.com/file/d/1TpyzV7OGEf-YQfGLUpusAI5cDDvF1kAJ/view?usp=drive_link",
        "master_resume_id": "1TpyzV7OGEf-YQfGLUpusAI5cDDvF1kAJ",
        "local_resume_path": r"C:\Users\mukil\OneDrive\placement questions\MK.PDF.RESUME.pdf"
    },
    "projects": {
        "VIZRO_VERTEX": {
            "name": "VIZRO VERTEX",
            "url": "https://vizro.vercel.app/",
            "purpose": "AI Engineering & Smart Software Architecture Suite with automated client requirement analysis and interactive freelance pricing estimator.",
            "founders": ["Mukilarasu (Boss / Creator)", "Siva", "Raamprasanth"],
            "ready_made_suites": [
                "Botify WhatsApp AI Bot SaaS Suite",
                "JurisFlow Law Chamber & Legal CRM",
                "Restaurant & Food POS Template",
                "Campus Connect School/College Suite",
                "Hospital & Health Care Suite"
            ],
            "capabilities": [
                "Social Media Marketing",
                "Mobile App Development",
                "Full-Stack Web Applications",
                "Desktop Applications",
                "AI Autonomous Agents & Automation Tools"
            ]
        },
        "SGC_BILLING_APP": {
            "name": "Sri Ganapathi Colours Desktop Billing App",
            "tech": "Electron, React, Tailwind, Google Drive Auto-Sync",
            "purpose": "A4 Xerox-ready GST tax invoice generation, customer ledgers, and overdue balance tracking."
        },
        "AURA_OS": {
            "name": "AURA OS / JARVIS Prime",
            "tech": "Python, Groq, Google Gemini 3.5/3.8, LibSQL/Turso, Open-Meteo REST",
            "purpose": "Mukil's 24/7 autonomous operating plane, multi-device memory, CodeAct terminal execution, and Telegram voice partner."
        },
        "BOTIFY": {
            "name": "Botify SaaS",
            "tech": "WhatsApp Business API, Python, LLM Reasoning",
            "purpose": "Automated conversational commerce, customer inquiries, and order management."
        }
    },
    "sgc_textile_and_washing_hub": {
        "business_name": "Sri Ganapathi Colours (SGC)",
        "specialty": "Hank Yarn Dyeing, Sizing & Industrial Garment Washing",
        "location": "Karur, Tamil Nadu",
        "financial_status": {
            "total_bills": 11,
            "gross_turnover": 66584.00,
            "taxable_turnover": 63412.14,
            "total_gst": 3170.61,
            "gst_rate": "5.00% (2.5% CGST + 2.5% SGST)",
            "drive_bills_folder_id": "11KMBP0HHa2AFl30zjL8-a_-BQk9MgWM9"
        },
        "washing_hub_ops": {
            "processes": ["Acid Bio-Polishing Enzyme Wash", "Silicon Softener Finish", "Shrinkage & Shade Matching"],
            "key_chemicals": "Bio-Polish Acid Enzyme (50L barrels), Cationic/Non-Ionic Silicon Softener, Acetic Acid buffer (pH 4.5 - 5.5)",
            "cycle_specs": "Temperature: 50-55°C, Duration: 45-60 mins, Followed by silicon softening at 40°C for 20 mins"
        },
        "accounts_payable": [
            {
                "vendor": "Lakshmi Chemicals",
                "category": "Chemicals & Enzymes (Bio-Polish Acid Enzyme 50L & Silicon Softener)",
                "amount": 25000.00,
                "invoice_ref": "LC-8842",
                "bank": "HDFC Bank (A/C: 50200078129043, IFSC: HDFC0001234, UPI: lakshmichem@hdfcbank)",
                "status": "PENDING"
            },
            {
                "vendor": "TNEB Commercial Power",
                "category": "Factory & Boiler Commercial Electricity",
                "consumer_no": "03-245-004-1290",
                "amount": 18500.00,
                "portal": "https://www.tnebnet.org",
                "status": "PENDING"
            }
        ]
    },
    "drive_mesh": {
        "node_01": {"id": "14fGVZomgy2CItfspYo7cVXSImAqJDZZX", "role": "Core Memory & Task Logs"},
        "node_02": {"id": "1rXA02dZn0palLwBl0hyTmUV9_-brkpKZ", "role": "Project Codebases & Git Repos"},
        "node_03": {"id": "1rl5EhQCcTiyyrVXp57l4P-4Bd76Q7YM2", "role": "Placement ATS Resumes & Portfolios"},
        "node_04": {"id": "1ebinMnwlZFz6RhaRFYtVHhB2whzvPXDK", "role": "B2B Scraped Data & Mill CSVs"},
        "node_05": {"id": "11KMBP0HHa2AFl30zjL8-a_-BQk9MgWM9", "role": "SGC Main Invoices & Ledgers"},
        "node_06": {"id": "1ckOQk0kLAlFr5S4xMkEZ3KXtm6hbSvjY", "role": "Visual Verification Screenshots"},
        "node_07": {"id": "1s4YowqJvRiSEv8r1r_rc35ejVw1A05lU", "role": "AI Model Weights & Audio Cache"},
        "node_08": {"id": "18L9Q6MC1fiT_LIPg0FKpLlQ0OR052yyJ", "role": "Learning Materials, Java DSA & Apti"},
        "node_09": {"id": "1SoZDnh1JPz59NaKxvnR72xtJSYWbL8uU", "role": "Cloud Database Snapshots & Recovery"},
        "node_10": {"id": "1Qdf3ac_4NEK5id-5ww9V7QgpD5eMxLYC", "role": "Multi-Agent Shared Overflow"}
    },
    "workflow_pipelines": {
        "FLOW_1_WEB_RESEARCH": "URL Input -> Scrape DOM -> Extract Core Purpose -> Check Founders/Team & Pricing -> Lock as Active Topic for Pronoun Resolution -> Deliver Tanglish Brief.",
        "FLOW_2_SGC_BILLING": "Inquiry -> Query Local DB (Checksum 8673c0651ca6029f) -> Compute 5% GST -> Render PDF -> Upload to Drive Node 05 -> Dispatch Summary.",
        "FLOW_3_CAREER_ATS": "Job Description -> Compare against Mukil's Master Resume (1TpyzV...) -> Calculate ATS Match (>90%) -> Generate Tailored LaTeX -> Save to job_applications_log.json.",
        "FLOW_4_MORNING_DAEMON": "06:00 AM (Open-Meteo Karur Weather & Yarn Drying) -> 06:05 AM (Workout Beast Shoulders/Arms) -> 07:00 AM Monthly 1st (GST CA Report) -> Dual Dispatch (Speakers + Telegram).",
        "FLOW_5_ANAPHORA_COHERENCE": "Evaluate Pronouns ('the company', 'it', 'they', 'authors') -> Bind to Active Entity from last 3-6 turns -> Deep-Dive on Bound Entity -> Zero False Default to SGC/Mukil."
    }
}


def query_master_knowledge(topic: str = "all") -> Dict[str, Any]:
    """
    Queries AURA's Master Knowledge Vault for structured facts about Mukil's credentials,
    projects (VIZRO VERTEX, Botify), SGC accounts payable, Drive mesh, or workflow pipelines.

    Args:
        topic: 'profile', 'projects', 'sgc', 'payables', 'drive_mesh', 'pipelines', or 'all'.
    """
    t_low = (topic or "all").lower().strip()

    # Refresh live payables if file exists
    try:
        payables_path = MEMORY_DIR / "accounts_payable.json"
        if payables_path.exists():
            with open(payables_path, "r", encoding="utf-8") as f:
                p_data = json.load(f)
                MASTER_KNOWLEDGE["sgc_textile_and_washing_hub"]["accounts_payable"] = p_data.get("payables", [])
    except Exception:
        pass

    if t_low in ["profile", "mukil", "personal", "credentials"]:
        return MASTER_KNOWLEDGE["profile"]
    elif t_low in ["projects", "vizro", "vizro_vertex", "botify"]:
        return MASTER_KNOWLEDGE["projects"]
    elif t_low in ["sgc", "textile", "washing_hub"]:
        return MASTER_KNOWLEDGE["sgc_textile_and_washing_hub"]
    elif t_low in ["payables", "bills_payable", "lakshmi", "eb"]:
        return {"accounts_payable": MASTER_KNOWLEDGE["sgc_textile_and_washing_hub"]["accounts_payable"]}
    elif t_low in ["drive", "drive_mesh", "nodes"]:
        return MASTER_KNOWLEDGE["drive_mesh"]
    elif t_low in ["pipelines", "flows", "workflows"]:
        return MASTER_KNOWLEDGE["workflow_pipelines"]
    else:
        return MASTER_KNOWLEDGE
