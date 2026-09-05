"""Device Presence & Smart Presentation Router for AURA-OS / JARVIS.
Handles "Open panni kaatu" / "Show me" requests by inspecting live hardware telemetry:
  - If PC is ONLINE: Dispatches to Local PC Worker to launch on physical Windows screen + take screenshot proof.
  - If PC is OFFLINE: Gracefully delivers direct Mobile Telegram Photo preview + Google Drive preview link.
"""
import os
import logging
from typing import Dict, Any, Optional
from pydantic import BaseModel

logger = logging.getLogger("DevicePresenceRouter")


class PresentationResult(BaseModel):
    mode_selected: str  # "PC_SCREEN_LAUNCH" | "MOBILE_TELEGRAM_PREVIEW"
    is_pc_online: bool
    status_message: str
    target_resource: str
    screenshot_path: Optional[str] = None
    drive_link: Optional[str] = None


class DevicePresenceRouter:
    """
    Intelligently routes presentation intents based on Mukil's active physical device state.
    """

    def __init__(self, bridge_server=None):
        self.bridge_server = bridge_server

    def check_pc_status(self) -> bool:
        """Returns True if the local PC worker is actively connected to the WebSocket bridge."""
        if self.bridge_server and hasattr(self.bridge_server, "is_pc_online"):
            try:
                return bool(self.bridge_server.is_pc_online())
            except Exception as e:
                logger.warning(f"Error checking bridge PC status: {e}")
        return False

    async def route_presentation(
        self,
        file_path_or_url: str,
        user_name: str = "Mukil",
        drive_link: Optional[str] = None
    ) -> PresentationResult:
        is_online = self.check_pc_status()
        resource = file_path_or_url.strip()

        if is_online:
            logger.info(f"🟢 PC is ONLINE. Dispatching '{resource}' to physical PC screen...")
            # If bridge server is bound, dispatch open command
            if self.bridge_server and hasattr(self.bridge_server, "dispatch_task"):
                try:
                    res = await self.bridge_server.dispatch_task(
                        command=f"Start-Process '{resource}'",
                        task_type="OPEN_ON_SCREEN"
                    )
                    return PresentationResult(
                        mode_selected="PC_SCREEN_LAUNCH",
                        is_pc_online=True,
                        status_message=f"Maapla, un laptop active-aa irukku! Screen-la direct-aa '{os.path.basename(resource)}' open panni vechuten, paaru! 💻✨",
                        target_resource=resource,
                        screenshot_path=res.get("screenshot_path"),
                        drive_link=drive_link
                    )
                except Exception as ex:
                    logger.warning(f"PC dispatch failed: {ex}. Falling back to mobile preview.")

        # Fallback / Offline route: Phone Telegram preview
        logger.info(f"🔴 PC is OFFLINE. Routing '{resource}' as Mobile Telegram preview...")
        drive_url = drive_link or "https://drive.google.com/drive/folders/1nGZG5-eIcxmkgQxBtZ7tjGTUoWWNY4m1"
        return PresentationResult(
            mode_selected="MOBILE_TELEGRAM_PREVIEW",
            is_pc_online=False,
            status_message=(
                f"Maapla, un laptop ippo standby / closed-la irukku. "
                f"No worries! Phone-laye paaka direct 5TB Drive preview link idho: {drive_url} 📱✨"
            ),
            target_resource=resource,
            screenshot_path=None,
            drive_link=drive_url
        )
