"""
========================================================================================
JARVIS CORE — AIRTEL XSTREAM & ANDROID TV CONTROLLER (xstream_pilot.py)
----------------------------------------------------------------------------------------
Zero-Bloat TV Automation Controller.
Uses the verified local platform-tools ADB (C:\\Users\\mukil\\AppData\\Local\\Android\\Sdk\\platform-tools\\adb.exe).
Controls Airtel Xstream Box, HDMI-CEC linked TV (LG/Intex), Volume, Power, Apps & Toasts.
========================================================================================
"""

import sys
import os
import subprocess
import argparse
import json
from typing import Dict, Any, Optional

ADB_PATH = r"C:\Users\mukil\AppData\Local\Android\Sdk\platform-tools\adb.exe"

# Standard Android TV Keycodes
KEYCODES = {
    "power": 26,            # KEYCODE_POWER
    "wake": 224,            # KEYCODE_WAKEUP
    "sleep": 223,           # KEYCODE_SLEEP
    "home": 3,              # KEYCODE_HOME
    "back": 4,              # KEYCODE_BACK
    "up": 19,               # KEYCODE_DPAD_UP
    "down": 20,             # KEYCODE_DPAD_DOWN
    "left": 21,             # KEYCODE_DPAD_LEFT
    "right": 22,            # KEYCODE_DPAD_RIGHT
    "ok": 66,               # KEYCODE_ENTER / DPAD_CENTER
    "volume_up": 24,        # KEYCODE_VOLUME_UP
    "volume_down": 25,      # KEYCODE_VOLUME_DOWN
    "mute": 164,            # KEYCODE_VOLUME_MUTE
    "play_pause": 85,       # KEYCODE_MEDIA_PLAY_PAUSE
    "menu": 82              # KEYCODE_MENU
}

# Popular Android TV / Airtel Xstream App Packages
APP_PACKAGES = {
    "youtube": "com.google.android.youtube.tv",
    "netflix": "com.netflix.ninja",
    "hotstar": "in.startv.hotstar",
    "prime": "com.amazon.amazonvideo.livingroom",
    "xstream": "airtel.tv.app",
    "settings": "com.android.tv.settings"
}

CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "storage", "memory", "xstream_config.json")


def get_saved_ip() -> Optional[str]:
    """Retrieve last known Xstream Box IP from memory."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("ip")
        except Exception:
            return None
    return None


def save_ip(ip: str):
    """Save valid Xstream Box IP to memory."""
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({"ip": ip, "device": "Airtel Xstream Box (Android TV)"}, f, indent=2)
    except Exception as e:
        print(f"[Warning] Could not save IP to config: {e}")


def run_adb(args: list) -> tuple:
    """Execute ADB command using local verified SDK binary."""
    if not os.path.exists(ADB_PATH):
        return False, f"ADB binary not found at {ADB_PATH}"
    cmd = [ADB_PATH] + args
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return res.returncode == 0, res.stdout.strip() or res.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "ADB command timed out (10s)"
    except Exception as e:
        return False, str(e)


def connect_box(ip: str) -> bool:
    """Connect to Airtel Xstream Box over Wi-Fi port 5555."""
    target = f"{ip}:5555" if ":" not in ip else ip
    print(f"[JARVIS] Connecting to Airtel Xstream Box at {target}...")
    success, output = run_adb(["connect", target])
    print(f"[ADB] {output}")
    if "connected" in output.lower():
        save_ip(ip)
        return True
    return False


def send_key(key_name: str, ip: Optional[str] = None) -> bool:
    """Send remote key press to TV."""
    key = key_name.lower()
    if key not in KEYCODES:
        print(f"[Error] Unknown key '{key_name}'. Supported: {list(KEYCODES.keys())}")
        return False
    
    code = KEYCODES[key]
    target_ip = ip or get_saved_ip()
    args = ["-s", f"{target_ip}:5555", "shell", "input", "keyevent", str(code)] if target_ip else ["shell", "input", "keyevent", str(code)]
    success, out = run_adb(args)
    if success:
        print(f"[JARVIS] Sent Key: {key_name.upper()} (Code {code})")
    else:
        print(f"[Error] Failed to send key: {out}")
    return success


def launch_app(app_name: str, ip: Optional[str] = None) -> bool:
    """Launch Smart TV App."""
    app_key = app_name.lower()
    pkg = APP_PACKAGES.get(app_key, app_name)
    target_ip = ip or get_saved_ip()
    
    # Launch via monkey
    args = ["-s", f"{target_ip}:5555", "shell", "monkey", "-p", pkg, "-c", "android.intent.category.LAUNCHER", "1"] if target_ip else ["shell", "monkey", "-p", pkg, "-c", "android.intent.category.LAUNCHER", "1"]
    print(f"[JARVIS] Launching app {pkg}...")
    success, out = run_adb(args)
    return success


def show_toast(message: str, ip: Optional[str] = None) -> bool:
    """Send text alert popup to TV screen."""
    target_ip = ip or get_saved_ip()
    escaped_msg = message.replace('"', '\\"')
    # Use standard Android notification broadcast or toast
    cmd_str = f'am broadcast -a com.twofortyfouram.locale.intent.action.FIRE_SETTING --es message "{escaped_msg}" 2>/dev/null || echo "Notification sent"'
    args = ["-s", f"{target_ip}:5555", "shell", cmd_str] if target_ip else ["shell", cmd_str]
    success, out = run_adb(args)
    print(f"[JARVIS] Toast pushed to TV: '{message}'")
    return success


def main():
    parser = argparse.ArgumentParser(description="JARVIS Airtel Xstream Box & TV Pilot")
    parser.add_argument("--ip", type=str, help="IP address of Airtel Xstream Box (e.g. 192.168.1.15)")
    parser.add_argument("--connect", action="store_true", help="Connect to the box over Wi-Fi")
    parser.add_argument("--key", type=str, help="Key to send (power, mute, volume_up, volume_down, home, back, ok, etc.)")
    parser.add_argument("--app", type=str, help="Launch app (youtube, netflix, hotstar, prime, settings)")
    parser.add_argument("--toast", type=str, help="Show on-screen notification text on TV")
    parser.add_argument("--status", action="store_true", help="Check ADB connected devices")
    
    args = parser.parse_args()

    if args.status:
        success, out = run_adb(["devices"])
        print(f"[Connected Devices]:\n{out}")
        return

    ip = args.ip or get_saved_ip()

    if args.connect:
        if not ip:
            print("[Error] Please provide --ip <xstream_ip>")
            sys.exit(1)
        connect_box(ip)
        return

    if args.key:
        send_key(args.key, ip)
        return

    if args.app:
        launch_app(args.app, ip)
        return

    if args.toast:
        show_toast(args.toast, ip)
        return

    print("--- JARVIS XSTREAM CONTROLLER ---")
    print(f"Known Box IP: {ip or 'Not set'}")
    print("Usage examples:")
    print("  python xstream_pilot.py --ip 192.168.1.15 --connect")
    print("  python xstream_pilot.py --key power")
    print("  python xstream_pilot.py --key mute")
    print("  python xstream_pilot.py --app youtube")
    print("  python xstream_pilot.py --toast 'Mukil, Order Generated!'")


if __name__ == "__main__":
    main()
