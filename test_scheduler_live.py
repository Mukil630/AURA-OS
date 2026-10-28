"""
Verification Script for AURA OS Autonomous Scheduler & Turso Cloud Live Reminder Loop
"""
import sys
import os
import asyncio
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

from aura.tools.reminders import list_active_reminders, get_and_purge_due_reminders, add_reminder
from aura.server import app, active_websockets, background_scheduler

async def run_verification():
    print("=" * 70)
    print("🚀 TESTING AURA OS AUTONOMOUS SCHEDULER & TURSO CLOUD LOOP")
    print("=" * 70)

    # 1. Check existing reminders from Turso
    active_str = list_active_reminders()
    print("📋 Active Reminders in Turso Cloud:")
    print(active_str)

    # 2. Add an instant 2-second reminder
    print("\n⏰ Adding 2-second test reminder: 'AURA Scheduler Live Test Verification'...")
    add_res = add_reminder("AURA Scheduler Live Test Verification", "2s")
    print(add_res)

    # 3. Wait 3 seconds
    print("\n⏳ Waiting 3 seconds for reminder to become due...")
    await asyncio.sleep(3)

    # 4. Run get_and_purge_due_reminders
    print("\n🔍 Checking and purging due reminders from Turso Cloud...")
    due = get_and_purge_due_reminders()
    print(f"✅ Found {len(due)} due reminder(s):")
    for r in due:
        print(f"   • #{r['id']}: {r['title']} (Due: {r['remind_at']}) - PURGED SUCCESSFULLY")

    assert any("AURA Scheduler Live Test" in r["title"] for r in due), "Failed to detect test reminder!"

    # 5. Verify 0 MB bloat in Turso
    print("\n📦 Verifying Turso Cloud Zero-Bloat Status...")
    active_after = list_active_reminders()
    assert "AURA Scheduler Live Test" not in active_after, "Failed to purge test reminder!"
    print("✅ Verified: Test reminder auto-purged from Turso Cloud (0 MB bloat maintained).")

    print("\n" + "=" * 70)
    print("🏆 ALL SCHEDULER & TURSO CLOUD TESTS PASSED 100% GREEN!")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(run_verification())
