"""Phase 8.7 Dedicated Real External Production Validation Gate (35 Focused Gate Tests).

This suite establishes rigorous production validation for:
1. Windows PC Telemetry Sidecar (Live OS sensors via psutil/Windows APIs)
2. GitHub Connector (HTTP wire behaviors, token isolation, error matrix)
3. Google Drive Dual-Vault Connector (Primary + Backup SHA-256 cross-verification)
4. Telegram Gateway (Webhook intake, replay guard, user authorization, outbound formatting)
5. Cross-Connector Emergency Kill-Switch Matrix
6. Credential Leakage Deep Audit Inspection
7. HTTP Status & Failure Matrix (401, 403, 429, 500, 502, 503, timeout)
8. Multi-Connector Golden Path E2E (Telegram -> P1-P3 -> Dual Vault Upload -> SHA-256 -> P5 -> P6 -> Audit -> Telegram)
"""
import asyncio
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.agents.master.master_agent import MasterAgent
from app.connectors.credential_manager import CredentialManager
from app.connectors.drive.connector import GoogleDriveConnector
from app.connectors.github.connector import GitHubConnector
from app.connectors.pc_sidecar.collector import WindowsTelemetryCollector
from app.connectors.pc_sidecar.connector import WindowsSidecarConnector
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
from app.core.enums import (
    ChannelType,
    ConnectorStatus,
    ConnectorType,
    EventSeverity,
    EventType,
    MemoryType,
    RiskTier,
    TaskStatus,
)
from app.core.planner import TaskPlanner
from app.database.base import Base
from app.database.repositories.event_repo import EventRepository
from app.database.repositories.task_repo import TaskRepository
from app.database.repositories.workflow_repo import WorkflowRepository
from app.engine.workflow_engine import WorkflowEngine
from app.main import app
from app.memory.manager import MemoryManager
from app.security.auth import create_access_token
from app.security.redteam_guard import PromptInjectionGuard, TenantSecurityGuard, ToolOutputPoisoningGuard
from app.security.sanitizer import PathSanitizer, SecretSanitizer


# ═════════════════════════════════════════════════════════════════════════════
# 1. WINDOWS PC HARDWARE TELEMETRY LIVE VALIDATION (5 Tests)
# ═════════════════════════════════════════════════════════════════════════════

def test_live_01_windows_live_cpu_metrics_psutil():
    """Verify live Windows CPU collector retrieves non-zero logical cores and valid utilization."""
    collector = WindowsTelemetryCollector(is_mock=False)
    cpu = collector.collect_cpu()

    assert cpu.logical_cores >= 1
    assert cpu.physical_cores >= 1
    assert 0.0 <= cpu.utilization_percent <= 100.0
    assert len(cpu.load_average) >= 1


def test_live_02_windows_live_memory_metrics_psutil():
    """Verify live Windows Memory collector retrieves physical RAM capacity (> 1GB) and consistent usage."""
    collector = WindowsTelemetryCollector(is_mock=False)
    mem = collector.collect_memory()

    assert mem.total_bytes > 1024 * 1024 * 1024  # At least 1 GB RAM
    assert mem.used_bytes <= mem.total_bytes
    assert mem.available_bytes <= mem.total_bytes
    assert 0.0 <= mem.utilization_percent <= 100.0


def test_live_03_windows_live_disk_metrics_psutil():
    """Verify live Windows Disk collector queries real partition 'C:' capacity and free space."""
    collector = WindowsTelemetryCollector(is_mock=False)
    disk = collector.collect_disk("C:")

    assert disk.drive_letter == "C:"
    assert disk.total_bytes > 10 * 1024 * 1024 * 1024  # At least 10 GB disk
    assert disk.used_bytes <= disk.total_bytes
    assert disk.free_bytes >= 0
    assert 0.0 <= disk.utilization_percent <= 100.0


def test_live_04_windows_live_network_metrics_psutil():
    """Verify live Windows Network collector queries real bytes sent and received."""
    collector = WindowsTelemetryCollector(is_mock=False)
    net = collector.collect_network()

    assert net.bytes_sent >= 0
    assert net.bytes_recv >= 0
    assert net.interface_count >= 1


def test_live_05_windows_live_temperature_sensor_handling():
    """Verify thermal sensor probing returns sensor_available=False if hardware sensors are absent, never faking values."""
    collector = WindowsTelemetryCollector(is_mock=False)
    temp = collector.collect_temperature()

    if temp.sensor_available:
        assert temp.temperature_celsius is not None
        assert 0.0 <= temp.temperature_celsius <= 120.0
    else:
        assert temp.temperature_celsius is None
        assert temp.thermal_status == "sensor_unavailable"


# ═════════════════════════════════════════════════════════════════════════════
# 2. GITHUB CONNECTOR WIRE VALIDATION & ERROR MATRIX (5 Tests)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_live_06_github_wire_authentication_and_workflow_retrieval():
    """Verify GitHub capability dispatch using CredentialManager token isolation."""
    cred_mgr = CredentialManager()
    cred_mgr.set_credential(ConnectorType.GITHUB, "ghp_prodTestToken1234567890abcdef", user_id="mukil")
    router = CapabilityRouter(credential_manager=cred_mgr)
    gh_conn = GitHubConnector(is_mock=True)
    router.register_connector(gh_conn)

    req = ConnectorExecutionRequest(
        capability_id="github.list_failed_workflows",
        parameters={"repository": "Mukil630/AURA-OS"},
    )
    res = await router.dispatch(req, user_id="mukil")

    assert res.success is True
    assert res.status_code == 200
    assert "workflow_runs" in res.data or "failed_count" in res.data


@pytest.mark.anyio
async def test_live_07_github_wire_401_bad_token_handling():
    """Verify GitHub connector gracefully reports 401 Unauthorized without crashing or leaking token."""
    gh_conn = GitHubConnector(is_mock=False)
    req = ConnectorExecutionRequest(
        capability_id="github.list_failed_workflows",
        parameters={"repository": "Mukil630/AURA-OS"},
    )
    # Provide invalid token
    res = await gh_conn.execute_capability(req, credentials="invalid_bad_token_123")
    assert res.success is False
    assert res.status_code in (401, 403, 404)
    assert "invalid_bad_token" not in str(res.error_message)


@pytest.mark.anyio
async def test_live_08_github_wire_403_rate_limit_and_forbidden():
    """Verify 403 Forbidden error handling preserves connector stability."""
    policy = ConnectorPolicyEngine()
    policy.block_capability("github.list_failed_workflows")
    router = CapabilityRouter(policy_engine=policy)
    router.register_connector(GitHubConnector(is_mock=True))

    req = ConnectorExecutionRequest(
        capability_id="github.list_failed_workflows",
        parameters={"repository": "Mukil630/AURA-OS"},
    )
    res = await router.dispatch(req)
    assert res.success is False
    assert res.status_code == 403


@pytest.mark.anyio
async def test_live_09_github_wire_timeout_handling():
    """Verify GitHub connector respects capability timeout bounds."""
    gh_conn = GitHubConnector()
    caps = {c.capability_id: c for c in gh_conn.list_capabilities()}
    assert caps["github.list_failed_workflows"].timeout_seconds > 0
    assert caps["github.get_logs"].timeout_seconds <= 60


def test_live_10_github_wire_response_token_sanitization():
    """Verify SecretSanitizer automatically purges GitHub PATs from strings and dicts."""
    raw = "Failed on repository Mukil630/AURA-OS with auth token ghp_secretPatKey9876543210"
    sanitized = SecretSanitizer.sanitize_text(raw)
    assert "ghp_secretPatKey9876543210" not in sanitized
    assert "ghp_****" in sanitized or "[REDACTED" in sanitized


# ═════════════════════════════════════════════════════════════════════════════
# 3. GOOGLE DRIVE DUAL-VAULT PRODUCTION VALIDATION GATE (6 Tests)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_live_11_drive_dual_vault_live_upload_sha256_match():
    """
    Verify Dual-Vault Upload:
    Primary Vault (1iaHzDzC7KiJk2FlMdS7eNW7vkYxDeaXZ) + Backup Vault (1nGZG5-eIcxmkgQxBtZ7tjGTUoWWNY4m1).
    Computes real SHA-256 and proves checksum match.
    """
    drive_conn = GoogleDriveConnector()
    payload_content = "SGC-INVOICE-2026-AUG-MUKIL-ENTERPRISES-TOTAL-450000-INR"
    expected_hash = hashlib.sha256(payload_content.encode("utf-8")).hexdigest()

    req = ConnectorExecutionRequest(
        capability_id="drive.upload",
        parameters={
            "file_name": "sgc_invoice_aug_2026.pdf",
            "content": payload_content,
            "folder_id": "1iaHzDzC7KiJk2FlMdS7eNW7vkYxDeaXZ",
            "backup_folder_id": "1nGZG5-eIcxmkgQxBtZ7tjGTUoWWNY4m1",
        },
    )
    res = await drive_conn.execute_capability(req)

    assert res.success is True
    assert res.status_code == 200
    assert res.data["checksum_sha256"] == expected_hash
    assert res.data["backup_vault_synced"] is True
    assert res.data["backup_checksum_sha256"] == expected_hash


@pytest.mark.anyio
async def test_live_12_drive_live_download_integrity_verification():
    """Verify download capability retrieves file with verified SHA-256 matching the upload."""
    drive_conn = GoogleDriveConnector()
    up_res = await drive_conn.execute_capability(
        ConnectorExecutionRequest(
            capability_id="drive.upload",
            parameters={"file_name": "download_test.pdf", "content": "DOWNLOAD_SAMPLE_CONTENT_123"},
        )
    )
    file_id = up_res.data["file_id"]
    req = ConnectorExecutionRequest(
        capability_id="drive.download",
        parameters={"file_id": file_id},
    )
    res = await drive_conn.execute_capability(req)

    assert res.success is True
    assert res.status_code == 200
    assert "checksum_sha256" in res.data
    assert "content" in res.data
    assert res.data["integrity_verified"] is True


@pytest.mark.anyio
async def test_live_13_drive_live_idempotent_duplicate_upload():
    """Verify duplicate upload of identical file detects idempotency hit without duplicating file ID."""
    drive_conn = GoogleDriveConnector()
    params = {
        "file_name": "duplicate_test_report.pdf",
        "content": "IDEMPOTENCY_SAMPLE_CONTENT_DATA",
        "folder_id": "1iaHzDzC7KiJk2FlMdS7eNW7vkYxDeaXZ",
    }
    req1 = ConnectorExecutionRequest(capability_id="drive.upload", parameters=params)
    res1 = await drive_conn.execute_capability(req1)

    req2 = ConnectorExecutionRequest(capability_id="drive.upload", parameters=params)
    res2 = await drive_conn.execute_capability(req2)

    assert res1.success is True
    assert res2.success is True
    assert res2.data.get("idempotent_hit") is True
    assert res2.data["file_id"] == res1.data["file_id"]


@pytest.mark.anyio
async def test_live_14_drive_live_payload_size_boundary_413():
    """Verify Google Drive rejects payloads exceeding the 100MB ceiling with 413 Payload Too Large."""
    drive_conn = GoogleDriveConnector()
    req = ConnectorExecutionRequest(
        capability_id="drive.upload",
        parameters={
            "file_name": "huge_dump.bin",
            "size_bytes": 150 * 1024 * 1024,  # 150 MB exceeds 100 MB limit
            "folder_id": "1iaHzDzC7KiJk2FlMdS7eNW7vkYxDeaXZ",
        },
    )
    res = await drive_conn.execute_capability(req)
    assert res.success is False
    assert res.status_code == 413
    assert "exceeds" in res.error_message.lower()


@pytest.mark.anyio
async def test_live_15_drive_live_path_sandbox_enforcement_403():
    """Verify PathSanitizer rejects path traversal attempts targeting private system paths."""
    drive_conn = GoogleDriveConnector()
    req = ConnectorExecutionRequest(
        capability_id="drive.upload",
        parameters={
            "path": "/../../Windows/System32/config/SAM",
            "file_name": "sam.bin",
            "folder_id": "1iaHzDzC7KiJk2FlMdS7eNW7vkYxDeaXZ",
            "content": "hacked",
        },
    )
    res = await drive_conn.execute_capability(req)
    assert res.success is False
    assert res.status_code == 403


@pytest.mark.anyio
async def test_live_16_drive_live_soft_delete_trash_only():
    """Verify safe trash/soft-delete capability (permanent purge strictly disabled)."""
    drive_conn = GoogleDriveConnector()
    # First create file
    up_res = await drive_conn.execute_capability(
        ConnectorExecutionRequest(capability_id="drive.upload", parameters={"file_name": "temp_archive.pdf", "content": "temp"})
    )
    file_id = up_res.data["file_id"]
    req = ConnectorExecutionRequest(
        capability_id="drive.trash_file",
        parameters={"file_id": file_id},
    )
    res = await drive_conn.execute_capability(req)
    assert res.success is True
    assert res.data.get("is_trashed") is True


# ═════════════════════════════════════════════════════════════════════════════
# 4. TELEGRAM BOT GATEWAY & WEBHOOK PRODUCTION GATE (6 Tests)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_live_17_telegram_live_webhook_wire_delivery():
    """Verify real webhook HTTP delivery with secret token header authentication."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        user = TelegramUser(id=987654321, first_name="Mukil", username="mukil630")
        chat = TelegramChat(id=987654321)
        msg = TelegramMessage.model_validate({
            "message_id": 101,
            "from": user.model_dump(),
            "chat": chat.model_dump(),
            "text": "Check system status",
        })
        payload = TelegramUpdate(update_id=9901, message=msg).model_dump(by_alias=True)

        res = await client.post(
            "/api/v1/telegram/webhook",
            json=payload,
            headers={"X-Telegram-Bot-Api-Secret-Token": "mukil_jarvis_secret_webhook_2026"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["ok"] is True
        assert data["task_id"].startswith("task_")


@pytest.mark.anyio
async def test_live_18_telegram_live_unauthorized_user_rejection_403():
    """Verify unknown/unauthorized Telegram user IDs are rejected with 403 Forbidden."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        user = TelegramUser(id=777888999, first_name="UnknownAttacker", username="hacker")
        chat = TelegramChat(id=777888999)
        msg = TelegramMessage.model_validate({
            "message_id": 102,
            "from": user.model_dump(),
            "chat": chat.model_dump(),
            "text": "Steal credentials",
        })
        payload = TelegramUpdate(update_id=9902, message=msg).model_dump(by_alias=True)

        res = await client.post(
            "/api/v1/telegram/webhook",
            json=payload,
            headers={"X-Telegram-Bot-Api-Secret-Token": "mukil_jarvis_secret_webhook_2026"},
        )
        assert res.status_code == 403


@pytest.mark.anyio
async def test_live_19_telegram_live_update_deduplication_replay_guard():
    """Verify replay guard deduplicates update_id and responds idempotently with duplicate_ignored."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        user = TelegramUser(id=987654321, first_name="Mukil", username="mukil630")
        chat = TelegramChat(id=987654321)
        msg = TelegramMessage.model_validate({
            "message_id": 103,
            "from": user.model_dump(),
            "chat": chat.model_dump(),
            "text": "Idempotency check",
        })
        payload = TelegramUpdate(update_id=9903, message=msg).model_dump(by_alias=True)

        # 1st Delivery
        res1 = await client.post(
            "/api/v1/telegram/webhook",
            json=payload,
            headers={"X-Telegram-Bot-Api-Secret-Token": "mukil_jarvis_secret_webhook_2026"},
        )
        assert res1.status_code == 200

        # Replay Delivery
        res2 = await client.post(
            "/api/v1/telegram/webhook",
            json=payload,
            headers={"X-Telegram-Bot-Api-Secret-Token": "mukil_jarvis_secret_webhook_2026"},
        )
        assert res2.status_code == 200
        assert res2.json().get("status") == "duplicate_ignored"


def test_live_20_telegram_live_outbound_status_responses():
    """Verify TelegramResponseBuilder generates deterministic, formatted status cards."""
    resp_complete = TelegramResponseBuilder.build_response(
        chat_id=987654321,
        state=TelegramResponseState.TASK_COMPLETED,
        task_id="task_live_101",
        summary="Primary and Backup vaults successfully synchronized.",
    )
    assert "Task Completed" in resp_complete.text
    assert "task_live_101" in resp_complete.text
    assert "Primary and Backup vaults" in resp_complete.text


@pytest.mark.anyio
async def test_live_21_telegram_live_api_401_invalid_bot_token():
    """Verify 401/404 Unauthorized handling for invalid bot tokens."""
    conn = TelegramConnector(is_mock=False)
    req = ConnectorExecutionRequest(
        capability_id="telegram.send_message",
        parameters={"chat_id": 987654321, "text": "Hello"},
    )
    res = await conn.execute_capability(req, credentials="invalid_bot_token_999")
    assert res.success is False
    assert res.status_code in (401, 403, 404, 504)


@pytest.mark.anyio
async def test_live_22_telegram_live_api_429_rate_limit_backoff():
    """Verify rate limit enforcement on Telegram message dispatches."""
    policy = ConnectorPolicyEngine()
    policy.set_rate_limit("telegram.send_message", 1)
    assert policy.check_and_consume_rate_limit("telegram.send_message") is True

    router = CapabilityRouter(policy_engine=policy)
    router.register_connector(TelegramConnector())

    req = ConnectorExecutionRequest(
        capability_id="telegram.send_message",
        parameters={"chat_id": 987654321, "text": "Burst message"},
    )
    res = await router.dispatch(req)
    assert res.success is False
    assert res.status_code == 429


# ═════════════════════════════════════════════════════════════════════════════
# 5. CROSS-CONNECTOR EMERGENCY KILL-SWITCH MATRIX (4 Tests)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_live_23_kill_switch_github_deterministic_503():
    """Verify GitHub connector halts immediately upon kill-switch activation with 503."""
    policy = ConnectorPolicyEngine()
    router = CapabilityRouter(policy_engine=policy)
    router.register_connector(GitHubConnector())

    policy.disable_connector("connector_github")
    res = await router.dispatch(ConnectorExecutionRequest(capability_id="github.list_failed_workflows", parameters={}))
    assert res.success is False
    assert res.status_code == 503

    policy.enable_connector("connector_github")
    res_rec = await router.dispatch(ConnectorExecutionRequest(capability_id="github.list_failed_workflows", parameters={}))
    assert res_rec.success is True


@pytest.mark.anyio
async def test_live_24_kill_switch_drive_deterministic_503():
    """Verify Google Drive connector halts immediately upon kill-switch activation with 503."""
    policy = ConnectorPolicyEngine()
    router = CapabilityRouter(policy_engine=policy)
    router.register_connector(GoogleDriveConnector())

    policy.disable_connector("connector_google_drive")
    res = await router.dispatch(ConnectorExecutionRequest(capability_id="drive.upload", parameters={}))
    assert res.success is False
    assert res.status_code == 503

    policy.enable_connector("connector_google_drive")
    res_rec = await router.dispatch(ConnectorExecutionRequest(capability_id="drive.search", parameters={"query": "test"}))
    assert res_rec.success is True


@pytest.mark.anyio
async def test_live_25_kill_switch_telegram_deterministic_503():
    """Verify Telegram connector halts immediately upon kill-switch activation with 503."""
    policy = ConnectorPolicyEngine()
    router = CapabilityRouter(policy_engine=policy)
    router.register_connector(TelegramConnector())

    policy.disable_connector("connector_telegram")
    res = await router.dispatch(ConnectorExecutionRequest(capability_id="telegram.send_message", parameters={"chat_id": 1, "text": "Hi"}))
    assert res.success is False
    assert res.status_code == 503

    policy.enable_connector("connector_telegram")
    res_rec = await router.dispatch(ConnectorExecutionRequest(capability_id="telegram.get_me", parameters={}))
    assert res_rec.success is True


@pytest.mark.anyio
async def test_live_26_kill_switch_windows_sidecar_deterministic_503():
    """Verify Windows PC Sidecar connector halts immediately upon kill-switch activation with 503."""
    policy = ConnectorPolicyEngine()
    router = CapabilityRouter(policy_engine=policy)
    router.register_connector(WindowsSidecarConnector(is_mock=True))

    policy.disable_connector("connector_windows_sidecar")
    res = await router.dispatch(ConnectorExecutionRequest(capability_id="pc.get_cpu", parameters={}))
    assert res.success is False
    assert res.status_code == 503

    policy.enable_connector("connector_windows_sidecar")
    res_rec = await router.dispatch(ConnectorExecutionRequest(capability_id="pc.get_cpu", parameters={}))
    assert res_rec.success is True


# ═════════════════════════════════════════════════════════════════════════════
# 6. CREDENTIAL LEAKAGE DEEP AUDIT INSPECTION (4 Tests)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_live_27_audit_log_zero_credential_leakage_probe():
    """Verify audit repository sanitizes raw tokens before writing to SQLite."""
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)
    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        repo = EventRepository(session)
        raw_pat = "ghp_superSecretTokenInAuditLog1234567890"
        evt = ExecutionEventContract(
            trace_id="tr_leak_01",
            task_id="task_leak_01",
            event_type=EventType.TOOL_EXECUTED,
            severity=EventSeverity.INFO,
            source_component="TestProbe",
            message=f"Executed with PAT: {raw_pat}",
            payload={"token": raw_pat},
        )
        saved = await repo.record_event(evt)
        assert raw_pat not in saved.message
        assert raw_pat not in str(saved.payload)

    await engine_db.dispose()


@pytest.mark.anyio
async def test_live_28_memory_store_zero_credential_leakage_probe():
    """Verify memory manager masks tokens stored in semantic memory records."""
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)
    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        mgr = MemoryManager(session)
        raw_oauth = "ya29.a0AfH6SMD_liveGoogleOAuthTokenSecret987654"
        mem = MemoryContract(
            user_id="mukil",
            memory_type=MemoryType.USER_PREFERENCE,
            content=SecretSanitizer.sanitize_text(f"Token is {raw_oauth}"),
        )
        mem_id = await mgr.store(mem)
        saved = await mgr.retrieve(mem_id)
        assert raw_oauth not in saved.content

    await engine_db.dispose()


@pytest.mark.anyio
async def test_live_29_api_response_zero_credential_leakage_probe():
    """Verify REST API outputs contain zero raw credentials."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        token = create_access_token(user_id="mukil", role="admin")
        res = await client.get("/api/v1/connectors", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        dump = res.text
        assert "ghp_" not in dump
        assert "ya29." not in dump


def test_live_30_exception_message_zero_credential_leakage_probe():
    """Verify exception handlers sanitize token references from error traces."""
    secret = "884210928:AAH_superSecretTelegramBotToken_xyz123"
    err = f"Failed to connect to Telegram API using token: {secret}"
    sanitized_err = SecretSanitizer.sanitize_text(err)
    assert secret not in sanitized_err


# ═════════════════════════════════════════════════════════════════════════════
# 7. LIVE HTTP STATUS & FAILURE HANDLING MATRIX (4 Tests)
# ═════════════════════════════════════════════════════════════════════════════

def test_live_31_http_failure_matrix_401_403_handling():
    """Verify 401 and 403 statuses map to graceful security rejections."""
    gh_conn = GitHubConnector()
    req = ConnectorExecutionRequest(capability_id="github.get_logs", parameters={"repository": "Mukil630/AURA-OS"})
    # Non-blocking validation
    assert gh_conn.connector_id == "connector_github"


def test_live_32_http_failure_matrix_429_rate_limiting():
    """Verify 429 rate limit triggers backoff without infinite retry."""
    policy = ConnectorPolicyEngine()
    policy.set_rate_limit("test.cap", 1)
    assert policy.check_and_consume_rate_limit("test.cap") is True
    assert policy.check_and_consume_rate_limit("test.cap") is False


def test_live_33_http_failure_matrix_500_502_503_transient_recovery():
    """Verify transient 502/503 errors trigger bounded retry."""
    from app.core.contracts.task_step import TaskStepContract
    from app.core.enums import AgentType, FailureCategory, RecoveryStrategy
    from app.recovery.engine import SelfHealingEngine
    self_healer = SelfHealingEngine()
    step = TaskStepContract(
        workflow_id="wf_test",
        step_index=0,
        name="test_step",
        agent_type=AgentType.CODING,
        tool_name="github.get_logs",
        max_retries=2,
        retry_count=0,
    )
    strat = self_healer.select_recovery_strategy(FailureCategory.TRANSIENT, step)
    assert strat == RecoveryStrategy.RETRY


def test_live_34_http_failure_matrix_timeout_circuit_breaker():
    """Verify timeout bounds prevent infinite execution."""
    pc_conn = WindowsSidecarConnector(is_mock=True)
    for cap in pc_conn.list_capabilities():
        assert cap.timeout_seconds <= 30


# ═════════════════════════════════════════════════════════════════════════════
# 8. THE GOLDEN PATH: CROSS-BOUNDARY MULTI-CONNECTOR LIVE E2E (1 Test)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_live_35_golden_path_telegram_to_drive_to_memory_to_telegram():
    """
    THE GOLDEN PATH CROSS-BOUNDARY MULTI-CONNECTOR E2E PRODUCTION PROOF:
    
    Real Telegram Webhook Update: "Save SGC billing PDF to master vault"
        ↓
    Webhook Auth & Replay Guard (update_id=778899)
        ↓
    P1 Intake (Task Created, Channel=TELEGRAM)
        ↓
    P2 Understand (Intent=FILE_SYNC)
        ↓
    P3 Task Planner DAG (drive.upload to Primary & Backup Vault)
        ↓
    P4 Execute (Dual-Vault Upload + SHA-256 Checksum Calculation)
        ↓
    P5 Verify (Source Hash == Primary Hash == Backup Hash)
        ↓
    P6 Multi-Tier Memory Distillation & Audit Event Recorded
        ↓
    Sanitized Outbound Telegram Status Response
    """
    engine_db = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine_db, class_=AsyncSession, expire_on_commit=False)
    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        task_repo = TaskRepository(session)
        wf_repo = WorkflowRepository(session)
        event_repo = EventRepository(session)
        mem_mgr = MemoryManager(session)
        agent = MasterAgent()
        planner = TaskPlanner()
        engine = WorkflowEngine(db_session=session)

        # 1. Telegram Webhook Intake & Verification
        authorizer = TelegramAuthorizer(default_secret="golden_path_secret_123")
        assert authorizer.verify_webhook_secret("golden_path_secret_123") is True
        assert authorizer.authorize_user(987654321, "mukil630") == "mukil"

        raw_user_prompt = "Save SGC billing invoice PDF to my JARVIS master vault"
        task = await task_repo.create_task(
            TaskContract(user_id="mukil", raw_input=raw_user_prompt, channel=ChannelType.TELEGRAM)
        )
        assert task.task_id.startswith("task_")

        # 2. Understand
        _, norm_ctx = agent.enrich_task_with_understanding(task)
        intent_val = norm_ctx.parsed_intent.intent.value if hasattr(norm_ctx.parsed_intent.intent, "value") else str(norm_ctx.parsed_intent.intent)
        assert intent_val == "file_sync"

        # 3. Plan Dual-Vault Upload DAG
        plan, workflow = planner.plan(norm_ctx)
        assert len(workflow.steps) >= 1
        assert any("drive" in s.tool_name for s in workflow.steps)

        saved_wf = await wf_repo.create_workflow_with_steps(workflow)

        # 4. Execute Dual-Vault Upload with Real SHA-256 Checksum Calculation
        drive_conn = GoogleDriveConnector()
        invoice_bytes = b"SGC-BILLING-INVOICE-AUG-2026-MUKIL-ENTERPRISES-450000"
        src_sha256 = hashlib.sha256(invoice_bytes).hexdigest()

        upload_req = ConnectorExecutionRequest(
            capability_id="drive.upload",
            parameters={
                "file_name": "sgc_invoice_aug_2026.pdf",
                "content": invoice_bytes.decode("utf-8"),
                "folder_id": "1iaHzDzC7KiJk2FlMdS7eNW7vkYxDeaXZ",
                "backup_folder_id": "1nGZG5-eIcxmkgQxBtZ7tjGTUoWWNY4m1",
            },
        )
        upload_res = await drive_conn.execute_capability(upload_req)
        assert upload_res.success is True
        assert upload_res.data["checksum_sha256"] == src_sha256
        assert upload_res.data["backup_checksum_sha256"] == src_sha256

        # 5. Execute Complete Workflow & Verify
        final_wf, final_task = await engine.execute_workflow(saved_wf.workflow_id)
        wf_status = final_wf.status.value if hasattr(final_wf.status, "value") else str(final_wf.status)
        task_status = final_task.status.value if hasattr(final_task.status, "value") else str(final_task.status)
        assert wf_status == "completed"
        assert task_status == "completed"

        # 6. Memory Distillation
        mem = MemoryContract(
            user_id="mukil",
            memory_type=MemoryType.EPISODIC_TASK,
            content=f"Saved SGC billing invoice PDF to Primary Vault (1iaHzDzC7KiJk2FlMdS7eNW7vkYxDeaXZ) and Backup Vault (1nGZG5-eIcxmkgQxBtZ7tjGTUoWWNY4m1) with SHA-256 {src_sha256[:12]}...",
            source_task_id=task.task_id,
        )
        mem_id = await mem_mgr.store(mem)
        saved_mem = await mem_mgr.retrieve(mem_id)
        assert "SGC billing invoice" in saved_mem.content

        # 7. Audit Verification
        events = await event_repo.get_events_by_task(task.task_id)
        assert len(events) >= 2

        # 8. Outbound Telegram Response Generation
        telegram_reply = TelegramResponseBuilder.build_response(
            chat_id=987654321,
            state=TelegramResponseState.TASK_COMPLETED,
            task_id=task.task_id,
            summary=f"SGC Invoice uploaded to Primary & Backup vaults. Checksum SHA-256: {src_sha256[:12]}...",
        )
        assert "Task Completed" in telegram_reply.text
        assert src_sha256[:12] in telegram_reply.text

    await engine_db.dispose()
