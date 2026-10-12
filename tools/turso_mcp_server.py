"""
AURA-OS TURSO CLOUD ENGINE - MODEL CONTEXT PROTOCOL (MCP) SERVER
tools/turso_mcp_server.py

Authoritative Serverless Cloud Memory & Limitless Scheduler MCP Server.
Connected to Turso LibSQL Cloud in AWS Mumbai (Free 5 GB Tier).
Provides NLP-powered reminders, 0 MB auto-purging, and Universal Vault memory.
"""

import sys
import os
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List

# Suppress warnings
import warnings
warnings.filterwarnings("ignore")

# Force UTF-8 on Windows
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

JARVIS_CORE_DIR = Path(__file__).resolve().parent.parent
if str(JARVIS_CORE_DIR) not in sys.path:
    sys.path.insert(0, str(JARVIS_CORE_DIR))

from mcp.server.fastmcp import FastMCP
from aura_agent_core.nlp_parser import parse_natural_time
from aura_agent_core.services import (
    create_reminder, list_active_reminders, cancel_reminder,
    save_to_vault, search_vault, delete_vault_item
)

mcp = FastMCP(
    "turso-mcp",
    instructions="AURA-OS Turso Cloud Database & Limitless Scheduler Engine (AWS Mumbai)."
)


@mcp.tool()
def turso_add_reminder(task: str, when: str) -> str:
    """
    Parses NLP/Tanglish time phrase and creates a scheduled reminder in Turso Cloud.
    Auto-purged upon dispatch to maintain 0 MB storage bloat.

    Args:
        task: Description of task or reminder (e.g. 'Pay Lakshmi Chemicals 25000').
        when: Natural language date/time or Tanglish (e.g. 'tomorrow 6pm', 'naalaiki kaalaila 9am', '10s').
    """
    parsed = parse_natural_time(when)
    if not parsed["success"]:
        return f"❌ Error: {parsed['error']}"

    rem_id = asyncio.run(create_reminder(task, parsed["scheduled_iso"]))
    return (
        f"✅ **Reminder Saved in Turso Cloud DB (AWS Mumbai)!**\n"
        f"• **Task ID:** #{rem_id}\n"
        f"• **Task:** {task}\n"
        f"• **Scheduled:** {parsed['scheduled_iso']} IST ({parsed['display']})\n"
        f"• **Behavior:** Dispatches wakeup alert and auto-deletes to keep 0 MB bloat!"
    )


@mcp.tool()
def turso_list_reminders() -> str:
    """
    Lists all active pending reminders currently sitting in Turso Cloud DB.
    """
    items = asyncio.run(list_active_reminders())
    if not items:
        return "ℹ️ No pending reminders in Turso Cloud. Database is 100% clean (0 MB)."

    out = [f"📋 **Active Reminders in Turso Cloud ({len(items)} Tasks):**"]
    for r in items:
        out.append(f"• **#{r['id']}**: `{r['title']}` | ⏰ `{r['remind_at']} IST`")
    return "\n".join(out)


@mcp.tool()
def turso_cancel_reminder(reminder_id: int) -> str:
    """
    Cancels and immediately purges a reminder from Turso Cloud DB.

    Args:
        reminder_id: Integer ID of the reminder to cancel.
    """
    success = asyncio.run(cancel_reminder(reminder_id))
    if success:
        return f"✅ Reminder #{reminder_id} successfully cancelled & purged from Turso Cloud."
    return f"❌ Reminder #{reminder_id} not found."


@mcp.tool()
def turso_save_memory_vault(category: str, title: str, content: str, drive_link: str = "", tags: str = "") -> str:
    """
    Saves personal facts, notes, conversation ideas, or Drive links into Turso Universal Vault.

    Args:
        category: 'PERSONAL', 'BILLS', 'JOB', 'IDEA', 'CONVO', or 'NOTE'.
        title: Short title summary.
        content: Detailed memory notes.
        drive_link: Optional Google Drive file URL.
        tags: Comma-separated search tags.
    """
    vault_id = asyncio.run(save_to_vault(category, title, content, drive_link, tags))
    return f"✅ Saved into Turso Universal Vault with ID #{vault_id} (Category: {category.upper()})!"


@mcp.tool()
def turso_search_memory_vault(keyword: str = "", category: str = "", limit: int = 10) -> str:
    """
    Searches Turso Universal Memory Vault across keywords, categories, and tags.

    Args:
        keyword: Search query in title, content, or tags.
        category: Optional category filter ('PERSONAL', 'BILLS', 'JOB', 'IDEA').
        limit: Max records to return.
    """
    results = asyncio.run(search_vault(keyword=keyword, category=category, limit=limit))
    if not results:
        return f"ℹ️ No memories found matching '{keyword}'."

    out = [f"🧠 **Found {len(results)} Memories in Turso Universal Vault:**"]
    for m in results:
        drive_info = f" | 🔗 [Drive]({m['drive_link']})" if m.get('drive_link') else ""
        out.append(f"• **[#{m['id']}] [{m['category']}] {m['title']}**\n  {m['content']}{drive_info}")
    return "\n".join(out)


if __name__ == "__main__":
    mcp.run()
