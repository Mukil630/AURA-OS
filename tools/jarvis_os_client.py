"""
JARVIS OS CLIENT HELPER
Communicates with the Local Interactive OS Companion (127.0.0.1:8765)
Enables Antigravity CLI and Telegram Bot to trigger native foreground actions effortlessly.
"""

import requests
import json

COMPANION_URL = "http://127.0.0.1:8765"

def check_companion_health() -> bool:
    try:
        r = requests.get(f"{COMPANION_URL}/health", timeout=2)
        return r.status_code == 200
    except Exception:
        return False

def execute_native_os(payload: dict, timeout: int = 30) -> dict:
    try:
        r = requests.post(f"{COMPANION_URL}/execute", json=payload, timeout=timeout)
        return r.json()
    except Exception as e:
        return {"status": "error", "message": f"Companion connection failed: {e}"}

# Quick helpers
def launch_app(app_name: str) -> dict:
    return execute_native_os({"action": "launch_app", "app": app_name})

def type_text(text: str, wpm: int = 85) -> dict:
    return execute_native_os({"action": "type_text", "text": text, "wpm": wpm})

def vision_click(target_description: str) -> dict:
    return execute_native_os({"action": "vision_click", "target": target_description})

def run_demo_notepad(text: str = None) -> dict:
    payload = {"action": "demo_notepad"}
    if text:
        payload["text"] = text
    return execute_native_os(payload, timeout=45)

if __name__ == "__main__":
    print("Companion Health:", check_companion_health())
