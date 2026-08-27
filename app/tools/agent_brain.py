"""Autonomous Agent Brain & Zero-Hardcode Tool Calling Engine for JARVIS / AURA-OS.
Uses LLM Function Calling to understand ANY natural language intent (English, Tanglish, Tamil)
and execute tools autonomously on the PC without hardcoded regex.
"""
import json
import logging
import os
from typing import Any, Dict, Optional, Tuple
from groq import Groq

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
    ):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.pc_pilot = pc_pilot or PCPilot()
        self.reminder_scheduler = reminder_scheduler or ReminderScheduler()
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

        if tool_name == "open_application":
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

        if not self._client:
            # Fallback if no LLM key
            handled, msg, photo = self.pc_pilot.try_execute_pc_intent(clean_input)
            if handled:
                return msg or "Action executed, Boss.", photo
            return f"வணக்கம் Boss! Request '{clean_input}' received.", None

        # Execute LLM reasoning with Tool Schemas
        for model in GROQ_MODELS:
            try:
                response = self._client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": SYSTEM_AGENT_PROMPT},
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
