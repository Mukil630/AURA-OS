import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from aura_agent_core.database import get_db_client, init_database

async def main():
    print("Checking Turso Cloud Database connection...")
    await init_database()
    client = get_db_client()
    try:
        tables = await client.execute("SELECT name FROM sqlite_master WHERE type='table';")
        print("TABLES IN TURSO CLOUD DB:")
        for row in tables:
            print(" -", row[0])

        reminders = await client.execute("SELECT id, title, remind_at, status, created_at FROM reminders;")
        print(f"\nREMINDERS (Total {len(reminders)}):")
        for r in reminders:
            print(f"  ID: {r[0]} | Title: {r[1]} | Remind At: {r[2]} | Status: {r[3]} | Created: {r[4]}")

        vault = await client.execute("SELECT id, category, title, drive_link, tags, created_at FROM aura_vault;")
        print(f"\nAURA VAULT ITEMS (Total {len(vault)}):")
        for v in vault:
            print(f"  ID: {v[0]} | Cat: {v[1]} | Title: {v[2]} | Drive: {v[3]} | Tags: {v[4]}")
            
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
