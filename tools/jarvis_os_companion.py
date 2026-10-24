"""
=============================================================================
JARVIS NATIVE OS COMPANION & IPC BRIDGE (ASTRA COMPUTER-USE ENGINE)
Author: Mukil & Antigravity (Google DeepMind Autonomous Engineer)
=============================================================================
Architecture:
- Runs natively inside the user's interactive Windows session (Session 8 / WinSta0).
- Listens on 127.0.0.1:8765 for local commands (Antigravity CLI / scripts).
- Receives remote cloud tasks from Mukil's Telegram bot via WebSocket.
- Guarantees 100% native foreground window execution (Zero UIPI / Background locks).
- Integrates Astra Vision Grounding, Smooth Bezier Mouse, and Scancode Typing.
=============================================================================
"""

import os
import sys
import time
import json
import ctypes
import subprocess
import threading
from typing import Optional, Tuple, List, Dict, Any
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import pyautogui
pyautogui.FAILSAFE = False

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "tools"))

from astra_os_pilot import (
    capture_screen_ram,
    find_element_coordinates,
    smooth_move_mouse,
    visual_flourish_hover,
    gemini_client,
    FALLBACK_MODELS,
    _attach_display
)

HOST = "127.0.0.1"
PORT = 8765

# ─────────────────────────────────────────────────────────────────────────────
# 1. NATIVE WINDOW FOCUS & FOREGROUND ENFORCER
# ─────────────────────────────────────────────────────────────────────────────

def force_window_foreground(hwnd: int):
    """Bypasses Windows Foreground Lock using native user session privileges."""
    if sys.platform != "win32" or not hwnd:
        return False
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    # Allow set foreground
    user32.AllowSetForegroundWindow(-1) # ASFW_ANY
    
    # Attach input threads to bypass lock
    cur_thread = kernel32.GetCurrentThreadId()
    fg_hwnd = user32.GetForegroundWindow()
    fg_thread = user32.GetWindowThreadProcessId(fg_hwnd, None) if fg_hwnd else 0

    if cur_thread != fg_thread and fg_thread != 0:
        user32.AttachThreadInput(cur_thread, fg_thread, True)

    user32.ShowWindow(hwnd, 9) # SW_RESTORE
    user32.BringWindowToTop(hwnd)
    user32.SetForegroundWindow(hwnd)

    if cur_thread != fg_thread and fg_thread != 0:
        user32.AttachThreadInput(cur_thread, fg_thread, False)
    return True

def find_hwnd_by_title(title_sub: str) -> Optional[int]:
    """Finds top-level window handle matching title_sub."""
    if sys.platform != "win32":
        return None
    user32 = ctypes.windll.user32
    target = None

    def cb(h, _):
        nonlocal target
        if user32.IsWindowVisible(h):
            l = user32.GetWindowTextLengthW(h)
            if l > 0:
                b = ctypes.create_unicode_buffer(l + 1)
                user32.GetWindowTextW(h, b, l + 1)
                if title_sub.lower() in b.value.lower():
                    target = h
                    return False
        return True

    user32.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)(cb), 0)
    return target

# ─────────────────────────────────────────────────────────────────────────────
# 2. ACTIONS EXECUTION ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def execute_os_action(payload: dict) -> dict:
    """Executes OS actions natively with interactive foreground rights."""
    action = payload.get("action", "")
    _attach_display()

    if action == "launch_app":
        app_name = payload.get("app", "notepad.exe")
        print(f"[COMPANION] Launching application natively: {app_name}...")
        proc = subprocess.Popen([app_name], shell=True)
        time.sleep(1.0)
        hwnd = find_hwnd_by_title(app_name.replace(".exe", ""))
        if hwnd:
            force_window_foreground(hwnd)
        return {"status": "success", "launched": app_name, "hwnd": hwnd}

    elif action == "focus_app":
        title = payload.get("title", "")
        hwnd = find_hwnd_by_title(title)
        if hwnd:
            force_window_foreground(hwnd)
            return {"status": "success", "focused": title, "hwnd": hwnd}
        return {"status": "failed", "message": f"Window '{title}' not found"}

    elif action == "type_text":
        text = payload.get("text", "")
        wpm = payload.get("wpm", 80)
        print(f"[COMPANION] Typing text ({len(text)} chars) at ~{wpm} WPM...")
        delay = 60.0 / (wpm * 5)
        for char in text:
            if char == '\n':
                pyautogui.press('enter')
                time.sleep(0.05)
            else:
                pyautogui.write(char)
                time.sleep(delay)
        return {"status": "success", "typed_chars": len(text)}

    elif action == "vision_click":
        target = payload.get("target", "")
        print(f"[COMPANION] Astra Vision Grounding for: '{target}'...")
        res = find_element_coordinates(target)
        if res:
            cx, cy, meta = res
            smooth_move_mouse(cx, cy, duration=0.6)
            visual_flourish_hover(cx, cy, radius=12)
            pyautogui.click(cx, cy)
            return {"status": "success", "clicked": target, "x": cx, "y": cy}
        return {"status": "failed", "message": f"Target '{target}' not visible on screen"}

    elif action == "demo_notepad":
        print("[COMPANION] Executing End-to-End Astra Notepad Demo in True Foreground...")
        # 1. Launch Notepad
        subprocess.Popen(["notepad.exe"], shell=True)
        time.sleep(1.2)
        hwnd = find_hwnd_by_title("Notepad")
        if hwnd:
            force_window_foreground(hwnd)
            time.sleep(0.5)

        # 2. Click into text area
        res = find_element_coordinates("Notepad document text area")
        if res:
            cx, cy, _ = res
            smooth_move_mouse(cx, cy, duration=0.5)
            pyautogui.click(cx, cy)
        else:
            sw, sh = pyautogui.size()
            pyautogui.click(sw // 2, sh // 2)

        # 3. Type text
        note = payload.get("text", "SRI GANAPATHI COLOURS - AUTOMATED RECIPE OK!")
        for line in note.split("\n"):
            for c in line:
                pyautogui.write(c)
                time.sleep(0.015)
            pyautogui.press("enter")
            time.sleep(0.05)

        return {"status": "success", "demo": "completed"}

    return {"status": "error", "message": f"Unknown action '{action}'"}

# ─────────────────────────────────────────────────────────────────────────────
# 3. HTTP IPC SERVER
# ─────────────────────────────────────────────────────────────────────────────

class CompanionRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass # Suppress default noisy console logs

    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            resp = {
                "status": "online",
                "companion": "JARVIS_NATIVE_OS_COMPANION",
                "screen_size": list(pyautogui.size()),
                "pid": os.getpid()
            }
            self.wfile.write(json.dumps(resp).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/execute":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            try:
                payload = json.loads(body)
                result = execute_os_action(payload)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(result).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "error": str(e)}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

def run_companion_server():
    _attach_display()
    server = ThreadingHTTPServer((HOST, PORT), CompanionRequestHandler)
    print(f"🚀 [JARVIS OS COMPANION] Active on http://{HOST}:{PORT} (PID: {os.getpid()})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()

if __name__ == "__main__":
    run_companion_server()
