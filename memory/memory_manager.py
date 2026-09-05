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

    def append_conversation(self, sender: str, text: str):
        convo_file = os.path.join(MEMORY_DIR, 'conversations_history.json')
        convos = []
        if os.path.exists(convo_file):
            try:
                with open(convo_file, 'r', encoding='utf-8') as f:
                    convos = json.load(f)
            except Exception:
                convos = []
        convos.append({
            'sender': sender,
            'text': text,
            'timestamp': datetime.now().isoformat()
        })
        # Keep last 50
        if len(convos) > 50:
            convos = convos[-50:]
        with open(convo_file, 'w', encoding='utf-8') as f:
            json.dump(convos, f, indent=2)

    def get_recent_conversations(self, limit: int = 6) -> list:
        convo_file = os.path.join(MEMORY_DIR, 'conversations_history.json')
        if os.path.exists(convo_file):
            try:
                with open(convo_file, 'r', encoding='utf-8') as f:
                    convos = json.load(f)
                    return convos[-limit:]
            except Exception:
                pass
        return []

    def get_system_prompt_context(self) -> str:
        ctx = self.get_context()
        prof = self.get_profile()
        user_name = prof.get('personal_details', {}).get('name', 'Mukilarasu S')
        phone = prof.get('personal_details', {}).get('phone', '9080030538')
        location = prof.get('personal_details', {}).get('location', 'Karur, Tamil Nadu')
        college = prof.get('personal_details', {}).get('college', 'VSB Engineering College, Karur')
        phase = ctx.get('active_phase', 'AURA-OS Autonomous Swarm Active')
        drive_url = ctx.get('drive_vault', {}).get('backup_vault_id', '1nGZG5-eIcxmkgQxBtZ7tjGTUoWWNY4m1')
        curr_task = ctx.get('current_task', 'Autonomous Partner Active')
        return (
            "=== PERSISTENT MEMORY & USER CORE CONTEXT ===\n"
            f"• User: {user_name} (Phone: {phone}, Location: {location}, College: {college})\n"
            "• Family Business: Sri Ganapathi Colours (SGC) - Yarn Dyeing & Textile Sizing located in Karur, Tamil Nadu.\n"
            "• SGC Invoicing & Bills: Handled via 'sgc-billing' desktop app. Active Bills Drive Vault ID: 11KMBP0HHa2AFl30zjL8-a_-BQk9MgWM9. Total 6 bills recorded (Latest is Bill #6: GAIA SUSTAINABLE SOLUTION, ₹956).\n"
            "• When Mukil mentions 'business bills', 'bills', 'kadai bills', or 'invoices', he is ALWAYS referring to Sri Ganapathi Colours (SGC).\n"
            "• COLLOQUIAL TANGLISH INSTRUCTION: 'Onu ella' or 'Onnum illa' means 'Nothing much / never mind / no worries' in Tanglish. It is NOT a company name!\n"
            "• PERMANENT MEMORY DIRECTIVE: You have FULL MULTI-DEVICE PERSISTENT MEMORY (PC, Phone/Telegram, and 250GB Google Drive mesh). NEVER tell Mukil that you don't have permanent memory or that memory doesn't carry over! You remember everything Mukil says.\n"
            f"• Active Phase: {phase}\n"
            f"• 250GB Mesh & Master Vault: {drive_url}\n"
            f"• Current Focus: {curr_task}\n"
            "============================================="
        )

if __name__ == '__main__':
    mem = MemoryManager()
    print(mem.get_system_prompt_context())
