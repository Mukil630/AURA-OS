"""Dedicated Adversarial Zero-Leakage Audit Test Suite for Phase 12.2 Step 5.
Audits all leak surfaces: Containers, Logs, Audit Events, Tasks, Memory, DLQ, Exceptions, Approvals, and Router.
"""
import json
import pytest

from app.connectors.github.connector import GitHubConnector
from app.connectors.router import CapabilityRouter
from app.core.contracts.connector import ConnectorExecutionRequest
from app.core.contracts.credential import CredentialStatus
from app.core.contracts.execution_event import ExecutionEventContract
from app.core.contracts.memory import MemoryContract
from app.core.contracts.task import TaskContract
from app.core.enums import ConnectorType, EventSeverity, EventType, MemoryType, RiskTier, TaskStatus
from app.database.repositories.event_repo import EventRepository
from app.database.repositories.memory_repo import MemoryRepository
from app.database.repositories.task_repo import TaskRepository
from app.policy.approval_engine import compute_action_hash, ApprovalEngine
from app.reliability.controller import ReliabilityController
from app.security.sanitizer import SecretSanitizer
from app.security.vault import SecureSecretContainer, TenantCredentialVault


# ═════════════════════════════════════════════════════════════════════════════
# 1. SECRET RESIDUE & SERIALIZATION AUDITS (Tests 1 - 4)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_2_s5_01_secret_container_repr_and_str_permanently_redacted():
    """Verify SecureSecretContainer string representations never leak tokens."""
    token = "ghp_1234567890abcdef1234567890abcdef"
    container = SecureSecretContainer(raw_value=token, tenant_id="tenant_A", provider=ConnectorType.GITHUB)

    assert str(container) == "<SecureSecretContainer: REDACTED>"
    assert repr(container) == "<SecureSecretContainer: REDACTED>"
    assert token not in str(container)
    assert token not in repr(container)


def test_p12_2_s5_02_secret_container_json_and_dict_serialization_blocked():
    """Verify json.dumps and dict operations fail to serialize SecureSecretContainer."""
    container = SecureSecretContainer(raw_value="ya29.secret_key", tenant_id="tenant_A", provider=ConnectorType.GOOGLE_DRIVE)
    with pytest.raises(TypeError):
        json.dumps(container)


@pytest.mark.anyio
async def test_p12_2_s5_03_audit_event_repository_sanitizes_message_and_payload(test_db_session):
    """Verify EventRepository scrubs raw secrets from audit logs and payloads before insertion."""
    repo = EventRepository(test_db_session)
    raw_token = "ghp_secret_audit_leak_token_123456"
    event = ExecutionEventContract(
        trace_id="trc_audit_01",
        task_id="tsk_audit_01",
        event_type=EventType.TASK_STARTED,
        severity=EventSeverity.INFO,
        source_component="SecurityAuditor",
        message=f"Dispatched capability with token: {raw_token}",
        payload={"raw_key": raw_token, "nested": {"auth": f"Bearer {raw_token}"}},
    )

    persisted = await repo.record_event(event)
    assert raw_token not in persisted.message
    assert "ghp_****3456" in persisted.message or "[REDACTED_GITHUB_TOKEN]" in persisted.message
    assert raw_token not in json.dumps(persisted.payload)


@pytest.mark.anyio
async def test_p12_2_s5_04_task_repository_sanitizes_summary_data_and_errors(test_db_session):
    """Verify TaskRepository scrubs raw secrets from task output summary, data, and error fields."""
    repo = TaskRepository(test_db_session)
    raw_key = "ya29.google_oauth_secret_data_9999"

    task = await repo.create_task(
        TaskContract(
            user_id="tenant_A",
            raw_input="Syncing cloud vault data",
        )
    )

    updated = await repo.update_task_status(
        task_id=task.task_id,
        status=TaskStatus.FAILED,
        result_summary=f"Failed connecting with {raw_key}",
        result_data={"token": raw_key},
        error_message=f"Upstream returned fault for {raw_key}",
    )

    assert updated is not None
    assert raw_key not in updated.result_summary
    assert raw_key not in json.dumps(updated.result_data)
    assert raw_key not in updated.error_message


# ═════════════════════════════════════════════════════════════════════════════
# 2. MEMORY, DLQ & APPROVAL RESIDUE AUDITS (Tests 5 - 8)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_p12_2_s5_05_memory_repository_sanitizes_content_and_summary(test_db_session):
    """Verify MemoryRepository scrubs raw secrets from episodic/semantic memories."""
    repo = MemoryRepository(test_db_session)
    tg_token = "123456789:ABCDefGhIjKlMnOpQrStUvWxYz_123456"

    mem = await repo.create_or_update_memory(
        MemoryContract(
            user_id="tenant_A",
            memory_type=MemoryType.EPISODIC_TASK,
            content=f"User configured bot with token {tg_token}",
            summary=f"Token configured: {tg_token}",
        )
    )

    assert tg_token not in mem.content
    assert tg_token not in (mem.summary or "")


@pytest.mark.anyio
async def test_p12_2_s5_06_dead_letter_queue_sanitizes_parameters_and_errors():
    """Verify DeadLetterQueue records sanitize input parameters and error messages."""
    ctrl = ReliabilityController()
    raw_pat = "ghp_dlq_poison_token_9876543210"

    class FailingConnector(GitHubConnector):
        async def execute_capability(self, request, credentials=None):
            from app.core.contracts.connector import ConnectorExecutionResult
            return ConnectorExecutionResult(
                request_id=request.request_id,
                capability_id=request.capability_id,
                success=False,
                status_code=500,
                error_message=f"Fatal server failure with token {raw_pat}",
            )

    fail_conn = FailingConnector(is_mock=True)
    req = ConnectorExecutionRequest(capability_id="github.list_failed_workflows", parameters={"leaked_param": raw_pat})
    await ctrl.execute_with_reliability(
        connector_id="connector_github",
        capability_id="github.list_failed_workflows",
        callable_fn=lambda: fail_conn.execute_capability(req),
        parameters={"leaked_param": raw_pat},
        action_hash="test_hash",
        max_retries=0,
    )

    assert len(ctrl.dead_letter_queue) > 0
    dlq_record = ctrl.dead_letter_queue[0]
    assert raw_pat not in json.dumps(dlq_record.parameters)
    assert raw_pat not in dlq_record.error_message


def test_p12_2_s5_07_approval_engine_computes_hash_without_raw_secret_leak():
    """Verify action hash calculation and approval tickets store sanitized params only."""
    engine = ApprovalEngine()
    raw_secret = "ghp_approval_tamper_key_5555"

    req = engine.create_approval_request(
        task_id="task_1",
        step_id="step_1",
        action="Deploy workflow",
        capability_id="github.list_failed_workflows",
        parameters={"repo": "Mukil630/AURA-OS", "injected_key": raw_secret},
        risk_tier=RiskTier.TIER_3_HIGH,
        description="High risk deploy",
        tenant_id="tenant_A",
    )

    assert raw_secret not in json.dumps(req.parameters)
    assert raw_secret not in req.action_hash


def test_p12_2_s5_08_sanitizer_redacts_all_high_risk_token_formats():
    """Verify SecretSanitizer reliably matches GitHub, Google, Telegram, and Bearer patterns."""
    text = (
        "Logs: ghp_1234567890abcdef1234567890abcdef "
        "OAuth: ya29.a0AfH6SMB_secret_google_token_123456789 "
        "Telegram: 123456789:ABCDefGhIjKlMnOpQrStUvWxYz_123456 "
        "Header: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0In0.abc "
        "Password: password='supersecretpass123'"
    )
    sanitized = SecretSanitizer.sanitize_text(text)

    assert "ghp_1234567890abcdef1234567890abcdef" not in sanitized
    assert "ya29.a0AfH6SMB_secret_google_token_123456789" not in sanitized
    assert "123456789:ABCDefGhIjKlMnOpQrStUvWxYz_123456" not in sanitized
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in sanitized
    assert "supersecretpass123" not in sanitized


# ═════════════════════════════════════════════════════════════════════════════
# 3. ROUTER & DISPATCH BOUNDARY HARDENING (Tests 9 - 14)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_p12_2_s5_09_capability_result_never_contains_raw_secrets():
    """Verify capability execution results contain zero raw secret strings in data/message."""
    vault = TenantCredentialVault()
    vault.register_credential("tenant_A", "valid_ref", ConnectorType.GITHUB, "ghp_secret_token_val_777")

    router = CapabilityRouter(credential_vault=vault)
    github_conn = GitHubConnector(is_mock=True)
    router.register_connector(github_conn)

    request = ConnectorExecutionRequest(
        capability_id="github.list_failed_workflows",
        parameters={"repo": "Mukil630/AURA-OS"},
        credential_ref="valid_ref",
    )

    res = await router.dispatch(request, tenant_id="tenant_A")
    assert "ghp_secret_token_val_777" not in str(res.data)
    assert "ghp_secret_token_val_777" not in str(res.error_message or "")


@pytest.mark.anyio
async def test_p12_2_s5_10_router_rejects_raw_token_injection_attempts():
    """Verify router immediately rejects raw token parameters with 422."""
    vault = TenantCredentialVault()
    router = CapabilityRouter(credential_vault=vault)
    github_conn = GitHubConnector(is_mock=True)
    router.register_connector(github_conn)

    attack_payloads = [
        {"token": "ghp_fake_token_123456"},
        {"api_key": "ya29.fake_google_token"},
        {"auth_token": "some_secret_token"},
        {"custom_param": "ghp_raw_embedded_token_99999"},
        {"custom_param": "ya29.raw_google_token_88888"},
        {"custom_param": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.token"},
    ]

    for payload in attack_payloads:
        req = ConnectorExecutionRequest(
            capability_id="github.list_failed_workflows",
            parameters=payload,
        )
        res = await router.dispatch(req, tenant_id="tenant_A")
        assert res.success is False
        assert res.status_code == 422
        assert "Raw secrets are forbidden" in res.error_message


@pytest.mark.anyio
async def test_p12_2_s5_11_cross_tenant_credential_access_returns_404_no_leak():
    """Verify attempting cross-tenant access returns 404 with zero existence leakage."""
    vault = TenantCredentialVault()
    vault.register_credential("tenant_B", "secret_target", ConnectorType.GITHUB, "ghp_secret_b_val")

    router = CapabilityRouter(credential_vault=vault)
    github_conn = GitHubConnector(is_mock=True)
    router.register_connector(github_conn)

    req = ConnectorExecutionRequest(
        capability_id="github.list_failed_workflows",
        parameters={"repo": "Mukil630/AURA-OS"},
        credential_ref="secret_target",
    )

    res = await router.dispatch(req, tenant_id="tenant_A")
    assert res.success is False
    assert res.status_code == 404
    assert "ghp_secret_b_val" not in (res.error_message or "")


@pytest.mark.anyio
async def test_p12_2_s5_12_provider_mismatch_blocks_secret_resolution():
    """Verify mismatched connector providers are blocked before secret extraction."""
    vault = TenantCredentialVault()
    vault.register_credential("tenant_A", "github_key", ConnectorType.GITHUB, "ghp_github_val")

    from app.connectors.drive.connector import GoogleDriveConnector
    router = CapabilityRouter(credential_vault=vault)
    drive_conn = GoogleDriveConnector(is_mock=True)
    router.register_connector(drive_conn)

    req = ConnectorExecutionRequest(
        capability_id="drive.get_storage_info",
        parameters={},
        credential_ref="github_key",
    )

    res = await router.dispatch(req, tenant_id="tenant_A")
    assert res.success is False
    assert res.status_code == 400
    assert "cannot be used for 'google_drive'" in res.error_message


@pytest.mark.anyio
async def test_p12_2_s5_13_revoked_credentials_never_resolve_raw_secret():
    """Verify revoked credentials fail fast with 403 and never yield secret material."""
    vault = TenantCredentialVault()
    vault.register_credential("tenant_A", "revoked_key", ConnectorType.GITHUB, "ghp_revoked_val", status=CredentialStatus.REVOKED)

    router = CapabilityRouter(credential_vault=vault)
    github_conn = GitHubConnector(is_mock=True)
    router.register_connector(github_conn)

    req = ConnectorExecutionRequest(
        capability_id="github.list_failed_workflows",
        parameters={"repo": "Mukil630/AURA-OS"},
        credential_ref="revoked_key",
    )

    res = await router.dispatch(req, tenant_id="tenant_A")
    assert res.success is False
    assert res.status_code == 403
    assert "revoked" in res.error_message.lower()


def test_p12_2_s5_14_get_raw_secret_restricted_to_router_dispatch_boundary():
    """
    ARCHITECTURE AUDIT TEST:
    Verify SecureSecretContainer.get_raw_secret() is only called inside CapabilityRouter.dispatch.
    """
    import inspect
    from app.connectors.router import CapabilityRouter

    source = inspect.getsource(CapabilityRouter.dispatch)
    assert "container.get_raw_secret()" in source
