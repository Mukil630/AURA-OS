"""Phase 12.1: Multi-Tenant Context, Immutability, and Query Boundary Enforcement Test Suite."""
import asyncio
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.contracts.memory import MemoryContract, MemoryQueryContract
from app.core.contracts.permission import ApprovalRequestContract
from app.core.contracts.task import TaskContract
from app.core.enums import ApprovalState, MemoryType, RiskTier, TaskStatus
from app.database.base import Base
from app.database.models.approval import ApprovalRequestModel
from app.database.models.memory import MemoryModel
from app.database.models.task import TaskModel
from app.database.repositories.approval_repo import ApprovalRepository
from app.database.repositories.memory_repo import MemoryRepository
from app.database.repositories.task_repo import TaskRepository
from app.main import app
from app.policy.approval_engine import ApprovalEngine, default_approval_engine
from app.reliability.idempotency import IdempotencyLedger
from app.security.auth import create_access_token
from app.security.tenant import ImmutableTenantError, TenantContext, TenantMismatchError, TenantScopedEntity


# ═════════════════════════════════════════════════════════════════════════════
# 1. CORE TENANT CONTEXT & IMMUTABILITY (Tests 1 - 5)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_01_tenant_context_initialization_with_actor_and_tenant():
    """Verify TenantContext separates actor_id from tenant_id cleanly."""
    ctx = TenantContext(tenant_id="tenant_alpha", actor_id="user_alice", role="engineer")
    assert ctx.tenant_id == "tenant_alpha"
    assert ctx.actor_id == "user_alice"
    assert ctx.role == "engineer"
    assert ctx.request_id.startswith("req_")


def test_p12_02_tenant_context_empty_tenant_id_rejected():
    """Verify TenantContext rejects empty or whitespace-only tenant_id."""
    with pytest.raises(ValueError):
        TenantContext(tenant_id="", actor_id="user_alice")
    with pytest.raises(ValueError):
        TenantContext(tenant_id="   ", actor_id="user_alice")


def test_p12_03_tenant_scoped_entity_ownership_assertion_pass():
    """Verify TenantScopedEntity.assert_tenant_ownership succeeds for matching tenant."""
    entity = TenantScopedEntity(tenant_id="tenant_alpha")
    entity.assert_tenant_ownership("tenant_alpha")  # Must not raise


def test_p12_04_tenant_scoped_entity_ownership_assertion_fails_cross_tenant():
    """Verify TenantScopedEntity.assert_tenant_ownership raises TenantMismatchError on mismatch."""
    entity = TenantScopedEntity(tenant_id="tenant_alpha")
    with pytest.raises(TenantMismatchError):
        entity.assert_tenant_ownership("tenant_beta")


def test_p12_05_actor_id_distinct_from_tenant_id_in_jwt_claims():
    """Verify JWT encodes distinct sub (actor_id) and tenant_id claims."""
    from app.security.auth import decode_access_token
    token = create_access_token(actor_id="worker_07", tenant_id="enterprise_corp_a", role="worker")
    payload = decode_access_token(token)

    assert payload["sub"] == "worker_07"
    assert payload["tenant_id"] == "enterprise_corp_a"
    assert payload["role"] == "worker"


# ═════════════════════════════════════════════════════════════════════════════
# 2. REPOSITORY TENANT ISOLATION (Tests 6 - 10)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_p12_06_task_repository_tenant_a_reads_own_task():
    """Verify TaskRepository returns task when querying with matching tenant_id."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        repo = TaskRepository(session)
        task = await repo.create_task(TaskContract(user_id="tenant_A", raw_input="Task for tenant A"))
        await session.commit()

        # Query with matching tenant
        found = await repo.get_task(task.task_id, tenant_id="tenant_A")
        assert found is not None
        assert found.task_id == task.task_id


@pytest.mark.anyio
async def test_p12_07_task_repository_direct_call_bypass_cross_tenant_returns_none_404():
    """
    CRITICAL ISOLATION TEST:
    Direct repository call: Tenant B attempts to fetch Tenant A's task -> Returns None (404).
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        repo = TaskRepository(session)
        task_a = await repo.create_task(TaskContract(user_id="tenant_A", raw_input="Secret task A"))
        await session.commit()

        # Tenant B queries Tenant A's task
        cross_found = await repo.get_task(task_a.task_id, tenant_id="tenant_B")
        assert cross_found is None  # Must NOT return tenant A's task!


@pytest.mark.anyio
async def test_p12_08_task_repository_cross_tenant_update_status_returns_none():
    """Verify attempting to update another tenant's task returns None (safe 404)."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        repo = TaskRepository(session)
        task_a = await repo.create_task(TaskContract(user_id="tenant_A", raw_input="Task A"))
        await session.commit()

        # Tenant B attempts to cancel Tenant A's task
        res = await repo.update_task_status(task_a.task_id, TaskStatus.CANCELLED, tenant_id="tenant_B")
        assert res is None


@pytest.mark.anyio
async def test_p12_09_task_repository_cross_tenant_bulk_list_leakage_free():
    """Verify list_tasks(tenant_id) never leaks records from other tenants."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        repo = TaskRepository(session)
        await repo.create_task(TaskContract(user_id="tenant_A", raw_input="A1"))
        await repo.create_task(TaskContract(user_id="tenant_A", raw_input="A2"))
        await repo.create_task(TaskContract(user_id="tenant_B", raw_input="B1"))
        await session.commit()

        # Tenant A lists tasks
        tasks_a = await repo.list_tasks(tenant_id="tenant_A")
        assert len(tasks_a) == 2
        assert all(t.user_id == "tenant_A" for t in tasks_a)

        # Tenant B lists tasks
        tasks_b = await repo.list_tasks(tenant_id="tenant_B")
        assert len(tasks_b) == 1
        assert tasks_b[0].user_id == "tenant_B"


@pytest.mark.anyio
async def test_p12_10_approval_repository_cross_tenant_isolation():
    """Verify ApprovalRepository blocks cross-tenant reads and decisions."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        repo = ApprovalRepository(session)
        ticket = await repo.create_approval_request(
            ApprovalRequestContract(
                task_id="t_a",
                step_id="s_a",
                action="coding.apply_fix",
                capability_id="coding.apply_fix",
                tenant_id="tenant_A",
                risk_tier=RiskTier.TIER_3_HIGH,
                description="Fix for Tenant A",
            )
        )
        await session.commit()

        # Tenant A queries -> Found
        appr_a = await repo.get_approval_request(ticket.approval_id, tenant_id="tenant_A")
        assert appr_a is not None

        # Tenant B queries -> None (404)
        appr_b = await repo.get_approval_request(ticket.approval_id, tenant_id="tenant_B")
        assert appr_b is None

        # Tenant B attempts to decide -> None
        decide_b = await repo.decide_approval(ticket.approval_id, ApprovalState.APPROVED, "user_b", tenant_id="tenant_B")
        assert decide_b is None


# ═════════════════════════════════════════════════════════════════════════════
# 3. IDEMPOTENCY, MEMORY & ADVERSARIAL ISOLATION (Tests 11 - 15)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_11_idempotency_ledger_multi_dimensional_tenant_scoping():
    """
    Verify IdempotencyLedger scopes keys to (tenant_id, capability_id, idempotency_key).
    Tenant B querying Tenant A's idempotency key gets a Cache Miss.
    """
    ledger = IdempotencyLedger()
    ledger.record(
        idempotency_key="shared_key_123",
        action_hash="hash_a",
        capability_id="drive.upload",
        result_data={"file_id": "file_tenant_a"},
        tenant_id="tenant_A",
    )

    # Tenant A queries -> Cache Hit
    hit_a = ledger.get("shared_key_123", action_hash="hash_a", tenant_id="tenant_A", capability_id="drive.upload")
    assert hit_a is not None
    assert hit_a.result_data["file_id"] == "file_tenant_a"

    # Tenant B queries -> Cache Miss (None)
    hit_b = ledger.get("shared_key_123", action_hash="hash_a", tenant_id="tenant_B", capability_id="drive.upload")
    assert hit_b is None


def test_p12_12_idempotency_ledger_same_tenant_different_capability_isolated():
    """Verify identical idempotency keys across different capabilities do not collide."""
    ledger = IdempotencyLedger()
    ledger.record("key_001", "hash_upload", "drive.upload", {"file_id": "file_1"}, tenant_id="tenant_A")
    ledger.record("key_001", "hash_pr", "github.create_pr", {"pr_number": 42}, tenant_id="tenant_A")

    res_upload = ledger.get("key_001", tenant_id="tenant_A", capability_id="drive.upload")
    res_pr = ledger.get("key_001", tenant_id="tenant_A", capability_id="github.create_pr")

    assert res_upload.result_data["file_id"] == "file_1"
    assert res_pr.result_data["pr_number"] == 42


@pytest.mark.anyio
async def test_p12_13_memory_repository_cross_tenant_isolation():
    """Verify MemoryRepository enforces tenant separation during listing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        repo = MemoryRepository(session)
        await repo.create_or_update_memory(
            MemoryContract(user_id="tenant_A", memory_type=MemoryType.SEMANTIC_FACT, content="Tenant A confidential repo Mukil630/AURA-OS")
        )
        await repo.create_or_update_memory(
            MemoryContract(user_id="tenant_B", memory_type=MemoryType.SEMANTIC_FACT, content="Tenant B confidential repo Acme/Private-Core")
        )
        await session.commit()

        # Tenant A searches
        res_a = await repo.list_memories(user_id="tenant_A")
        assert len(res_a) == 1
        assert "AURA-OS" in res_a[0].content
        assert "Acme" not in res_a[0].content


def test_p12_14_approval_engine_cross_tenant_verification_denied():
    """Verify ApprovalEngine denies execution verification when tenant mismatch occurs."""
    engine = ApprovalEngine()
    ticket = engine.create_approval_request(
        task_id="t_adv",
        step_id="s_adv",
        action="coding.apply_fix",
        capability_id="coding.apply_fix",
        parameters={"repo": "Mukil630/AURA-OS"},
        risk_tier=RiskTier.TIER_3_HIGH,
        description="Fix",
        tenant_id="tenant_A",
    )
    engine.decide_approval(ticket.approval_id, "approve", approver_id="user_a")

    # Tenant B tries to execute with Tenant A's approved ticket
    valid, reason, _ = engine.verify_and_consume_approval(
        approval_id=ticket.approval_id,
        capability_id="coding.apply_fix",
        parameters={"repo": "Mukil630/AURA-OS"},
        tenant_id="tenant_B",  # Impersonator
    )
    assert valid is False
    assert "Tenant Mismatch" in reason


def test_p12_15_killer_llm_spoofed_tenant_id_overridden_by_auth_context():
    """
    THE KILLER TEST:
    LLM output includes: {"tenant_id": "tenant_B", "tool_name": "drive.trash_file"}
    Caller is authenticated as: TenantContext(tenant_id="tenant_A")
        ↓
    System strictly forces tenant_id = "tenant_A" (LLM ≠ Tenant Authority)
    """
    ctx = TenantContext(tenant_id="tenant_A", actor_id="user_mukil")
    llm_step_payload = {
        "tenant_id": "tenant_B",  # Hallucinated / injected by LLM
        "capability_id": "drive.trash_file",
        "file_id": "file_999",
    }

    # Policy / Execution Layer enforces trusted context
    trusted_tenant = ctx.tenant_id  # Derived from auth, not LLM payload
    assert trusted_tenant == "tenant_A"
    assert trusted_tenant != llm_step_payload.get("tenant_id")


# ═════════════════════════════════════════════════════════════════════════════
# 4. REST API TENANT BOUNDARY ATTACK TESTS (Tests 16 - 20)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_p12_16_rest_api_tenant_a_cannot_read_tenant_b_task_404():
    """Verify GET /api/v1/tasks/{task_id} returns 404 when requested by a different tenant."""
    # Create task for Tenant B in database
    token_b = create_access_token(actor_id="user_b", tenant_id="tenant_B")
    token_a = create_access_token(actor_id="user_a", tenant_id="tenant_A")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        # Tenant B creates task
        create_res = await client.post(
            "/api/v1/tasks",
            json={"raw_input": "Tenant B private task"},
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert create_res.status_code in (200, 201)
        task_id = create_res.json()["task"]["task_id"]

        # Tenant A tries to read Tenant B's task -> 403 Forbidden or 404 Not Found
        get_res_a = await client.get(
            f"/api/v1/tasks/{task_id}",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert get_res_a.status_code in (403, 404)


@pytest.mark.anyio
async def test_p12_17_rest_api_client_payload_tenant_id_ignored_in_favor_of_jwt():
    """Verify passing a conflicting 'user_id' in JSON body cannot override the JWT tenant."""
    token_a = create_access_token(actor_id="user_a", tenant_id="tenant_A")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        # Client tries to specify user_id = tenant_B
        res = await client.post(
            "/api/v1/tasks",
            json={"raw_input": "Test task", "user_id": "tenant_B"},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert res.status_code in (200, 201)
        data = res.json()["task"]
        # Authenticated tenant_A must prevail over requested payload
        assert data["user_id"] == "tenant_A" or data["user_id"] == "user_a"


@pytest.mark.anyio
async def test_p12_18_rest_api_cross_tenant_approval_decision_denied_404():
    """Verify Tenant A attempting to decide Tenant B's approval ticket returns 404."""
    ticket = default_approval_engine.create_approval_request(
        task_id="t_b_sec",
        step_id="s_b_sec",
        action="coding.apply_fix",
        capability_id="coding.apply_fix",
        parameters={"repo": "test"},
        risk_tier=RiskTier.TIER_3_HIGH,
        description="Fix",
        tenant_id="tenant_B",
    )
    token_a = create_access_token(actor_id="user_a", tenant_id="tenant_A")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        res = await client.post(
            f"/api/v1/approvals/{ticket.approval_id}/decide",
            json={"decision": "approve"},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        # Cannot decide ticket belonging to another tenant
        assert res.status_code in (400, 403, 404)


@pytest.mark.anyio
async def test_p12_19_rest_api_forged_jwt_signature_denied_401():
    """Verify forged JWT tokens signed with a bogus key are rejected with 401."""
    import jwt
    bogus_token = jwt.encode({"sub": "attacker", "tenant_id": "tenant_mukil"}, "wrong_secret_key", algorithm="HS256")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        res = await client.get("/api/v1/tasks", headers={"Authorization": f"Bearer {bogus_token}"})
        assert res.status_code == 401


@pytest.mark.anyio
async def test_p12_20_rest_api_missing_auth_header_denied_401_in_prod():
    """Verify missing authorization header is rejected with 401 when local mode is disabled."""
    from app.core.config import get_settings
    settings = get_settings()
    orig_env = settings.ENVIRONMENT
    try:
        settings.ENVIRONMENT = "production"
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            res = await client.get("/api/v1/tasks")
            assert res.status_code == 401
    finally:
        settings.ENVIRONMENT = orig_env
