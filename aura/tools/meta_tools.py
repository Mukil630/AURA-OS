"""
AURA OS Meta-Tool & Dynamic Self-Extending Engine
Allows AURA to write new Python tools, test them in an isolated sandbox,
and hot-register them into the live ToolRegistry at runtime without server restart.
"""
import sys
import os
import inspect
import importlib.util
import subprocess
import json
from pathlib import Path
from typing import Dict, Any

from aura.config import DATA_DIR, ROOT_DIR

CUSTOM_TOOLS_DIR = ROOT_DIR / "aura" / "tools" / "custom"
CUSTOM_TOOLS_DIR.mkdir(parents=True, exist_ok=True)
CUSTOM_TOOLS_MANIFEST = DATA_DIR / "custom_tools_manifest.json"

def create_and_register_new_tool(tool_name: str, code: str, test_code: str, description: str) -> str:
    """
    Synthesizes a new Python tool, writes it to disk, executes isolated verification,
    and dynamically registers it into AURA's active superpowers registry without restarting.
    
    Args:
        tool_name: Python function name (snake_case, e.g., 'download_youtube_audio')
        code: Complete Python source code defining the function
        test_code: Python test script that calls the function and asserts expected output
        description: Plain English/Tanglish summary of what the tool accomplishes
    """
    clean_name = tool_name.strip().lower()
    tool_file = CUSTOM_TOOLS_DIR / f"{clean_name}.py"
    test_file = CUSTOM_TOOLS_DIR / f"test_{clean_name}.py"
    
    # 1. Write the tool implementation file
    tool_file.write_text(code, encoding="utf-8")
    
    # 2. Write the isolated verification test file
    full_test_script = f"""
import sys
from pathlib import Path
sys.path.insert(0, r"{ROOT_DIR}")
sys.path.insert(0, r"{CUSTOM_TOOLS_DIR}")

from {clean_name} import {clean_name}

{test_code}
print("VERIFICATION_PASS_OK")
"""
    test_file.write_text(full_test_script, encoding="utf-8")
    
    # 3. Execute isolated sandbox test via subprocess
    try:
        proc = subprocess.run(
            [sys.executable, str(test_file)],
            capture_output=True,
            text=True,
            timeout=20,
            encoding="utf-8"
        )
        if proc.returncode != 0 or "VERIFICATION_PASS_OK" not in proc.stdout:
            error_details = (proc.stderr or proc.stdout).strip()
            return f"❌ Tool Verification FAILED for '{clean_name}'. Sandbox Error:\n{error_details}\nPlease analyze traceback, fix code, and call again."
    except Exception as e:
        return f"❌ Subprocess execution exception while testing '{clean_name}': {str(e)}"
    
    # 4. Dynamically import and hot-register into live registry
    try:
        from aura.tools.registry import registry
        
        spec = importlib.util.spec_from_file_location(clean_name, tool_file)
        if spec is None or spec.loader is None:
            return f"❌ Could not load spec for {tool_file}"
            
        module = importlib.util.module_from_spec(spec)
        sys.modules[clean_name] = module
        spec.loader.exec_module(module)
        
        if not hasattr(module, clean_name):
            return f"❌ Module created but function '{clean_name}' not found inside."
            
        target_func = getattr(module, clean_name)
        registry.register(clean_name, target_func)
        
        # 5. Persist to manifest
        manifest = {}
        if CUSTOM_TOOLS_MANIFEST.exists():
            try:
                manifest = json.loads(CUSTOM_TOOLS_MANIFEST.read_text(encoding="utf-8"))
            except Exception:
                manifest = {}
                
        manifest[clean_name] = {
            "file": str(tool_file),
            "description": description
        }
        CUSTOM_TOOLS_MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        
        return f"✅ SUCCESS: New superpower '{clean_name}' synthesized, verified 100% in sandbox, and hot-registered into AURA's live memory! Ready for immediate use."
    except Exception as e:
        return f"❌ Failed to hot-register '{clean_name}' into registry: {str(e)}"

def list_custom_tools() -> str:
    """Lists all dynamically synthesized custom tools created by AURA at runtime."""
    if not CUSTOM_TOOLS_MANIFEST.exists():
        return "No custom dynamic tools registered yet. Use create_and_register_new_tool to synthesize one."
    try:
        data = json.loads(CUSTOM_TOOLS_MANIFEST.read_text(encoding="utf-8"))
        if not data:
            return "No custom dynamic tools registered yet."
        lines = [f"Synthesized Custom Superpowers ({len(data)}):"]
        for name, meta in data.items():
            lines.append(f"  • {name}: {meta.get('description', '')}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error reading manifest: {e}"
