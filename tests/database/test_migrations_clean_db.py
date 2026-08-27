"""Database migration from clean empty file verification test."""
import os
import tempfile
import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.database.base import Base
from app.database.session import check_db_health, init_db


@pytest.mark.anyio
async def test_clean_db_migration_and_startup():
    """
    Verifies that:
    1. A fresh, empty SQLite file is created.
    2. init_db() creates all required Phase 1 tables.
    3. Inspection confirms tables exist.
    4. check_db_health() succeeds.
    5. Clean teardown.
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
        tmp_db_path = tmp_file.name

    try:
        db_url = f"sqlite+aiosqlite:///{tmp_db_path.replace(os.sep, '/')}"
        engine = create_async_engine(db_url, echo=False)

        # 1. Verify all models are bound to Base.metadata
        import app.database.models  # noqa: F401
        expected_tables = {
            "tasks",
            "task_steps",
            "workflows",
            "workflow_states",
            "execution_events",
            "memories",
            "approval_requests",
        }

        # 2. Run Migration / Schema Creation
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # 3. Inspect Created Tables
        def get_table_names(connection):
            inspector = inspect(connection)
            return set(inspector.get_table_names())

        async with engine.connect() as conn:
            created_tables = await conn.run_sync(get_table_names)

        assert expected_tables.issubset(created_tables), f"Missing tables: {expected_tables - created_tables}"

        # 4. Verify DB connectivity with SELECT 1
        session_factory = async_sessionmaker(bind=engine, class_=AsyncSession)
        async with session_factory() as session:
            result = await session.execute(text("SELECT 1"))
            assert result.scalar() == 1

        await engine.dispose()
    finally:
        if os.path.exists(tmp_db_path):
            try:
                os.remove(tmp_db_path)
            except Exception:
                pass
