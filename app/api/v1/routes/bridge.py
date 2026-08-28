"""FastAPI WebSocket & REST Endpoints for Cloud ⟷ Local PC Bridge."""
import json
import logging
from typing import Any, Dict
from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, Field

from app.connectors.bridge.pc_cloud_bridge import bridge_server

logger = logging.getLogger("BridgeRoute")

router = APIRouter(prefix="/bridge", tags=["Cloud ⟷ PC Bridge"])


class RemoteDispatchContract(BaseModel):
    command: str = Field(..., description="Natural language command or task to execute on PC")
    task_type: str = Field(default="EXECUTE_INTENT", description="Task classification")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Optional parameters")


@router.get("/status", summary="Check PC Bridge Status")
async def get_bridge_status() -> Dict[str, Any]:
    """Returns real-time online status of connected local PC workers."""
    return {
        "pc_online": bridge_server.is_pc_online(),
        "active_workers": list(bridge_server.active_connections.keys()),
        "queued_offline_tasks": len(bridge_server.offline_queue),
    }


@router.post("/dispatch", summary="Dispatch Task to Local PC from Cloud")
async def dispatch_task_to_pc(payload: RemoteDispatchContract) -> Dict[str, Any]:
    """Sends a remote task to Mukil's PC and returns the output + screenshot verification."""
    result = await bridge_server.dispatch_task(
        command=payload.command,
        task_type=payload.task_type,
        parameters=payload.parameters,
    )
    return result


@router.websocket("/ws")
async def websocket_pc_endpoint(
    websocket: WebSocket,
    worker_id: str = Query(default="mukil_pc"),
    token: str = Query(default=""),
):
    """
    WebSocket endpoint that Mukil's local PC connects to.
    Receives tasks from Cloud Server and returns execution results.
    """
    connected = await bridge_server.connect_worker(websocket, worker_id, token)
    if not connected:
        return

    try:
        while True:
            data_text = await websocket.receive_text()
            try:
                data = json.loads(data_text)
                bridge_server.handle_worker_response(data)
            except Exception as e:
                logger.warning(f"Invalid worker message: {e}")
    except WebSocketDisconnect:
        bridge_server.disconnect_worker(worker_id)
    except Exception as e:
        logger.error(f"WebSocket error for worker '{worker_id}': {e}")
        bridge_server.disconnect_worker(worker_id)
