"""Standalone Client Worker for Mukil's Local PC.
Connects to the 24/7 Cloud Server via WebSocket, listens for tasks from Telegram,
and executes them locally on the physical PC hardware using AutonomousAgentBrain & Antigravity.
Also streams real-time Live Brain Context synchronization to the Cloud Server.
"""
import asyncio
import json
import logging
import os
import sys
import websockets
from dotenv import load_dotenv

# Load local environment
load_dotenv()

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from app.tools.agent_brain import AutonomousAgentBrain
from tools.live_brain_syncer import compile_live_brain_context

os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs"), exist_ok=True)
log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "pc_bridge_worker.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file, encoding="utf-8")
    ]
)
logger = logging.getLogger("PCWorkerClient")

CLOUD_SERVER_URL = os.getenv("CLOUD_SERVER_URL", "wss://aura-os-jarvis.onrender.com/api/v1/bridge/ws")
BRIDGE_SECRET = os.getenv("PC_BRIDGE_SECRET", "mukil-aura-pc-bridge-secret-2026")
WORKER_ID = os.getenv("WORKER_ID", "mukil_primary_pc")


async def sync_brain_loop(ws):
    """Continuously streams AGY live context to the Cloud Server every 15s."""
    logger.info("🧠 Live Brain Context sync loop started.")
    while True:
        try:
            payload = compile_live_brain_context()
            msg = {
                "type": "SYNC_BRAIN_CONTEXT",
                "worker_id": WORKER_ID,
                "context": payload,
            }
            await ws.send(json.dumps(msg))
            logger.debug("📡 Sent SYNC_BRAIN_CONTEXT to Cloud Server.")
        except Exception as e:
            logger.warning(f"Notice in sync_brain_loop: {e}")
            break
        await asyncio.sleep(15)


async def run_pc_worker():
    """Persistent loop that maintains a connection to the Cloud Server."""
    brain = AutonomousAgentBrain()
    ws_uri = f"{CLOUD_SERVER_URL}?worker_id={WORKER_ID}&token={BRIDGE_SECRET}"

    logger.info("=" * 60)
    logger.info("🌌 JARVIS LOCAL PC WORKER BRIDGE STARTING...")
    logger.info(f"📍 Target Server: {CLOUD_SERVER_URL}")
    logger.info(f"💻 Worker ID: {WORKER_ID}")
    logger.info("=" * 60)

    while True:
        sync_task = None
        try:
            logger.info(f"Connecting to Cloud Server at {CLOUD_SERVER_URL}...")
            async with websockets.connect(ws_uri, ping_interval=20, ping_timeout=10) as ws:
                logger.info("🟢 100% CONNECTED! Local PC Worker is listening for Cloud tasks...")
                
                # Start live brain sync in background
                sync_task = asyncio.create_task(sync_brain_loop(ws))
                
                while True:
                    raw_msg = await ws.recv()
                    task = json.loads(raw_msg)
                    task_id = task.get("task_id", "unknown")
                    command = task.get("command", "")
                    if not command or not command.strip() or task.get("type") in ["PING", "HEARTBEAT"]:
                        continue
                    logger.info(f"⚡ Received Cloud Task [{task_id}]: '{command}'")

                    task_type = task.get("task_type") or task.get("type")
                    if task_type == "TRIGGER_PHONE_CALL" or (command.lower().startswith("call") and "phone" in command.lower()):
                        calling_script = os.path.join(r"C:\Users\mukil\continuous-calling-agent", "call_mukil.py")
                        if not os.path.exists(calling_script):
                            calling_script = os.path.join(r"C:\Users\mukil\aura-os\voice_calling_agent", "call_mukil.py")
                        
                        call_res_text = ""
                        try:
                            import subprocess
                            c_proc = subprocess.run([sys.executable, calling_script], capture_output=True, text=True, timeout=15)
                            if c_proc.returncode == 0 and "SUCCESS" in c_proc.stdout:
                                call_res_text = "📞 Incoming phone call successfully triggered on your Redmi Note 14 Pro+ 5G! Arc-Reactor Call HUD is ringing!"
                            else:
                                call_res_text = f"⚠️ Phone call intent attempted, but ADB notice: {c_proc.stdout.strip() or c_proc.stderr.strip()}"
                        except Exception as ce:
                            call_res_text = f"❌ Phone call trigger error: {ce}"
                        
                        response_payload = {
                            "task_id": task_id,
                            "status": "COMPLETED",
                            "output_text": call_res_text,
                            "photo_path": None,
                        }
                        await ws.send(json.dumps(response_payload))
                        logger.info(f"✅ Finished Phone Call Task [{task_id}]")
                        continue

                    # Execute task locally on PC via AutonomousAgentBrain
                    res_text, photo_path = await brain.process_user_intent(
                        user_input=command,
                        user_name="Mukil",
                    )

                    response_payload = {
                        "task_id": task_id,
                        "status": "COMPLETED",
                        "output_text": res_text,
                        "photo_path": photo_path,
                    }
                    await ws.send(json.dumps(response_payload))
                    logger.info(f"✅ Finished Task [{task_id}] & reported back to Cloud Server.")

        except (websockets.exceptions.ConnectionClosed, ConnectionRefusedError) as e:
            logger.warning(f"Connection to Cloud Server lost: {e}. Reconnecting in 5s...")
        except Exception as ex:
            logger.error(f"Unexpected worker loop error: {ex}. Reconnecting in 5s...")
        finally:
            if sync_task and not sync_task.done():
                sync_task.cancel()
        await asyncio.sleep(5)


if __name__ == "__main__":
    try:
        asyncio.run(run_pc_worker())
    except KeyboardInterrupt:
        logger.info("PC Worker stopped by user.")
