"""
JARVIS Autonomous Instant Call Trigger Loop
tools/trigger_live_call.py
Listens for phone to connect to Render Cloud WebSocket or ADB USB/Wi-Fi and fires the call immediately.
"""
import os
import sys
import json
import time
import subprocess
import urllib.request
import urllib.error

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

STATUS_URL = "https://aura-os-jarvis.onrender.com/api/v1/call/status"
TRIGGER_URL = "https://aura-os-jarvis.onrender.com/api/v1/call/trigger"
ADB_PATH = os.path.expanduser(r"~\AppData\Local\Android\Sdk\platform-tools\adb.exe")

def check_and_fire():
    print("=" * 60)
    print("📞 JARVIS ACTIVE CALL TRIGGER ENGINE")
    print("=" * 60)
    print("Scanning Cloud WebSocket & Hardware ADB for Mukil's Phone...")

    # 1. Check Cloud WebSocket Status
    cloud_connected = False
    try:
        req = urllib.request.Request(STATUS_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            count = data.get("connected_devices_count", 0)
            devs = data.get("devices", [])
            print(f"[CLOUD UPLINK] Active Phones on Cloud: {count} {devs}")
            if count > 0:
                cloud_connected = True
    except Exception as e:
        print(f"[CLOUD UPLINK] Check notice: {e}")

    # 2. Fire Cloud Call if connected
    if cloud_connected:
        print("⚡ Firing Instant Incoming Call via Cloud WebSocket...")
        payload = json.dumps({
            "caller_name": "JARVIS PRIME",
            "reason": "instant_test_call",
            "custom_message": "Vanakkam Boss Mukil! JARVIS incoming call is live and connected!"
        }).encode("utf-8")
        treq = urllib.request.Request(TRIGGER_URL, data=payload, headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(treq, timeout=6) as tresp:
                res = json.loads(tresp.read().decode("utf-8"))
                print(f"✅ CALL TRANSMITTED OVER CLOUD! {res}")
                print("🔔 Phone is ringing with Arc Reactor HUD & ringtone!")
                return True
        except Exception as te:
            print(f"Error transmitting cloud call: {te}")

    # 3. Check ADB Hardware (USB / Wi-Fi)
    if os.path.exists(ADB_PATH):
        try:
            # Reconnect Wi-Fi port 5555
            subprocess.run([ADB_PATH, "connect", "192.168.1.12:5555"], capture_output=True, timeout=2)
            out = subprocess.check_output([ADB_PATH, "devices"], text=True)
            lines = [l.strip() for l in out.strip().split("\n")[1:] if l.strip() and "offline" not in l]
            print(f"[ADB HARDWARE] Connected ADB Devices: {lines}")
            if lines:
                target = lines[0].split()[0]
                print(f"⚡ Firing Hardware Call Intent to {target}...")
                cmd = [
                    ADB_PATH, "-s", target, "shell", "am", "start",
                    "-n", "com.example.voiceassistantapp/.MainActivity",
                    "--ez", "incoming_call", "true",
                    "--es", "caller", "JARVIS PRIME",
                    "--es", "message", "Vanakkam Boss! Call attend pannunga!"
                ]
                r = subprocess.run(cmd, capture_output=True, text=True)
                print("✅ HARDWARE INTENT DISPATCHED:", r.stdout.strip())
                print("🔔 PHONE IS RINGING NOW!")
                return True
        except Exception as ae:
            print(f"[ADB HARDWARE] Notice: {ae}")

    print("\n⚠️ Phone currently offline on both Cloud WebSocket and ADB.")
    print("👉 Solution: Phone-la VoiceAssistantApp open pannunga, or USB connect pannunga!")
    return False

if __name__ == "__main__":
    check_and_fire()
