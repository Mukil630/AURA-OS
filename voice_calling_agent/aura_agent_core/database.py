import libsql_client
from aura_agent_core.config import TURSO_DATABASE_URL, TURSO_AUTH_TOKEN


def get_db_client():
    """Returns an async LibSQL client connected to Turso Cloud"""
    if not TURSO_DATABASE_URL or not TURSO_AUTH_TOKEN:
        raise ValueError("Missing TURSO_DATABASE_URL or TURSO_AUTH_TOKEN in environment!")
    return libsql_client.create_client(TURSO_DATABASE_URL, auth_token=TURSO_AUTH_TOKEN)


async def init_database():
    """Initializes all tables in Turso Cloud DB if they do not exist"""
    async with get_db_client() as client:
        # 1. Reminders Table (Limitless auto-clean)
        await client.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            remind_at TEXT NOT NULL,
            status TEXT DEFAULT 'PENDING',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # 2. Universal Vault Table (Notes, Convos, Memories, Drive Links)
        await client.execute("""
        CREATE TABLE IF NOT EXISTS aura_vault (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            drive_link TEXT DEFAULT '',
            tags TEXT DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """)
    return True
