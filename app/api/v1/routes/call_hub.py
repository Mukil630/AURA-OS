"""
AURA-OS Cloud Mobile Calling Hub
app/api/v1/routes/call_hub.py
Enables 24/7 internet-wide incoming call signaling directly between Render Cloud and Mukil's Android device.
"""

import json
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from pydantic import BaseModel

logger = logging.getLogger("CallHubRoute")

router = APIRouter(prefix="/call", tags=["AURA-OS Cloud Calling Hub"])

class CallTriggerRequest(BaseModel):
    caller_name: Optional[str] = "JARVIS"
    reason: Optional[str] = "executive_update"
    custom_message: Optional[str] = None

class CallHubManager:
    def __init__(self):
        self.active_devices: Dict[str, WebSocket] = {}

    async def register_device(self, device_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_devices[device_id] = websocket
        logger.info(f"📱 Phone connected to Cloud Calling Hub: {device_id} (Total: {len(self.active_devices)})")
        # Send welcome ack
        await websocket.send_text(json.dumps({
            "event": "connected",
            "message": "JARVIS Cloud Calling Uplink Active 24/7"
        }))

    def unregister_device(self, device_id: str):
        if device_id in self.active_devices:
            del self.active_devices[device_id]
            logger.info(f"📱 Phone disconnected from Cloud Calling Hub: {device_id}")

    async def trigger_call(self, caller_name: str = "JARVIS", reason: str = "executive_update", custom_message: Optional[str] = None) -> bool:
        if not self.active_devices:
            logger.warning("No phones currently connected to Cloud Calling Hub.")
            return False

        payload = json.dumps({
            "event": "incoming_call",
            "caller": caller_name,
            "reason": reason,
            "message": custom_message or "வணக்கம் முகில் மாப்ள! நான் ஜார்விஸ் பேசுறேன்."
        })

        success = False
        for dev_id, ws in list(self.active_devices.items()):
            try:
                await ws.send_text(payload)
                logger.info(f"⚡ Dispatched incoming call intent to {dev_id} over Cloud WebSocket!")
                success = True
            except Exception as e:
                logger.error(f"Failed to transmit to {dev_id}: {e}")
                self.unregister_device(dev_id)

        return success

call_hub_manager = CallHubManager()

@router.get("/status")
async def get_call_hub_status():
    """Returns real-time connection status of mobile devices."""
    return {
        "status": "online",
        "service": "aura-os-cloud-calling-hub",
        "connected_devices_count": len(call_hub_manager.active_devices),
        "devices": list(call_hub_manager.active_devices.keys())
    }

@router.post("/trigger")
async def trigger_call_to_phone(req: CallTriggerRequest = CallTriggerRequest()):
    """Triggers an incoming phone call to Mukil's Android device over Cloud Internet."""
    success = await call_hub_manager.trigger_call(
        caller_name=req.caller_name or "JARVIS",
        reason=req.reason or "executive_update",
        custom_message=req.custom_message
    )
    if success:
        return {"status": "success", "message": "Call signal transmitted to phone over Cloud!"}
    else:
        return {
            "status": "pending_or_offline",
            "message": "Call signal queued. Phone currently not connected to Cloud WebSocket."
        }

@router.websocket("/ws")
async def websocket_call_endpoint(
    websocket: WebSocket,
    device_id: str = Query(default="mukil_phone")
):
    """Persistent 24/7 Cloud WebSocket endpoint for Mukil's Android app."""
    await call_hub_manager.register_device(device_id, websocket)
    try:
        while True:
            text = await websocket.receive_text()
            try:
                msg = json.loads(text)
                if msg.get("event") == "ping":
                    await websocket.send_text(json.dumps({"event": "pong"}))
            except Exception:
                pass
    except (WebSocketDisconnect, Exception):
        call_hub_manager.unregister_device(device_id)
