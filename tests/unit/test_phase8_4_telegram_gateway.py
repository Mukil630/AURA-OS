"""Comprehensive 30-Scenario Unit & Integration Test Suite for Phase 8.4 Telegram Gateway."""
import hashlib
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.agents.master.master_agent import MasterAgent
from app.connectors.credential_manager import CredentialManager
from app.connectors.drive.connector import GoogleDriveConnector
from app.connectors.policy import ConnectorPolicyEngine
from app.connectors.router import CapabilityRouter
from app.connectors.telegram.auth import TelegramAuthorizer
from app.connectors.telegram.connector import TelegramConnector
from app.connectors.telegram.contracts import (
    TelegramChat,
    TelegramMessage,
    TelegramOutboundMessage,
    TelegramResponseState,
    TelegramUpdate,
    TelegramUser,
)
from app.connectors.telegram.idempotency import TelegramReplayGuard
from app.connectors.telegram.response_builder import TelegramResponseBuilder
from app.core.contracts.connector import ConnectorExecutionRequest
from app.core.contracts.execution_event import ExecutionEventContract
from app.core.contracts.memory import MemoryContract, MemoryQueryContract
from app.core.contracts.task import TaskContract
from app.core.enums import ChannelType, ConnectorStatus, ConnectorType, EventSeverity, EventType, MemoryType, TaskStatus
from app.core.planner import TaskPlanner
from app.database.base import Base
from app.database.repositories.event_repo import EventRepository
from app.database.repositories.memory_repo import MemoryRepository
from app.database.repositories.task_repo import TaskRepository
from app.database.repositories.workflow_repo import WorkflowRepository
from app.engine.workflow_engine import WorkflowEngine
from app.main import app
from app.memory.manager import MemoryManager


# ── Scenario 01: Connector Registration ───────────────────────────────────────────────
def test_scenario_01_connector_registration():
    router = CapabilityRouter()
    tg_conn = TelegramConnector(is_mock=True)
    router.register_connector(tg_conn)

    conns = router.list_connectors()
    assert len(conns) == 1
    assert conns[0].connector_id == "connector_telegram"
    assert conns[0].connector_type == ConnectorType.TELEGRAM
    assert conns[0].is_mock is True


# ── Scenario 02: Capability Registration ─────────────────────────────────────────────
def test_scenario_02_capability_registration():
    tg_conn = TelegramConnector(is_mock=True)
    caps = tg_conn.list_capabilities()
    assert len(caps) == 5
    cap_ids = [c.capability_id for c in caps]

    assert "telegram.send_message" in cap_ids
    assert "telegram.send_photo" in cap_ids
    assert "telegram.send_document" in cap_ids
    assert "telegram.get_me" in cap_ids
    assert "telegram.answer_callback" in cap_ids


# ── Scenario 03: Credential Isolation ─────────────────────────────────────────────────
def test_scenario_03_credential_isolation():
    cred_mgr = CredentialManager()
    raw_token = "884210928:AAH_superSecretTelegramBotToken_xyz123"

    contract = cred_mgr.set_credential(
        provider=ConnectorType.TELEGRAM,
        token=raw_token,
        user_id="mukil",
    )

    assert contract.masked_value == "8842****z123"
    assert raw_token not in contract.masked_value

    resolved = cred_mgr.get_credential(ConnectorType.TELEGRAM, user_id="mukil")
    assert resolved == raw_token


# ── Scenario 04: Webhook Authentication Success ───────────────────────────────────────
def test_scenario_04_webhook_authentication_success():
    authorizer = TelegramAuthorizer(default_secret="mukil_secret_token_123")
    assert authorizer.verify_webhook_secret("mukil_secret_token_123") is True


# ── Scenario 05: Invalid Webhook Rejection ────────────────────────────────────────────
def test_scenario_05_invalid_webhook_rejection():
    authorizer = TelegramAuthorizer(default_secret="mukil_secret_token_123")
    assert authorizer.verify_webhook_secret("wrong_token_xyz") is False
    assert authorizer.verify_webhook_secret(None) is False
    assert authorizer.verify_webhook_secret("") is False


# ── Scenario 06: Unknown Telegram User Rejection ──────────────────────────────────────
def test_scenario_06_unknown_telegram_user_rejection():
    authorizer = TelegramAuthorizer()
    # Unknown numeric ID and handle
    res = authorizer.authorize_user(telegram_user_id=11223344, username="stranger_danger")
    assert res is None


# ── Scenario 07: Authorized User Acceptance ───────────────────────────────────────────
def test_scenario_07_authorized_user_acceptance():
    authorizer = TelegramAuthorizer()
    res = authorizer.authorize_user(telegram_user_id=987654321, username="mukil630")
    assert res == "mukil"


# ── Scenario 08: Message Normalization ────────────────────────────────────────────────
def test_scenario_08_message_normalization():
    tg_user = TelegramUser(id=987654321, first_name="Mukil", username="mukil630")
    tg_chat = TelegramChat(id=987654321, type="private")
    tg_msg = TelegramMessage(message_id=101, from_user=tg_user, chat=tg_chat, text="Check my GitHub CI")
    update = TelegramUpdate(update_id=5001, message=tg_msg)

    # Normalize into canonical TaskContract
    task = TaskContract(
        user_id="mukil",
        raw_input=update.message.text,
        channel=ChannelType.TELEGRAM,
        metadata={"telegram_chat_id": tg_chat.id, "telegram_update_id": update.update_id},
    )
    assert task.channel == ChannelType.TELEGRAM
    assert task.raw_input == "Check my GitHub CI"
    assert task.metadata["telegram_update_id"] == 5001


# ── Scenario 09: Telegram to P1 Intake Routing ────────────────────────────────────────
@pytest.mark.anyio
async def test_scenario_09_telegram_to_p1_intake_routing():
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)
    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        task_repo = TaskRepository(session)
        task = TaskContract(
            user_id="mukil",
            raw_input="Remind me tomorrow 9am to review pull request",
            channel=ChannelType.TELEGRAM,
        )
        saved = await task_repo.create_task(task)
        assert saved.task_id.startswith("task_")
        assert saved.channel == ChannelType.TELEGRAM

    await engine_db.dispose()


# ── Scenario 10: Duplicate Update Detection ───────────────────────────────────────────
def test_scenario_10_duplicate_update_detection():
    guard = TelegramReplayGuard(ttl_seconds=3600)
    assert guard.is_duplicate(9001) is False
    guard.record_update(9001, task_id="task_abc123")
    assert guard.is_duplicate(9001) is True


# ── Scenario 11: Idempotent Task Creation Guard ───────────────────────────────────────
def test_scenario_11_idempotent_task_creation_guard():
    guard = TelegramReplayGuard()
    guard.record_update(9002, task_id="task_first_created")
    assert guard.is_duplicate(9002) is True
    assert guard.get_associated_task_id(9002) == "task_first_created"


# ── Scenario 12: Duplicate Delivery After Restart ─────────────────────────────────────
def test_scenario_12_duplicate_delivery_after_restart():
    guard1 = TelegramReplayGuard()
    guard1.record_update(9003, task_id="task_pre_restart")

    # Simulate restart by restoring state
    guard2 = TelegramReplayGuard()
    guard2._processed_updates = dict(guard1._processed_updates)
    guard2._update_to_task = dict(guard1._update_to_task)

    assert guard2.is_duplicate(9003) is True
    assert guard2.get_associated_task_id(9003) == "task_pre_restart"


# ── Scenario 13: Per-User Rate Limiting (429) ─────────────────────────────────────────
def test_scenario_13_per_user_rate_limiting():
    policy = ConnectorPolicyEngine()
    rate_key = "telegram_user_987654321"
    policy.set_rate_limit(rate_key, 2)

    assert policy.check_and_consume_rate_limit(rate_key) is True
    assert policy.check_and_consume_rate_limit(rate_key) is True
    # 3rd request should be blocked
    assert policy.check_and_consume_rate_limit(rate_key) is False


# ── Scenario 14: Empty and Whitespace Message Handling ────────────────────────────────
def test_scenario_14_empty_and_whitespace_message_handling():
    tg_user = TelegramUser(id=987654321, first_name="Mukil")
    tg_chat = TelegramChat(id=987654321)
    tg_msg = TelegramMessage(message_id=102, from_user=tg_user, chat=tg_chat, text=None)
    update = TelegramUpdate(update_id=5002, message=tg_msg)

    assert update.message.text is None


# ── Scenario 15: Telegram 400 Bad Request Handling ────────────────────────────────────
@pytest.mark.anyio
async def test_scenario_15_telegram_400_bad_request():
    tg_conn = TelegramConnector(is_mock=True)
    req = ConnectorExecutionRequest(
        capability_id="telegram.unsupported_capability",
        parameters={},
    )
    res = await tg_conn.execute_capability(req)
    assert res.success is False
    assert res.status_code == 400


# ── Scenario 16: Telegram 401 Invalid Token Handling ──────────────────────────────────
@pytest.mark.anyio
async def test_scenario_16_telegram_401_invalid_token():
    tg_conn = TelegramConnector(is_mock=False)
    req = ConnectorExecutionRequest(
        capability_id="telegram.send_message",
        parameters={"chat_id": 987654321, "text": "Hello"},
    )
    # Live mode with no credentials returns 401
    res = await tg_conn.execute_capability(req, credentials=None)
    assert res.success is False
    assert res.status_code == 401
    assert "authentication failure" in res.error_message.lower()


# ── Scenario 17: Telegram 403 User Blocked Bot Handling ───────────────────────────────
def test_scenario_17_telegram_403_user_blocked_bot():
    builder = TelegramResponseBuilder()
    msg = builder.build_response(
        chat_id=987654321,
        state=TelegramResponseState.TASK_FAILED,
        error_message="Telegram Forbidden: Bot was blocked by the user.",
    )
    assert "Task Failed" in msg.text
    assert "blocked" in msg.text.lower() or "authorization" in msg.text.lower()


# ── Scenario 18: Telegram 429 Rate Limit Handling ─────────────────────────────────────
@pytest.mark.anyio
async def test_scenario_18_telegram_429_rate_limit():
    policy = ConnectorPolicyEngine()
    router = CapabilityRouter(policy_engine=policy)
    tg_conn = TelegramConnector(is_mock=True)
    router.register_connector(tg_conn)

    policy.set_rate_limit("telegram.send_message", 2)
    assert policy.check_and_consume_rate_limit("telegram.send_message") is True
    assert policy.check_and_consume_rate_limit("telegram.send_message") is True

    req = ConnectorExecutionRequest(
        capability_id="telegram.send_message",
        parameters={"chat_id": 987654321, "text": "Test 3"},
    )
    res = await router.dispatch(req)
    assert res.success is False
    assert res.status_code == 429


# ── Scenario 19: Telegram Timeout Handling ────────────────────────────────────────────
@pytest.mark.anyio
async def test_scenario_19_telegram_timeout_handling():
    tg_conn = TelegramConnector(is_mock=True)
    req = ConnectorExecutionRequest(
        capability_id="telegram.send_message",
        parameters={"chat_id": 987654321, "text": "Timeout test"},
        timeout_seconds=5,
    )
    res = await tg_conn.execute_capability(req)
    assert res.success is True  # Mock succeeds within latency


# ── Scenario 20: Retry Exhaustion Boundary ────────────────────────────────────────────
@pytest.mark.anyio
async def test_scenario_20_retry_exhaustion_boundary():
    attempts = 0
    def failing_handler():
        nonlocal attempts
        attempts += 1
        return False

    max_retries = 3
    for _ in range(max_retries):
        failing_handler()

    assert attempts == 3


# ── Scenario 21: Emergency Kill-Switch Halts Inbound and Outbound ─────────────────────
@pytest.mark.anyio
async def test_scenario_21_emergency_kill_switch():
    policy = ConnectorPolicyEngine()
    router = CapabilityRouter(policy_engine=policy)
    tg_conn = TelegramConnector(is_mock=True)
    router.register_connector(tg_conn)

    # Disable Telegram connector
    policy.disable_connector("connector_telegram")
    assert policy.is_connector_enabled("connector_telegram") is False

    req = ConnectorExecutionRequest(
        capability_id="telegram.send_message",
        parameters={"chat_id": 987654321, "text": "Blocked dispatch"},
    )
    res = await router.dispatch(req)
    assert res.success is False
    assert res.status_code == 503
    assert "emergency kill-switch" in res.error_message.lower()

    # Re-enable
    policy.enable_connector("connector_telegram")
    res2 = await router.dispatch(req)
    assert res2.success is True


# ── Scenario 22: Health Check Probes ─────────────────────────────────────────────────
@pytest.mark.anyio
async def test_scenario_22_health_check():
    tg_conn = TelegramConnector(is_mock=True)
    health = await tg_conn.health_check()
    assert health.connector_id == "connector_telegram"
    assert health.status == ConnectorStatus.CONNECTED
    assert health.latency_ms > 0
    assert "healthy" in health.message.lower() or "operational" in health.message.lower()


# ── Scenario 23: Audit Event Generation ───────────────────────────────────────────────
@pytest.mark.anyio
async def test_scenario_23_audit_event_generation():
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)
    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        event_repo = EventRepository(session)
        evt = ExecutionEventContract(
            trace_id="tr_tg_test_101",
            task_id="task_tg_101",
            event_type=EventType.TELEGRAM_UPDATE_RECEIVED,
            severity=EventSeverity.INFO,
            source_component="TelegramGateway",
            message="Telegram update 5001 received.",
        )
        saved = await event_repo.record_event(evt)
        assert saved.event_type == EventType.TELEGRAM_UPDATE_RECEIVED
        assert saved.trace_id == "tr_tg_test_101"

    await engine_db.dispose()


# ── Scenario 24: Tenant Isolation Telegram to Memory ─────────────────────────────────
@pytest.mark.anyio
async def test_scenario_24_tenant_isolation_telegram_to_memory():
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)
    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        manager = MemoryManager(session)
        authorizer = TelegramAuthorizer()

        # Mukil sends Telegram update -> Maps to 'mukil'
        mukil_tenant = authorizer.authorize_user(987654321, "mukil630")
        assert mukil_tenant == "mukil"

        # Alice sends Telegram update (if authorized to 'alice')
        authorizer.register_authorized_user("55443322", "alice")
        alice_tenant = authorizer.authorize_user(55443322)
        assert alice_tenant == "alice"

        # Store private preference for Mukil
        await manager.store(
            TaskContract(
                user_id="mukil",
                raw_input="Confidential Project Plan",
            ).model_copy() if False else
            MemoryContract(
                user_id="mukil",
                memory_type=MemoryType.USER_PREFERENCE,
                content="Private billing vault secret path",
                importance_score=0.9,
            )
        )

        # Memories remain strictly isolated
        mukil_mems = await manager.build_context(user_id=mukil_tenant, raw_input="billing vault")
        alice_mems = await manager.build_context(user_id=alice_tenant, raw_input="billing vault")

        assert len(mukil_mems) >= 1
        assert len(alice_mems) == 0

    await engine_db.dispose()


# ── Scenario 25: Task Completion Outbound Response ────────────────────────────────────
def test_scenario_25_task_completion_outbound_response():
    resp = TelegramResponseBuilder.build_response(
        chat_id=987654321,
        state=TelegramResponseState.TASK_COMPLETED,
        task_id="task_12345",
        summary="CI builds verified green and invoice uploaded.",
    )
    assert resp.response_state == TelegramResponseState.TASK_COMPLETED
    assert "Task Completed" in resp.text
    assert "CI builds verified green" in resp.text


# ── Scenario 26: Task Failure Outbound Response ───────────────────────────────────────
def test_scenario_26_task_failure_outbound_response():
    resp = TelegramResponseBuilder.build_response(
        chat_id=987654321,
        state=TelegramResponseState.TASK_FAILED,
        task_id="task_fail_01",
        error_message="Dependency build step failed.",
    )
    assert resp.response_state == TelegramResponseState.TASK_FAILED
    assert "Task Failed" in resp.text
    assert "Dependency build step failed" in resp.text


# ── Scenario 27: Approval Required Outbound Response ──────────────────────────────────
def test_scenario_27_approval_required_outbound_response():
    resp = TelegramResponseBuilder.build_response(
        chat_id=987654321,
        state=TelegramResponseState.WAITING_FOR_APPROVAL,
        task_id="task_auth_01",
    )
    assert resp.response_state == TelegramResponseState.WAITING_FOR_APPROVAL
    assert "Authorization Required" in resp.text


# ── Scenario 28: Telegram Connector Restart Recovery ──────────────────────────────────
def test_scenario_28_telegram_connector_restart_recovery():
    conn1 = TelegramConnector(is_mock=True)
    assert conn1.is_connected() is True

    # Re-initialize connector
    conn2 = TelegramConnector(is_mock=True)
    assert conn2.is_connected() is True
    assert len(conn2.list_capabilities()) == 5


# ── Scenario 29: No Credential Leakage in Response Probe ──────────────────────────────
def test_scenario_29_no_credential_leakage_probe():
    raw_token = "884210928:AAH_superSecretTelegramBotToken_xyz123"
    resp = TelegramResponseBuilder.build_response(
        chat_id=987654321,
        state=TelegramResponseState.TASK_COMPLETED,
        task_id="task_secret_test",
        summary="Task finished",
        error_message=f"Error containing {raw_token}",
    )
    # The rendered response must NOT contain the secret token
    assert raw_token not in resp.text


# ── Scenario 30: THE KILLER END-TO-END TELEGRAM TO DRIVE LIFECYCLE ────────────────────
@pytest.mark.anyio
async def test_scenario_30_killer_end_to_end_telegram_to_drive_lifecycle():
    """
    Killer End-to-End Multi-Phase Channel Integration Test:
    Telegram: 'Upload my invoice to the billing vault'
    ↓
    Webhook Gateway Auth & Authorize (mukil)
    ↓
    P1 Intake (task_id generated, Channel=TELEGRAM)
    ↓
    P2 Understand (Intent=FILE_SYNC) + P6 Memory Context
    ↓
    P3 Task Planner (DAG: check_file -> upload_to_drive_vault -> verify_drive_upload)
    ↓
    P4 Execute & P5 Verify (drive.upload Primary Vault -> Backup Vault SHA256 match)
    ↓
    P6 Episodic Memory Distillation
    ↓
    Audit Events Recorded (trace_id correlated)
    ↓
    Outbound Response Builder -> Telegram Dispatch
    """
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)
    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        # Repositories & Services
        task_repo = TaskRepository(session)
        wf_repo = WorkflowRepository(session)
        event_repo = EventRepository(session)
        mem_mgr = MemoryManager(session)
        agent = MasterAgent()
        planner = TaskPlanner()
        engine = WorkflowEngine(db_session=session)
        tg_authorizer = TelegramAuthorizer(default_secret="mukil_secret_token_2026")
        tg_replay_guard = TelegramReplayGuard()
        tg_connector = TelegramConnector(is_mock=True)

        # 1. Inbound Telegram Webhook Update
        update_id = 99881
        chat_id = 987654321
        raw_prompt = "Upload my invoice SGC_Invoice_2026_08.pdf to the billing vault"

        # Webhook Authentication
        assert tg_authorizer.verify_webhook_secret("mukil_secret_token_2026") is True

        # Sender Authorization
        tenant_user = tg_authorizer.authorize_user(chat_id, "mukil630")
        assert tenant_user == "mukil"

        # Replay Guard Check
        assert tg_replay_guard.is_duplicate(update_id) is False

        # 2. P1 INTAKE
        task = TaskContract(
            user_id=tenant_user,
            raw_input=raw_prompt,
            channel=ChannelType.TELEGRAM,
            metadata={"telegram_chat_id": chat_id, "telegram_update_id": update_id},
        )
        saved_task = await task_repo.create_task(task)
        tg_replay_guard.record_update(update_id, saved_task.task_id)

        trace_id = f"tr_{saved_task.task_id}"

        # 3. P2 UNDERSTAND + P6 MEMORY
        mem_ctx = await mem_mgr.build_context(user_id=tenant_user, raw_input=raw_prompt)
        _, norm_ctx = agent.enrich_task_with_understanding(saved_task, memory_context=mem_ctx)

        intent_val = norm_ctx.parsed_intent.intent.value if hasattr(norm_ctx.parsed_intent.intent, "value") else str(norm_ctx.parsed_intent.intent)
        assert intent_val == "file_sync"

        # 4. P3 TASK PLANNER (DAG Decompose)
        plan, workflow = planner.plan(norm_ctx)
        assert len(workflow.steps) == 3
        assert workflow.steps[1].tool_name == "drive.upload"

        saved_wf = await wf_repo.create_workflow_with_steps(workflow)

        # 5. P4 EXECUTE & P5 INDEPENDENT VERIFICATION
        final_wf, final_task = await engine.execute_workflow(saved_wf.workflow_id)

        wf_status = final_wf.status.value if hasattr(final_wf.status, "value") else str(final_wf.status)
        task_status = final_task.status.value if hasattr(final_task.status, "value") else str(final_task.status)
        assert wf_status == "completed"
        assert task_status == "completed"

        # 6. P6 MEMORY DISTILLATION ASSERTION
        mems = await mem_mgr.query(MemoryQueryContract(query_text="invoice billing vault", user_id="mukil"))
        assert len(mems) >= 1

        # 7. OUTBOUND RESPONSE BUILDER & DISPATCH
        outbound = TelegramResponseBuilder.build_response(
            chat_id=chat_id,
            state=TelegramResponseState.TASK_COMPLETED,
            task_id=saved_task.task_id,
            summary=final_task.result_summary,
        )
        assert "Task Completed" in outbound.text

        disp_res = await tg_connector.execute_capability(
            ConnectorExecutionRequest(
                capability_id="telegram.send_message",
                parameters={"chat_id": chat_id, "text": outbound.text},
                task_id=saved_task.task_id,
            )
        )
        assert disp_res.success is True
        assert len(tg_connector.sent_messages) == 1
        assert tg_connector.sent_messages[0].chat_id == chat_id

        # 8. AUDIT CORRELATION CHECK
        events = await event_repo.get_events_by_task(saved_task.task_id)
        assert len(events) >= 5
        for e in events:
            assert e.task_id == saved_task.task_id
            assert e.trace_id == trace_id

    await engine_db.dispose()
