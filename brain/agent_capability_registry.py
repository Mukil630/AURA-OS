"""
Agent Capability Registry (agent_capability_registry.py)
Bridges the gap between high-level cognitive router tracks/intents and concrete
agent action names. Solves the connectivity error where the router sends track
names (e.g. "AUTONOMOUS_HEAVY_TASK") that agents don't recognize.

Each agent advertises its supported actions. The orchestrator can then:
1. Validate that an action is supported by the target agent
2. Translate high-level intent → concrete action
3. Auto-route to the correct agent when only an intent is given
"""
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("AgentCapabilityRegistry")

AGENT_CAPABILITIES: Dict[str, Dict] = {
    "Antigravity": {
        "supported_actions": [
            "BUILD_PROJECT", "CREATE_CODE", "SCAFFOLD",
            "INSPECT_CODE", "VIEW_FILE",
            "RUN_TERMINAL", "EXECUTE_COMMAND",
            "EDIT_FILE", "REPLACE_CONTENT",
        ],
        "description": "Autonomous Principal Engineer — scaffolding, code editing, terminal execution",
        "intent_map": {
            "AUTONOMOUS_HEAVY_TASK": "BUILD_PROJECT",
            "code_engineering": "BUILD_PROJECT",
            "create_project": "SCAFFOLD",
            "fix_bug": "EDIT_FILE",
            "write_code": "CREATE_CODE",
            "view_file": "VIEW_FILE",
            "inspect_code": "INSPECT_CODE",
            "run_terminal": "RUN_TERMINAL",
            "edit_file": "EDIT_FILE",
        },
    },
    "WebScout": {
        "supported_actions": [
            "SCRAPE_JOBS", "FIND_OPENINGS",
            "SCRAPE_B2B_LEADS", "SCRAPE_MILLS",
        ],
        "description": "Web scraping, B2B lead discovery, market research",
        "intent_map": {
            "AUTONOMOUS_HEAVY_TASK": "SCRAPE_B2B_LEADS",
            "scrape_website": "SCRAPE_B2B_LEADS",
            "find_jobs": "SCRAPE_JOBS",
            "scrape_jobs": "SCRAPE_JOBS",
            "scrape_leads": "SCRAPE_B2B_LEADS",
        },
    },
    "PlacementHunter": {
        "supported_actions": [
            "TAILOR_RESUME", "APPLY_TO_JOB", "CHECK_APPLICATION_STATUS",
        ],
        "description": "Career pipeline, ATS resume tailoring, job application",
        "intent_map": {
            "AUTONOMOUS_HEAVY_TASK": "TAILOR_RESUME",
            "apply_to_jobs": "APPLY_TO_JOB",
            "tailor_resume": "TAILOR_RESUME",
            "check_applications": "CHECK_APPLICATION_STATUS",
        },
    },
    "SGCExecutive": {
        "supported_actions": [
            "CHECK_OVERDUE", "DRAFT_REMINDER", "GET_LATEST_BILL",
            "GET_BILLING_DATA", "GENERATE_INVOICE",
        ],
        "description": "SGC billing, overdue radar, customer ledgers",
        "intent_map": {
            "STATUS_OR_MEMORY_QUERY": "GET_BILLING_DATA",
            "sgc_billing": "GET_BILLING_DATA",
            "check_overdue": "CHECK_OVERDUE",
            "draft_reminder": "DRAFT_REMINDER",
            "get_latest_bill": "GET_LATEST_BILL",
        },
    },
    "MemoryVault": {
        "supported_actions": [
            "GET_DRIVE_NODE", "ROUTE_STORAGE",
            "LIST_ALL_MESH_NODES", "STORAGE_STATUS",
            "QUERY_TASK_STATUS", "GET_LAST_LOG",
            "STORE_FACT", "SAVE_MEMORY",
            "ALLOCATE_PROJECT_MEMORY", "ALLOCATE_PROJECT",
            "LIST_ALLOCATIONS", "CONFIRM_MEMORY_STATUS", "CHECK_MEMORY",
        ],
        "description": "Persistent memory, 250GB distributed drive mesh, living task ledger",
        "intent_map": {
            "STATUS_OR_MEMORY_QUERY": "QUERY_TASK_STATUS",
            "memory_query": "QUERY_TASK_STATUS",
            "list_mesh_nodes": "LIST_ALL_MESH_NODES",
            "get_drive_node": "GET_DRIVE_NODE",
            "store_fact": "STORE_FACT",
            "save_memory": "SAVE_MEMORY",
            "allocate_project": "ALLOCATE_PROJECT_MEMORY",
        },
    },
    "PCPilot": {
        "supported_actions": [
            "TAKE_SCREENSHOT", "CAPTURE_PROOF",
            "OPEN_ON_SCREEN", "LAUNCH_APP",
            "PLAY_MEDIA", "PLAY_YOUTUBE",
            "EXECUTE_POWERSHELL", "RUN_COMMAND",
            "LOCK_PC", "LOCK_WORKSTATION",
            "SET_VOLUME", "VOLUME",
            "SET_BRIGHTNESS", "BRIGHTNESS",
            "GET_BATTERY", "BATTERY_STATUS",
        ],
        "description": "Physical Windows PC control, hardware telemetry, desktop operations",
        "intent_map": {
            "DEVICE_PRESENTATION": "OPEN_ON_SCREEN",
            "open_on_screen": "OPEN_ON_SCREEN",
            "take_screenshot": "TAKE_SCREENSHOT",
            "play_youtube": "PLAY_YOUTUBE",
            "run_powershell": "EXECUTE_POWERSHELL",
            "check_device": "GET_BATTERY",
            "lock_pc": "LOCK_PC",
            "set_volume": "SET_VOLUME",
            "set_brightness": "SET_BRIGHTNESS",
        },
    },
    "ServerAgent": {
        "supported_actions": [
            "ALLOCATE_SERVER_MEMORY", "GET_SERVER_MEMORY",
            "CHECK_SERVER_STATUS", "SERVER_HEALTH", "PING_SERVER",
            "SYNC_MEMORY", "SYNC_MEMORY_TO_CLOUD",
        ],
        "description": "24/7 cloud server, cloud memory, WebSocket tunnel",
        "intent_map": {
            "STATUS_OR_MEMORY_QUERY": "CHECK_SERVER_STATUS",
            "server_status": "CHECK_SERVER_STATUS",
            "ping_server": "PING_SERVER",
            "allocate_memory": "ALLOCATE_SERVER_MEMORY",
        },
    },
}


class AgentCapabilityRegistry:
    """
    Central registry for agent capabilities.
    Used by the SwarmOrchestrator to validate and translate actions.
    """

    def __init__(self):
        self._capabilities: Dict[str, Dict] = AGENT_CAPABILITIES

    def get_supported_actions(self, agent_name: str) -> List[str]:
        cap = self._capabilities.get(agent_name)
        if not cap:
            return []
        return cap["supported_actions"]

    def is_action_supported(self, agent_name: str, action: str) -> bool:
        supported = self.get_supported_actions(agent_name)
        action_upper = action.upper()
        return action_upper in [s.upper() for s in supported]

    def translate_intent(self, agent_name: str, intent_or_action: str) -> Optional[str]:
        """
        Translates a high-level intent (e.g. cognitive router track name)
        or alias into a concrete action the agent understands.
        Returns None if no translation is possible.
        """
        cap = self._capabilities.get(agent_name)
        if not cap:
            return None

        intent_map = cap.get("intent_map", {})
        action_upper = intent_or_action.upper()

        # Exact match on supported action
        if action_upper in [s.upper() for s in cap["supported_actions"]]:
            return action_upper

        # Lookup in intent_map (case-insensitive)
        for key, mapped_action in intent_map.items():
            if key.upper() == action_upper:
                return mapped_action.upper()

        return None

    def find_agent_for_action(self, action: str) -> Optional[str]:
        """
        Finds which agent can handle a given action (or intent).
        Returns the first agent that supports it.
        """
        action_upper = action.upper()
        for agent_name, cap in self._capabilities.items():
            if action_upper in [s.upper() for s in cap["supported_actions"]]:
                return agent_name
            intent_map = cap.get("intent_map", {})
            for key in intent_map:
                if key.upper() == action_upper:
                    return agent_name
        return None

    def resolve_action(
        self, agent_name: str, action: str
    ) -> Tuple[str, bool, Optional[str]]:
        """
        Resolves an action for a given agent.
        Returns (resolved_action, was_translated, original_action_if_untranslatable).

        If the action is already supported, returns it as-is.
        If not, tries to translate it via intent_map.
        If translation fails, returns (action, False, action) so the caller
        can attempt failover or report the error.
        """
        if self.is_action_supported(agent_name, action):
            return action.upper(), False, None

        translated = self.translate_intent(agent_name, action)
        if translated:
            if self.is_action_supported(agent_name, translated):
                return translated, True, None
            return translated, True, None

        return action, False, action

    def get_compatibility_report(self) -> Dict[str, Dict]:
        """Returns a report of each agent and its supported actions."""
        return {
            name: {
                "description": cap["description"],
                "supported_actions": cap["supported_actions"],
                "intent_aliases": list(cap.get("intent_map", {}).keys()),
            }
            for name, cap in self._capabilities.items()
        }


capability_registry = AgentCapabilityRegistry()
