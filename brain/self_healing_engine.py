"""Autonomous Self-Healing & Error Diagnosis Engine for AURA-OS.
Parses runtime tracebacks, diagnoses root causes, auto-installs missing dependencies,
and instructs the LLM to rewrite broken code chunks.
"""
import re
import sys
import subprocess
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("SelfHealingEngine")


class SelfHealingEngine:
    """
    Diagnoses code execution errors and auto-resolves missing pip packages
    and common Python runtime exceptions.
    """

    @staticmethod
    def extract_missing_module(stderr_text: str) -> Optional[str]:
        """Extracts the missing package name from ModuleNotFoundError or ImportError."""
        # e.g. "No module named 'openpyxl'"
        match = re.search(r"No module named ['\"]([^'\"]+)['\"]", stderr_text)
        if match:
            return match.group(1).split(".")[0]
        
        # e.g. "cannot import name 'X' from 'Y'"
        match2 = re.search(r"cannot import name .* from ['\"]([^'\"]+)['\"]", stderr_text)
        if match2:
            return match2.group(1).split(".")[0]
        
        return None

    @classmethod
    def attempt_auto_heal(cls, stderr_text: str) -> Dict[str, Any]:
        """
        Attempts automated recovery on common errors without user intervention.
        """
        missing_module = cls.extract_missing_module(stderr_text)
        if missing_module:
            # Map internal aliases to pip package names if needed
            pip_target = missing_module
            if missing_module in ["bs4"]:
                pip_target = "beautifulsoup4"
            elif missing_module in ["cv2"]:
                pip_target = "opencv-python"
            elif missing_module in ["PIL"]:
                pip_target = "pillow"

            logger.info(f"🔄 Self-Healing triggered: Auto-installing missing module '{pip_target}'...")
            try:
                proc = subprocess.run(
                    [sys.executable, "-m", "pip", "install", pip_target],
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                if proc.returncode == 0:
                    logger.info(f"✅ Successfully auto-installed '{pip_target}'.")
                    return {
                        "healed": True,
                        "action_taken": f"Auto-installed pip package '{pip_target}'",
                        "package": pip_target
                    }
                else:
                    return {
                        "healed": False,
                        "error": proc.stderr,
                        "action_taken": f"Failed to install '{pip_target}'"
                    }
            except Exception as e:
                return {"healed": False, "error": str(e)}

        return {
            "healed": False,
            "action_taken": "No deterministic heuristic rule matched. Forwarding traceback to LLM for code repair."
        }
