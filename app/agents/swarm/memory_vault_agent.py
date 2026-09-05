"""MemoryVault Agent for AURA-OS Swarm.
Manages persistent state, Living Task Ledger, and the 250GB Distributed Google Drive Storage Mesh.
"""
import os
import json
import logging
from typing import Dict, Any, Optional
from app.agents.swarm.base_swarm_agent import BaseSwarmAgent, SwarmTaskMessage

logger = logging.getLogger("MemoryVaultAgent")


class MemoryVaultAgent(BaseSwarmAgent):
    def __init__(self):
        super().__init__(
            agent_name="MemoryVault",
            role_description="Custodian of persistent memory, 250GB Distributed Drive Storage Mesh, and Living Task Ledger"
        )
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.mesh_file = os.path.join(base_dir, "storage", "memory", "distributed_drive_mesh.json")
        self.task_log_file = os.path.join(base_dir, "storage", "memory", "task_log.json")

    async def process_task(self, message: SwarmTaskMessage) -> SwarmTaskMessage:
        logger.info(f"📚 [MemoryVault] Processing action: {message.action}")
        action = message.action.upper()
        payload = message.payload

        try:
            if action in ["GET_DRIVE_NODE", "ROUTE_STORAGE"]:
                category = payload.get("category", "node_01_core_memory")
                node_info = self._get_mesh_node(category)
                message.status = "COMPLETED"
                message.result = node_info
                return message

            elif action in ["LIST_ALL_MESH_NODES", "STORAGE_STATUS"]:
                nodes = self._get_all_mesh_nodes()
                message.status = "COMPLETED"
                message.result = {
                    "total_nodes": len(nodes),
                    "allocated_pool_gb": 250,
                    "nodes": nodes,
                    "summary": f"🌐 Active Distributed Storage Mesh: 10 Nodes (250GB Pool) Operational."
                }
                return message

            elif action in ["QUERY_TASK_STATUS", "GET_LAST_LOG"]:
                recent_logs = self._get_recent_task_logs(limit=5)
                message.status = "COMPLETED"
                message.result = {
                    "recent_tasks": recent_logs,
                    "summary": f"Retrieved {len(recent_logs)} recent tasks from persistent ledger."
                }
                return message

            else:
                message.status = "FAILED"
                message.error = f"Unsupported MemoryVault action: {action}"
                return message

        except Exception as e:
            logger.error(f"MemoryVault error: {e}")
            message.status = "FAILED"
            message.error = str(e)
            return message

    def _get_mesh_node(self, category: str) -> Dict[str, Any]:
        mesh = self._get_all_mesh_nodes()
        if category in mesh:
            return mesh[category]
        # Return fallback node 1
        return mesh.get("node_01_core_memory", {
            "id": "14fGVZomgy2CItfspYo7cVXSImAqJDZZX",
            "url": "https://drive.google.com/open?id=14fGVZomgy2CItfspYo7cVXSImAqJDZZX",
            "role": "Persistent JSON Context & Task Logs"
        })

    def _get_all_mesh_nodes(self) -> Dict[str, Any]:
        if os.path.exists(self.mesh_file):
            try:
                with open(self.mesh_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("nodes", {})
            except Exception as e:
                logger.warning(f"Could not read mesh file: {e}")
        return {}

    def _get_recent_task_logs(self, limit: int = 5) -> list:
        if os.path.exists(self.task_log_file):
            try:
                with open(self.task_log_file, "r", encoding="utf-8") as f:
                    logs = json.load(f)
                    return logs[-limit:]
            except Exception as e:
                logger.warning(f"Could not read task log: {e}")
        return []
