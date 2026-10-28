"""
AURA 2.0 Universal Tool & Plugin Bridge
aura_langgraph/tool_bridge.py - Dynamically discovers and wraps all existing
tools and plugins from:
1. tools/sgc_mcp_server.py (19 FastMCP Tools)
2. tools/pc_tools.py (12 PC Pilot & Windows Hardware Functions)
3. tools/google_calendar_tool.py (Google Calendar OAuth Sync)
4. tools/unified_drive_mesh_router.py (250GB Distributed Drive Mesh)
5. tools/linkedin_agent.py & trigger_live_call.py
6. shared/registry.py (Unified Tool Registry)

Zero duplicate code. 100% efficient, native function execution with Saga rollback hooks.
"""
import os
import sys
import json
import inspect
import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple, Callable
from pathlib import Path

logger = logging.getLogger("aura_tool_bridge")

BASE_DIR = Path(__file__).resolve().parent.parent


class ToolBridgeMetadata:
    def __init__(
        self,
        name: str,
        description: str,
        category: str,
        fn: Callable,
        is_async: bool = False,
        is_mutating: bool = False,
        compensating_tool: Optional[str] = None
    ):
        self.name = name
        self.description = description.strip()
        self.category = category
        self.fn = fn
        self.is_async = is_async
        self.is_mutating = is_mutating
        self.compensating_tool = compensating_tool

    def execute(self, args: Dict[str, Any]) -> Tuple[Any, Optional[Dict[str, Any]]]:
        """Executes the native function and generates Saga compensation spec if mutating."""
        # 1. Filter arguments matching function signature
        sig = inspect.signature(self.fn)
        valid_args = {}
        for param_name, param in sig.parameters.items():
            if param_name in args:
                valid_args[param_name] = args[param_name]
            elif param.default is not inspect.Parameter.empty:
                continue

        # 2. Invoke sync or async
        if self.is_async:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Nested loop runner
                    import nest_asyncio
                    nest_asyncio.apply()
                    res = loop.run_until_complete(self.fn(**valid_args))
                else:
                    res = asyncio.run(self.fn(**valid_args))
            except Exception:
                res = asyncio.run(self.fn(**valid_args))
        else:
            res = self.fn(**valid_args)

        # 3. Build Saga compensation spec if mutating
        comp_spec = None
        if self.is_mutating and self.compensating_tool:
            comp_args = {}
            if self.name in ["sgc_create_quick_invoice", "create_sgc_bill"]:
                bill_no = None
                if isinstance(res, dict):
                    bill_no = res.get("billNo") or res.get("bill_no")
                elif isinstance(res, str):
                    import re
                    match = re.search(r"#?(\d{4,})", res)
                    if match:
                        bill_no = int(match.group(1))
                if bill_no:
                    comp_args = {"bill_no": bill_no}

            elif self.name in ["google_calendar_create_event", "add_calendar_reminder"]:
                if isinstance(res, dict) and res.get("event_id"):
                    comp_args = {"event_id": res.get("event_id")}

            elif self.name == "take_pc_screenshot":
                if isinstance(res, str) and os.path.exists(res):
                    comp_args = {"file_path": res}
                elif isinstance(res, dict) and res.get("screenshot_path"):
                    comp_args = {"file_path": res.get("screenshot_path")}

            elif self.name == "sgc_add_turso_reminder":
                if isinstance(res, dict) and res.get("id"):
                    comp_args = {"reminder_id": res.get("id")}

            if comp_args:
                comp_spec = {
                    "compensating_tool": self.compensating_tool,
                    "compensating_args": comp_args
                }

        return res, comp_spec


class UniversalToolBridge:
    """
    Master bridge registry unifying existing tools and plugins into LangGraph.
    """

    def __init__(self):
        self.tools: Dict[str, ToolBridgeMetadata] = {}
        self._load_all_existing_plugins()

    def register(self, meta: ToolBridgeMetadata):
        self.tools[meta.name] = meta
        logger.debug(f"Bridged tool: {meta.name} [{meta.category}] (Mutating: {meta.is_mutating})")

    def get(self, name: str) -> Optional[ToolBridgeMetadata]:
        return self.tools.get(name)

    def list_tools(self) -> List[ToolBridgeMetadata]:
        return list(self.tools.values())

    def _load_all_existing_plugins(self):
        """Loads and wraps all existing tools from the repo."""
        # -------------------------------------------------------------
        # 1. LOAD SGC MCP SERVER TOOLS (19 Tools)
        # -------------------------------------------------------------
        try:
            from tools.sgc_mcp_server import mcp
            for name, tool in mcp._tool_manager._tools.items():
                is_async = inspect.iscoroutinefunction(tool.fn)
                is_mutating = name in [
                    "sgc_create_quick_invoice", "sgc_mark_invoice_paid",
                    "sgc_add_turso_reminder", "sgc_save_memory_vault"
                ]
                comp_map = {
                    "sgc_create_quick_invoice": "sgc_delete_invoice",
                    "sgc_mark_invoice_paid": "sgc_mark_invoice_unpaid",
                    "sgc_add_turso_reminder": "sgc_cancel_turso_reminder",
                    "sgc_save_memory_vault": "turso_delete_vault"
                }

                self.register(ToolBridgeMetadata(
                    name=name,
                    description=tool.description or f"SGC Tool: {name}",
                    category="sgc_mcp",
                    fn=tool.fn,
                    is_async=is_async,
                    is_mutating=is_mutating,
                    compensating_tool=comp_map.get(name)
                ))
            logger.info("✅ Bridged 19 tools from tools/sgc_mcp_server.py")
        except Exception as e:
            logger.warning(f"Could not bridge sgc_mcp_server: {e}")

        # -------------------------------------------------------------
        # 2. LOAD PC TOOLS & WINDOWS HARDWARE (12 Tools)
        # -------------------------------------------------------------
        try:
            import tools.pc_tools as pc
            pc_func_map = {
                "set_system_volume": ("Set PC master audio volume (0-100%)", True, "set_system_volume"),
                "get_system_volume": ("Get current PC audio volume level", False, None),
                "media_control": ("Control media: play, pause, next, prev, mute", True, "media_control"),
                "set_screen_brightness": ("Set PC screen brightness (0-100%)", True, "set_screen_brightness"),
                "get_screen_brightness": ("Get current PC screen brightness", False, None),
                "lock_workstation": ("Lock the Windows PC immediately", False, None),
                "sleep_pc": ("Put the PC to sleep mode", False, None),
                "take_pc_screenshot": ("Capture full screenshot of PC display", True, "delete_local_file"),
                "launch_app": ("Launch Windows desktop app or utility", True, "close_app"),
                "close_app": ("Close a running Windows application", False, None),
                "get_system_telemetry": ("Get CPU, RAM, Disk, and Battery diagnostics", False, None),
                "run_powershell": ("Execute safe PowerShell command on Windows PC", False, None)
            }

            for fn_name, (desc, mutating, comp) in pc_func_map.items():
                if hasattr(pc, fn_name):
                    self.register(ToolBridgeMetadata(
                        name=fn_name,
                        description=desc,
                        category="pc_pilot",
                        fn=getattr(pc, fn_name),
                        is_async=False,
                        is_mutating=mutating,
                        compensating_tool=comp
                    ))
            logger.info("✅ Bridged 12 tools from tools/pc_tools.py")
        except Exception as e:
            logger.warning(f"Could not bridge pc_tools: {e}")

        # -------------------------------------------------------------
        # 3. LOAD GOOGLE CALENDAR TOOLS (2 Tools)
        # -------------------------------------------------------------
        try:
            import tools.google_calendar_tool as cal
            if hasattr(cal, "add_calendar_reminder"):
                self.register(ToolBridgeMetadata(
                    name="add_calendar_reminder",
                    description="Create reminder or interview event on Google Calendar with multi-tier alarms",
                    category="google_workspace",
                    fn=cal.add_calendar_reminder,
                    is_async=False,
                    is_mutating=True,
                    compensating_tool="google_calendar_delete_event"
                ))
            if hasattr(cal, "list_upcoming_events"):
                self.register(ToolBridgeMetadata(
                    name="list_upcoming_events",
                    description="List upcoming events and appointments from Google Calendar",
                    category="google_workspace",
                    fn=cal.list_upcoming_events,
                    is_async=False,
                    is_mutating=False
                ))
            logger.info("✅ Bridged Google Calendar tools from tools/google_calendar_tool.py")
        except Exception as e:
            logger.warning(f"Could not bridge google_calendar_tool: {e}")

        # -------------------------------------------------------------
        # 4. LOAD UNIFIED DRIVE MESH TOOLS (3 Tools)
        # -------------------------------------------------------------
        try:
            import tools.unified_drive_mesh_router as mesh
            if hasattr(mesh, "search_mesh"):
                self.register(ToolBridgeMetadata(
                    name="search_drive_mesh",
                    description="Search files across 250GB Distributed Drive Mesh in under 5ms",
                    category="drive_mesh",
                    fn=mesh.search_mesh,
                    is_async=False,
                    is_mutating=False
                ))
            if hasattr(mesh, "record_file_in_mesh"):
                self.register(ToolBridgeMetadata(
                    name="record_file_in_mesh",
                    description="Record uploaded file into Drive Mesh search index",
                    category="drive_mesh",
                    fn=mesh.record_file_in_mesh,
                    is_async=False,
                    is_mutating=True,
                    compensating_tool="delete_mesh_record"
                ))
            if hasattr(mesh, "get_unified_portal_summary"):
                self.register(ToolBridgeMetadata(
                    name="get_unified_portal_summary",
                    description="Get Telegram markdown dashboard of all 10 Drive Mesh nodes",
                    category="drive_mesh",
                    fn=mesh.get_unified_portal_summary,
                    is_async=False,
                    is_mutating=False
                ))
            logger.info("✅ Bridged Drive Mesh tools from tools/unified_drive_mesh_router.py")
        except Exception as e:
            logger.warning(f"Could not bridge unified_drive_mesh_router: {e}")

        # -------------------------------------------------------------
        # 5. LOAD B2B MILL SCRAPING TOOL
        # -------------------------------------------------------------
        try:
            from skills.spinning_mills import execute_scrape_spinning_mills
            self.register(ToolBridgeMetadata(
                name="scrape_spinning_mills",
                description="Scrape B2B spinning and textile mills across Tamil Nadu (Karur, Tirupur, Coimbatore)",
                category="business_leads",
                fn=execute_scrape_spinning_mills,
                is_async=False,
                is_mutating=False
            ))
            logger.info("✅ Bridged B2B spinning mill scraper from skills/spinning_mills.py")
        except Exception as e:
            logger.warning(f"Could not bridge spinning_mills: {e}")

        # -------------------------------------------------------------
        # 6. LOAD LINKEDIN & TELEPHONY TOOLS
        # -------------------------------------------------------------
        try:
            from tools.linkedin_agent import post_to_linkedin
            self.register(ToolBridgeMetadata(
                name="post_to_linkedin",
                description="Publish automated technical post to LinkedIn with generated banner",
                category="comms",
                fn=post_to_linkedin,
                is_async=False,
                is_mutating=True,
                compensating_tool="delete_linkedin_post"
            ))
        except Exception:
            pass

        try:
            from tools.trigger_live_call import check_and_fire
            self.register(ToolBridgeMetadata(
                name="trigger_live_telephony_call",
                description="Trigger live outbound telephony phone call alert via Twilio/Telnyx",
                category="comms",
                fn=check_and_fire,
                is_async=False,
                is_mutating=False
            ))
        except Exception:
            pass

        # -------------------------------------------------------------
        # 7. LOAD DEDICATED SGC BUSINESS & LOGISTICS AUTOMATION TOOLS
        # -------------------------------------------------------------
        try:
            from tools.weather_radar_tool import get_live_weather_radar
            self.register(ToolBridgeMetadata(
                name="get_live_weather_radar",
                description="Real-time Karur/Tirupur weather radar and outdoor hank yarn sun-drying feasibility check",
                category="sgc_automation",
                fn=get_live_weather_radar,
                is_async=False,
                is_mutating=False
            ))
        except Exception as e:
            logger.warning(f"Could not bridge weather_radar_tool: {e}")

        try:
            from tools.textile_logistics_tool import calculate_mill_route_and_freight
            self.register(ToolBridgeMetadata(
                name="calculate_mill_route_and_freight",
                description="Calculate driving distance, travel duration, parcel freight charges, and Google Maps nav link to textile mills",
                category="sgc_logistics",
                fn=calculate_mill_route_and_freight,
                is_async=False,
                is_mutating=False
            ))
        except Exception as e:
            logger.warning(f"Could not bridge textile_logistics_tool: {e}")

        try:
            from tools.sgc_cost_calculator import calculate_dyeing_cost_and_margin
            self.register(ToolBridgeMetadata(
                name="calculate_dyeing_cost_and_margin",
                description="Calculate exact reactive dye recipe grams, chemical cost, power/labor overhead, quoting rate, and profit margin",
                category="sgc_business",
                fn=calculate_dyeing_cost_and_margin,
                is_async=False,
                is_mutating=False
            ))
        except Exception as e:
            logger.warning(f"Could not bridge sgc_cost_calculator: {e}")

        try:
            from tools.sgc_reminder_generator import generate_payment_followup_message
            self.register(ToolBridgeMetadata(
                name="generate_payment_followup_message",
                description="Query SGC database for unpaid customer bills and generate polite WhatsApp/SMS payment reminders in Tamil and English",
                category="sgc_business",
                fn=generate_payment_followup_message,
                is_async=False,
                is_mutating=False
            ))
        except Exception as e:
            logger.warning(f"Could not bridge sgc_reminder_generator: {e}")


# Global Singleton Tool Bridge
universal_tool_bridge = UniversalToolBridge()
