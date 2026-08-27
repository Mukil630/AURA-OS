"""Comprehensive Unit & Integration Test Suite for Phase 6 Memory System."""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.contracts.memory import MemoryContract, MemoryQueryContract
from app.core.enums import EventType, MemoryScope, MemoryType
from app.database.base import Base
from app.database.repositories.event_repo import EventRepository
from app.database.repositories.memory_repo import MemoryRepository
from app.memory.manager import MemoryManager


# ── Scenario 1: Store Episodic and Semantic Memory ────────────────────────────────────
@pytest.mark.anyio
async def test_scenario_1_store_episodic_and_semantic_memory():
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)
    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        manager = MemoryManager(session)

        # 1. Semantic Memory
        sem_mem = MemoryContract(
            user_id="mukil",
            memory_type=MemoryType.SEMANTIC_FACT,
            content="Preferred GitHub repository is Mukil630/AURA-OS",
            summary="Primary repository: Mukil630/AURA-OS",
            importance_score=0.9,
            tags=["github", "repository", "aura"],
        )
        mem_id_1 = await manager.store(sem_mem)
        assert mem_id_1.startswith("mem_")

        # 2. Episodic Memory
        epi_mem = MemoryContract(
            user_id="mukil",
            memory_type=MemoryType.EPISODIC_TASK,
            content="Task task_101 resolved CI failure by updating auth token expiry check in auth.py",
            summary="CI fix: token expiry boundary condition",
            importance_score=0.75,
            source_task_id="task_101",
            tags=["ci", "auth", "fix"],
        )
        mem_id_2 = await manager.store(epi_mem)
        assert mem_id_2.startswith("mem_")

    await engine_db.dispose()


# ── Scenario 2: Retrieve Exact Memory by ID ───────────────────────────────────────────
@pytest.mark.anyio
async def test_scenario_2_retrieve_exact_memory_by_id():
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)
    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        manager = MemoryManager(session)
        mem = MemoryContract(
            user_id="mukil",
            memory_type=MemoryType.USER_PREFERENCE,
            content="Preferred notification channel is Telegram",
            importance_score=0.8,
            tags=["telegram", "notifications"],
        )
        mem_id = await manager.store(mem)

        retrieved = await manager.retrieve(mem_id)
        assert retrieved is not None
        assert retrieved.memory_id == mem_id
        assert retrieved.content == "Preferred notification channel is Telegram"
        assert retrieved.memory_type == MemoryType.USER_PREFERENCE

    await engine_db.dispose()


# ── Scenario 3: Semantic Relevance Retrieval ──────────────────────────────────────────
@pytest.mark.anyio
async def test_scenario_3_semantic_relevance_retrieval():
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)
    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        manager = MemoryManager(session)

        # Store multiple disparate memories
        await manager.store(
            MemoryContract(
                user_id="mukil",
                memory_type=MemoryType.SEMANTIC_FACT,
                content="Primary project repository is Mukil630/AURA-OS with Python 3.10 and FastAPI",
                tags=["github", "repository", "fastapi"],
                importance_score=0.9,
            )
        )
        await manager.store(
            MemoryContract(
                user_id="mukil",
                memory_type=MemoryType.USER_PREFERENCE,
                content="Always use Google Drive folder 'JARVIS Master Vault' for bill backups",
                tags=["drive", "vault", "billing"],
                importance_score=0.8,
            )
        )

        # Query for GitHub repo
        q = MemoryQueryContract(
            query_text="Check my project GitHub repository CI status",
            user_id="mukil",
            top_k=3,
        )
        results = await manager.query(q)
        assert len(results) >= 1
        assert "AURA-OS" in results[0].content

    await engine_db.dispose()


# ── Scenario 4: Relevance Threshold Filtering ─────────────────────────────────────────
@pytest.mark.anyio
async def test_scenario_4_relevance_threshold_filtering():
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)
    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        manager = MemoryManager(session)
        await manager.store(
            MemoryContract(
                user_id="mukil",
                memory_type=MemoryType.SEMANTIC_FACT,
                content="Preferred programming language is Python and TypeScript",
                tags=["coding", "python", "typescript"],
                importance_score=0.7,
            )
        )

        # Completely unrelated query
        q = MemoryQueryContract(
            query_text="Find best recipes for cooking mushroom soup",
            user_id="mukil",
            top_k=5,
        )
        results = await manager.query(q)
        assert len(results) == 0  # Below 0.15 relevance cutoff!

    await engine_db.dispose()


# ── Scenario 5: User and Tenant Isolation ─────────────────────────────────────────────
@pytest.mark.anyio
async def test_scenario_5_user_and_tenant_isolation():
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)
    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        manager = MemoryManager(session)

        # Store Secret Fact for User A (Mukil)
        await manager.store(
            MemoryContract(
                user_id="mukil",
                memory_type=MemoryType.SEMANTIC_FACT,
                content="Mukil's private API secret token is sk_live_99999",
                tags=["secret", "token"],
                importance_score=1.0,
            )
        )

        # User B (Alice) queries for secret token
        q_alice = MemoryQueryContract(
            query_text="secret token api",
            user_id="alice_tenant",
            top_k=5,
        )
        alice_results = await manager.query(q_alice)
        assert len(alice_results) == 0  # Absolute zero leak!

    await engine_db.dispose()


# ── Scenario 6: Duplicate Handling & Deduplication ────────────────────────────────────
@pytest.mark.anyio
async def test_scenario_6_duplicate_handling_deduplication():
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)
    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        repo = MemoryRepository(session)

        # 1. First insertion
        mem1 = MemoryContract(
            user_id="mukil",
            memory_type=MemoryType.SEMANTIC_FACT,
            content="Active Drive Folder ID is 1iaHzDzC7KiJk2FlMdS7eNW7vkYxDeaXZ",
            importance_score=0.5,
            tags=["drive", "folder"],
        )
        saved1 = await repo.create_or_update_memory(mem1)

        # 2. Second insertion of equivalent fact with higher importance and new tag
        mem2 = MemoryContract(
            user_id="mukil",
            memory_type=MemoryType.SEMANTIC_FACT,
            content="Active Drive Folder ID is 1iaHzDzC7KiJk2FlMdS7eNW7vkYxDeaXZ ",
            importance_score=0.95,
            tags=["vault", "master"],
        )
        saved2 = await repo.create_or_update_memory(mem2)

        # Must merge into single memory record rather than creating duplicate row
        assert saved2.memory_id == saved1.memory_id
        assert saved2.importance_score == 0.95
        assert "vault" in saved2.tags
        assert "drive" in saved2.tags

        all_mems = await repo.list_memories(user_id="mukil")
        assert len(all_mems) == 1

    await engine_db.dispose()


# ── Scenario 7: Memory Mutation and Update ────────────────────────────────────────────
@pytest.mark.anyio
async def test_scenario_7_memory_mutation_and_update():
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)
    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        repo = MemoryRepository(session)
        mem = MemoryContract(
            user_id="mukil",
            memory_type=MemoryType.USER_PREFERENCE,
            content="Communication tone: formal english",
            importance_score=0.6,
        )
        saved = await repo.create_or_update_memory(mem)

        # Update
        updated_contract = MemoryContract(
            memory_id=saved.memory_id,
            user_id="mukil",
            memory_type=MemoryType.USER_PREFERENCE,
            content="Communication tone: Friendly Tanglish Maapla tone",
            importance_score=0.95,
            tags=["tone", "tanglish"],
        )
        res = await repo.update_memory(updated_contract)
        assert res is not None
        assert res.content == "Communication tone: Friendly Tanglish Maapla tone"
        assert res.importance_score == 0.95

    await engine_db.dispose()


# ── Scenario 8: Memory Deletion & Forgetting ──────────────────────────────────────────
@pytest.mark.anyio
async def test_scenario_8_memory_deletion_and_forgetting():
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)
    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        manager = MemoryManager(session)
        mem = MemoryContract(
            user_id="mukil",
            memory_type=MemoryType.SEMANTIC_FACT,
            content="Old deprecated API key sk_old_111",
            importance_score=0.3,
        )
        mem_id = await manager.store(mem)

        # Delete
        ok = await manager.delete(mem_id, user_id="mukil")
        assert ok is True

        retrieved = await manager.retrieve(mem_id)
        assert retrieved is None

    await engine_db.dispose()


# ── Scenario 9: Provenance and Importance Tracking ────────────────────────────────────
@pytest.mark.anyio
async def test_scenario_9_provenance_and_importance_tracking():
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)
    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        manager = MemoryManager(session)
        mem = MemoryContract(
            user_id="mukil",
            memory_type=MemoryType.EPISODIC_TASK,
            content="Autonomous build fix applied to branch main",
            importance_score=0.88,
            source_task_id="task_auto_99",
            tags=["build", "fix"],
        )
        mem_id = await manager.store(mem)

        saved = await manager.retrieve(mem_id)
        assert saved.source_task_id == "task_auto_99"
        assert saved.importance_score == 0.88
        assert saved.created_at is not None

    await engine_db.dispose()


# ── Scenario 10: Retrieval and Store Audit Trail ──────────────────────────────────────
@pytest.mark.anyio
async def test_scenario_10_retrieval_and_store_audit_trail():
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)
    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        event_repo = EventRepository(session)
        manager = MemoryManager(session)

        # Store
        mem = MemoryContract(
            user_id="mukil",
            memory_type=MemoryType.SEMANTIC_FACT,
            content="Google Drive master resume link is 1TpyzV7OGEf-YQfGLUpusAI5cDDvF1kAJ",
            tags=["resume", "drive"],
            importance_score=0.9,
        )
        await manager.store(mem)

        # Query
        await manager.query(MemoryQueryContract(query_text="resume drive link", user_id="mukil"))

        # Verify audit logs
        events = await event_repo.list_events(limit=10)
        types = [e.event_type for e in events]
        assert EventType.MEMORY_SAVED in types
        assert EventType.MEMORY_RETRIEVED in types

    await engine_db.dispose()


# ── Scenario 11: Empty and Noisy Query Handling ───────────────────────────────────────
@pytest.mark.anyio
async def test_scenario_11_empty_and_noisy_query_handling():
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)
    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        manager = MemoryManager(session)
        await manager.store(
            MemoryContract(
                user_id="mukil",
                memory_type=MemoryType.USER_PREFERENCE,
                content="Standard priority is normal",
                importance_score=0.8,
            )
        )

        # Empty / whitespace-only query
        q = MemoryQueryContract(query_text="   ", user_id="mukil", top_k=5)
        results = await manager.query(q)
        assert len(results) == 1  # Gracefully returns top items without exception

    await engine_db.dispose()


# ── Scenario 12: Context Builder for Planner ──────────────────────────────────────────
@pytest.mark.anyio
async def test_scenario_12_context_builder_for_planner():
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)
    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        manager = MemoryManager(session)

        # User previously configured default repo
        await manager.store(
            MemoryContract(
                user_id="mukil",
                memory_type=MemoryType.USER_PREFERENCE,
                content="Default repository for CI checks is Mukil630/AURA-OS",
                tags=["github", "repository", "default"],
                importance_score=0.9,
            )
        )

        # User now prompts without explicitly specifying repo name: "Check CI builds"
        context_mems = await manager.build_context(
            user_id="mukil",
            raw_input="Check my CI builds and fix errors",
        )
        assert len(context_mems) >= 1
        assert "Mukil630/AURA-OS" in context_mems[0].content

    await engine_db.dispose()
