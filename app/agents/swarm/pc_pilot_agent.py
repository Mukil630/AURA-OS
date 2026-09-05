"""PCPilot Agent for AURA-OS Swarm.
Controls physical Windows hardware, executes PowerShell commands, launches apps, and captures visual proofs.
"""
import logging
from typing import Dict, Any
from app.agents.swarm.base_swarm_agent import BaseSwarmAgent, SwarmTaskMessage
from tools import pc_tools

logger = logging.getLogger("PCPilotAgent")


class PCPilotAgent(BaseSwarmAgent):
    def __init__(self):
        super().__init__(
            agent_name="PCPilot",
            role_description="Physical Windows PC controller, hardware telemetry monitor, and desktop UI operator"
        )

    async def process_task(self, message: SwarmTaskMessage) -> SwarmTaskMessage:
        logger.info(f"🖥️ [PCPilot] Processing action: {message.action}")
        action = message.action.upper()
        payload = message.payload

        try:
            if action in ["TAKE_SCREENSHOT", "CAPTURE_PROOF"]:
                shot_path = pc_tools.take_pc_screenshot()
                message.status = "COMPLETED"
                message.result = {
                    "screenshot_path": shot_path,
                    "summary": f"📸 Captured live PC screen proof: {shot_path}"
                }
                return message

            elif action in ["GET_BATTERY", "BATTERY_STATUS"]:
                status_raw = pc_tools.run_powershell(
                    "(Get-WmiObject -Class Win32_Battery) | Select-Object -Property Name, EstimatedChargeRemaining, BatteryStatus | ConvertTo-Json"
                )
                message.status = "COMPLETED"
                message.result = {
                    "telemetry": status_raw,
                    "summary": "🔋 Battery telemetry retrieved successfully."
                }
                return message

            elif action in ["OPEN_ON_SCREEN", "LAUNCH_APP"]:
                target = payload.get("target", "https://mail.google.com")
                pc_tools.open_browser_url(target)
                import time
                time.sleep(1.5)
                shot_path = pc_tools.take_pc_screenshot()
                summary_msg = f"🖥️ Successfully launched '{target}' on your laptop screen, Boss!"
                if shot_path:
                    summary_msg += f"\n\n📸 Proof Screenshot: `{shot_path}`"
                message.status = "COMPLETED"
                message.result = {
                    "target": target,
                    "screenshot_path": shot_path,
                    "summary": summary_msg
                }
                return message

            elif action in ["PLAY_MEDIA", "PLAY_YOUTUBE"]:
                query = payload.get("query", "vj siddhu vlogs")
                clean_q = query.lower()
                for prefix in ["open youtube and play", "play on laptop", "play on lap", "ella lap la play pannu", "lap la play pannu", "play pannu", "open youtube", "open", "play"]:
                    clean_q = clean_q.replace(prefix, "").strip()
                if not clean_q or len(clean_q) < 2:
                    clean_q = "vj siddhu vlogs"
                out = pc_tools.play_youtube_song(clean_q)
                import time
                time.sleep(2)
                shot_path = pc_tools.take_pc_screenshot()
                summary_msg = f"🎬 YouTube-la '{clean_q}' un laptop screen-la open panni play panna vechuten Boss!"
                if shot_path:
                    summary_msg += f"\n\n📸 Proof Screenshot: `{shot_path}`"
                message.status = "COMPLETED"
                message.result = {
                    "query": clean_q,
                    "output": out,
                    "screenshot_path": shot_path,
                    "summary": summary_msg
                }
                return message

            elif action in ["EXECUTE_POWERSHELL", "RUN_COMMAND"]:
                cmd = payload.get("command", "Get-Date")
                out = pc_tools.run_powershell(cmd)
                summary_text = payload.get("summary", f"Executed PowerShell command: {cmd}")
                import time
                time.sleep(1.5)
                shot_path = pc_tools.take_pc_screenshot()
                summary_msg = summary_text
                if shot_path:
                    summary_msg += f"\n\n📸 Proof Screenshot: `{shot_path}`"
                message.status = "COMPLETED"
                message.result = {
                    "command": cmd,
                    "output": out,
                    "screenshot_path": shot_path,
                    "summary": summary_msg
                }
                return message

            else:
                message.status = "FAILED"
                message.error = f"Unsupported PCPilot action: {action}"
                return message

        except Exception as e:
            logger.error(f"PCPilot error: {e}")
            message.status = "FAILED"
            message.error = str(e)
            return message
