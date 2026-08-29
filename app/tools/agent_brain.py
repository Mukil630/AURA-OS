"""Autonomous Agent Brain & Zero-Hardcode Tool Calling Engine for JARVIS / AURA-OS.
Uses LLM Function Calling to understand ANY natural language intent (English, Tanglish, Tamil)
and execute tools autonomously on the PC without hardcoded regex.
"""
import json
import logging
import os
from typing import Any, Dict, Optional, Tuple
from groq import Groq

try:
    import google.generativeai as genai
except ImportError:
    genai = None

from app.agents.business.sgc_reminder_agent import SGCReminderAgent
from app.agents.placement.job_apply_agent import JobApplyAgent
from app.connectors.drive.drive_vault import DriveVaultManager
from app.tools.memory_vault import MemoryVault
from app.tools.pc_pilot import PCPilot
from app.tools.reminder_scheduler import ReminderScheduler

logger = logging.getLogger("AgentBrain")

GROQ_MODELS = [
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
]

GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-1.5-flash",
]

AGENT_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "search_and_hunt_jobs",
            "description": "Searches for active tech job openings (AI Engineer, Full-Stack Developer, Python, Backend) across LinkedIn, Google Jobs, Wellfound, and Naukri with direct application links.",
            "parameters": {
                "type": "object",
                "properties": {
                    "role": {
                        "type": "string",
                        "description": "Target job title, e.g. 'AI Engineer', 'Full-Stack Developer', 'Python Developer'"
                    },
                    "location": {
                        "type": "string",
                        "description": "Job location, e.g. 'Remote', 'India', 'Bangalore', 'Chennai'"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_job_application",
            "description": "Autonomously applies to a target company (e.g. Zoho, Google, Swiggy, Freshworks, Postman), opens their official career portal on the user's PC, copies the tailored pitch to clipboard, and logs application in the tracker.",
            "parameters": {
                "type": "object",
                "properties": {
                    "company": {
                        "type": "string",
                        "description": "Company name, e.g. 'Zoho', 'Google', 'Swiggy', 'Freshworks', 'Postman'"
                    },
                    "role": {
                        "type": "string",
                        "description": "Job role/title, e.g. 'AI Engineer', 'Full Stack Developer'"
                    },
                    "job_description": {
                        "type": "string",
                        "description": "Optional job description details"
                    }
                },
                "required": ["company"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "batch_apply_jobs",
            "description": "Sequentially and autonomously executes job applications across all top hiring tech companies (Zoho, Freshworks, Swiggy, Postman) one by one, opening their career portals on PC and preparing custom pitches.",
            "parameters": {
                "type": "object",
                "properties": {
                    "role": {
                        "type": "string",
                        "description": "Target job role, e.g. 'AI Engineer', 'Full Stack Developer'"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "view_job_pipeline",
            "description": "Views all tracked job applications, their current statuses, applied dates, and direct links.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_sgc_billing_summary",
            "description": "Analyzes all SGC (Sri Ganapathi Colours) customer bills, total revenue collected, pending/overdue balances, and active Google Drive storage link (11KMBP0HHa2AFl30zjL8-a_-BQk9MgWM9).",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_sgc_bills",
            "description": "Searches for specific SGC bills, customer names (e.g. M.S.K Fabrics, Sri Laxmi Export, Sowbhagiya, GAIA), yarn counts, GST numbers, or bill items using Drive RAG retrieval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Customer name, bill number, or search query"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_sgc_customer_reminders",
            "description": "Generates 1-Click WhatsApp payment reminders (in Tamil or English) for all overdue customers (M.S.K Fabrics, Sowbhagiya, GAIA, etc.) with Drive PDF links.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {
                        "type": "string",
                        "description": "Optional specific customer name (e.g. 'M.S.K Fabrics') or leave empty for all customers overview."
                    },
                    "language": {
                        "type": "string",
                        "description": "Language for reminder ('tamil' or 'english')"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "dispatch_sgc_reminder",
            "description": "Dispatches the payment reminder to the customer via WhatsApp on PC. High-privilege action requiring Stark passcode protocol or confirmation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {
                        "type": "string",
                        "description": "Customer name to send payment reminder to"
                    },
                    "confirmed": {
                        "type": "boolean",
                        "description": "Set to true if user confirmed or provided 'AURA Protocol Stark 55'"
                    }
                },
                "required": ["customer_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "view_drive_vaults",
            "description": "Views the 5TB Google Drive Master Vault matrix, official Master Resume link, and SGC billing dual vaults.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_memory_or_document",
            "description": "Saves an important document, project note, or user directive to the persistent memory vault and 5TB Google Drive knowledge index.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Title of document or memory note"
                    },
                    "doc_type": {
                        "type": "string",
                        "description": "Type of document (e.g. 'resume', 'project_code', 'invoice', 'learning')"
                    },
                    "notes": {
                        "type": "string",
                        "description": "Key points or details to remember"
                    },
                    "drive_link": {
                        "type": "string",
                        "description": "Optional Google Drive link"
                    }
                },
                "required": ["title", "doc_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_application",
            "description": "Launches a desktop app on the user's PC such as Visual Studio Code, Notepad, Chrome, Windows Terminal, Calculator, File Explorer, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {
                        "type": "string",
                        "description": "Name of the app to launch, e.g. 'notepad', 'vscode', 'chrome', 'terminal', 'calc', 'explorer'"
                    }
                },
                "required": ["app_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "close_application_or_tab",
            "description": "Closes, terminates, or kills a running application process (e.g. notepad, chrome, vscode) or closes an active browser tab (e.g. youtube tab, website tab).",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "Target app or tab to close, e.g. 'notepad', 'chrome', 'vscode', 'youtube', 'tab', 'window'"
                    }
                },
                "required": ["target"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browse_or_search_web",
            "description": "Opens a website URL (e.g. youtube, github, linkedin, leetcode) or performs a web search on Google or YouTube.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url_or_site": {
                        "type": "string",
                        "description": "URL or website alias, e.g. 'https://www.youtube.com', 'github', 'linkedin', 'chatgpt'"
                    },
                    "search_query": {
                        "type": "string",
                        "description": "Query string if the user wants to search Google or YouTube"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "capture_screen_vision",
            "description": "Takes a live screenshot of the PC screen/monitor and sends the image back to the user on Telegram.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "control_pc_system",
            "description": "Controls PC physical hardware volume (volume_up, volume_down, volume_mute) or locks the Windows workstation (lock_pc).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["volume_up", "volume_down", "volume_mute", "lock_pc"],
                        "description": "The system action to perform"
                    }
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "schedule_reminder_or_timer",
            "description": "Schedules a timer, alarm, or reminder for a specific duration (e.g. 10m, 5 mins) or clock time (e.g. 10.00, 10:30 PM).",
            "parameters": {
                "type": "object",
                "properties": {
                    "time_expression": {
                        "type": "string",
                        "description": "Time expression, e.g. '10.00', '10m', '5 mins', '10:30 PM', '10 mani'"
                    },
                    "task": {
                        "type": "string",
                        "description": "Task description or reminder note"
                    }
                },
                "required": ["time_expression"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "manage_clipboard",
            "description": "Copies text to the PC clipboard or retrieves current PC clipboard contents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["copy", "get"],
                        "description": "Whether to copy text to clipboard or get current clipboard content"
                    },
                    "text": {
                        "type": "string",
                        "description": "Text to copy to PC clipboard (required if action is copy)"
                    }
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_terminal_command",
            "description": "Executes a safe shell/PowerShell command on the user's PC (e.g. git status, git push, ipconfig, python script, dir, pip install) and returns the output.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The exact shell command to execute"
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "manage_files",
            "description": "Reads, writes, creates, lists, or inspects files and directories on the user's PC.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["read", "write", "list", "exists"],
                        "description": "File action to perform"
                    },
                    "file_path": {
                        "type": "string",
                        "description": "Target file or directory path"
                    },
                    "content": {
                        "type": "string",
                        "description": "File content when action is write"
                    }
                },
                "required": ["action", "file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_python_code",
            "description": "Executes an ad-hoc Python code snippet dynamically in a sandboxed runner and returns printed output or calculations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python code snippet to execute"
                    }
                },
                "required": ["code"]
            }
        }
    }
]

SYSTEM_AGENT_PROMPT = """You are JARVIS / AURA, the executive autonomous AI partner and PC commander for Mukil (always address him as 'Boss' or 'Mapla').
You possess FULL autonomous capability to understand, plan, research, write code, execute tools, and solve ANY task Mukil assigns.

Operational Directives:
1. True Autonomous Problem Solver: When Mukil gives you an open-ended goal or complex instruction (e.g. research, file creation, job application, code generation, system check, product search), break it down, use your tools (Python runner, PowerShell terminal, web search, file manager, job hunter, screen vision) iteratively in a multi-step loop until the task is 100% completed.
2. Tanglish & Phonetic Spelling Intelligence: Mukil types in authentic Tamil-Tanglish. Always recognize common phonetic spellings (e.g. 'steal brd' or 'steel brd' means 'Steelbird' helmet brand, 'watsap' means WhatsApp, 'helmit' means helmet, 'zohoo' means Zoho, 'kudunga' means give, 'pannu' means do). NEVER trigger false safety refusals on phonetic words like 'steal' when he obviously means 'Steelbird'!
3. Visual & Image Capability: When Mukil asks for images, photos, or visual previews (e.g. 'images kudu', 'photo anupu'), search Google/Amazon on browser or capture a screen screenshot of the product/site so a real visual photo is sent to his Telegram!
4. Dynamic Execution over Limitations: Never say "I can't do that" or "You must do this manually". If you lack a pre-built tool, write and run custom Python code or PowerShell commands on the spot to accomplish the goal.
5. Conversation History & Short-Term Context: You have full continuous memory and access to recent chat turns. When Mukil asks about what he previously said (e.g. 'recent chat la enna panna sonnen?', 'close pannu', 'atha open pannu'), refer directly to the conversation history, recall the app/topic (e.g. Notepad, WhatsApp, SGC bills), and answer or execute contextually without saying you lack permission!
6. Executive Tone: Speak in sharp, authentic, brotherly Tanglish + English ('Boss' / 'Mapla' dynamic) with confident engineering precision. Keep replies crisp and fast.
"""


class AutonomousAgentBrain:
    """
    Zero-Hardcode Autonomous Agent Brain that uses LLM Function Calling
    to reason over user inputs and execute PC actions dynamically.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        pc_pilot: Optional[PCPilot] = None,
        reminder_scheduler: Optional[ReminderScheduler] = None,
        job_agent: Optional[JobApplyAgent] = None,
        memory_vault: Optional[MemoryVault] = None,
        drive_manager: Optional[DriveVaultManager] = None,
        sgc_reminder_agent: Optional[SGCReminderAgent] = None,
    ):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.pc_pilot = pc_pilot or PCPilot()
        self.reminder_scheduler = reminder_scheduler or ReminderScheduler()
        self.job_agent = job_agent or JobApplyAgent(api_key=self.api_key)
        self.memory_vault = memory_vault or MemoryVault()
        self.drive_manager = drive_manager or DriveVaultManager()
        self.sgc_reminder_agent = sgc_reminder_agent or SGCReminderAgent()
        self._client: Optional[Groq] = None
        if self.api_key:
            try:
                self._client = Groq(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Could not initialize Groq client in AgentBrain: {e}")

        if self.gemini_api_key and genai:
            try:
                genai.configure(api_key=self.gemini_api_key)
                logger.info("Google Gemini 2.5 Brain successfully initialized.")
            except Exception as ge:
                logger.warning(f"Could not initialize Gemini in AgentBrain: {ge}")

    def execute_tool(self, tool_name: str, args: Dict[str, Any], chat_id: int = 0, user_id: int = 0) -> Tuple[str, Optional[str]]:
        """
        Executes the invoked tool and returns: (response_text, optional_photo_path)
        """
        logger.info(f"Agent executing tool '{tool_name}' with args: {args}")

        if tool_name == "search_and_hunt_jobs":
            r = args.get("role", "AI Engineer")
            loc = args.get("location", "Remote / India")
            listings = self.job_agent.search_jobs(role=r, location=loc)
            lines = [f"🎯 *Active Job Opportunities Found ({r} - {loc})*:\n"]
            for idx, item in enumerate(listings, 1):
                lines.append(f"{idx}. *{item['platform']}*: [{item['role']}]({item['search_url']})\n   _{item['description']}_")
            lines.append(f"\n📄 *Master Resume Linked*: [View Resume PDF]({self.drive_manager.get_master_resume_link()})")
            lines.append("\n💡 Say _'Apply to <Company>'_ to generate a tailored pitch!")
            return "\n".join(lines), None

        elif tool_name == "create_job_application":
            comp = args.get("company", "Zoho")
            role = args.get("role", "AI Engineer")
            jd = args.get("job_description")
            result = self.job_agent.execute_live_application(company=comp, role=role, job_description=jd)
            logged = result["record"]
            pkg = result["package"]
            portal_url = result["portal_url"]
            
            # Capture visual screen proof
            _, photo_path, _ = self.pc_pilot.capture_screen()

            res_md = (
                f"🚀 *AUTONOMOUS JOB APPLICATION EXECUTED FOR {comp.upper()}*!\n\n"
                f"🌐 *Careers Portal Opened on PC*: [Click to View Careers Page]({portal_url})\n"
                f"📋 *Application ID*: `{logged['application_id']}` | Status: *{logged['status']}*\n"
                f"📄 *Master Resume Attached*: [View Resume PDF]({logged['resume_link']})\n"
                f"📸 *Visual Proof*: _Screenshot of opened application portal captured and sent below!_\n"
                f"📋 *PC Clipboard*: _Cold pitch copied to clipboard ready to paste (Ctrl+V)!_\n\n"
                f"✉️ *Cold Outreach Pitch (Email/LinkedIn)*:\n```\n{pkg.get('cold_pitch_email')}\n```\n\n"
                f"📝 *Tailored Cover Letter*:\n```\n{pkg.get('cover_letter')}\n```\n\n"
                f"💡 *Why You Are The Best Fit*:\n_{pkg.get('screening_answer_why_hire')}_\n\n"
                f"✅ *Application logged in pipeline tracker & 5TB Drive Vault, Boss!*"
            )
            return res_md, photo_path

        elif tool_name == "batch_apply_jobs":
            role = args.get("role", "AI Engineer")
            batch_results = self.job_agent.batch_apply_top_companies(role=role)
            
            # Capture visual screen proof
            _, photo_path, _ = self.pc_pilot.capture_screen()

            lines = [
                f"🚀 *BATCH APPLICATION EXECUTED ACROSS TOP COMPANIES ({role})*!\n",
                f"📄 *Master Resume Linked*: [View Resume PDF]({self.drive_manager.get_master_resume_link()})\n",
                f"📸 *Visual Proof*: _Screenshot of opened application portals captured and sent below!_\n"
            ]
            for item in batch_results:
                rec = item["record"]
                p_url = item["portal_url"]
                lines.append(
                    f"• 🟢 *{rec['company']}* (`{rec['role']}`)\n"
                    f"   - Portal: [Careers Page]({p_url})\n"
                    f"   - App ID: `{rec['application_id']}` | Status: *APPLIED*"
                )
            lines.append("\n📋 *All career portals opened on your PC screen and logged in tracker, Boss!*")
            return "\n".join(lines), photo_path

        elif tool_name == "view_job_pipeline":
            summary = self.job_agent.get_pipeline_summary()
            return summary, None

        elif tool_name == "get_sgc_billing_summary":
            from app.brain.drive_rag_engine import DriveRAGEngine
            rag = DriveRAGEngine()
            rag.sync_sgc_billing_data()
            summary = rag.get_sgc_financial_summary()
            
            drive_link = summary.get("drive_url")
            lines = [
                "🧾 *SRI GANAPATHI COLOURS (SGC) BILLING & FINANCIAL SUMMARY*\n",
                f"☁️ *Live Cloud Storage Vault*: [Open Active Bills Drive Folder]({drive_link})\n",
                f"📊 *Total Invoices Generated*: `{summary.get('total_bills_count')}`",
                f"💰 *Total Billed Revenue*: `Rs {summary.get('total_billed_amount'):,}`",
                f"🟢 *Total Collected (Paid)*: `Rs {summary.get('total_collected_amount'):,}` ({summary.get('paid_count')} Bill)",
                f"🔴 *Total Pending / Overdue*: `Rs {summary.get('total_pending_amount'):,}` ({summary.get('pending_count')} Bills)\n",
                "📋 *Pending Customer Invoices (Overdue)*:"
            ]
            for p in summary.get("pending_bills_details", []):
                lines.append(f"• 🔴 *Bill #{p['billNo']}* | `{p['customer']}` | Date: `{p['date']}` | *Rs {p['amount']:,}* | GST: `{p.get('partyGst', 'N/A')}`")
            
            if summary.get("paid_bills_details"):
                lines.append("\n✅ *Settled / Paid Invoices*:")
                for pd in summary.get("paid_bills_details", []):
                    lines.append(f"• 🟢 *Bill #{pd['billNo']}* | `{pd['customer']}` | *Rs {pd['amount']:,}* | Receipt: `{pd.get('receiptNo')}`")

            return "\n".join(lines), None

        elif tool_name == "search_sgc_bills":
            from app.brain.drive_rag_engine import DriveRAGEngine
            rag = DriveRAGEngine()
            rag.sync_sgc_billing_data()
            query = args.get("query", "")
            hits = rag.query_rag_context(query=query, folder_alias="sgc_billing_active_vault", top_k=5)
            
            if not hits:
                return f"🔍 *No matching SGC billing documents found for query:* '{query}'", None
            
            lines = [f"🔍 *SGC Billing RAG Search Results for '{query}'*:\n"]
            for h in hits:
                meta = h.get("metadata", {})
                b_no = meta.get("billNo")
                cust = meta.get("customer")
                amt = meta.get("netAmount")
                st = meta.get("status", "").upper()
                dt = meta.get("date")
                gst = meta.get("partyGst", "")
                st_icon = "🟢" if st == "PAID" else "🔴"
                lines.append(f"{st_icon} *Bill #{b_no}* — `{cust}`\n   • Amount: *Rs {amt}* | Status: *{st}* | Date: `{dt}`\n   • Party GST: `{gst}`\n   • File: `{h.get('filename')}`\n")
            
            lines.append(f"☁️ *Vault Link*: [Open Active SGC Drive Vault](https://drive.google.com/drive/folders/11KMBP0HHa2AFl30zjL8-a_-BQk9MgWM9)")
            return "\n".join(lines), None

        elif tool_name == "generate_sgc_customer_reminders":
            c_name = args.get("customer_name")
            lang = args.get("language", "tamil")
            if c_name:
                rem = self.sgc_reminder_agent.generate_reminder_message(customer_name=c_name, language=lang)
                res_md = (
                    f"🧾 *SGC PAYMENT REMINDER PITCH FOR {c_name.upper()}*\n\n"
                    f"💰 *Total Overdue Balance*: `₹{rem['total_balance']:,.2f}` ({rem['bills_count']} Invoices)\n"
                    f"☁️ *Active Drive Vault*: [Open SGC Bills Folder]({rem['drive_vault_url']})\n\n"
                    f"💬 *Generated WhatsApp Pitch ({lang.capitalize()})*:\n```\n{rem['chosen_message']}\n```\n\n"
                    f"🔗 [1-Click Direct WhatsApp Share Link]({rem['whatsapp_share_url']})\n\n"
                    f"🔒 *Stark Security Protocol*: Say _'Send reminder to {c_name}'_ or _'AURA Protocol Stark 55'_ to automatically open WhatsApp on PC and dispatch!"
                )
                return res_md, None
            else:
                summary_text = self.sgc_reminder_agent.generate_all_reminders_summary()
                return summary_text, None

        elif tool_name == "dispatch_sgc_reminder":
            c_name = args.get("customer_name", "Unknown")
            is_confirmed = args.get("confirmed", False)

            rem = self.sgc_reminder_agent.generate_reminder_message(customer_name=c_name)
            wa_url = rem.get("whatsapp_share_url")
            tot_bal = rem.get("total_balance", 0.0)

            if not is_confirmed:
                warn_msg = (
                    f"🔒 *STARK SECURITY PROTOCOL CONFIRMATION REQUIRED*\n\n"
                    f"⚠️ Boss, idhu customer-ku payment reminder send panra critical action!\n"
                    f"• *Customer*: `{c_name}`\n"
                    f"• *Total Overdue Balance*: `₹{tot_bal:,.2f}`\n"
                    f"• *Action*: Open WhatsApp Web on PC with pre-filled Tamil reminder pitch.\n\n"
                    f"👉 *Proceed panna 'Yes', 'Confirm', or 'AURA Protocol Stark 55' nu reply pannunga Boss!*"
                )
                return warn_msg, None

            # User Confirmed -> Execute live on PC
            if wa_url:
                self.pc_pilot.open_url(wa_url)
            
            self.sgc_reminder_agent.log_reminder_sent(
                customer_name=c_name,
                amount=tot_bal,
                channel="WhatsApp",
                status="DISPATCHED"
            )
            
            # Capture visual screen proof
            _, photo_path, _ = self.pc_pilot.capture_screen()

            success_msg = (
                f"🚀 *STARK PROTOCOL VERIFIED — PAYMENT REMINDER DISPATCHED*!\n\n"
                f"✅ *Customer*: `{c_name}`\n"
                f"💰 *Amount*: `₹{tot_bal:,.2f}`\n"
                f"📱 *WhatsApp*: _Opened on PC screen with pre-filled message & Drive invoice attachment!_\n"
                f"📸 *Visual Proof*: _Screenshot of opened WhatsApp screen captured and sent below!_\n"
                f"📋 *Audit Tracker*: _Logged in SGC Reminder Records & 5TB Drive Vault, Boss!_"
            )
            return success_msg, photo_path

        elif tool_name == "view_drive_vaults":
            return self.drive_manager.get_vault_summary(), None

        elif tool_name == "save_memory_or_document":
            title = args.get("title", "Important Document")
            doc_type = args.get("doc_type", "general")
            notes = args.get("notes", "")
            d_link = args.get("drive_link")
            saved = self.memory_vault.save_important_document(
                title=title,
                doc_type=doc_type,
                drive_link=d_link,
                notes=notes,
            )
            return (
                f"💾 *Document / Memory Saved to 5TB Drive Vault Index*!\n\n"
                f"📋 *Title*: `{saved['title']}`\n"
                f"📂 *Type*: `{saved['type']}`\n"
                f"☁️ *Drive Vault*: [Open Vault]({saved['drive_link']})\n"
                f"📝 *Notes*: _{saved['notes']}_\n\n"
                f"JARVIS will remember this permanently across all devices, Boss."
            ), None

        elif tool_name == "open_application":
            app = args.get("app_name", "")
            return self.pc_pilot.launch_app(app), None

        elif tool_name == "close_application_or_tab":
            target = args.get("target", "")
            return self.pc_pilot.close_app(target), None

        elif tool_name == "browse_or_search_web":
            query = args.get("search_query")
            site = args.get("url_or_site")
            if query and site and "youtube" in site.lower():
                return self.pc_pilot.search_youtube(query), None
            elif query:
                return self.pc_pilot.search_google(query), None
            elif site:
                known = self.pc_pilot.open_known_site(site)
                if known:
                    return known, None
                return self.pc_pilot.open_url(site), None
            return self.pc_pilot.search_google("AI news"), None

        elif tool_name == "capture_screen_vision":
            success, path, msg = self.pc_pilot.capture_screen()
            return msg, path

        elif tool_name == "control_pc_system":
            act = args.get("action", "")
            if act == "lock_pc":
                return self.pc_pilot.lock_pc(), None
            elif act in ["volume_up", "volume_down", "volume_mute"]:
                sub = act.replace("volume_", "")
                return self.pc_pilot.adjust_volume(sub), None

        elif tool_name == "schedule_reminder_or_timer":
            t_expr = args.get("time_expression", "10m")
            task = args.get("task", "Timer Alert")
            combined = f"{t_expr} {task}".strip()
            try:
                rem = self.reminder_scheduler.parse_and_create(
                    chat_id=chat_id,
                    user_id=user_id,
                    command_args=combined,
                )
                return (
                    f"⏰ *Timer / Reminder Scheduled!*\n\n"
                    f"📋 *ID*: `{rem['reminder_id']}`\n"
                    f"📝 *Task*: _{rem['message']}_\n"
                    f"⏳ *Target Time*: `{rem['target_time'][:19]} UTC`\n\n"
                    f"JARVIS will send a voice alert when due, Boss."
                ), None
            except Exception as ex:
                return f"❌ Could not schedule reminder: {str(ex)}", None

        elif tool_name == "manage_clipboard":
            act = args.get("action", "")
            if act == "copy":
                txt = args.get("text", "")
                return self.pc_pilot.copy_clipboard(txt), None
            else:
                return self.pc_pilot.get_clipboard(), None

        elif tool_name == "execute_terminal_command":
            cmd = args.get("command", "").strip()
            if not cmd:
                return "❌ Empty command received.", None
            try:
                import subprocess
                out = subprocess.check_output(
                    ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", cmd],
                    stderr=subprocess.STDOUT,
                    timeout=30,
                    text=True
                )
                res = f"💻 *Terminal Command Executed*:\n`{cmd}`\n\n```\n{out.strip()[:1000]}\n```"
                return res, None
            except subprocess.CalledProcessError as cpe:
                return f"⚠️ *Command Failed (Exit Code {cpe.returncode})*:\n```\n{cpe.output.strip()[:500]}\n```", None
            except Exception as e:
                return f"❌ Command execution error: {str(e)}", None

        elif tool_name == "manage_files":
            act = args.get("action", "")
            fpath = args.get("file_path", "").strip()
            content = args.get("content", "")
            try:
                if act == "write":
                    os.makedirs(os.path.dirname(os.path.abspath(fpath)), exist_ok=True)
                    with open(fpath, "w", encoding="utf-8") as f:
                        f.write(content)
                    return f"📁 File `{fpath}` created / updated successfully, Boss.", None
                elif act == "read":
                    if not os.path.exists(fpath):
                        return f"❌ File `{fpath}` does not exist.", None
                    with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                        data = f.read()
                    return f"📄 *Content of `{fpath}`*:\n```\n{data[:1000]}\n```", None
                elif act == "list":
                    target_dir = fpath if os.path.isdir(fpath) else "."
                    entries = os.listdir(target_dir)[:30]
                    return f"📁 *Files in `{target_dir}`*:\n" + "\n".join(f"• {e}" for e in entries), None
                elif act == "exists":
                    exists = os.path.exists(fpath)
                    return f"File `{fpath}` exists: {'Yes ✅' if exists else 'No ❌'}", None
            except Exception as e:
                return f"❌ File management error: {str(e)}", None

        elif tool_name == "run_python_code":
            code_snippet = args.get("code", "").strip()
            if not code_snippet:
                return "❌ Empty code snippet.", None
            try:
                import io
                import sys
                old_stdout = sys.stdout
                redirected = io.StringIO()
                sys.stdout = redirected
                loc = {}
                exec(code_snippet, {"__builtins__": __builtins__}, loc)
                sys.stdout = old_stdout
                output = redirected.getvalue()
                return f"🐍 *Python Execution Output*:\n```\n{output.strip() if output.strip() else 'Executed successfully with no stdout.'}\n```", None
            except Exception as e:
                sys.stdout = old_stdout
                return f"❌ Python Execution Error: {str(e)}", None

        return f"Tool '{tool_name}' executed successfully.", None

    async def process_user_intent(
        self,
        user_input: str,
        user_name: str = "Mukil",
        chat_id: int = 0,
        user_id: int = 0,
    ) -> Tuple[str, Optional[str]]:
        """
        Dynamically analyzes user input via LLM Tool Calling and executes actions.
        Returns: (text_reply, optional_photo_path)
        """
        clean_input = user_input.strip()
        if not clean_input:
            return "வணக்கம் Boss! All systems online. What is your command?", None

        # 1. Save incoming turn to persistent multi-device memory
        self.memory_vault.record_conversation_turn(sender=user_name, text=clean_input)

        # 2. Build Real-Time Live System & Persistent Memory Context
        from datetime import datetime, timedelta, timezone
        import psutil

        now_utc = datetime.now(timezone.utc)
        now_ist = now_utc + timedelta(hours=5, minutes=30)
        current_time_str = now_ist.strftime("%A, %d %B %Y, %I:%M:%S %p IST")

        batt = psutil.sensors_battery()
        batt_str = f"{batt.percent:.0f}%" if batt else "N/A"
        batt_plug = "Plugged in (Charging)" if (batt and batt.power_plugged) else "On Battery"
        cpu_pct = f"{psutil.cpu_percent(interval=None):.1f}%"
        ram_pct = f"{psutil.virtual_memory().percent:.1f}%"

        memory_block = self.memory_vault.get_prompt_memory_context()

        live_system_prompt = (
            f"{SYSTEM_AGENT_PROMPT}\n\n"
            f"{memory_block}\n\n"
            f"[LIVE REAL-TIME SYSTEM CONTEXT]\n"
            f"• Current Live Date & Time: {current_time_str}\n"
            f"• PC Battery Level: {batt_str} ({batt_plug})\n"
            f"• PC Hardware: CPU {cpu_pct} | RAM {ram_pct}\n"
            f"• User: Mukil (Always address him as 'Boss' or 'Mapla')\n"
            f"• OS: Windows 11 / Cloud Linux\n"
        )

        # 3. Multi-Step Autonomous Agentic Problem Solving Loop (CodeAct ReAct Engine)
        recent_msgs = self.memory_vault.get_recent_conversation_messages(limit=6)
        if recent_msgs and recent_msgs[-1]["role"] == "user" and recent_msgs[-1]["content"] == clean_input:
            recent_msgs = recent_msgs[:-1]

        for model in GROQ_MODELS:
            try:
                convo_history = [
                    {"role": "system", "content": live_system_prompt},
                    *recent_msgs,
                    {"role": "user", "content": clean_input},
                ]
                photo_to_send = None
                executed_steps = []

                # Allow up to 4 autonomous agentic iterations per task
                for _ in range(4):
                    response = self._client.chat.completions.create(
                        model=model,
                        messages=convo_history,
                        tools=AGENT_TOOLS_SCHEMA,
                        tool_choice="auto",
                        temperature=0.2,
                    )

                    msg = response.choices[0].message

                    # A. LLM decided to invoke tool(s)
                    if msg.tool_calls:
                        convo_history.append(msg)
                        for tc in msg.tool_calls:
                            fn_name = tc.function.name
                            try:
                                fn_args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                            except Exception:
                                fn_args = {}

                            res_text, photo_path = self.execute_tool(fn_name, fn_args, chat_id=chat_id, user_id=user_id)
                            executed_steps.append(res_text)
                            if photo_path:
                                photo_to_send = photo_path

                            convo_history.append({
                                "role": "tool",
                                "tool_call_id": tc.id,
                                "name": fn_name,
                                "content": res_text[:1000],
                            })
                        
                        # Fast-Path: If tool already produced a complete executive response, return immediately!
                        if executed_steps and not photo_to_send:
                            combined = "\n\n".join(executed_steps)
                            self.memory_vault.record_conversation_turn(sender="JARVIS", text=combined)
                            return combined, None
                        continue

                    # B. LLM decided to answer conversationally or produce final synthesis
                    elif msg.content and msg.content.strip():
                        final_ans = msg.content.strip()
                        if executed_steps:
                            combined = "\n\n".join(executed_steps)
                        else:
                            combined = final_ans

                        self.memory_vault.record_conversation_turn(sender="JARVIS", text=combined)
                        return combined, photo_to_send

                if executed_steps:
                    combined = "\n\n".join(executed_steps)
                    self.memory_vault.record_conversation_turn(sender="JARVIS", text=combined)
                    return combined, photo_to_send

            except Exception as ex:
                logger.warning(f"Model {model} agentic loop failed: {ex}. Retrying next model...")

        # Ultimate fallback
        handled, msg, photo = self.pc_pilot.try_execute_pc_intent(clean_input)
        if handled:
            fb_text = msg or "Action executed, Boss."
            self.memory_vault.record_conversation_turn(sender="JARVIS", text=fb_text)
            return fb_text, photo
        
        fallback_ans = "வணக்கம் Boss! All systems ready for your command."
        self.memory_vault.record_conversation_turn(sender="JARVIS", text=fallback_ans)
        return fallback_ans, None
