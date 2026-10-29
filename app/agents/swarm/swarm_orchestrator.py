"""Swarm Orchestrator for AURA-OS.
Coordinates the specialized worker agents (WebScout, PlacementHunter, SGCExecutive, PCPilot, MemoryVault)
under a unified async message dispatching plane with circuit breaker, timeout, and backup failover.
"""
import asyncio
import logging
import time
from typing import Dict, Any, Optional, List
from uuid import uuid4

from app.agents.swarm.base_swarm_agent import BaseSwarmAgent, SwarmTaskMessage
from app.agents.swarm.web_scout_agent import WebScoutAgent
from app.agents.swarm.placement_hunter_agent import PlacementHunterAgent
from app.agents.swarm.sgc_executive_agent import SGCExecutiveAgent
from app.agents.swarm.pc_pilot_agent import PCPilotAgent
from app.agents.swarm.memory_vault_agent import MemoryVaultAgent
from app.agents.swarm.antigravity_agent import AntigravityAgent
from app.agents.swarm.server_agent import ServerAgent

from brain.agent_health_monitor import health_registry
from brain.agent_capability_registry import capability_registry

logger = logging.getLogger("SwarmOrchestrator")

DEFAULT_TIMEOUT_SECONDS = 120.0
DEFAULT_FAILURE_THRESHOLD = 3
DEFAULT_BREAKER_TIMEOUT = 60.0

BACKUP_FALLBACK_MAP: Dict[str, str] = {
    "Antigravity": "ServerAgent",
    "WebScout": "MemoryVault",
    "PlacementHunter": "MemoryVault",
    "SGCExecutive": "MemoryVault",
    "PCPilot": "ServerAgent",
    "ServerAgent": "MemoryVault",
    "MemoryVault": "SGCExecutive",
}


class SwarmOrchestrator:
    def __init__(self):
        self.agents: Dict[str, BaseSwarmAgent] = {
            "WebScout": WebScoutAgent(),
            "PlacementHunter": PlacementHunterAgent(),
            "SGCExecutive": SGCExecutiveAgent(),
            "PCPilot": PCPilotAgent(),
            "MemoryVault": MemoryVaultAgent(),
            "Antigravity": AntigravityAgent(),
            "ServerAgent": ServerAgent()
        }
        self.backup_agent_map: Dict[str, str] = BACKUP_FALLBACK_MAP
        self.default_timeout = DEFAULT_TIMEOUT_SECONDS

        for agent_name in self.agents:
            health_registry.register_agent(
                agent_name,
                failure_threshold=DEFAULT_FAILURE_THRESHOLD,
                timeout=DEFAULT_BREAKER_TIMEOUT
            )

    @property
    def unhealthy_agents(self) -> List[str]:
        return health_registry.get_unhealthy_agents()

    def _get_backup_agent(self, primary_name: str) -> Optional[str]:
        return self.backup_agent_map.get(primary_name)

    async def _dispatch_with_timeout(
        self,
        agent: BaseSwarmAgent,
        msg: SwarmTaskMessage,
        timeout: float
    ) -> SwarmTaskMessage:
        """Wraps agent.process_task with a hard timeout."""
        try:
            result = await asyncio.wait_for(agent.process_task(msg), timeout=timeout)
            return result
        except asyncio.TimeoutError:
            logger.error(f"[Timeout] Agent '{msg.recipient}' did not respond within {timeout}s")
            msg.status = "FAILED"
            msg.error = f"Agent '{msg.recipient}' timed out after {timeout}s (possible connectivity issue)."
            return msg
        except Exception as e:
            logger.error(f"[Dispatch] Agent '{msg.recipient}' raised: {type(e).__name__}: {e}", exc_info=True)
            msg.status = "FAILED"
            msg.error = f"Agent '{msg.recipient}' crashed: {type(e).__name__}: {str(e)}"
            return msg

    async def _try_dispatch(
        self,
        target_agent: str,
        action: str,
        payload: Dict[str, Any],
        task_id: str,
        attempt_label: str,
        timeout: float
    ) -> tuple:
        """Attempts dispatch to one agent, records health metrics. Returns (result_msg, latency_ms)."""
        agent = self.agents.get(target_agent)
        if not agent:
            logger.error(f"Unknown agent '{target_agent}'")
            msg = SwarmTaskMessage(
                task_id=task_id,
                sender="SwarmOrchestrator",
                recipient=target_agent,
                action=action,
                payload=payload,
                status="FAILED",
                error=f"Swarm agent '{target_agent}' is not registered."
            )
            return msg, 0.0

        msg = SwarmTaskMessage(
            task_id=task_id,
            sender="SwarmOrchestrator",
            recipient=target_agent,
            action=action,
            payload=payload,
            status="IN_PROGRESS"
        )

        health_registry.record_call_start(target_agent)
        start = time.time()
        logger.info(f"🚀 [SwarmOrchestrator:{attempt_label}] Dispatching '{action}' to {target_agent} [{task_id}]...")
        result = await self._dispatch_with_timeout(agent, msg, timeout)
        latency_ms = (time.time() - start) * 1000

        if result.status == "COMPLETED":
            health_registry.record_success(target_agent, latency_ms)
            logger.info(f"[SwarmOrchestrator] {target_agent} succeeded in {latency_ms:.0f}ms")
        else:
            health_registry.record_failure(target_agent, Exception(result.error), latency_ms)
            logger.warning(f"[SwarmOrchestrator] {target_agent} failed in {latency_ms:.0f}ms: {result.error}")

        return result, latency_ms

    async def dispatch(
        self,
        target_agent: str,
        action: str,
        payload: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        allow_backup: bool = True,
        auto_translate: bool = True,
    ) -> SwarmTaskMessage:
        """
        Dispatches a task to a designated specialized worker agent.

        Parameters:
            target_agent: The agent name (e.g. "Antigravity", "PCPilot")
            action: Either a concrete agent action (e.g. "VIEW_FILE") or
                    a high-level intent/track (e.g. "AUTONOMOUS_HEAVY_TASK").
                    When auto_translate=True, high-level intents are translated
                    to the concrete action the agent understands.
            payload: Task parameters
            timeout: Max seconds to wait for agent response
            allow_backup: If True, fail over to a backup agent on failure
            auto_translate: If True, translate high-level intents to concrete actions

        If the primary agent's circuit breaker is OPEN, immediately fails over to backup.
        If the primary fails (and allow_backup=True), automatically delegates to a backup agent.
        """
        payload = payload or {}
        task_id = f"task_{uuid4().hex[:8]}"
        timeout = timeout or self.default_timeout

        # --- Step 1: Validate target agent exists ---
        if target_agent not in self.agents:
            logger.error(f"[SwarmOrchestrator] Target agent '{target_agent}' is not registered. Available: {list(self.agents.keys())}")
            return SwarmTaskMessage(
                task_id=task_id,
                sender="SwarmOrchestrator",
                recipient=target_agent,
                action=action,
                payload=payload,
                status="FAILED",
                error=f"Agent '{target_agent}' is not registered. Available: {list(self.agents.keys())}"
            )

        # --- Step 2: Validate / translate action ---
        resolved_action = action
        original_action = action
        if auto_translate:
            resolved_action, was_translated, unresolvable = capability_registry.resolve_action(
                target_agent, action
            )
            if was_translated:
                logger.info(f"[SwarmOrchestrator] Translated intent '{original_action}' -> '{resolved_action}' for agent '{target_agent}'")
                action = resolved_action
            if unresolvable is not None:
                logger.warning(
                    f"[SwarmOrchestrator] Action '{original_action}' is not supported by agent '{target_agent}'. "
                    f"Attempting auto-route to a compatible agent..."
                )
                compatible_agent = capability_registry.find_agent_for_action(original_action)
                if compatible_agent and compatible_agent != target_agent:
                    logger.info(f"[SwarmOrchestrator] Auto-routing '{original_action}' from '{target_agent}' -> '{compatible_agent}'")
                    return await self.dispatch(
                        target_agent=compatible_agent,
                        action=original_action,
                        payload=payload,
                        timeout=timeout,
                        allow_backup=allow_backup,
                        auto_translate=True,
                    )
                else:
                    # Try backup agent translation as last resort
                    if allow_backup:
                        backup_name = self._get_backup_agent(target_agent)
                        if backup_name:
                            backup_resolved, _, _ = capability_registry.resolve_action(backup_name, original_action)
                            if backup_resolved and capability_registry.is_action_supported(backup_name, backup_resolved):
                                logger.info(f"[SwarmOrchestrator] Failover: routing '{original_action}' to backup agent '{backup_name}' as '{backup_resolved}'")
                                return await self.dispatch(
                                    target_agent=backup_name,
                                    action=backup_resolved,
                                    payload=payload,
                                    timeout=timeout,
                                    allow_backup=False,
                                    auto_translate=False,
                                )
                    return self._build_failover_failed_message(
                        task_id, target_agent, action, payload,
                        f"Action '{original_action}' is not supported by agent '{target_agent}' "
                        f"or any backup agent. Supported by {target_agent}: "
                        f"{capability_registry.get_supported_actions(target_agent)}"
                    )

        # --- Step 3: Circuit breaker check ---
        primary_breaker = health_registry.get_breaker(target_agent)
        if primary_breaker and not primary_breaker.allow_call():
            logger.warning(f"[SwarmOrchestrator] Circuit breaker OPEN for '{target_agent}' — initiating failover")
            if allow_backup:
                backup_name = self._get_backup_agent(target_agent)
                if backup_name and backup_name in self.agents:
                    logger.info(f"[SwarmOrchestrator] Failing over to backup agent: {backup_name}")
                    return await self.dispatch(
                        target_agent=backup_name,
                        action=resolved_action,
                        payload=payload,
                        timeout=timeout,
                        allow_backup=False,
                        auto_translate=False,
                    )
                else:
                    return self._build_failover_failed_message(
                        task_id, target_agent, action, payload,
                        "No registered backup agent for failover"
                    )
            else:
                return self._build_failover_failed_message(
                    task_id, target_agent, action, payload,
                    "Circuit breaker OPEN and failover disabled"
                )

        # --- Step 4: Dispatch to primary agent ---
        result, _ = await self._try_dispatch(
            target_agent, resolved_action, payload, task_id,
            attempt_label="PRIMARY", timeout=timeout
        )

        if result.status == "COMPLETED":
            return result

        # --- Step 5: Backup failover ---
        if allow_backup and result.status == "FAILED":
            backup_name = self._get_backup_agent(target_agent)
            if backup_name and backup_name in self.agents:
                backup_breaker = health_registry.get_breaker(backup_name)
                if backup_breaker and not backup_breaker.allow_call():
                    logger.warning(f"[SwarmOrchestrator] Backup agent '{backup_name}' circuit breaker is also OPEN")
                    return self._build_failover_failed_message(
                        task_id, target_agent, action, payload,
                        f"Primary failed: {result.error}. Backup '{backup_name}' also unavailable (breaker OPEN)."
                    )

                backup_action = resolved_action
                if auto_translate:
                    backup_action, _, _ = capability_registry.resolve_action(
                        backup_name, resolved_action
                    )

                logger.info(f"[SwarmOrchestrator] Primary failed, failing over to backup: {backup_name} with action '{backup_action}'")
                backup_result, _ = await self._try_dispatch(
                    backup_name, backup_action, payload, task_id,
                    attempt_label=f"BACKUP(via_{target_agent})", timeout=timeout
                )

                if backup_result.status == "COMPLETED":
                    backup_result.sender = f"SwarmOrchestrator->Backup({backup_name})"
                    backup_result.result["original_agent"] = target_agent
                    backup_result.result["backup_delegated_from"] = target_agent
                    logger.info(f"[SwarmOrchestrator] Backup agent '{backup_name}' succeeded!")
                    return backup_result

                return self._build_failover_failed_message(
                    task_id, target_agent, action, payload,
                    f"Primary '{target_agent}' failed: {result.error}. "
                    f"Backup '{backup_name}' also failed: {backup_result.error}"
                )

            return self._build_failover_failed_message(
                task_id, target_agent, action, payload,
                f"Primary '{target_agent}' failed: {result.error}. No backup agent configured."
            )

        return result

    async def auto_dispatch(
        self,
        intent: str,
        payload: Optional[Dict[str, Any]] = None,
        target_agent: Optional[str] = None,
    ) -> SwarmTaskMessage:
        """
        Auto-dispatch based on intent alone — the orchestrator figures out
        which agent and action to use. This is the main entry point from the
        cognitive router, which passes track names like "AUTONOMOUS_HEAVY_TASK".
        """
        if target_agent:
            return await self.dispatch(target_agent, intent, payload)

        resolved_agent = capability_registry.find_agent_for_action(intent)
        if resolved_agent:
            logger.info(f"[SwarmOrchestrator] Auto-dispatch: intent '{intent}' -> agent '{resolved_agent}'")
            return await self.dispatch(resolved_agent, intent, payload)

        return SwarmTaskMessage(
            task_id=f"task_{uuid4().hex[:8]}",
            sender="SwarmOrchestrator",
            recipient="UNKNOWN",
            action=intent,
            payload=payload or {},
            status="FAILED",
            error=f"No agent found that can handle intent '{intent}'. "
                  f"Available intents: {[k for cap in capability_registry._capabilities.values() for k in cap.get('intent_map', {}).keys()]}"
        )

    @staticmethod
    def _build_failover_failed_message(
        task_id: str,
        agent_name: str,
        action: str,
        payload: Dict[str, Any],
        error_msg: str
    ) -> SwarmTaskMessage:
        return SwarmTaskMessage(
            task_id=task_id,
            sender="SwarmOrchestrator",
            recipient=agent_name,
            action=action,
            payload=payload,
            status="FAILED",
            error=error_msg,
        )

    def get_status_report(self) -> Dict[str, Any]:
        """Returns a full health snapshot of all agents in the swarm."""
        return {
            "agents": health_registry.get_snapshot(),
            "unhealthy_agents": self.unhealthy_agents,
        }
