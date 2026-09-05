"""24/7 Cloud Sandboxed CodeAct Runner for AURA-OS / JARVIS.
Dynamically executes Python scripts in the cloud/local runtime with automatic
dependency auto-installation and iterative LLM self-healing.
"""
import os
import sys
from uuid import uuid4
import logging
import subprocess
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from groq import Groq

from brain.self_healing_engine import SelfHealingEngine

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import GROQ_API_KEY

logger = logging.getLogger("CodeActCloudRunner")


class CodeActResult(BaseModel):
    task_id: str
    status: str  # "SUCCESS" | "FAILED"
    stdout: str
    stderr: str
    retries: int = 0
    artifacts_created: List[str] = Field(default_factory=list)
    script_path: str


class CodeActCloudRunner:
    """
    Executes arbitrary Python code in an isolated sub-process with self-healing capabilities.
    """

    def __init__(self, scratch_dir: Optional[str] = None):
        base_dir = os.path.dirname(os.path.dirname(__file__))
        self.scratch_dir = scratch_dir or os.path.join(base_dir, "storage", "scratch")
        os.makedirs(self.scratch_dir, exist_ok=True)
        self.client = Groq(api_key=GROQ_API_KEY)
        self.repair_model = "llama-3.3-70b-versatile"

    def execute_script(self, script_code: str, task_name: str = "dynamic_task", max_retries: int = 2) -> CodeActResult:
        task_id = f"task_{uuid4().hex[:8]}"
        script_file = os.path.join(self.scratch_dir, f"{task_name}_{task_id}.py")
        current_code = script_code

        for attempt in range(max_retries + 1):
            with open(script_file, "w", encoding="utf-8") as f:
                f.write(current_code)

            logger.info(f"⚡ [Attempt {attempt + 1}/{max_retries + 1}] Executing {script_file}...")
            try:
                proc = subprocess.run(
                    [sys.executable, script_file],
                    capture_output=True,
                    text=True,
                    timeout=90,
                    cwd=os.path.dirname(os.path.dirname(__file__))
                )
                stdout = proc.stdout
                stderr = proc.stderr

                if proc.returncode == 0:
                    logger.info(f"✅ CodeAct execution SUCCESS on attempt {attempt + 1}")
                    return CodeActResult(
                        task_id=task_id,
                        status="SUCCESS",
                        stdout=stdout,
                        stderr=stderr,
                        retries=attempt,
                        script_path=script_file
                    )

                logger.warning(f"⚠️ CodeAct failed with return code {proc.returncode}. Stderr: {stderr[:200]}")

                # 1. Attempt deterministic dependency heal
                heal_res = SelfHealingEngine.attempt_auto_heal(stderr)
                if heal_res.get("healed"):
                    logger.info("Retrying execution after auto-healing missing module...")
                    continue

                # 2. Attempt LLM code repair if retries remaining
                if attempt < max_retries:
                    logger.info("Requesting LLM to repair the broken Python script...")
                    repair_prompt = (
                        "You are an expert Python debugger for AURA-OS.\n"
                        "The following Python script threw a runtime error.\n\n"
                        f"--- SCRIPT ---\n{current_code}\n\n"
                        f"--- ERROR STDERR ---\n{stderr}\n\n"
                        "Rewrite the Python script to fix the error. Return ONLY the complete executable Python code inside a ```python ``` block."
                    )
                    repair_resp = self.client.chat.completions.create(
                        model=self.repair_model,
                        messages=[{"role": "user", "content": repair_prompt}],
                        temperature=0.2
                    )
                    fixed_text = repair_resp.choices[0].message.content or ""
                    if "```python" in fixed_text:
                        current_code = fixed_text.split("```python")[1].split("```")[0].strip()
                    elif "```" in fixed_text:
                        current_code = fixed_text.split("```")[1].split("```")[0].strip()
                    else:
                        current_code = fixed_text.strip()

            except subprocess.TimeoutExpired:
                logger.error(f"Execution timed out on attempt {attempt + 1}")
                return CodeActResult(
                    task_id=task_id,
                    status="FAILED",
                    stdout="",
                    stderr="Execution timed out after 90 seconds.",
                    retries=attempt,
                    script_path=script_file
                )
            except Exception as ex:
                logger.error(f"Unexpected error in runner: {ex}")
                stderr = str(ex)

        return CodeActResult(
            task_id=task_id,
            status="FAILED",
            stdout="",
            stderr=stderr,
            retries=max_retries,
            script_path=script_file
        )
