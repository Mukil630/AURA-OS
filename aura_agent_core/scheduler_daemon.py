import asyncio
import os
from datetime import datetime
from aura_agent_core.config import IST, POLL_INTERVAL_SECONDS
from aura_agent_core.services import get_due_reminders, purge_completed_reminder


async def default_agent_wakeup_handler(reminder_id: int, title: str, scheduled_time: str):
    """
    Default callback when a reminder is triggered.
    Dispatches to console, and notifies Telegram if credentials/bridge available.
    """
    print(f"\n" + "=" * 60)
    print(f"[ALARM TRIGGERED] Waking up Main Agent!")
    print(f" Task ID     : #{reminder_id}")
    print(f" Task Title  : {title}")
    print(f" Scheduled   : {scheduled_time} IST")
    print(f" Action      : Dispatched to Main Agent. Auto-deleting from Turso...")
    print("=" * 60 + "\n")

    # Optional Telegram dispatch if configured
    try:
        from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN") or TELEGRAM_BOT_TOKEN
        chat_id = os.getenv("TELEGRAM_CHAT_ID") or TELEGRAM_CHAT_ID
        if bot_token and chat_id:
            import httpx
            msg = (
                f"🚨 <b>AURA-OS EXECUTIVE ALARM</b>\n\n"
                f"📌 <b>Task #{reminder_id}</b>: {title}\n"
                f"⏰ <b>Trigger Time</b>: {scheduled_time} IST\n"
                f"🧹 <i>Purged from Turso Cloud (0 MB bloat).</i>"
            )
            async with httpx.AsyncClient(timeout=10.0) as http_client:
                await http_client.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"}
                )
    except Exception as notify_err:
        print(f"[DAEMON] Telegram dispatch skipped or failed: {notify_err}")


class AuraSchedulerDaemon:
    def __init__(self, wakeup_callback=None):
        self.is_running = False
        self.wakeup_callback = wakeup_callback or default_agent_wakeup_handler

    async def start(self):
        self.is_running = True
        print(f"[*] AURA-OS Scheduler Daemon ACTIVE. Polling Turso Cloud every {POLL_INTERVAL_SECONDS}s...")
        while self.is_running:
            try:
                now_iso = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
                due_list = await get_due_reminders(now_iso)
                for item in due_list:
                    r_id, r_title, r_time = item["id"], item["title"], item["remind_at"]
                    # 1. Dispatch event / Wake up Main Agent!
                    try:
                        await self.wakeup_callback(r_id, r_title, r_time)
                    except Exception as cb_err:
                        print(f"[ERROR] Wakeup callback error for #{r_id}: {cb_err}")

                    # 2. Limitless Purge: Immediately delete from Turso Cloud
                    await purge_completed_reminder(r_id)
                    print(f"[CLEANUP] Purged Reminder #{r_id} from Turso. Storage remains 0 MB.")
            except Exception as e:
                print(f"[ERROR] Daemon check failed: {e}")

            await asyncio.sleep(POLL_INTERVAL_SECONDS)

    def stop(self):
        self.is_running = False
        print("[*] Scheduler Daemon STOPPED.")
