"""
AURA OS Tool Registry - Schema generator and dispatcher
Supports Eager & Lazy tool execution modeled on Google Antigravity.
"""
import inspect
from typing import Callable, Dict, Any, List

# Core tools
from aura.tools.system_tools import run_command, view_file, write_file, reverse_engineer, get_system_health
from aura.tools.web_search import search_web
from aura.tools.github_tools import get_github_profile, list_github_repositories
from aura.tools.voice_tools import speak_voice
from aura.tools.sgc_radar import (
    get_sgc_financial_summary,
    get_sgc_dual_month_gst,
    get_sgc_latest_bill,
    get_sgc_bill_by_number,
    get_sgc_customer_ledger,
    list_sgc_recent_invoices
)
from aura.tools.bleaching_tools import (
    record_bleaching_production,
    record_bleaching_expense,
    get_bleaching_daily_summary,
    get_bleaching_sheet_link
)
from aura.tools.drive_mesh import get_drive_mesh_status, get_master_resume_link
from aura.tools.github_tools import get_github_profile, list_github_repositories
from aura.tools.screen_vision import inspect_screen
from aura.tools.reminders import add_reminder, list_active_reminders, cancel_reminder, complete_task, list_active_tasks
from aura.tools.daily_schedule import get_daily_schedule, log_routine_completed, modify_daily_schedule
from aura.tools.telegram_tools import send_telegram_alert, send_telegram_document
from aura.tools.voice_tools import speak_voice, list_voice_personas, generate_voice_file, set_active_persona
from aura.tools.antigravity_bridge import uplink_to_antigravity, sync_unified_credentials_and_state
from aura.tools.meta_tools import create_and_register_new_tool, list_custom_tools, CUSTOM_TOOLS_MANIFEST
from aura.kernel.hooks import hooks_engine
from aura.kernel.swarm import subagent_swarm
from aura.kernel.task_manager import task_manager
from aura.memory.brain_store import brain_store
import json
import importlib.util
from pathlib import Path

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Callable] = {}
        self._schemas: Dict[str, Dict[str, Any]] = {}
        
        # 1. System & Developer Universal Primitives (CodeAct)
        self.register("run_command", run_command)
        self.register("view_file", view_file)
        self.register("write_file", write_file)
        self.register("reverse_engineer", reverse_engineer)
        self.register("search_web", search_web)
        self.register("get_system_health", get_system_health)
        self.register("get_github_profile", get_github_profile)
        self.register("list_github_repositories", list_github_repositories)
        self.register("speak_voice", speak_voice)
        
        # 2. SGC Business & Finance Tools
        self.register("get_sgc_financial_summary", get_sgc_financial_summary)
        self.register("get_sgc_dual_month_gst", get_sgc_dual_month_gst)
        self.register("get_sgc_latest_bill", get_sgc_latest_bill)
        self.register("get_sgc_bill_by_number", get_sgc_bill_by_number)
        self.register("get_sgc_customer_ledger", get_sgc_customer_ledger)
        self.register("list_sgc_recent_invoices", list_sgc_recent_invoices)
        self.register("record_bleaching_production", record_bleaching_production)
        self.register("record_bleaching_expense", record_bleaching_expense)
        self.register("get_bleaching_daily_summary", get_bleaching_daily_summary)
        self.register("get_bleaching_sheet_link", get_bleaching_sheet_link)
        
        # 3. 250GB Distributed Drive Mesh & Placement / GitHub Tools
        self.register("get_drive_mesh_status", get_drive_mesh_status)
        self.register("get_master_resume_link", get_master_resume_link)
        self.register("get_github_profile", get_github_profile)
        self.register("list_github_repositories", list_github_repositories)
        
        # 4. PC Vision & Multimodal Eye
        self.register("inspect_screen", inspect_screen)

        # 5. Temporal Tasks & Turso Cloud Reminders
        self.register("add_reminder", add_reminder)
        self.register("list_active_reminders", list_active_reminders)
        self.register("cancel_reminder", cancel_reminder)
        self.register("complete_task", complete_task)
        self.register("list_active_tasks", list_active_tasks)
        self.register("get_daily_schedule", get_daily_schedule)
        self.register("log_routine_completed", log_routine_completed)
        self.register("modify_daily_schedule", modify_daily_schedule)

        # 6. Telegram Mobile Gateway & Neural Speech Voice Link
        self.register("send_telegram_alert", send_telegram_alert)
        self.register("send_telegram_document", send_telegram_document)
        self.register("speak_voice", speak_voice)
        self.register("generate_voice_file", generate_voice_file)
        self.register("list_voice_personas", list_voice_personas)
        self.register("set_active_persona", set_active_persona)

        # 7. Self-Extending Meta Superpowers
        self.register("create_and_register_new_tool", create_and_register_new_tool)
        self.register("list_custom_tools", list_custom_tools)

        # 7. Antigravity-Grade Subagent Swarm & Brain Memory
        self.register("invoke_subagent", self._tool_invoke_subagent)
        self.register("list_background_tasks", self._tool_list_background_tasks)
        self.register("search_brain_memory", self._tool_search_brain_memory)
        
        # 8. Antigravity (JARVIS Prime) Supreme Uplink Bridge
        self.register("uplink_to_antigravity", uplink_to_antigravity)
        self.register("sync_unified_credentials_and_state", sync_unified_credentials_and_state)

        # Load any previously synthesized tools
        self._load_custom_tools()

    def _tool_invoke_subagent(self, role: str, goal: str) -> str:
        """Dispatches an asynchronous specialized subagent (Roles: 'PlacementHunter', 'SGCExecutive', 'WashingHub', 'ResearchPilot')."""
        res = subagent_swarm.invoke_subagent(role, goal)
        return json.dumps(res, indent=2)

    def _tool_list_background_tasks(self) -> str:
        """Lists all active and completed background tasks and their execution duration."""
        tasks = task_manager.list_tasks()
        return json.dumps(tasks, indent=2)

    def _tool_search_brain_memory(self, query: str) -> str:
        """Searches past conversations and archived sessions using SQLite FTS5 Full-Text Search."""
        results = brain_store.search_brain(query)
        return json.dumps(results, indent=2)

    def _load_custom_tools(self):
        """Loads any custom tools persisted from prior runs."""
        if not CUSTOM_TOOLS_MANIFEST.exists():
            return
        try:
            manifest = json.loads(CUSTOM_TOOLS_MANIFEST.read_text(encoding="utf-8"))
            for name, meta in manifest.items():
                file_path = Path(meta["file"])
                if file_path.exists():
                    spec = importlib.util.spec_from_file_location(name, file_path)
                    if spec and spec.loader:
                        mod = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(mod)
                        if hasattr(mod, name):
                            self.register(name, getattr(mod, name))
        except Exception:
            pass

    def register(self, name: str, func: Callable):
        """Registers a Python function and builds its OpenAI-compatible JSON schema."""
        self._tools[name] = func
        
        doc = inspect.getdoc(func) or f"Executes {name}"
        sig = inspect.signature(func)
        
        properties = {}
        required = []
        
        type_mapping = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            dict: "object",
            list: "array"
        }
        
        for param_name, param in sig.parameters.items():
            param_type = type_mapping.get(param.annotation, "string")
            properties[param_name] = {
                "type": param_type,
                "description": f"Parameter {param_name}"
            }
            if param.default == inspect.Parameter.empty:
                required.append(param_name)
                
        schema = {
            "type": "function",
            "function": {
                "name": name,
                "description": doc.split("\n\n")[0].strip(),
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            }
        }
        self._schemas[name] = schema

    def get_schemas(self, tool_names: List[str] = None) -> List[Dict[str, Any]]:
        """Returns schemas for requested tools (Contextual Tool Pruning)."""
        if tool_names is None:
            return list(self._schemas.values())
        return [self._schemas[n] for n in tool_names if n in self._schemas]

    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Executes a tool with AGY Lifecycle Hooks (Pre-tool check and Post-tool sanitization)."""
        if tool_name not in self._tools:
            return f"Error: Tool '{tool_name}' not found in registry."
        
        # 1. Pre-Tool Lifecycle Hook Interception
        ctx, allowed, block_reason = hooks_engine.run_pre_tool(tool_name, arguments)
        if not allowed:
            return f"[Hook Blocked]: {block_reason}"

        func = self._tools[tool_name]
        try:
            sig = inspect.signature(func)
            has_var_keyword = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
            if has_var_keyword:
                valid_args = arguments
            else:
                valid_args = {k: v for k, v in arguments.items() if k in sig.parameters}
            result = func(**valid_args)
            
            # 2. Post-Tool Lifecycle Hook Interception
            sanitized_result = hooks_engine.run_post_tool(ctx, str(result))
            return sanitized_result
        except Exception as e:
            err = f"Execution Error in {tool_name}: {str(e)}"
            return hooks_engine.run_post_tool(ctx, err)

# Singleton registry instance
registry = ToolRegistry()
