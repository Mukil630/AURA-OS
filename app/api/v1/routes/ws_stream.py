"""
Real-Time WebSocket Stream & Multi-Device Synchronization Hub.
Enables instant sub-30ms voice audio, terminal execution streams, and telemetry updates between Phone and PC.
"""
import asyncio
import json
import logging
from typing import List, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(prefix="/ws", tags=["Real-Time WebSocket Hub"])
logger = logging.getLogger("WebSocketHub")

class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket client connected. Total active: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket client disconnected. Total active: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        dead_connections = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.add(connection)
        for dead in dead_connections:
            self.active_connections.discard(dead)

manager = ConnectionManager()

@router.websocket("/stream")
async def websocket_stream_endpoint(websocket: WebSocket):
    """Bidirectional WebSocket connection for live voice, terminal logs, and system events."""
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                event_type = msg.get("type", "CHAT")

                if event_type == "PING":
                    await websocket.send_json({"type": "PONG", "timestamp": msg.get("timestamp")})

                elif event_type == "VOICE_CHUNK":
                    # Process voice chunk in real time
                    transcript = msg.get("text", "")
                    if transcript:
                        from brain.agent_brain import AgentBrain
                        brain = AgentBrain()
                        reply = brain.process_message(transcript, user_name="Mukil")
                        await websocket.send_json({
                            "type": "VOICE_REPLY",
                            "transcript": transcript,
                            "reply": reply
                        })

                elif event_type == "TERMINAL_INPUT":
                    cmd = msg.get("command", "")
                    from tools.pc_tools import run_powershell
                    out = run_powershell(cmd)
                    await websocket.send_json({
                        "type": "TERMINAL_OUTPUT",
                        "command": cmd,
                        "output": out
                    })

                else:
                    # Echo broadcast to all connected devices
                    await manager.broadcast({
                        "type": "SYNC_EVENT",
                        "data": msg
                    })

            except json.JSONDecodeError:
                await websocket.send_text("Invalid JSON payload")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket exception: {e}")
        manager.disconnect(websocket)
