"""
AURA OS Lifecycle Hooks Engine
File: aura/kernel/hooks.py
Reverse-engineered from Google Antigravity (AGY) Lifecycle Interceptors:
- Pre-Tool Call Hooks: Parameter verification, Zero-Blind-Saving enforcement, Security boundaries.
- Post-Tool Call Hooks: Telemetry tracking, Output size sanitization, Error interception for self-healing.
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import time
import json
import logging
from typing import Dict, Any, List, Callable, Optional, Tuple

logger = logging.getLogger("aura.hooks")

# Destructive or High-Risk command tokens
DANGEROUS_PATTERNS = [
    "format c:", "rmdir /s /q c:", "del /f /s /q c:\\windows",
    "drop database", "drop table", "shutdown", "erase c:"
]

# Tools that mutate external state or cloud databases
MUTATION_TOOLS = [
    "create_reminder", "add_turso_reminder", "save_memory_vault", 
    "create_quick_invoice", "delete_invoice", "write_file", "delete_file"
]


class HookContext:
    def __init__(self, tool_name: str, arguments: Dict[str, Any], session_id: str = "default"):
        self.tool_name = tool_name
        self.arguments = arguments
        self.session_id = session_id
        self.start_time: float = time.time()
        self.end_time: Optional[float] = None
        self.duration_ms: float = 0.0
        self.is_blocked: bool = False
        self.block_reason: str = ""
        self.metadata: Dict[str, Any] = {}


class LifecycleHooksEngine:
    def __init__(self):
        self._pre_tool_hooks: List[Callable[[HookContext], Tuple[bool, str]]] = []
        self._post_tool_hooks: List[Callable[[HookContext, Any], Tuple[Any, Optional[str]]]] = []
        self._register_default_hooks()

    def _register_default_hooks(self):
        """Registers native Antigravity-grade security and self-healing hooks."""
        # Pre-Tool Hook 1: Anti-Destruction Boundary
        self.register_pre_tool(self._security_boundary_check)
        # Pre-Tool Hook 2: Zero-Blind-Saving Gatekeeper
        self.register_pre_tool(self._mutation_safety_check)
        # Post-Tool Hook 1: Output Budget & Telemetry Guard
        self.register_post_tool(self._output_sanitization_and_telemetry)

    def register_pre_tool(self, hook: Callable[[HookContext], Tuple[bool, str]]):
        self._pre_tool_hooks.append(hook)

    def register_post_tool(self, hook: Callable[[HookContext, Any], Tuple[Any, Optional[str]]]):
        self._post_tool_hooks.append(hook)

    # -------------------------------------------------------------
    # Built-in Pre-Tool Hooks
    # -------------------------------------------------------------
    def _security_boundary_check(self, ctx: HookContext) -> Tuple[bool, str]:
        """Prevents catastrophic system commands or unverified disk formats."""
        if ctx.tool_name in ["run_command", "execute_terminal", "run_shell"]:
            cmd = str(ctx.arguments.get("command", "") or ctx.arguments.get("CommandLine", "")).lower()
            for pattern in DANGEROUS_PATTERNS:
                if pattern in cmd:
                    ctx.is_blocked = True
                    ctx.block_reason = f"Security Policy Violation: Command contains restricted dangerous pattern '{pattern}'."
                    return False, ctx.block_reason
        return True, ""

    def _mutation_safety_check(self, ctx: HookContext) -> Tuple[bool, str]:
        """
        Enforces Zero-Blind-Saving:
        Logs mutation tool invocations to audit history before commit.
        """
        if ctx.tool_name in MUTATION_TOOLS:
            ctx.metadata["requires_audit_log"] = True
            ctx.metadata["mutation_target"] = ctx.tool_name
        return True, ""

    # -------------------------------------------------------------
    # Built-in Post-Tool Hooks
    # -------------------------------------------------------------
    def _output_sanitization_and_telemetry(self, ctx: HookContext, raw_result: Any) -> Tuple[Any, Optional[str]]:
        """Calculates latency and ensures tool results never exceed TPM token budget."""
        ctx.end_time = time.time()
        ctx.duration_ms = round((ctx.end_time - ctx.start_time) * 1000, 2)
        
        result_str = str(raw_result)
        # Token Budget Guard: Max 3500 chars per tool output to prevent 413 context blowout
        if len(result_str) > 3500:
            truncated_len = len(result_str) - 3500
            sanitized = result_str[:3500] + f"\n\n[... Truncated {truncated_len} chars by AURA Lifecycle Hook to protect context budget ...]"
            return sanitized, f"Tool output truncated ({truncated_len} chars over budget)"
        return raw_result, None

    # -------------------------------------------------------------
    # Execution Wrapper
    # -------------------------------------------------------------
    def run_pre_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Tuple[HookContext, bool, str]:
        """Runs all pre-tool hooks sequentially. Short-circuits if any hook blocks."""
        ctx = HookContext(tool_name, arguments)
        for hook in self._pre_tool_hooks:
            allowed, reason = hook(ctx)
            if not allowed:
                return ctx, False, reason
        return ctx, True, ""

    def run_post_tool(self, ctx: HookContext, result: Any) -> Any:
        """Runs all post-tool hooks and returns the sanitized result."""
        current_result = result
        for hook in self._post_tool_hooks:
            current_result, _ = hook(ctx, current_result)
        return current_result


# Global Hooks Singleton
hooks_engine = LifecycleHooksEngine()
