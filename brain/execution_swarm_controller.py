"""
========================================================================================
AURA-OS — AUTONOMOUS EXECUTION SWARM CONTROLLER (execution_swarm_controller.py)
----------------------------------------------------------------------------------------
Core Architectural Mandate (By Mukil):
1. ACTION-BEFORE-SPEECH:
   - An agent NEVER replies to the user before running tools & querying memory.
   - First Execute -> Observe physical output -> Formulate truthful reply based ONLY on observed reality.
2. HONEST FAILURE DISCLOSURE:
   - If primary agent/tool fails, disclose the failure immediately to the user.
3. DYNAMIC BACKUP AGENT SWARM & AUTO-RETRY:
   - Automatically delegate failed task to a backup agent / secondary tool.
   - Retry execution and observe result.
4. STATE PERSISTENCE:
   - Update context.json with physical proof only.
========================================================================================
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional, Callable, Tuple

logger = logging.getLogger("ExecutionSwarmController")
CONTEXT_PATH = r"C:\Users\mukil\jarvis-core\storage\memory\context.json"


class AgentTaskResult:
    def __init__(self, success: bool, output: Any, error: Optional[str] = None, agent_used: str = "Primary"):
        self.success = success
        self.output = output
        self.error = error
        self.agent_used = agent_used
        self.retried_with_backup = False
        self.backup_agent_used = None


class ExecutionSwarmController:
    """
    Orchestrates Action-Before-Speech, Physical Verification, and Backup Agent Failover.
    """

    def __init__(self, primary_agent_name: str, backup_agent_name: str):
        self.primary_agent_name = primary_agent_name
        self.backup_agent_name = backup_agent_name

    def execute_with_fallback(
        self,
        task_name: str,
        primary_tool_fn: Callable[[], Tuple[bool, Any]],
        backup_tool_fn: Optional[Callable[[], Tuple[bool, Any]]] = None,
        context_updater: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        Executes task strictly BEFORE speech.
        If primary fails, truthfully logs failure, delegates to backup agent, and retries.
        """
        logger.info(f"[Swarm] Initiating task '{task_name}' via Primary Agent: {self.primary_agent_name}")
        
        # STEP 1: Execute Primary Tool FIRST (Zero Text Output to User Yet)
        try:
            p_success, p_output = primary_tool_fn()
        except Exception as e:
            p_success = False
            p_output = str(e)

        # STEP 2: Evaluate Primary Outcome
        if p_success:
            logger.info(f"[Swarm] Primary Agent '{self.primary_agent_name}' succeeded.")
            reply = self._synthesize_verified_reply(task_name, p_output, agent_name=self.primary_agent_name)
            self._persist_to_memory(task_name, success=True, agent=self.primary_agent_name, proof=p_output)
            return {
                "success": True,
                "agent_used": self.primary_agent_name,
                "retried": False,
                "verified_output": p_output,
                "final_reply": reply
            }

        # STEP 3: Primary Failed — Prepare Honest Disclosure
        logger.warning(f"[Swarm] Primary Agent '{self.primary_agent_name}' FAILED: {p_output}")
        disclosure = f"Warning: Primary Agent ({self.primary_agent_name}) encountered an issue: '{p_output}'."

        # STEP 4: If Backup Agent Exists, Handover & Retry Immediately
        if backup_tool_fn:
            logger.info(f"[Swarm] Initiating Failover to Backup Agent: {self.backup_agent_name}")
            try:
                b_success, b_output = backup_tool_fn()
            except Exception as e:
                b_success = False
                b_output = str(e)

            if b_success:
                logger.info(f"[Swarm] Backup Agent '{self.backup_agent_name}' succeeded on retry!")
                reply = (
                    f"{disclosure} But don't worry, Boss! Switched to Backup Agent ({self.backup_agent_name}) "
                    f"and successfully completed the task: {b_output}"
                )
                self._persist_to_memory(
                    task_name, success=True, agent=self.backup_agent_name, proof=b_output, fallback_from=self.primary_agent_name
                )
                return {
                    "success": True,
                    "agent_used": self.backup_agent_name,
                    "retried": True,
                    "fallback_triggered": True,
                    "verified_output": b_output,
                    "final_reply": reply
                }
            else:
                # Both Primary and Backup Failed — Complete Truthful Disclosure (Zero Fake Success)
                logger.error(f"[Swarm] Both Primary and Backup agents failed for task '{task_name}'")
                final_error_reply = (
                    f"Task execution failed, Boss. Primary ({self.primary_agent_name}) error: {p_output}. "
                    f"Backup ({self.backup_agent_name}) retry also failed: {b_output}. "
                    f"Physical action could not be completed."
                )
                self._persist_to_memory(
                    task_name, success=False, agent=f"{self.primary_agent_name}+{self.backup_agent_name}", proof=final_error_reply
                )
                return {
                    "success": False,
                    "agent_used": "None",
                    "retried": True,
                    "all_failed": True,
                    "final_reply": final_error_reply
                }

        # No backup provided and primary failed
        no_backup_reply = f"{disclosure} No secondary backup configured for this task. Action aborted."
        self._persist_to_memory(task_name, success=False, agent=self.primary_agent_name, proof=no_backup_reply)
        return {
            "success": False,
            "agent_used": self.primary_agent_name,
            "retried": False,
            "final_reply": no_backup_reply
        }

    def _synthesize_verified_reply(self, task_name: str, verified_output: Any, agent_name: str) -> str:
        """
        Synthesizes reply strictly from verified physical output.
        """
        return f"Task '{task_name}' successfully executed by {agent_name}. Verified Result: {verified_output}"

    def _persist_to_memory(self, task_name: str, success: bool, agent: str, proof: Any, fallback_from: Optional[str] = None):
        """
        Persists verified execution trace into context.json.
        """
        if not os.path.exists(CONTEXT_PATH):
            return
        try:
            with open(CONTEXT_PATH, "r", encoding="utf-8") as f:
                ctx = json.load(f)
            
            ctx.setdefault("swarm_execution_log", [])
            log_item = {
                "task": task_name,
                "agent": agent,
                "success": success,
                "proof": str(proof),
                "fallback_from": fallback_from
            }
            ctx["swarm_execution_log"].append(log_item)
            ctx["swarm_execution_log"] = ctx["swarm_execution_log"][-30:] # Maintain 30 entries (0 MB bloat)

            with open(CONTEXT_PATH, "w", encoding="utf-8") as f:
                json.dump(ctx, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not persist swarm log: {e}")
