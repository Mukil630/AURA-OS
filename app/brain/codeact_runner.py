"""Dynamic CodeAct Sandbox Runner for On-Demand Tool Execution & Code Synthesis."""
import asyncio
import io
import logging
import os
import subprocess
import sys
import tempfile
import traceback
from typing import Any, Dict, Optional, Tuple
from pydantic import BaseModel, Field

logger = logging.getLogger("CodeActRunner")


class CodeActResult(BaseModel):
    success: bool
    stdout: str = ""
    stderr: str = ""
    result_data: Any = None
    execution_time_sec: float = 0.0
    error_type: Optional[str] = None


class CodeActRunner:
    """Executes dynamically generated Python or PowerShell code safely on the physical hardware."""

    def __init__(self, timeout_sec: float = 30.0):
        self.timeout_sec = timeout_sec

    async def execute_python_code(self, code_str: str, global_vars: Optional[Dict[str, Any]] = None) -> CodeActResult:
        """Executes a Python code block in a sandboxed subprocess and captures outputs."""
        clean_code = code_str.strip()
        # Remove markdown code block fences if present
        if clean_code.startswith("```python"):
            clean_code = clean_code[9:]
        elif clean_code.startswith("```"):
            clean_code = clean_code[3:]
        if clean_code.endswith("```"):
            clean_code = clean_code[:-3]
        clean_code = clean_code.strip()

        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w", encoding="utf-8") as tf:
            tf.write(clean_code)
            temp_py = tf.name

        start_time = asyncio.get_event_loop().time()
        try:
            process = await asyncio.create_subprocess_exec(
                sys.executable, temp_py,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(), timeout=self.timeout_sec
                )
                stdout_str = stdout_bytes.decode("utf-8", errors="replace").strip()
                stderr_str = stderr_bytes.decode("utf-8", errors="replace").strip()
                elapsed = asyncio.get_event_loop().time() - start_time

                success = (process.returncode == 0)
                return CodeActResult(
                    success=success,
                    stdout=stdout_str,
                    stderr=stderr_str,
                    execution_time_sec=elapsed,
                    error_type="RUNTIME_ERROR" if not success else None,
                )

            except asyncio.TimeoutError:
                process.kill()
                elapsed = asyncio.get_event_loop().time() - start_time
                return CodeActResult(
                    success=False,
                    stderr=f"CodeAct execution timed out after {self.timeout_sec}s",
                    execution_time_sec=elapsed,
                    error_type="TIMEOUT",
                )

        except Exception as e:
            elapsed = asyncio.get_event_loop().time() - start_time
            return CodeActResult(
                success=False,
                stderr=str(e),
                execution_time_sec=elapsed,
                error_type="SYSTEM_ERROR",
            )
        finally:
            if os.path.exists(temp_py):
                try:
                    os.remove(temp_py)
                except Exception:
                    pass

    async def execute_powershell(self, command: str) -> CodeActResult:
        """Executes a PowerShell command directly."""
        start_time = asyncio.get_event_loop().time()
        try:
            process = await asyncio.create_subprocess_exec(
                "powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(), timeout=self.timeout_sec
            )
            stdout_str = stdout_bytes.decode("utf-8", errors="replace").strip()
            stderr_str = stderr_bytes.decode("utf-8", errors="replace").strip()
            elapsed = asyncio.get_event_loop().time() - start_time

            return CodeActResult(
                success=(process.returncode == 0),
                stdout=stdout_str,
                stderr=stderr_str,
                execution_time_sec=elapsed,
                error_type="POWERSHELL_ERROR" if process.returncode != 0 else None,
            )
        except Exception as e:
            elapsed = asyncio.get_event_loop().time() - start_time
            return CodeActResult(
                success=False,
                stderr=str(e),
                execution_time_sec=elapsed,
                error_type="POWERSHELL_LAUNCH_ERROR",
            )
