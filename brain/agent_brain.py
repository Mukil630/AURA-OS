import os
import sys
import json
import logging
import concurrent.futures

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import GROQ_API_KEY, DRIVE_VAULT_URL, DRIVE_FOLDER_ID
from memory.memory_manager import MemoryManager
from tools import pc_tools
from groq import Groq
from brain.intent_router import IntentRouter
from brain.adaptive_scheduler import AdaptiveScheduler

logger = logging.getLogger(__name__)

TOOLS_DEFINITION = [
    {
        "type": "function",
        "function": {
            "name": "create_placement_sprint",
            "description": "Create a temporary high-intensity placement drive sprint (e.g. Capgemini, TCS, Zoho drive prep) that overrides the daily schedule for a specific number of days and auto-reverts back to baseline routine on deadline completion.",
            "parameters": {
                "type": "object",
                "properties": {
                    "company_name": {
                        "type": "string",
                        "description": "Name of the company or placement drive event (e.g. 'Capgemini Placement Sprint', 'TCS NQT Prep')."
                    },
                    "duration_days": {
                        "type": "integer",
                        "description": "Duration of the sprint in days (default 7)."
                    }
                },
                "required": ["company_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_daily_schedule",
            "description": "Get today's active schedule (shows active sprint override if in progress, or baseline Java/Python/Aptitude routine).",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_browser_url",
            "description": "Open any website, URL, or web service (e.g. Gmail, YouTube, Google, GitHub, LinkedIn, ChatGPT) directly on Mukil's PC screen in the browser.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The exact web URL to open (e.g. 'https://mail.google.com', 'https://youtube.com', 'https://github.com')."
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_powershell",
            "description": "Execute any PowerShell command on Mukil's Windows PC. Use for getting battery info, launching apps/browsers (e.g. Start-Process 'https://mail.google.com'), checking processes, git commands, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The exact PowerShell command line to execute."
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_folder",
            "description": "Create a new folder/directory on Mukil's PC.",
            "parameters": {
                "type": "object",
                "properties": {
                    "folder_path": {
                        "type": "string",
                        "description": "Absolute or relative folder path (e.g. C:/Users/mukil/Desktop/NewProject)."
                    }
                },
                "required": ["folder_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_text_file",
            "description": "Create or write content to a file on Mukil's PC.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Target file path on PC."
                    },
                    "content": {
                        "type": "string",
                        "description": "Text content to write into the file."
                    }
                },
                "required": ["file_path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_text_file",
            "description": "Read file contents from Mukil's PC.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "File path on PC to read."
                    }
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and subfolders in a directory on Mukil's PC.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory_path": {
                        "type": "string",
                        "description": "Directory path on PC to inspect."
                    }
                },
                "required": ["directory_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_drive_vault_info",
            "description": "Get the URL and details of Mukil's 5TB Google Drive Master Vault.",
            "parameters": {
                "type": "object",
                "properties": {},
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_whatsapp_message",
            "description": "Automate sending a WhatsApp message to a specific contact on Mukil's PC.",
            "parameters": {
                "type": "object",
                "properties": {
                    "contact_name": {
                        "type": "string",
                        "description": "The contact or person name to search for (e.g. 'Amma', 'Mukil', 'Dad')."
                    },
                    "message": {
                        "type": "string",
                        "description": "The exact message to send."
                    }
                },
                "required": ["contact_name", "message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_screen_brightness",
            "description": "Set PC screen brightness percentage (0 to 100).",
            "parameters": {
                "type": "object",
                "properties": {
                    "level": {
                        "type": "integer",
                        "description": "Brightness percentage from 0 to 100."
                    }
                },
                "required": ["level"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_screen_brightness",
            "description": "Get current PC screen brightness level.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_system_volume",
            "description": "Set PC master audio volume percentage (0 to 100).",
            "parameters": {
                "type": "object",
                "properties": {
                    "level": {
                        "type": "integer",
                        "description": "Volume level percentage from 0 to 100."
                    }
                },
                "required": ["level"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "take_pc_screenshot",
            "description": "Take a screenshot of the PC screen and save it.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "lock_workstation",
            "description": "Lock the Windows PC immediately.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "apply_indeed_jobs",
            "description": "Launch autonomous browser to search and apply for jobs on Indeed India.",
            "parameters": {
                "type": "object",
                "properties": {
                    "keywords": {
                        "type": "string",
                        "description": "Job title or keywords (e.g. 'Software Engineer', 'Python Developer', 'AI Engineer')."
                    },
                    "location": {
                        "type": "string",
                        "description": "Job location (e.g. 'Remote', 'Bangalore', 'Tamil Nadu')."
                    },
                    "max_applications": {
                        "type": "integer",
                        "description": "Number of job applications to process (e.g. 2 or 3)."
                    }
                },
                "required": ["keywords"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "play_youtube_song",
            "description": "Search and play any song or video on YouTube in the browser.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Song name or YouTube search query (e.g. 'Believer', 'Arabic Kuthu', 'Lofi beats')."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browser_search",
            "description": "Use autonomous Chrome browser to search Google for information, links, and summaries.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query string."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browser_open_and_screenshot",
            "description": "Open any website URL in Chrome, take a screenshot of the page, and return it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The full website URL to visit."
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browser_read_page",
            "description": "Visit any website URL and extract its text content for analysis.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The website URL to read."
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browser_auto_fill_form",
            "description": "Visit a website URL/form and automatically fill fields with Mukil's profile details.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The form or portal website URL."
                    }
                },
                "required": ["url"]
            }
        }
    }
]

class AgentBrain:
    def __init__(self):
        self.mem = MemoryManager()
        self.client = Groq(api_key=GROQ_API_KEY)
        self.model = "openai/gpt-oss-120b"
        self.router = IntentRouter()

    def _execute_tool_sync(self, name: str, args: dict) -> str:
        if name == "create_placement_sprint":
            sched = AdaptiveScheduler()
            res = sched.create_sprint_override(
                event_name=args.get("company_name", "Placement Drive Sprint"),
                duration_days=args.get("duration_days", 7)
            )
            return f"✅ 7-Day Sprint '{res['sprint_name']}' created successfully! Expiry Date: {res['expiry_date']}. Daily schedule has been prioritized for this drive and will auto-revert upon completion."
        elif name == "get_daily_schedule":
            sched = AdaptiveScheduler()
            res = sched.get_today_active_schedule()
            return f"📅 Today's Active Schedule (Mode: {res['mode']}):\n" + json.dumps(res['schedule'], indent=2)
        elif name == "open_browser_url":
            return pc_tools.open_browser_url(args.get("url", "https://google.com"))
        elif name == "run_powershell":
            return pc_tools.run_powershell(args.get("command", ""))
        elif name == "create_folder":
            return pc_tools.create_folder(args.get("folder_path", ""))
        elif name == "write_text_file":
            return pc_tools.write_text_file(args.get("file_path", ""), args.get("content", ""))
        elif name == "read_text_file":
            return pc_tools.read_text_file(args.get("file_path", ""))
        elif name == "list_files":
            return pc_tools.list_files(args.get("directory_path", ""))
        elif name == "get_drive_vault_info":
            return f"5TB Drive Vault URL: {DRIVE_VAULT_URL} (Folder ID: {DRIVE_FOLDER_ID})"
        elif name == "send_whatsapp_message":
            return pc_tools.send_whatsapp_message(args.get("contact_name", ""), args.get("message", ""))
        elif name == "set_screen_brightness":
            return pc_tools.set_screen_brightness(args.get("level", 100))
        elif name == "get_screen_brightness":
            return pc_tools.get_screen_brightness()
        elif name == "set_system_volume":
            return pc_tools.set_system_volume(args.get("level", 50))
        elif name == "take_pc_screenshot":
            return pc_tools.take_pc_screenshot()
        elif name == "lock_workstation":
            return pc_tools.lock_workstation()
        elif name == "apply_indeed_jobs":
            return pc_tools.apply_indeed_jobs(
                keywords=args.get("keywords", "Software Engineer"),
                location=args.get("location", "Remote"),
                max_applications=args.get("max_applications", 3)
            )
        elif name == "play_youtube_song":
            return pc_tools.play_youtube_song(args.get("query", "Believer"))
        elif name == "browser_search":
            return pc_tools.browser_search(args.get("query", ""))
        elif name == "browser_open_and_screenshot":
            return pc_tools.browser_open_and_screenshot(args.get("url", ""))
        elif name == "browser_read_page":
            return pc_tools.browser_read_page(args.get("url", ""))
        elif name == "browser_auto_fill_form":
            return pc_tools.browser_auto_fill_form(args.get("url", ""))
        else:
            return f"Unknown tool: {name}"

    def execute_tool(self, name: str, args: dict) -> str:
        logger.info(f"Executing tool: {name} with args: {args}")
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self._execute_tool_sync, name, args)
                return future.result(timeout=120)
        except Exception as e:
            logger.error(f"Tool execution failed for {name}: {e}")
            return f"Tool {name} execution failed: {str(e)}"

    def process_message(self, user_message: str, user_name: str = "Mukil") -> str:
        sys_context = self.mem.get_system_prompt_context()
        system_prompt = (
            f"You are AURA (Autonomous Unified Response Assistant), {user_name}'s autonomous personal AI agent, executive partner, and co-developer.\n\n"
            "🧠 AGENTIC THINKING & INTELLIGENCE:\n"
            "- Always analyze the user's intent deeply before acting or answering.\n"
            "- If the user requests an action on their PC (e.g. schedule, sprints, open websites/apps, battery, WhatsApp, files, commands) -> CALL THE APPROPRIATE TOOL immediately.\n"
            "- For placement sprints or scheduling, use 'create_placement_sprint' or 'get_daily_schedule'.\n"
            "- For opening websites/apps (like Gmail, YouTube, Google), use 'open_browser_url' or 'run_powershell'.\n"
            "- If the user asks a question, technical explanation, or general chat -> give a smart, structured, insightful answer.\n\n"
            "🌐 STRICT LANGUAGE & TONE DIRECTIVE:\n"
            "1. IF THE USER SPEAKS IN TAMIL OR TANGLISH (e.g., uses words like 'maapla', 'epdi irukka', 'pannu', 'sollu', 'paaru', or Tamil script):\n"
            "   -> REPLY IN NATURAL, ENERGETIC TAMIL-TANGLISH ('Maapla' style).\n"
            "   -> Use authentic Tamil phrases like 'kandippa maapla', 'panniten', 'mudinjadhu', 'sollu', 'mass'.\n"
            "   -> DO NOT use Kannada, Telugu, or Hindi words.\n\n"
            "2. IF THE USER SPEAKS IN ENGLISH (e.g., 'What is microservices?', 'Check my disk space', 'Summarize this topic'):\n"
            "   -> REPLY IN CLEAN, HIGH-PRECISION, ARTICULATE ENGLISH.\n"
            "   -> Do NOT mix Tanglish slang into pure English answers. Keep it sharp, confident, and professional.\n\n"
            "3. AFTER TOOL EXECUTION:\n"
            "   -> State the outcome clearly and concisely in the user's chosen language.\n\n"
            + sys_context
        )

        intent = self.router.classify(user_message)
        logger.info(f"Intent classified: {intent.category} | Agent: {intent.target_agent} | Background: {intent.requires_background_task}")

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]

        try:
            # OPTIMIZATION: If purely CONVERSATIONAL, skip tool overhead for ultra-low latency (<0.5s)
            if intent.category == "CONVERSATION":
                res = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.6,
                    max_tokens=1000
                )
                reply = res.choices[0].message.content or "Done maapla!"
                self.mem.log_task("CHAT_RESPONSE", f"[CONVERSATION] User: {user_message[:60]}... | Reply: {reply[:60]}...")
                return reply

            # For SYNC_ACTION and ASYNC_PROCESS -> Run Tool-calling loop
            for turn in range(5):
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=TOOLS_DEFINITION,
                    tool_choice="auto",
                    temperature=0.4,
                    max_tokens=1000
                )

                msg = response.choices[0].message

                # If no tool calls -> return final text reply
                if not msg.tool_calls:
                    reply = msg.content or "Task completed successfully!"
                    self.mem.log_task("CHAT_RESPONSE", f"User: {user_message[:60]}... | Reply: {reply[:60]}...")
                    return reply

                # Append assistant tool calls
                messages.append(msg)

                # Execute each tool call
                for tool_call in msg.tool_calls:
                    fn_name = tool_call.function.name
                    try:
                        fn_args = json.loads(tool_call.function.arguments or "{}")
                    except Exception:
                        fn_args = {}
                    
                    tool_output = self.execute_tool(fn_name, fn_args)
                    self.mem.log_task("TOOL_EXECUTION", f"Tool: {fn_name}", {"args": fn_args, "output_preview": tool_output[:100]})
                    
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": fn_name,
                        "content": str(tool_output)
                    })

            # If reached max loop turns, call once more with tools to get final text
            final_res = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=TOOLS_DEFINITION,
                tool_choice="auto",
                temperature=0.6,
                max_tokens=1000
            )
            final_reply = final_res.choices[0].message.content or "Completed task maapla!"
            return final_reply

        except Exception as e:
            logger.error(f"Error in agent processing: {e}")
            try:
                fallback_res = self.client.chat.completions.create(
                    model="openai/gpt-oss-120b",
                    messages=[
                        {"role": "system", "content": "You are JARVIS. Reply in friendly Tamil-Tanglish."},
                        {"role": "user", "content": user_message}
                    ],
                    temperature=0.6,
                    max_tokens=500
                )
                return fallback_res.choices[0].message.content or "Done maapla!"
            except Exception:
                return f"Jarvis Brain Error: {str(e)}"

if __name__ == "__main__":
    brain = AgentBrain()
    print("AgentBrain prompt updated with pure Tamil-Tanglish!")
