import asyncio
import sys
import os

# Add root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aura_agent_core.nlp_parser import parse_natural_time
from aura_agent_core.services import (
    create_reminder, list_active_reminders, cancel_reminder,
    save_to_vault, search_vault
)


async def main_cli():
    while True:
        print("\n" + "=" * 60)
        print(" AURA-OS EXECUTIVE ASSISTANT CONSOLE")
        print("=" * 60)
        print(" [1] Set Smart Reminder (NLP Date + Timing + Month)")
        print(" [2] List Active Reminders in Turso Cloud")
        print(" [3] Save Memory / Note / Drive Link to Vault")
        print(" [4] Search Vault (Keyword / Category / Tags)")
        print(" [5] Exit")
        print("=" * 60)

        choice = input("Enter choice (1-5): ").strip()

        if choice == "1":
            task = input("\n[?] Enter reminder task: ").strip()
            when = input("[?] When to trigger? (e.g. '14th oct 10am', 'tomorrow 6pm', '10s'): ").strip()
            parsed = parse_natural_time(when)
            if not parsed["success"]:
                print(f"[!] Error: {parsed['error']}")
                continue

            rem_id = await create_reminder(task, parsed["scheduled_iso"])
            print(f"\n[+] Saved to Turso Cloud! ID #{rem_id}")
            print(f" Scheduled for: {parsed['scheduled_iso']} IST ({parsed['display']})")

        elif choice == "2":
            items = await list_active_reminders()
            print(f"\n[+] Active Reminders in Cloud: {len(items)}")
            for it in items:
                print(f" - #{it['id']}: '{it['title']}' at {it['remind_at']} IST")

        elif choice == "3":
            category = input("\n[?] Category (IDEA / CONVO / BILLS / JOB / PERSONAL): ").strip() or "NOTE"
            title = input("[?] Title: ").strip()
            content = input("[?] Content / Note details: ").strip()
            drive_link = input("[?] Google Drive Link (optional, press Enter to skip): ").strip()
            tags = input("[?] Tags (e.g. 'sgc, textile' or 'placement'): ").strip()

            vault_id = await save_to_vault(category, title, content, drive_link, tags)
            print(f"\n[+] Memory Saved in Turso Cloud Vault! ID #{vault_id}")

        elif choice == "4":
            kw = input("\n[?] Search keyword: ").strip()
            res = await search_vault(keyword=kw)
            print(f"\n[+] Found {len(res)} matching memories:")
            for item in res:
                print(f"\n--- [ID #{item['id']}] [{item['category']}] {item['title']} ---")
                print(f"Content: {item['content']}")
                if item['drive_link']:
                    print(f"Drive Link: {item['drive_link']}")
                print(f"Tags: {item['tags']} | Created: {item['created_at']}")

        elif choice == "5":
            print("\nGoodbye mapla!")
            break


if __name__ == "__main__":
    asyncio.run(main_cli())
