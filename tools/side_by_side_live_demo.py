"""
=============================================================================
SIDE-BY-SIDE VISUAL ASTRA LIVE DEMO
Automatically un-maximizes and positions the terminal on the LEFT half,
launches Notepad on the RIGHT half, glides the mouse cursor right into
Notepad, clicks, and types the live SGC Dye Recipe Card!
=============================================================================
"""

import sys
import time
import ctypes
import subprocess
import math
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

from astra_os_pilot import _attach_display, smooth_move_mouse, visual_flourish_hover

NOTE_CONTENT = """==================================================
SRI GANAPATHI COLOURS (SGC) - SHADE BATCH CARD
Target Shade : Royal Navy Blue (SGC-NB-04)
Yarn Lot     : 100 kg Cotton (2/20s Loom Count)
Liquor Ratio : 1:7 (700 Liters)
--------------------------------------------------
* Reactive Blue HERD : 2.80 kg
* Reactive Red HE7B  : 650 grams
* Reactive Yellow    : 120 grams
* Glauber's Salt     : 80 kg (3 Dosing Steps)
* Soda Ash           : 20 kg (Progressive Fixation)
--------------------------------------------------
Status       : 100% Verified Live on Mukil's PC!
Engine       : JARVIS Astra Autonomous OS Controller
=================================================="""

def run_side_by_side():
    print("\n" + "="*65)
    print("🚀 LAUNCHING SIDE-BY-SIDE ASTRA LIVE DEMO...")
    print("="*65)
    _attach_display()

    user32 = ctypes.windll.user32
    sw, sh = pyautogui.size()
    half_w = sw // 2

    # 1. Find Windows
    term_hwnd = None
    notepad_hwnd = None

    def enum_cb(h, _):
        nonlocal term_hwnd, notepad_hwnd
        if user32.IsWindowVisible(h):
            l = user32.GetWindowTextLengthW(h)
            if l > 0:
                b = ctypes.create_unicode_buffer(l + 1)
                user32.GetWindowTextW(h, b, l + 1)
                val = b.value.lower()
                if "agy-auto" in val or "command prompt" in val:
                    term_hwnd = h
                elif "notepad" in val:
                    notepad_hwnd = h
        return True

    user32.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)(enum_cb), 0)

    # 2. Dock Terminal to LEFT Half (0 to half_w)
    if term_hwnd:
        print("[1/4] Docking Terminal window to LEFT half of monitor...")
        user32.ShowWindow(term_hwnd, 9) # SW_RESTORE (Un-maximize)
        time.sleep(0.3)
        user32.MoveWindow(term_hwnd, 10, 10, half_w - 20, sh - 60, True)
        time.sleep(0.3)

    # 3. Launch & Dock Notepad to RIGHT Half (half_w to sw)
    print("[2/4] Docking Notepad to RIGHT half of monitor...")
    if not notepad_hwnd:
        subprocess.Popen(["notepad.exe"], shell=True)
        time.sleep(1.2)
        user32.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)(enum_cb), 0)

    if notepad_hwnd:
        user32.ShowWindow(notepad_hwnd, 9)
        time.sleep(0.3)
        user32.MoveWindow(notepad_hwnd, half_w + 10, 10, half_w - 20, sh - 60, True)
        user32.BringWindowToTop(notepad_hwnd)
        user32.SetForegroundWindow(notepad_hwnd)
        time.sleep(0.5)

    # 4. Smooth Mouse Glide into Notepad Right Half
    target_x = half_w + 250
    target_y = 250
    print(f"[3/4] Gliding mouse smoothly across monitor to Notepad at ({target_x}, {target_y})...")
    smooth_move_mouse(target_x, target_y, duration=0.8)
    visual_flourish_hover(target_x, target_y, radius=15)
    pyautogui.click(target_x, target_y)
    time.sleep(0.3)

    # 5. Live Typing SGC Recipe Note
    print("[4/4] Typing SGC Dye Recipe Card live on your screen...")
    for line in NOTE_CONTENT.split("\n"):
        for char in line:
            pyautogui.write(char)
            time.sleep(0.012)
        pyautogui.press("enter")
        time.sleep(0.06)

    print("\n" + "="*65)
    print("🎉 SIDE-BY-SIDE ASTRA LIVE DEMO COMPLETED SUCCESSFULLY!")
    print("="*65 + "\n")

if __name__ == "__main__":
    run_side_by_side()
