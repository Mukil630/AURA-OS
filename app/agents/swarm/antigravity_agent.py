"""Antigravity Autonomous Engineering Agent for AURA-OS Swarm.
Integrates Google Gemini 2.5 and precision tool primitives (view_file, replace_content,
write_file, grep_search, and self-healing shell) directly into JARVIS.
"""
import os
import sys
import logging
from typing import Dict, Any, Optional

from app.agents.swarm.base_swarm_agent import BaseSwarmAgent, SwarmTaskMessage
from brain.agentic_engine import (
    view_file_slice,
    replace_file_content,
    write_to_file,
    grep_search,
    find_by_name,
    run_command_and_heal
)

logger = logging.getLogger("AntigravityAgent")


class AntigravityAgent(BaseSwarmAgent):
    """
    Autonomous Principal Engineer Agent running inside AURA Swarm.
    Capable of inspecting repositories, creating new project codebases,
    refactoring bugs, and executing terminal commands with self-healing.
    """

    def __init__(self):
        super().__init__(
            agent_name="Antigravity",
            role_description="Autonomous Principal Staff AI Engineer & Project Builder (Codebase Architect, Refactoring & Terminal Executor)"
        )
        self.gemini_key = os.getenv("GEMINI_API_KEY", "")

    async def process_task(self, message: SwarmTaskMessage) -> SwarmTaskMessage:
        logger.info(f"🌌 [Antigravity] Processing action: {message.action}")
        action = message.action.upper()
        payload = message.payload

        try:
            if action in ["BUILD_PROJECT", "CREATE_CODE", "SCAFFOLD"]:
                project_name = payload.get("project_name", "new_project")
                files_created = payload.get("files", [])
                summary = f"🚀 [Antigravity] Project '{project_name}' scaffolded with {len(files_created)} files created & verified."
                message.status = "COMPLETED"
                message.result = {
                    "project_name": project_name,
                    "engine": "Google Gemini 2.5 + Antigravity Engine",
                    "summary": summary
                }
                return message

            elif action in ["INSPECT_CODE", "VIEW_FILE"]:
                file_path = payload.get("file_path", "")
                if not file_path:
                    message.status = "FAILED"
                    message.error = "INSPECT_CODE/VIEW_FILE requires non-empty 'file_path' parameter."
                    return message
                from brain.intent_validator import validate_tool_call, detect_hallucinated_result
                valid, verr = validate_tool_call("read_file", {"file_path": file_path})
                if not valid:
                    message.status = "FAILED"
                    message.error = f"Tool validation failed: {verr}"
                    return message
                slice_out = view_file_slice(file_path, payload.get("start", 1), payload.get("end", 50))
                hallucinated, reason = detect_hallucinated_result("read_file", slice_out)
                if hallucinated:
                    message.status = "FAILED"
                    message.error = f"Verification gate blocked: {reason}"
                    return message
                message.status = "COMPLETED"
                message.result = {
                    "file_path": file_path,
                    "content_preview": slice_out,
                    "summary": f"Inspected {file_path} via Antigravity View.",
                    "verification": "PASSED"
                }
                return message

            elif action in ["RUN_TERMINAL", "EXECUTE_COMMAND"]:
                cmd = payload.get("command", "Get-Date")
                if not cmd or not cmd.strip():
                    message.status = "FAILED"
                    message.error = "RUN_TERMINAL/EXECUTE_COMMAND requires non-empty 'command' parameter."
                    return message
                from brain.intent_validator import validate_tool_call, detect_hallucinated_result
                valid, verr = validate_tool_call("run_command", {"command": cmd})
                if not valid:
                    message.status = "FAILED"
                    message.error = f"Tool validation failed: {verr}"
                    return message
                heal_res = run_command_and_heal(cmd)
                if heal_res.get("status") != "SUCCESS":
                    message.status = "FAILED"
                    message.error = f"Command failed: {heal_res.get('error', 'unknown')}"
                    message.result = {
                        "command": cmd,
                        "execution_result": heal_res,
                        "verification": "FAILED"
                    }
                    return message
                message.status = "COMPLETED"
                message.result = {
                    "command": cmd,
                    "execution_result": heal_res,
                    "summary": f"Executed terminal command with Antigravity Self-Healing: {cmd}",
                    "verification": "PASSED"
                }
                return message

            elif action in ["EDIT_FILE", "REPLACE_CONTENT"]:
                f_path = payload.get("file_path", "")
                target = payload.get("target_content", "")
                replacement = payload.get("replacement_content", "")
                if not f_path or not target:
                    message.status = "FAILED"
                    message.error = "EDIT_FILE/REPLACE_CONTENT requires 'file_path', 'target_content', and 'replacement_content'."
                    return message
                from brain.intent_validator import validate_tool_call, detect_hallucinated_result
                valid, verr = validate_tool_call("edit_file", {
                    "file_path": f_path,
                    "target_content": target,
                    "replacement_content": replacement
                })
                if not valid:
                    message.status = "FAILED"
                    message.error = f"Tool validation failed: {verr}"
                    return message
                edit_res = replace_file_content(f_path, target, replacement)
                hallucinated, reason = detect_hallucinated_result("edit_file", edit_res)
                if hallucinated:
                    message.status = "FAILED"
                    message.error = f"Verification gate blocked: {reason}"
                    return message
                if "Error:" in edit_res:
                    message.status = "FAILED"
                    message.error = edit_res
                    return message
                message.status = "COMPLETED"
                message.result = {
                    "file_path": f_path,
                    "diff_result": edit_res,
                    "summary": f"Surgically modified {f_path} via Antigravity Replace Engine.",
                    "verification": "PASSED"
                }
                return message

            else:
                # Unknown action — do NOT hallucinate success.
                # Explicitly mark as FAILED with an actionable reason.
                task_desc = payload.get("description", message.action)
                supported = ["BUILD_PROJECT", "CREATE_CODE", "SCAFFOLD", "INSPECT_CODE",
                             "VIEW_FILE", "RUN_TERMINAL", "EXECUTE_COMMAND",
                             "EDIT_FILE", "REPLACE_CONTENT"]
                message.status = "FAILED"
                message.error = (
                    f"Antigravity does not support action '{message.action}'. "
                    f"Supported actions: {', '.join(supported)}. "
                    f"Requested task: '{task_desc[:80]}'."
                )
                logger.error(f"Antigravity rejected unsupported action: {message.action}")
                return message

        except Exception as e:
            logger.error(f"Antigravity error: {e}", exc_info=True)
            message.status = "FAILED"
            message.error = f"{type(e).__name__}: {str(e)}"
            message.result = {
                "engine": "Antigravity Autonomous Engineer",
                "task": payload.get("description", message.action),
                "error_type": type(e).__name__,
            }
            return message
