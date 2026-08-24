import os
import json
from datetime import datetime

MEMORY_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'storage', 'memory')
CONTEXT_FILE = os.path.join(MEMORY_DIR, 'context.json')
PROFILE_FILE = os.path.join(MEMORY_DIR, 'user_profile.json')
TASK_LOG_FILE = os.path.join(MEMORY_DIR, 'task_log.json')

class MemoryManager:
    def __init__(self):
        os.makedirs(MEMORY_DIR, exist_ok=True)

    def get_context(self) -> dict:
        if os.path.exists(CONTEXT_FILE):
            with open(CONTEXT_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def get_profile(self) -> dict:
        if os.path.exists(PROFILE_FILE):
            with open(PROFILE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def update_context(self, updates: dict):
        current = self.get_context()
        current.update(updates)
        current['last_updated'] = datetime.now().isoformat()
        with open(CONTEXT_FILE, 'w', encoding='utf-8') as f:
            json.dump(current, f, indent=2)

    def log_task(self, event: str, description: str, metadata: dict = None):
        logs = []
        if os.path.exists(TASK_LOG_FILE):
            try:
                with open(TASK_LOG_FILE, 'r', encoding='utf-8') as f:
                    logs = json.load(f)
            except Exception:
                logs = []
        entry = {
            'timestamp': datetime.now().isoformat(),
            'event': event,
            'description': description,
            'metadata': metadata or {}
        }
        logs.append(entry)
        with open(TASK_LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(logs, f, indent=2)

    def get_system_prompt_context(self) -> str:
        ctx = self.get_context()
        prof = self.get_profile()
        user_name = prof.get('name', 'Mukil')
        phase = ctx.get('active_phase', 'N/A')
        drive_url = ctx.get('drive_vault', {}).get('url', 'N/A')
        curr_task = ctx.get('current_task', 'Idle')
        return (
            '=== PERSISTENT MEMORY CONTEXT ===\n'
            f'User: {user_name}\n'
            f'Active Phase: {phase}\n'
            f'Drive Vault: {drive_url}\n'
            f'Current Task: {curr_task}\n'
            '================================='
        )

if __name__ == '__main__':
    mem = MemoryManager()
    print(mem.get_system_prompt_context())
