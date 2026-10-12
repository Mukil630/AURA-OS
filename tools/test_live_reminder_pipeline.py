import asyncio
import json
import sys
import websockets
import httpx

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

async def test_pipeline():
    ws_url = "ws://127.0.0.1:8000/api/v1/call/ws?device_id=test_phone_client"
    print(f"[*] Step 1: Connecting phone test client to {ws_url}...")

    async with websockets.connect(ws_url) as ws:
        init_msg = await ws.recv()
        print(f"[OK] Phone connected! Handshake: {init_msg}")

        # Step 2: Schedule a reminder 5s from now
        print("[*] Step 2: Submitting 5-second test reminder via /api/reminders/add...")

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "http://127.0.0.1:8000/api/reminders/add",
                json={
                    "task": "Boss Mukil Cloud Reminder Test",
                    "when": "5s"
                }
            )
            print(f"[OK] Reminder API response: {resp.json()}")

        print("[*] Step 3: Waiting for Daemon to trigger Call Hub and ring the phone client (max 30s)...")
        try:
            call_event = await asyncio.wait_for(ws.recv(), timeout=30.0)
            print(f"\n" + "=" * 60)
            print(f"SUCCESS! PHONE RECEIVED INCOMING CALL ALARM SIGNAL:")
            print(f"Payload: {call_event}")
            print(f"=" * 60 + "\n")
        except asyncio.TimeoutError:
            print("[ERROR] Timed out waiting for incoming call signal.")

asyncio.run(test_pipeline())
