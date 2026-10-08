import os
import shutil
import subprocess
import sys
import time

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

def find_adb():
    adb_which = shutil.which("adb")
    if adb_which:
        return adb_which

    sdk_adb = os.path.expanduser(r"~\AppData\Local\Android\Sdk\platform-tools\adb.exe")
    if os.path.exists(sdk_adb):
        return sdk_adb

    return "adb"

def call_mukil():
    print("=" * 60)
    print("[JARVIS PRIME] INITIATING SECURE CALL TO MUKIL")
    print("=" * 60)

    adb_bin = find_adb()

    try:
        devices_out = subprocess.check_output([adb_bin, "devices"], text=True)
        lines = [line.strip() for line in devices_out.strip().split("\n")[1:] if line.strip()]
        if not lines:
            print("[ERROR] No connected device found via ADB! Please connect phone via USB or Wi-Fi.")
            return False

        device_id = lines[0].split()[0]
        print(f"[OK] Target Device Connected: {device_id} (Redmi Note 14 Pro+ 5G)")

        # Fire Incoming Call Intent (Natively turns on screen & wakes device)
        print("[SIGNAL] Transmitting Stark Quantum Voice Uplink Intent...")
        cmd = [
            adb_bin, "-s", device_id, "shell", "am", "start",
            "-n", "com.example.voiceassistantapp/.MainActivity",
            "--ez", "incoming_call", "true"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print("[SUCCESS] Incoming call triggered on phone!")
            print("[RING] Stark Radar Chime & Arc-Reactor Call HUD active on device screen.")
            print("[READY] Phone is ringing! Tap 'ACCEPT CALL' to begin voice uplink.")
            return True
        else:
            print(f"[ERROR] Failed to trigger call intent: {result.stderr}")
            return False

    except Exception as e:
        print(f"[ERROR] Exception during call trigger: {e}")
        return False

if __name__ == "__main__":
    call_mukil()
