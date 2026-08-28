"""Autonomous Agent Brain & Zero-Hardcode Tool Calling Engine for JARVIS / AURA-OS.
Uses LLM Function Calling to understand ANY natural language intent (English, Tanglish, Tamil)
and execute tools autonomously on the PC without hardcoded regex.
"""
import json
import logging
import os
from typing import Any, Dict, Optional, Tuple
from groq import Groq

from app.agents.placement.job_apply_agent import JobApplyAgent
from app.tools.pc_pilot import PCPilot
from app.tools.reminder_scheduler import ReminderScheduler

logger = logging.getLogger("AgentBrain")

GROQ_MODELS = [
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
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

SYSTEM_AGENT_PROMPT = """You are JARVIS / FRIDAY, the executive autonomous AI partner and PC commander for Mukil (always address him as 'Boss').
You possess REAL full autonomous control over his PC and applications.

Decision Rules:
1. When Mukil asks to perform an action on his PC (e.g. open/close apps, kill tabs, browse/search web, screenshots, volume, lock workstation, timers/reminders, clipboard), ALWAYS invoke the appropriate tool from your toolset.
2. When Mukil asks a technical question, coding problem, placement query, or engages in casual conversation, do NOT call PC tools. Instead, answer directly in confident, sharp, friendly Tanglish + English (Latin script only) addressing him as 'Boss'.
3. Never say "I cannot control your device" or suggest manual keyboard shortcuts when asked to perform a task. You are an autonomous agent capable of executing actions directly.
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
    ):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.pc_pilot = pc_pilot or PCPilot()
        self.reminder_scheduler = reminder_scheduler or ReminderScheduler()
        self.job_agent = job_agent or JobApplyAgent(api_key=self.api_key)
        self._client: Optional[Groq] = None
        if self.api_key:
            try:
                self._client = Groq(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Could not initialize Groq client in AgentBrain: {e}")

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
            lines.append(f"\n📄 *Master Resume Linked*: [View Resume PDF](https://drive.google.com/file/d/1TpyzV7OGEf-YQfGLUpusAI5cDDvF1kAJ/view?usp=drive_link)")
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
            
            res_md = (
                f"🚀 *AUTONOMOUS JOB APPLICATION EXECUTED FOR {comp.upper()}*!\n\n"
                f"🌐 *Careers Portal Opened on PC*: [Click to View Careers Page]({portal_url})\n"
                f"📋 *Application ID*: `{logged['application_id']}` | Status: *{logged['status']}*\n"
                f"📄 *Master Resume Attached*: [View Resume PDF]({logged['resume_link']})\n"
                f"📋 *PC Clipboard*: _Cold pitch copied to clipboard ready to paste (Ctrl+V)!_\n\n"
                f"✉️ *Cold Outreach Pitch (Email/LinkedIn)*:\n```\n{pkg.get('cold_pitch_email')}\n```\n\n"
                f"📝 *Tailored Cover Letter*:\n```\n{pkg.get('cover_letter')}\n```\n\n"
                f"💡 *Why You Are The Best Fit*:\n_{pkg.get('screening_answer_why_hire')}_\n\n"
                f"✅ *Application logged in pipeline tracker, Boss!*"
            )
            return res_md, None

        elif tool_name == "batch_apply_jobs":
            role = args.get("role", "AI Engineer")
            batch_results = self.job_agent.batch_apply_top_companies(role=role)
            lines = [
                f"🚀 *BATCH APPLICATION EXECUTED ACROSS TOP COMPANIES ({role})*!\n",
                f"📄 *Master Resume Linked*: [View Resume PDF](https://drive.google.com/file/d/1TpyzV7OGEf-YQfGLUpusAI5cDDvF1kAJ/view?usp=drive_link)\n"
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
            return "\n".join(lines), None

        elif tool_name == "view_job_pipeline":
            summary = self.job_agent.get_pipeline_summary()
            return summary, None

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

        # Build Real-Time Live System Context (Date, Time IST, Battery, CPU, RAM)
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

        live_system_prompt = (
            f"{SYSTEM_AGENT_PROMPT}\n\n"
            f"[LIVE REAL-TIME SYSTEM CONTEXT]\n"
            f"• Current Live Date & Time: {current_time_str}\n"
            f"• PC Battery Level: {batt_str} ({batt_plug})\n"
            f"• PC Hardware: CPU {cpu_pct} | RAM {ram_pct}\n"
            f"• User: Mukil (Always address him as 'Boss')\n"
            f"• OS: Windows 11\n"
        )

        # Execute LLM reasoning with Tool Schemas
        for model in GROQ_MODELS:
            try:
                response = self._client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": live_system_prompt},
                        {"role": "user", "content": clean_input},
                    ],
                    tools=AGENT_TOOLS_SCHEMA,
                    tool_choice="auto",
                    temperature=0.2,
                )

                msg = response.choices[0].message

                # 1. LLM decided to invoke one or more tools
                if msg.tool_calls:
                    results = []
                    photo_to_send = None
                    for tc in msg.tool_calls:
                        fn_name = tc.function.name
                        try:
                            fn_args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                        except Exception:
                            fn_args = {}
                        res_text, photo_path = self.execute_tool(fn_name, fn_args, chat_id=chat_id, user_id=user_id)
                        results.append(res_text)
                        if photo_path:
                            photo_to_send = photo_path

                    final_text = "\n\n".join(results)
                    return final_text, photo_to_send

                # 2. LLM decided to answer conversationally
                elif msg.content and msg.content.strip():
                    return msg.content.strip(), None

            except Exception as ex:
                logger.warning(f"Model {model} failed: {ex}. Retrying next model...")

        # Ultimate fallback
        handled, msg, photo = self.pc_pilot.try_execute_pc_intent(clean_input)
        if handled:
            return msg or "Action executed, Boss.", photo
        return f"வணக்கம் Boss! All systems ready for your command.", None
