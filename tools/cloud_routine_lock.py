import os
import sys
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

logger = logging.getLogger("cloud_routine_lock")
IST_TZ = timezone(timedelta(hours=5, minutes=30))

def try_claim_daily_routine_lock(routine_id: str, date_str: str = None) -> bool:
    """
    Synchronously claims an atomic lock in Turso Cloud.
    Returns:
        True: If successfully claimed (FIRST time today -> PERMIT DISPATCH).
        False: If already claimed today (BLOCK DUPLICATE).
    """
    if not date_str:
        date_str = datetime.now(IST_TZ).strftime("%Y-%m-%d")

    turso_url = os.getenv("TURSO_DATABASE_URL")
    turso_token = os.getenv("TURSO_AUTH_TOKEN")
    if not turso_url or not turso_token:
        # Load from .env if missing
        from dotenv import load_dotenv
        load_dotenv(r"C:\Users\mukil\aura-os\.env")
        load_dotenv(r"C:\Users\mukil\jarvis-core\.env")
        turso_url = os.getenv("TURSO_DATABASE_URL")
        turso_token = os.getenv("TURSO_AUTH_TOKEN")

    if not turso_url or not turso_token:
        return True

    # Always enforce HTTPS REST url to prevent websocket handshake issues
    if turso_url.startswith("libsql://"):
        turso_url = turso_url.replace("libsql://", "https://")

    try:
        import libsql_client

        async def _query():
            async with libsql_client.create_client(turso_url, auth_token=turso_token) as client:
                await client.execute("""
                CREATE TABLE IF NOT EXISTS routine_daily_dispatches (
                    routine_id TEXT NOT NULL,
                    dispatch_date TEXT NOT NULL,
                    dispatched_at TEXT NOT NULL,
                    dispatched_by TEXT DEFAULT 'cloud',
                    PRIMARY KEY (routine_id, dispatch_date)
                );
                """)

                res = await client.execute(
                    "SELECT 1 FROM routine_daily_dispatches WHERE routine_id = ? AND dispatch_date = ?;",
                    [routine_id, date_str]
                )
                if len(res.rows) > 0:
                    return False  # Already dispatched today!

                try:
                    await client.execute(
                        "INSERT INTO routine_daily_dispatches (routine_id, dispatch_date, dispatched_at, dispatched_by) VALUES (?, ?, datetime('now'), 'cloud');",
                        [routine_id, date_str]
                    )
                    return True
                except Exception:
                    return False

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    return pool.submit(lambda: asyncio.run(_query())).result(timeout=10)
            else:
                return loop.run_until_complete(_query())
        except Exception:
            return asyncio.run(_query())

    except Exception as e:
        logger.warning(f"[CloudLock] Turso check notice: {e}")
        return True

if __name__ == "__main__":
    # Test checking morning_wakeup for 2026-11-03 (already claimed earlier)
    r1 = try_claim_daily_routine_lock("morning_wakeup", "2026-11-03")
    print("morning_wakeup for 2026-11-03:", r1)  # Should be False!

    # Test claiming a new dummy routine for 2026-11-03
    r2 = try_claim_daily_routine_lock("test_dummy_routine", "2026-11-03")
    print("test_dummy_routine (1st attempt):", r2)  # Should be True!

    r3 = try_claim_daily_routine_lock("test_dummy_routine", "2026-11-03")
    print("test_dummy_routine (2nd attempt):", r3)  # Should be False!
