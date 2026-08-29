"""JARVIS Persistent Memory & Knowledge Vault Engine.
Maintains continuous multi-device context across Phone (Telegram), PC, and Cloud Server.
Persists chat history, user directives, document indexes, and links to 5TB Google Drive.
"""
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("MemoryVault")

MEMORY_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "memory")
PROFILE_FILE = os.path.join(MEMORY_DIR, "user_profile.json")
CONTEXT_FILE = os.path.join(MEMORY_DIR, "context.json")
CONVERSATIONS_FILE = os.path.join(MEMORY_DIR, "conversations.json")
DOCUMENTS_FILE = os.path.join(MEMORY_DIR, "documents_vault.json")

DEFAULT_PROFILE = {
    "user_name": "Mukil",
    "full_name": "MUKILARASU S",
    "role": "AI Engineer / Full-Stack Developer & Entrepreneur",
    "college": "VSB Engineering College, Karur (B.Tech IT, 2022-2026, CGPA: 7.9)",
    "master_resume_link": "https://drive.google.com/file/d/1TpyzV7OGEf-YQfGLUpusAI5cDDvF1kAJ/view?usp=drive_link",
    "master_drive_vault_id": "1iaHzDzC7KiJk2FlMdS7eNW7vkYxDeaXZ",
    "shared_drive_vault_url": "https://drive.google.com/drive/folders/1iaHzDzC7KiJk2FlMdS7eNW7vkYxDeaXZ?usp=drive_link",
    "sgc_billing_vault_1": "155EqYOwPJ2Fc9QfqVSrZu5VnYzZgRcyZ",
    "sgc_billing_vault_2": "1a9VJAP_Nypn_mjUEYCNvMpkGN5H9Kwf4",
    "github_portfolio": "https://github.com/Mukil630",
    "primary_skills": [
        "Python", "FastAPI", "Generative AI", "Autonomous Multi-Agent Architecture",
        "React", "TypeScript", "Node.js", "Docker", "PostgreSQL", "Linux/Windows Automation"
    ],
    "family_business": "Sri Ganapathi Colours (SGC) - Automated Billing & Invoicing",
    "tone": "Executive, proactive, authentic Tamil-Tanglish ('Boss' / 'Mapla' dynamic)",
    "birthday_launch": "September 3, 2026",
}


class MemoryVault:
    """
    Persistent Memory Manager that ensures JARVIS never forgets across sessions.
    """

    def __init__(self):
        self._ensure_storage()

    def _ensure_storage(self) -> None:
        """Initializes storage files with default profile if not present."""
        os.makedirs(MEMORY_DIR, exist_ok=True)

        if not os.path.exists(PROFILE_FILE):
            with open(PROFILE_FILE, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_PROFILE, f, indent=2, ensure_ascii=False)

        if not os.path.exists(CONTEXT_FILE):
            initial_context = {
                "last_active": datetime.now(timezone.utc).isoformat(),
                "active_tasks": [],
                "recent_focus": "Autonomous Job Hunting & 5TB Drive Vault Sync",
                "notes": ["Master Resume and 5TB Drive Vault linked."],
            }
            with open(CONTEXT_FILE, "w", encoding="utf-8") as f:
                json.dump(initial_context, f, indent=2, ensure_ascii=False)

        if not os.path.exists(CONVERSATIONS_FILE):
            with open(CONVERSATIONS_FILE, "w", encoding="utf-8") as f:
                json.dump([], f, indent=2)

        if not os.path.exists(DOCUMENTS_FILE):
            with open(DOCUMENTS_FILE, "w", encoding="utf-8") as f:
                json.dump([], f, indent=2)

    def get_profile(self) -> Dict[str, Any]:
        """Returns Mukil's master user profile."""
        try:
            with open(PROFILE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return DEFAULT_PROFILE

    def get_context(self) -> Dict[str, Any]:
        """Returns live context and active focus."""
        try:
            with open(CONTEXT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def update_context(self, key: str, value: Any) -> None:
        """Updates a key in persistent context."""
        ctx = self.get_context()
        ctx[key] = value
        ctx["last_active"] = datetime.now(timezone.utc).isoformat()
        with open(CONTEXT_FILE, "w", encoding="utf-8") as f:
            json.dump(ctx, f, indent=2, ensure_ascii=False)

    def record_conversation_turn(self, sender: str, text: str, channel: str = "Telegram") -> None:
        """Saves a conversation turn to persistent history."""
        try:
            with open(CONVERSATIONS_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = []

        history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sender": sender,
            "channel": channel,
            "text": text[:1000],
        })

        # Keep last 100 turns
        history = history[-100:]
        with open(CONVERSATIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)

    def get_recent_conversation_messages(self, limit: int = 6) -> List[Dict[str, str]]:
        """Returns recent turns formatted for LLM message history."""
        try:
            with open(CONVERSATIONS_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            return []

        recent = history[-limit:] if len(history) > limit else history
        msgs = []
        for turn in recent:
            sender = turn.get("sender", "")
            role = "user" if sender.lower() in ("mukil", "user", "boss") else "assistant"
            txt = turn.get("text", "").strip()
            if txt:
                msgs.append({"role": role, "content": txt[:600]})
        return msgs

    def get_recent_conversations_summary(self, limit: int = 6) -> str:
        """Returns a string summary of recent conversational turns."""
        try:
            with open(CONVERSATIONS_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            return "No previous conversations logged."

        recent = history[-limit:] if len(history) > limit else history
        lines = []
        for h in recent:
            lines.append(f"{h.get('sender')}: {h.get('text')}")
        return "\n".join(lines)

    def save_important_document(self, title: str, doc_type: str, drive_link: Optional[str] = None, local_path: Optional[str] = None, notes: Optional[str] = None) -> Dict[str, Any]:
        """Saves reference to an important document in Google Drive / local storage."""
        try:
            with open(DOCUMENTS_FILE, "r", encoding="utf-8") as f:
                docs = json.load(f)
        except Exception:
            docs = []

        entry = {
            "title": title.strip(),
            "type": doc_type.strip(),
            "drive_link": drive_link or DEFAULT_PROFILE["shared_drive_vault_url"],
            "local_path": local_path,
            "added_at": datetime.now(timezone.utc).isoformat(),
            "notes": notes or "Stored in JARVIS Master Vault",
        }

        docs.insert(0, entry)
        with open(DOCUMENTS_FILE, "w", encoding="utf-8") as f:
            json.dump(docs, f, indent=2, ensure_ascii=False)

        return entry

    def list_documents(self) -> List[Dict[str, Any]]:
        """Returns indexed important documents."""
        try:
            with open(DOCUMENTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def get_prompt_memory_context(self) -> str:
        """Generates dynamic persistent memory block to inject into LLM prompts."""
        profile = self.get_profile()
        ctx = self.get_context()
        docs = self.list_documents()

        doc_summary = ", ".join([d["title"] for d in docs[:5]]) if docs else "Master Resume linked in Drive"

        return f"""
[PERSISTENT MEMORY & 5TB DRIVE VAULT KNOWLEDGE]
• User: {profile.get('user_name')} ({profile.get('full_name')}) - {profile.get('role')}
• College: {profile.get('college')}
• Master Resume Drive Link: {profile.get('master_resume_link')}
• 5TB Master Drive Vault URL: {profile.get('shared_drive_vault_url')} (ID: {profile.get('master_drive_vault_id')})
• SGC Billing Redundant Vaults: {profile.get('sgc_billing_vault_1')} & {profile.get('sgc_billing_vault_2')}
• Indexed Vault Documents: {doc_summary}
• Recent Focus: {ctx.get('recent_focus', 'Full placement & business automation')}
"""
