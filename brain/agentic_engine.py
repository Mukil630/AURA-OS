"""
Antigravity-Grade Agentic Engine for AURA-OS / JARVIS.
Includes precision surgical file editing, ripgrep code search, self-healing execution loops, and subagent swarm delegation.
"""
import os
import re
import sys
import json
import time
import subprocess
import logging
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger("AgenticEngine")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ==============================================================================
# 1. PRECISION FILE SYSTEM & DISCOVERY TOOLS (Antigravity Core)
# ==============================================================================

def view_file_slice(file_path: str, start_line: Optional[int] = 1, end_line: Optional[int] = 100) -> str:
    """Views a specific line range slice of a file with 1-based indexing."""
    if not os.path.isabs(file_path):
        file_path = os.path.join(BASE_DIR, file_path)
    
    if not os.path.exists(file_path):
        return f"Error: File not found at '{file_path}'"
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        
        total_lines = len(lines)
        start = max(1, start_line or 1)
        end = min(total_lines, end_line or total_lines)
        
        output = [f"--- File: {file_path} (Lines {start}-{end} of {total_lines}) ---"]
        for idx in range(start - 1, end):
            output.append(f"{idx + 1:4d}: {lines[idx].rstrip()}")
        return "\n".join(output)
    except Exception as e:
        return f"Error reading file slice: {e}"

def replace_file_content(file_path: str, target_content: str, replacement_content: str) -> str:
    """Performs an exact atomic search-and-replace edit on a file without rewriting the whole file."""
    if not os.path.isabs(file_path):
        file_path = os.path.join(BASE_DIR, file_path)

    if not os.path.exists(file_path):
        return f"Error: File not found at '{file_path}'"

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        if target_content not in content:
            return f"Error: target_content was not found in '{file_path}'. Make sure whitespace and indentation match exactly."

        occurrences = content.count(target_content)
        if occurrences > 1:
            return f"Error: target_content occurs {occurrences} times. Please provide more surrounding context lines to make the target unique."

        new_content = content.replace(target_content, replacement_content, 1)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        return f"Successfully updated '{file_path}' (1 replacement made)."
    except Exception as e:
        return f"Error updating file: {e}"

def write_to_file(file_path: str, code_content: str, overwrite: bool = True) -> str:
    """Creates or overwrites a file cleanly on disk."""
    if not os.path.isabs(file_path):
        file_path = os.path.join(BASE_DIR, file_path)

    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        if os.path.exists(file_path) and not overwrite:
            return f"Error: File already exists at '{file_path}' and overwrite=False."

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(code_content)
        return f"Successfully wrote {len(code_content)} characters to '{file_path}'."
    except Exception as e:
        return f"Error writing to file: {e}"

def grep_search(query: str, search_path: Optional[str] = None, is_regex: bool = False) -> str:
    """Searches for pattern matches across files in a directory."""
    target_path = search_path or BASE_DIR
    if not os.path.isabs(target_path):
        target_path = os.path.join(BASE_DIR, target_path)

    results = []
    try:
        pattern = re.compile(query if is_regex else re.escape(query), re.IGNORECASE)
        for root, dirs, files in os.walk(target_path):
            dirs[:] = [d for d in dirs if d not in {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 'storage'}]
            for file in files:
                if file.endswith(('.py', '.html', '.js', '.css', '.json', '.md', '.ts', '.tsx', '.bat', '.sh')):
                    fpath = os.path.join(root, file)
                    try:
                        with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                            for idx, line in enumerate(f, 1):
                                if pattern.search(line):
                                    rel_path = os.path.relpath(fpath, BASE_DIR)
                                    results.append(f"{rel_path}:{idx}: {line.strip()}")
                                    if len(results) >= 40:
                                        break
                    except Exception:
                        continue
            if len(results) >= 40:
                break
        
        if not results:
            return f"No matches found for query: '{query}' in '{target_path}'"
        return "\n".join(results)
    except Exception as e:
        return f"Grep search failed: {e}"

def find_by_name(pattern: str, search_path: Optional[str] = None) -> str:
    """Finds files and directories matching a glob pattern."""
    import fnmatch
    target_path = search_path or BASE_DIR
    if not os.path.isabs(target_path):
        target_path = os.path.join(BASE_DIR, target_path)

    matches = []
    try:
        for root, dirs, files in os.walk(target_path):
            dirs[:] = [d for d in dirs if d not in {'.git', 'node_modules', '__pycache__', '.venv', 'venv'}]
            for name in dirs + files:
                if fnmatch.fnmatch(name.lower(), f"*{pattern.lower()}*"):
                    full = os.path.join(root, name)
                    rel = os.path.relpath(full, BASE_DIR)
                    matches.append(rel)
                    if len(matches) >= 30:
                        break
            if len(matches) >= 30:
                break
        if not matches:
            return f"No files or directories matching '{pattern}' found."
        return "\n".join(matches)
    except Exception as e:
        return f"Find by name failed: {e}"

# ==============================================================================
# 2. AUTONOMOUS SELF-HEALING RUNNER LOOP
# ==============================================================================

def run_command_and_heal(command: str, cwd: Optional[str] = None, max_retries: int = 2) -> Dict[str, Any]:
    """Runs a shell command. If it fails, reads the error and attempts autonomous self-correction."""
    target_cwd = cwd or BASE_DIR
    if not os.path.isabs(target_cwd):
        target_cwd = os.path.join(BASE_DIR, target_cwd)

    current_cmd = command
    history = []

    for attempt in range(max_retries + 1):
        logger.info(f"Self-Healing Runner: Executing (Attempt {attempt+1}): {current_cmd}")
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", current_cmd],
            cwd=target_cwd,
            capture_output=True,
            text=True,
            timeout=120
        )
        
        history.append({
            "attempt": attempt + 1,
            "command": current_cmd,
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip()
        })

        if proc.returncode == 0:
            return {
                "status": "SUCCESS",
                "final_command": current_cmd,
                "attempts": attempt + 1,
                "stdout": proc.stdout.strip(),
                "history": history
            }

        # If failed and retries remain -> analyze error and attempt self-heal
        err_msg = (proc.stderr or proc.stdout).strip()
        logger.warning(f"Command failed with code {proc.returncode}. Attempting self-heal: {err_msg[:120]}")

        # Check for missing pip packages
        pip_match = re.search(r"No module named ['\"]([^'\"]+)['\"]", err_msg)
        if pip_match:
            missing_pkg = pip_match.group(1)
            install_cmd = f"pip install {missing_pkg}"
            logger.info(f"Self-Healing: Installing missing package '{missing_pkg}' via '{install_cmd}'")
            subprocess.run(["powershell", "-Command", install_cmd], cwd=target_cwd)
            continue

        # Check for missing npm packages
        npm_match = re.search(r"Cannot find module ['\"]([^'\"]+)['\"]", err_msg)
        if npm_match:
            missing_pkg = npm_match.group(1)
            install_cmd = f"npm install {missing_pkg}"
            logger.info(f"Self-Healing: Installing missing NPM package '{missing_pkg}' via '{install_cmd}'")
            subprocess.run(["powershell", "-Command", install_cmd], cwd=target_cwd)
            continue

    return {
        "status": "FAILED",
        "final_command": current_cmd,
        "attempts": len(history),
        "error": history[-1]["stderr"] or history[-1]["stdout"],
        "history": history
    }

# ==============================================================================
# 3. MULTI-AGENT SUBAGENT SWARM REGISTRY
# ==============================================================================

class SubagentWorker:
    def __init__(self, name: str, role: str, system_directive: str):
        self.name = name
        self.role = role
        self.system_directive = system_directive

    def execute(self, prompt: str) -> Dict[str, Any]:
        """Executes a delegated prompt in an isolated cognitive context."""
        from brain.agent_brain import AgentBrain
        brain = AgentBrain()
        combined_prompt = f"[SUBAGENT: {self.name} | Role: {self.role}]\nDIRECTIVE: {self.system_directive}\n\nTASK: {prompt}"
        reply = brain.process_message(combined_prompt, user_name="Mukil")
        return {
            "subagent": self.name,
            "role": self.role,
            "task": prompt,
            "report": reply,
            "timestamp": time.strftime("%H:%M:%S")
        }

class SubagentSwarm:
    def __init__(self):
        self.agents: Dict[str, SubagentWorker] = {
            "research": SubagentWorker(
                "research",
                "Deep Codebase & Documentation Researcher",
                "Explore codebase, find exact files, extract key logic, and summarize cleanly."
            ),
            "coder": SubagentWorker(
                "coder",
                "Precision Systems & Code Architect",
                "Write clean, modular code, fix lint errors, and verify compilation."
            ),
            "placement_hunter": SubagentWorker(
                "placement_hunter",
                "Career & Placement Auto-Apply Strategist",
                "Match ATS keywords, customize resume profile, and track application proofs."
            ),
            "finance_analyst": SubagentWorker(
                "finance_analyst",
                "SGC Billing & Financial Reconciler",
                "Audit pending invoice balances, calculate overdue totals, and generate summaries."
            )
        }

    def invoke(self, subagent_name: str, task_prompt: str) -> Dict[str, Any]:
        agent = self.agents.get(subagent_name.lower())
        if not agent:
            agent = self.agents["research"]
        return agent.execute(task_prompt)

swarm = SubagentSwarm()
