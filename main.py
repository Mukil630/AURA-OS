"""
AURA OS Main Entrypoint
Run: python main.py
"""
import sys
import os

# Hide pygame prompt
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

# Force Windows UTF-8 console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from aura.cli import main

if __name__ == "__main__":
    main()
