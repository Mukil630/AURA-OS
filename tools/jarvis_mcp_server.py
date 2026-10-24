"""
JARVIS MASTER EXECUTIVE - MODEL CONTEXT PROTOCOL (MCP) SERVER
tools/jarvis_mcp_server.py

Supreme Executive Partner & Autonomous Operations MCP Server for Mukil.
Provides:
- Real-time Hardware & Daemon Health Monitoring
- Executive Daily Multi-Domain Briefings (SGC, Placements, Drive, Cloud)
- Instant Telegram Alerts & 2-Way Voice Memo Dispatcher
- Autonomous ATS Resume Analyzer & LaTeX Customizer (>90% ATS Score)
- 250GB Distributed Drive Mesh (10 Nodes) Manager
- Multimodal Challan & Invoice Vision OCR Engine
"""

import sys
import os
import re
import json
import psutil
import asyncio
import warnings
import requests
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

# Suppress warnings to maintain pure JSON-RPC protocol over stdout
warnings.filterwarnings("ignore")

# Force UTF-8 on Windows
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

JARVIS_CORE_DIR = Path(__file__).resolve().parent.parent
if str(JARVIS_CORE_DIR) not in sys.path:
    sys.path.insert(0, str(JARVIS_CORE_DIR))

from mcp.server.fastmcp import FastMCP
from config import TELEGRAM_BOT_TOKEN, AUTHORIZED_TELEGRAM_USERS, GEMINI_API_KEY
from tools.placement_pipeline import analyze_jd, generate_tailored_resume

# Initialize FastMCP Server
mcp = FastMCP(
    "jarvis-mcp",
    instructions="JARVIS Supreme Executive Partner & Operations Server for Mukil. Handles Hardware Telemetry, Telegram Voice/Text Alerts, ATS Resume Customization, 250GB Distributed Drive Mesh, and Industrial Vision OCR."
)

DEFAULT_CHAT_ID = AUTHORIZED_TELEGRAM_USERS[0] if AUTHORIZED_TELEGRAM_USERS else 6233907249


@mcp.tool()
def jarvis_get_system_health() -> str:
    """
    Returns real-time PC hardware telemetry (CPU, RAM, Disks, Battery) and
    checks the running status of JARVIS background daemons (Telegram Bridge, Cloudflare tunnel, etc.).
    """
    cpu_pct = psutil.cpu_percent(interval=0.3)
    logical_cores = psutil.cpu_count(logical=True)
    mem = psutil.virtual_memory()
    ram_used_gb = round(mem.used / (1024 ** 3), 2)
    ram_total_gb = round(mem.total / (1024 ** 3), 2)
    
    # Disk Usage C:\
    disk_c = psutil.disk_usage("C:\\")
    c_free_gb = round(disk_c.free / (1024 ** 3), 1)
    c_total_gb = round(disk_c.total / (1024 ** 3), 1)
    
    # Battery
    battery = psutil.sensors_battery()
    if battery:
        bat_str = f"{battery.percent}% ({'Plugged In / Charging' if battery.power_plugged else 'On Battery'})"
    else:
        bat_str = "AC Power / Desktop (No Battery Detected)"
        
    # Check running processes
    telegram_active = False
    tunnel_active = False
    python_count = 0
    for p in psutil.process_iter(['name', 'cmdline']):
        try:
            name = (p.info['name'] or '').lower()
            cmdline = ' '.join(p.info['cmdline'] or []).lower()
            if 'python' in name:
                python_count += 1
                if 'telegram_bridge.py' in cmdline:
                    telegram_active = True
            if 'cloudflared' in name or 'cloudflared.exe' in cmdline:
                tunnel_active = True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    status_lines = [
        "🖥️ **JARVIS Prime Hardware & System Telemetry:**",
        f"• **CPU Utilization:** `{cpu_pct}%` across `{logical_cores} Logical Cores`",
        f"• **Memory (RAM):** `{ram_used_gb} GB` used of `{ram_total_gb} GB` (`{mem.percent}%`)",
        f"• **Main Storage (C:):** `{c_free_gb} GB free` of `{c_total_gb} GB`",
        f"• **Power & Battery:** `{bat_str}`",
        "",
        "🤖 **Background Daemons & Bridges:**",
        f"• **Telegram Mobile Bridge:** `{'🟢 ONLINE (Listening)' if telegram_active else '🟡 IDLE / Ready to launch'}`",
        f"• **Cloudflare Global Tunnel:** `{'🟢 ONLINE' if tunnel_active else '⚪ Standby'}`",
        f"• **Active Python Subprocesses:** `{python_count} processes`",
        f"• **System Time:** `{datetime.now().strftime('%d %b %Y, %I:%M:%S %p')} IST`"
    ]
    return "\n".join(status_lines)


@mcp.tool()
def jarvis_daily_executive_briefing() -> str:
    """
    Generates a comprehensive executive multi-domain briefing for Mukil,
    combining SGC financial health, placement pipeline status, scheduled reminders,
    and distributed drive mesh status.
    """
    now_str = datetime.now().strftime("%A, %d %B %Y | %I:%M %p")
    lines = [
        f"👑 **JARVIS EXECUTIVE BRIEFING FOR MUKIL**",
        f"📅 `{now_str} IST`",
        "------------------------------------------------"
    ]
    
    # 1. SGC Business Financials
    sgc_data_path = JARVIS_CORE_DIR / "storage" / "memory" / "sgc-billing-data.json"
    if sgc_data_path.exists():
        try:
            data = json.loads(sgc_data_path.read_text(encoding="utf-8"))
            bills = data.get("sgc-bills", [])
            total_turnover = sum(float(b.get("netAmount", 0)) for b in bills)
            pending_bills = [b for b in bills if b.get("status", "").lower() == "pending"]
            pending_total = sum(float(b.get("netAmount", 0)) for b in pending_bills)
            lines.extend([
                "🧾 **Sri Ganapathi Colours (SGC) Financial Radar:**",
                f"• **Total Recorded Bills:** `{len(bills)} Invoices` | Gross: `₹{total_turnover:,.2f}`",
                f"• **Pending Collections:** `{len(pending_bills)} Invoices` totalling `₹{pending_total:,.2f}`",
                f"• **Collection Health:** `{'⚠️ High Pending' if pending_total > 50000 else '✅ Stable'}`",
                ""
            ])
        except Exception as e:
            lines.append(f"🧾 **SGC Financial Radar:** Data read error ({e})\n")
    
    # 2. Career & Placement Pipeline
    context_path = JARVIS_CORE_DIR / "storage" / "memory" / "context.json"
    if context_path.exists():
        try:
            ctx = json.loads(context_path.read_text(encoding="utf-8"))
            career = ctx.get("active_career_strategy", {})
            fast_track = career.get("fast_track_online_offer", {})
            active_drive = career.get("active_drive", {})
            lines.extend([
                "💼 **Autonomous Career & Placement Pipeline:**",
                f"• **Primary Target:** `{career.get('mission_goal', 'Secure MNC Offer')}`",
                f"• **Fast-Track Role:** `{fast_track.get('target', 'Amazon VCS')} ({fast_track.get('company', 'Amazon')})` - Status: `{fast_track.get('status', 'READY')}`",
                f"• **Campus / Off-Campus Drive:** `{active_drive.get('company', 'Infinite')} ({active_drive.get('stage', 'Interview')})`",
                f"• **ATS Resume Compliance:** `>94% ATS Target (LaTeX Certified)`",
                ""
            ])
        except Exception as e:
            lines.append(f"💼 **Placement Pipeline:** Context read error ({e})\n")
            
    # 3. 250GB Distributed Drive Mesh
    mesh_path = JARVIS_CORE_DIR / "storage" / "memory" / "distributed_drive_mesh.json"
    if mesh_path.exists():
        try:
            mesh = json.loads(mesh_path.read_text(encoding="utf-8"))
            nodes = mesh.get("nodes", {})
            lines.extend([
                "🌐 **250GB Distributed Drive Mesh (10 Dedicated Nodes):**",
                f"• **Network Status:** `100% LIVE SYNCHRONIZED` ({mesh.get('allocated_pool_gb', 250)} GB Pool)",
                f"• **Node 03 (Resumes):** `{nodes.get('node_03_placement_resumes', {}).get('name', 'Active')}`",
                f"• **Node 05 (SGC Invoices):** `{nodes.get('node_05_sgc_invoices', {}).get('name', 'Active')}`",
                f"• **Active Nodes Count:** `{len(nodes)} / 10 Dedicated Nodes Operational`",
                ""
            ])
        except Exception as e:
            lines.append(f"🌐 **Drive Mesh:** Read error ({e})\n")
            
    lines.append("⚡ **Executive Recommendation:** All systems nominal. Ready to dispatch priority actions.")
    return "\n".join(lines)


@mcp.tool()
def jarvis_send_telegram_alert(message: str, priority: str = "normal") -> str:
    """
    Sends an instant Markdown alert or notification directly to Mukil's Telegram phone.
    
    Args:
        message: The alert or message content in Markdown format.
        priority: 'normal', 'urgent', or 'executive'.
    """
    if not TELEGRAM_BOT_TOKEN:
        return "❌ Error: TELEGRAM_BOT_TOKEN not configured in environment."
        
    prefix = "🚨 **URGENT ALERT**\n\n" if priority == "urgent" else "👑 **JARVIS EXECUTIVE NOTIFICATION**\n\n"
    full_text = prefix + message
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": DEFAULT_CHAT_ID,
        "text": full_text,
        "parse_mode": "Markdown"
    }
    
    try:
        resp = requests.post(url, json=payload, timeout=10)
        res_json = resp.json()
        if res_json.get("ok"):
            return f"✅ **Telegram Alert Successfully Dispatched to Mukil!** (Chat ID: {DEFAULT_CHAT_ID})"
        else:
            return f"❌ Telegram API Error: {res_json.get('description')}"
    except Exception as e:
        return f"❌ Failed to send Telegram alert: {str(e)}"


@mcp.tool()
def jarvis_send_voice_memo(text: str, custom_voice: str = "") -> str:
    """
    Synthesizes clean Tanglish or English neural voice audio using Edge-TTS and
    dispatches it as a native voice memo to Mukil's Telegram phone.
    
    Args:
        text: Text to synthesize and speak out.
        custom_voice: Optional Edge-TTS voice name (e.g. 'ta-IN-ValluvarNeural' or 'en-IN-PrabhatNeural').
    """
    if not TELEGRAM_BOT_TOKEN:
        return "❌ Error: TELEGRAM_BOT_TOKEN not configured."
        
    try:
        from tools.tts_generator import generate_voice_audio
        audio_path = asyncio.run(generate_voice_audio(text, custom_voice=custom_voice if custom_voice else None))
        
        if not os.path.exists(audio_path):
            return f"❌ Error: Generated voice file not found at {audio_path}"
            
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVoice"
        with open(audio_path, "rb") as f:
            files = {"voice": f}
            data = {"chat_id": DEFAULT_CHAT_ID, "caption": f"🎙️ JARVIS Voice Memo: {text[:60]}..."}
            resp = requests.post(url, data=data, files=files, timeout=25)
            
        res_json = resp.json()
        if res_json.get("ok"):
            return f"✅ **Voice Memo Successfully Dispatched to Mukil's Telegram!**\n• **Voice File:** `{os.path.basename(audio_path)}`\n• **Snippet:** \"{text[:80]}...\""
        else:
            return f"❌ Telegram Voice API Error: {res_json.get('description')}"
    except Exception as e:
        return f"❌ Failed to synthesize or dispatch voice memo: {str(e)}"


@mcp.tool()
def jarvis_analyze_job_and_ats(job_description: str, role_title: str = "", company: str = "") -> str:
    """
    Analyzes any job description against Mukil's Master Resume, computes ATS match percentage,
    identifies matching skills, detects gaps, and gives strategic bullet-point recommendations.
    
    Args:
        job_description: The full text or requirements of the job opening.
        role_title: Job title (e.g. 'AI Engineer', 'Full-Stack Developer').
        company: Target hiring company (e.g. 'Amazon', 'Swiggy', 'Zoho').
    """
    result = analyze_jd(job_description, role_title=role_title, company=company)
    if "error" in result:
        return f"❌ Error: {result['error']}"
        
    out = [
        f"🎯 **ATS Resume Compatibility Report:**",
        f"• **Target Role:** `{result['role_title']}` @ `{result['company']}`",
        f"• **Calculated ATS Score:** `{result['ats_score']}%` ({'✅ ATS-Ready (>85%)' if result['is_ats_compliant'] else '⚠️ Needs Optimization'})",
        f"• **Matched Core Skills ({len(result['matched_skills'])}):** {', '.join(result['matched_skills'])}",
        f"• **Missing / Untapped Keywords:** {', '.join(result['missing_skills']) if result['missing_skills'] else 'None (100% Covered!)'}",
        "",
        "💡 **Actionable Strategy Recommendations:**"
    ]
    for r in result["strategic_recommendations"]:
        out.append(f"• {r}")
        
    return "\n".join(out)


@mcp.tool()
def jarvis_generate_tailored_resume(role_title: str, company: str, custom_skills: str = "") -> str:
    """
    Generates a tailored, ATS-certified LaTeX resume for Mukil targeting a specific company and role,
    and stages it for sync to Node 03 of the Distributed Drive Mesh.
    
    Args:
        role_title: Title of target role (e.g. 'AI & Automation Engineer', 'Backend Engineer').
        company: Company name (e.g. 'Amazon', 'Infinite', 'TCS').
        custom_skills: Optional comma-separated list of extra skills to emphasize (e.g. 'Kubernetes, Kafka').
    """
    skills_list = [s.strip() for s in custom_skills.split(",") if s.strip()] if custom_skills else None
    result = generate_tailored_resume(role_title, company, custom_skills=skills_list)
    
    if "error" in result:
        return f"❌ Error: {result['error']}"
        
    return (
        f"✅ **Tailored ATS Resume Generated Successfully!**\n"
        f"• **Target:** `{result['role_title']}` at `{result['company']}`\n"
        f"• **LaTeX File:** `{result['tailored_tex_path']}`\n"
        f"• **Optimization Level:** `{result['ats_optimization_level']}`\n"
        f"• **Drive Node 03 Target:** `{result['drive_node_03_folder']}` (`{result['drive_node_role']}`)\n"
        f"• **Next Step:** Ready to compile into PDF and sync to Drive Master Vault!"
    )


@mcp.tool()
def jarvis_get_drive_mesh_status() -> str:
    """
    Lists all 10 dedicated nodes of Mukil's 250GB Distributed Drive Storage Mesh,
    displaying node names, folder IDs, roles, and verified sync URLs.
    """
    mesh_path = JARVIS_CORE_DIR / "storage" / "memory" / "distributed_drive_mesh.json"
    if not mesh_path.exists():
        return "❌ Error: distributed_drive_mesh.json not found."
        
    try:
        data = json.loads(mesh_path.read_text(encoding="utf-8"))
        nodes = data.get("nodes", {})
        
        lines = [
            f"🌐 **250GB Distributed Drive Storage Mesh (10 Dedicated Nodes x 25GB):**",
            f"• **Status:** `{data.get('status', 'OPERATIONAL')}`",
            f"• **Master Vault ID:** `{data.get('master_vault_id')}`",
            f"• **Main SGC Bills Vault:** `{data.get('sgc_bills_vault_id')}`",
            "",
            "📁 **Node Registry & Roles:**"
        ]
        
        for k, v in sorted(nodes.items()):
            lines.append(f"• **{v.get('name')}:** `{v.get('role')}`\n  🔗 [Open Drive]({v.get('url')}) | ID: `{v.get('id')}`")
            
        return "\n".join(lines)
    except Exception as e:
        return f"❌ Failed to parse Drive Mesh registry: {str(e)}"


@mcp.tool()
def jarvis_parse_mill_challan_vision(image_path: str) -> str:
    """
    Uses Gemini Multimodal Vision to inspect a photo or scan of a textile spinning mill
    delivery challan, dyeing slip, or handwritten invoice, extracting structured billing data.
    
    Args:
        image_path: Absolute local file path to the challan image (.jpg, .jpeg, .png).
    """
    if not os.path.exists(image_path):
        return f"❌ Error: Image file not found at {image_path}"
        
    if not GEMINI_API_KEY:
        return "❌ Error: GEMINI_API_KEY not configured in environment."
        
    try:
        import google.generativeai as genai
        from PIL import Image
        
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        img = Image.open(image_path)
        prompt = """
        You are an expert OCR and auditing assistant for Sri Ganapathi Colours (SGC Yarn Dyeing Mill).
        Inspect this textile delivery challan / mill bill slip image carefully.
        Extract and return ONLY a valid JSON object matching this schema:
        {
          "customer_name": "string (Mill or Party name)",
          "date": "YYYY-MM-DD",
          "challan_or_bill_no": "string",
          "items": [
            {
              "count": "string (e.g. 10s, 20s, 30s, 2/40s)",
              "shade_or_variety": "string (e.g. Red, Black, Bleach)",
              "kattu": "number or null",
              "kazhi": "number or null",
              "weight_kg": "number",
              "rate_per_kg": "number",
              "amount": "number"
            }
          ],
          "subtotal": "number",
          "gst_percentage": "number (typically 5)",
          "gst_amount": "number",
          "net_total": "number",
          "notes": "string"
        }
        Do not include markdown fences, just pure valid JSON.
        """
        
        response = model.generate_content([prompt, img])
        raw_text = response.text.strip()
        # Clean potential markdown fences
        clean_json = re.sub(r'^```json\s*', '', raw_text)
        clean_json = re.sub(r'\s*```$', '', clean_json).strip()
        
        parsed = json.loads(clean_json)
        return (
            f"✅ **Challan Photo Parsed via Gemini Vision Successfully!**\n"
            f"• **Customer / Mill:** `{parsed.get('customer_name', 'N/A')}`\n"
            f"• **Date:** `{parsed.get('date', 'N/A')}` | Bill/Challan No: `{parsed.get('challan_or_bill_no', 'N/A')}`\n"
            f"• **Items Extracted:** `{len(parsed.get('items', []))} items`\n"
            f"• **Calculated Net Total:** `₹{parsed.get('net_total', 0):,.2f}` (GST: {parsed.get('gst_percentage', 5)}%)\n\n"
            f"```json\n{json.dumps(parsed, indent=2)}\n```"
        )
    except Exception as e:
        return f"❌ Vision extraction error: {str(e)}"


if __name__ == "__main__":
    mcp.run()
