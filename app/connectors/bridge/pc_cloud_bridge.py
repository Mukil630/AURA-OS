"""Bi-Directional Cloud ⟷ Local PC WebSocket Bridge and Task Dispatcher.
Enables 24/7 Cloud Servers (Railway/Render) to securely orchestrate tasks on Mukil's Local PC
(Antigravity Project Building, Local PowerShell, Screen Proof, App Control) in real-time.
"""
import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set
from uuid import uuid4

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("CloudPCBridge")

BRIDGE_SECRET_TOKEN = os.getenv("PC_BRIDGE_SECRET", "mukil-aura-pc-bridge-secret-2026")


class CloudPCBridgeServer:
    """
    Cloud Server-side WebSocket Hub that manages connections to Mukil's Local PC Workers.
    Dispatches tasks from Telegram/Cloud agents to the local PC and receives visual proofs.
    """

    def __init__(self, secret_token: Optional[str] = None):
        self.secret_token = secret_token or BRIDGE_SECRET_TOKEN
        self.active_connections: Dict[str, WebSocket] = {}
        self.pending_tasks: Dict[str, asyncio.Future] = {}
        self.offline_queue: List[Dict[str, Any]] = []

    def is_pc_online(self) -> bool:
        """Returns True if at least one local PC worker is actively connected."""
        return len(self.active_connections) > 0

    async def connect_worker(self, websocket: WebSocket, worker_id: str, auth_token: str) -> bool:
        """Authenticates and accepts a local PC worker connection."""
        if auth_token != self.secret_token:
            logger.warning(f"Rejected PC Worker connection '{worker_id}': Invalid auth token.")
            await websocket.close(code=4003, reason="Unauthorized")
            return False

        await websocket.accept()
        self.active_connections[worker_id] = websocket
        logger.info(f"🟢 Local PC Worker '{worker_id}' CONNECTED and ONLINE.")

        # Flush any queued offline tasks
        if self.offline_queue:
            logger.info(f"Flushing {len(self.offline_queue)} queued offline tasks to '{worker_id}'...")
            for task in self.offline_queue:
                try:
                    await websocket.send_json(task)
                except Exception as e:
                    logger.warning(f"Could not dispatch queued task: {e}")
            self.offline_queue.clear()

        return True

    def disconnect_worker(self, worker_id: str) -> None:
        """Handles worker disconnection."""
        if worker_id in self.active_connections:
            del self.active_connections[worker_id]
            logger.warning(f"🔴 Local PC Worker '{worker_id}' DISCONNECTED.")

    async def dispatch_task(
        self,
        command: str,
        task_type: str = "EXECUTE_INTENT",
        parameters: Optional[Dict[str, Any]] = None,
        timeout_seconds: float = 45.0,
    ) -> Dict[str, Any]:
        """
        Dispatches a task from Cloud Server to Local PC Worker.
        Waits for local execution and returns result + visual screenshot proof.
        """
        task_id = f"task_{uuid4().hex[:8]}"
        payload = {
            "task_id": task_id,
            "type": task_type,
            "command": command,
            "parameters": parameters or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if not self.is_pc_online():
            logger.info(f"PC Worker offline. Queuing task '{task_id}' for next connection.")
            self.offline_queue.append(payload)
            return {
                "status": "QUEUED_OFFLINE",
                "task_id": task_id,
                "message": "PC is currently in standby. Task has been queued in 5TB Drive Vault and will execute the moment your PC turns on, Boss!",
            }

        # Pick the active worker
        worker_id, ws = next(iter(self.active_connections.items()))
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        self.pending_tasks[task_id] = fut

        try:
            await ws.send_json(payload)
            result = await asyncio.wait_for(fut, timeout=timeout_seconds)
            return result
        except asyncio.TimeoutError:
            logger.error(f"Task '{task_id}' timed out after {timeout_seconds}s.")
            return {
                "status": "TIMEOUT",
                "task_id": task_id,
                "message": f"Local PC execution timed out after {timeout_seconds}s.",
            }
        except Exception as ex:
            logger.error(f"Error dispatching task '{task_id}': {ex}")
            return {
                "status": "ERROR",
                "task_id": task_id,
                "message": f"Bridge dispatch error: {str(ex)}",
            }
        finally:
            self.pending_tasks.pop(task_id, None)

    def handle_worker_response(self, response_data: Dict[str, Any]) -> None:
        """Processes task result received from the local PC worker."""
        task_id = response_data.get("task_id")
        if task_id and task_id in self.pending_tasks:
            fut = self.pending_tasks[task_id]
            if not fut.done():
                fut.set_result(response_data)


# Global singleton instance for Cloud Server
bridge_server = CloudPCBridgeServer()


class LocalPCWorkerClient:
    """
    Client agent running on Mukil's local PC that executes cloud tasks locally
    using AutonomousAgentBrain, PCPilot, and Antigravity.
    """

    def __init__(
        self,
        server_ws_url: str = "ws://localhost:8000/api/v1/bridge/ws",
        worker_id: str = "mukil_primary_pc",
        auth_token: Optional[str] = None,
        agent_brain: Optional[Any] = None,
    ):
        self.server_ws_url = server_ws_url
        self.worker_id = worker_id
        self.auth_token = auth_token or BRIDGE_SECRET_TOKEN
        self.agent_brain = agent_brain
        self.is_running = False

    async def execute_local_task(self, task_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Executes the task on the local PC hardware and returns results."""
        task_id = task_payload.get("task_id", "unknown")
        command = task_payload.get("command", "")
        task_type = task_payload.get("type", "EXECUTE_INTENT")

        logger.info(f"Local Worker executing task [{task_id}]: '{command}'")

        try:
            if not self.agent_brain:
                from app.tools.agent_brain import AutonomousAgentBrain
                self.agent_brain = AutonomousAgentBrain()

            res_text, photo_path = await self.agent_brain.process_user_intent(
                user_input=command,
                user_name="Mukil",
            )

            return {
                "task_id": task_id,
                "status": "COMPLETED",
                "output_text": res_text,
                "photo_path": photo_path,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as ex:
            logger.error(f"Local execution failed for [{task_id}]: {ex}")
            return {
                "task_id": task_id,
                "status": "FAILED",
                "error": str(ex),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
