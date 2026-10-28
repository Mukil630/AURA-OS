"""
AURA OS Live Phone Call Experience & Simulation Test
Plays incoming phone ringtone, connects the secure voice link,
and streams the 06:00 AM executive briefing through hardware speakers.
"""
import sys
import os
import time
import winsound
from pathlib import Path

# Fix Windows console UTF-8 output
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

import pygame

AUDIO_PATH = Path("C:/Users/mukil/Desktop/AURA_Morning_Wakeup_Call.mp3")

def play_phone_ring(times: int = 2):
    """Simulates realistic incoming telephone ringtone beeps."""
    for i in range(times):
        print(f"🔔 [RING {i+1}] Dd-r-r-i-n-n-g-g... Incoming Call from JARVIS Prime!")
        winsound.Beep(440, 600)
        winsound.Beep(480, 600)
        time.sleep(0.8)

def run_live_call():
    print("\n" + "=" * 70)
    print("📱 INITIATING AUTONOMOUS CALL SEQUENCE: JARVIS Prime ➡️ Boss Mukil")
    print("=" * 70)
    time.sleep(0.5)

    # 1. Ringing phase
    play_phone_ring(2)

    # 2. Call pickup
    print("\n" + "=" * 70)
    print("📞 [CALL PICKED UP] Voice Uplink Established!")
    print("📡 Caller: JARVIS Prime (Executive AI Partner)")
    print("🔊 Streaming High-Definition Neural Speech Audio to Speakers...")
    print("=" * 70 + "\n")

    # 3. Play speech audio via pygame
    if not AUDIO_PATH.exists():
        print(f"❌ Error: Audio file not found at {AUDIO_PATH}")
        return

    pygame.mixer.init()
    pygame.mixer.music.load(str(AUDIO_PATH))
    pygame.mixer.music.play()

    # Track playback
    start_time = time.time()
    while pygame.mixer.music.get_busy():
        elapsed = int(time.time() - start_time)
        sys.stdout.write(f"\r🎙️ [CALL IN PROGRESS] Speaking to Mukil... ({elapsed}s elapsed)")
        sys.stdout.flush()
        time.sleep(0.5)

    print("\n\n" + "=" * 70)
    print("📞 [CALL DISCONNECTED] Duration: ~38 seconds.")
    print("🏆 Executive morning briefing delivered successfully to Mukil!")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    run_live_call()
