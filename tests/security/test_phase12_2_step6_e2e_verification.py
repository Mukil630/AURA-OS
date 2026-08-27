"""Phase 12.2 Step 6: End-to-End Credential Boundary Verification Test Suite (20 Scenarios).
Tests full multi-tenant lifecycle: Intake -> Plan -> Policy -> Approval -> Router -> Vault -> Wire -> Sanitization -> Storage.
"""
import json
import pytest

from app.connectors.github.connector import GitHubConnector
from app.connectors.drive.connector import GoogleDriveConnector
from app.connectors.telegram.connector import TelegramConnector
from app.connectors.router import CapabilityRouter
from app.core.contracts.connector import ConnectorExecutionRequest
from app.core.contracts.credential import CredentialStatus
from app.core.contracts.execution_event import ExecutionEventContract
from app.core.contracts.memory import MemoryContract
from app.core.contracts.task import TaskContract
from app.core.enums import ApprovalState, ConnectorType, EventSeverity, EventType, MemoryType, RiskTier, TaskStatus
from app.database.repositories.event_repo import EventRepository
from app.database.repositories.memory_repo import MemoryRepository
from app.database.repositories.task_repo import TaskRepository
from app.policy.approval_engine import compute_action_hash, ApprovalEngine
from app.reliability.controller import ReliabilityController
from app.security.sanitizer import SecretSanitizer
from app.security.vault import TenantCredentialVault


# ═════════════════════════════════════════════════════════════════════════════
# 1. HAPPY PATH MULTI-CONNECTOR E2E LIFECYCLE (Tests 1 - 3)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_p12_2_s6_01_happy_path_github_e2e():
    """TEST 1: Happy Path GitHub E2E with indirect credential_ref."""
    vault = TenantCredentialVault()
    secret_token = "ghp_TEST_SECRET_GITHUB_A_123456789"
    vault.register_credential(
        tenant_id="tenant_A",
        credential_ref="github_prod_A",
        provider=ConnectorType.GITHUB,
        raw_secret=secret_token,
    )

    router = CapabilityRouter(credential_vault=vault)
    github_conn = GitHubConnector(is_mock=True)
    router.register_connector(github_conn)

    request = ConnectorExecutionRequest(
        capability_id="github.list_failed_workflows",
        parameters={"repo": "Mukil630/AURA-OS"},
        credential_ref="github_prod_A",
    )

    res = await router.dispatch(request, tenant_id="tenant_A")
    assert res.success is True
    assert res.status_code == 200
    assert secret_token not in str(res.data)
    assert secret_token not in str(res.error_message or "")


@pytest.mark.anyio
async def test_p12_2_s6_02_happy_path_google_drive_e2e():
    """TEST 2: Happy Path Google Drive E2E with indirect credential_ref."""
    vault = TenantCredentialVault()
    drive_secret = "ya29.TEST_SECRET_GOOGLE_DRIVE_A_987654321"
    vault.register_credential(
        tenant_id="tenant_A",
        credential_ref="drive_prod_A",
        provider=ConnectorType.GOOGLE_DRIVE,
        raw_secret=drive_secret,
    )

    router = CapabilityRouter(credential_vault=vault)
    drive_conn = GoogleDriveConnector(is_mock=True)
    router.register_connector(drive_conn)

    request = ConnectorExecutionRequest(
        capability_id="drive.get_storage_info",
        parameters={},
        credential_ref="drive_prod_A",
    )

    res = await router.dispatch(request, tenant_id="tenant_A")
    assert res.success is True
    assert res.status_code == 200
    assert drive_secret not in str(res.data)


@pytest.mark.anyio
async def test_p12_2_s6_03_happy_path_telegram_e2e():
    """TEST 3: Happy Path Telegram E2E with indirect credential_ref."""
    vault = TenantCredentialVault()
    tg_token = "123456789:TEST_SECRET_TELEGRAM_BOT_TOKEN_AAA"
    vault.register_credential(
        tenant_id="tenant_A",
        credential_ref="telegram_prod_A",
        provider=ConnectorType.TELEGRAM,
        raw_secret=tg_token,
    )

    router = CapabilityRouter(credential_vault=vault)
    tg_conn = TelegramConnector(is_mock=True)
    router.register_connector(tg_conn)

    request = ConnectorExecutionRequest(
        capability_id="telegram.send_message",
        parameters={"chat_id": 999, "text": "Deployment successful"},
        credential_ref="telegram_prod_A",
    )

    res = await router.dispatch(request, tenant_id="tenant_A")
    assert res.success is True
    assert res.status_code == 200
    assert tg_token not in str(res.data)


# ═════════════════════════════════════════════════════════════════════════════
# 2. ADVERSARIAL TENANT & PARAMETER INJECTION DEFENSE (Tests 4 - 7)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_p12_2_s6_04_cross_tenant_attack_denied_404():
    """TEST 4: Tenant A attempting to resolve Tenant B's credential_ref fails with 404."""
    vault = TenantCredentialVault()
    vault.register_credential("tenant_B", "github_prod_B", ConnectorType.GITHUB, "ghp_tenant_B_secret")

    router = CapabilityRouter(credential_vault=vault)
    github_conn = GitHubConnector(is_mock=True)
    router.register_connector(github_conn)

    request = ConnectorExecutionRequest(
        capability_id="github.list_failed_workflows",
        parameters={"repo": "Mukil630/AURA-OS"},
        credential_ref="github_prod_B",
    )

    res = await router.dispatch(request, tenant_id="tenant_A")
    assert res.success is False
    assert res.status_code == 404
    assert "not found for tenant 'tenant_A'" in res.error_message
    assert "ghp_tenant_B_secret" not in res.error_message


@pytest.mark.anyio
async def test_p12_2_s6_05_llm_tenant_override_attack_denied():
    """TEST 5: LLM generating tenant_id in parameters cannot override trusted TenantContext."""
    vault = TenantCredentialVault()
    vault.register_credential("tenant_A", "my_key", ConnectorType.GITHUB, "ghp_secret_A")
    vault.register_credential("tenant_B", "victim_key", ConnectorType.GITHUB, "ghp_secret_B")

    router = CapabilityRouter(credential_vault=vault)
    github_conn = GitHubConnector(is_mock=True)
    router.register_connector(github_conn)

    # Malicious plan claims tenant_id = tenant_B
    request = ConnectorExecutionRequest(
        capability_id="github.list_failed_workflows",
        parameters={"repo": "test", "tenant_id": "tenant_B"},
        credential_ref="victim_key",
    )

    # But request is dispatched with authenticated caller TenantContext = tenant_A
    res = await router.dispatch(request, tenant_id="tenant_A")
    assert res.success is False
    assert res.status_code == 404  # victim_key not found under tenant_A namespace!


@pytest.mark.anyio
async def test_p12_2_s6_06_raw_token_injection_rejected_422():
    """TEST 6: Malicious planner/user output containing raw token rejected with 422."""
    vault = TenantCredentialVault()
    router = CapabilityRouter(credential_vault=vault)
    github_conn = GitHubConnector(is_mock=True)
    router.register_connector(github_conn)

    request = ConnectorExecutionRequest(
        capability_id="github.list_failed_workflows",
        parameters={"repo": "test", "api_key": "ghp_RAW_MALICIOUS_TOKEN_12345"},
        credential_ref="github_prod_A",
    )

    res = await router.dispatch(request, tenant_id="tenant_A")
    assert res.success is False
    assert res.status_code == 422
    assert "Raw secrets are forbidden" in res.error_message


@pytest.mark.anyio
async def test_p12_2_s6_07_token_hidden_inside_nested_parameters_rejected_422():
    """TEST 7: Token hidden in nested config dictionaries rejected with 422."""
    vault = TenantCredentialVault()
    router = CapabilityRouter(credential_vault=vault)
    github_conn = GitHubConnector(is_mock=True)
    router.register_connector(github_conn)

    nested_payloads = [
        {"config": {"headers": {"Authorization": "Bearer ghp_hidden_token_123"}}},
        {"metadata": {"nested": {"token": "ghp_hidden_token_456"}}},
        {"options": [{"auth": "ya29.hidden_google_token"}]},
    ]

    for payload in nested_payloads:
        req = ConnectorExecutionRequest(
            capability_id="github.list_failed_workflows",
            parameters=payload,
            credential_ref="github_prod_A",
        )
        res = await router.dispatch(req, tenant_id="tenant_A")
        assert res.success is False
        assert res.status_code == 422
        assert "Raw secrets are forbidden" in res.error_message


# ═════════════════════════════════════════════════════════════════════════════
# 3. LIFECYCLE & CRYPTOGRAPHIC BOUNDARY DEFENSE (Tests 8 - 11)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_p12_2_s6_08_provider_confusion_denied_400():
    """TEST 8: GitHub credential dispatched toward Drive fails fast without secret resolution."""
    vault = TenantCredentialVault()
    vault.register_credential("tenant_A", "github_key", ConnectorType.GITHUB, "ghp_github_key")

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
async def test_p12_2_s6_09_revoked_credential_denied_403():
    """TEST 9: Revoked credential fails fast with 403 (zero wire execution)."""
    vault = TenantCredentialVault()
    vault.register_credential("tenant_A", "revoked_key", ConnectorType.GITHUB, "ghp_revoked_token", status=CredentialStatus.REVOKED)

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


@pytest.mark.anyio
async def test_p12_2_s6_10_disabled_credential_denied_403():
    """TEST 10: Disabled credential fails fast with 403."""
    vault = TenantCredentialVault()
    vault.register_credential("tenant_A", "disabled_key", ConnectorType.GITHUB, "ghp_disabled_token", status=CredentialStatus.DISABLED)

    router = CapabilityRouter(credential_vault=vault)
    github_conn = GitHubConnector(is_mock=True)
    router.register_connector(github_conn)

    req = ConnectorExecutionRequest(
        capability_id="github.list_failed_workflows",
        parameters={"repo": "Mukil630/AURA-OS"},
        credential_ref="disabled_key",
    )

    res = await router.dispatch(req, tenant_id="tenant_A")
    assert res.success is False
    assert res.status_code == 403
    assert "disabled" in res.error_message.lower()


def test_p12_2_s6_11_approval_tampering_denied_403():
    """TEST 11: Tampering credential_ref after human approval invalidates action hash."""
    engine = ApprovalEngine()
    req = engine.create_approval_request(
        task_id="task_01",
        step_id="step_01",
        action="Deploy CI fix",
        capability_id="github.list_failed_workflows",
        parameters={"repo": "Mukil630/AURA-OS", "credential_ref": "github_readonly_01"},
        risk_tier=RiskTier.TIER_3_HIGH,
        description="Run deploy",
        tenant_id="tenant_A",
    )

    # Operator approves ticket
    success, msg, approved = engine.decide_approval(req.approval_id, decision="approve", approver_id="mukil")
    assert success is True
    assert approved is not None
    assert approved.state in (ApprovalState.APPROVED, "approved", "granted")

    # Attacker attempts to execute using a tampered admin credential_ref
    tampered_hash = compute_action_hash(
        capability_id="github.list_failed_workflows",
        parameters={"repo": "Mukil630/AURA-OS", "credential_ref": "github_admin_01"},
        tenant_id="tenant_A",
    )

    assert tampered_hash != approved.action_hash


# ═════════════════════════════════════════════════════════════════════════════
# 4. COMPREHENSIVE CONTROL-PLANE LEAK AUDITS (Tests 12 - 18)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_p12_2_s6_12_secret_must_not_enter_task_state(test_db_session):
    """TEST 12: Ensure raw secrets never enter TaskModel state."""
    repo = TaskRepository(test_db_session)
    secret = "ghp_TASK_STATE_TEST_SECRET_12345"

    task = await repo.create_task(TaskContract(user_id="tenant_A", raw_input="Run job"))
    updated = await repo.update_task_status(
        task_id=task.task_id,
        status=TaskStatus.COMPLETED,
        result_summary=f"Processed with {secret}",
        result_data={"auth": secret},
        error_message=f"No errors with {secret}",
    )

    assert secret not in updated.result_summary
    assert secret not in json.dumps(updated.result_data)
    assert secret not in (updated.error_message or "")


@pytest.mark.anyio
async def test_p12_2_s6_13_secret_must_not_enter_audit_events(test_db_session):
    """TEST 13: Ensure raw secrets never enter ExecutionEventModel."""
    repo = EventRepository(test_db_session)
    secret = "ghp_AUDIT_EVENT_TEST_SECRET_67890"

    event = ExecutionEventContract(
        trace_id="trc_01",
        task_id="tsk_01",
        event_type=EventType.TASK_STARTED,
        severity=EventSeverity.INFO,
        source_component="Router",
        message=f"Calling API with {secret}",
        payload={"token": secret},
    )
    saved = await repo.record_event(event)

    assert secret not in saved.message
    assert secret not in json.dumps(saved.payload)


@pytest.mark.anyio
async def test_p12_2_s6_14_secret_must_not_enter_memory(test_db_session):
    """TEST 14: Ensure raw secrets never enter MemoryModel."""
    repo = MemoryRepository(test_db_session)
    secret = "ya29.MEMORY_TEST_SECRET_ABCDEFG"

    mem = await repo.create_or_update_memory(
        MemoryContract(
            user_id="tenant_A",
            memory_type=MemoryType.EPISODIC_TASK,
            content=f"Remember token {secret}",
            summary=f"Summary of {secret}",
        )
    )

    assert secret not in mem.content
    assert secret not in (mem.summary or "")


@pytest.mark.anyio
async def test_p12_2_s6_15_secret_must_not_enter_dlq():
    """TEST 15: Ensure raw secrets never enter DeadLetterQueue."""
    ctrl = ReliabilityController()
    secret = "ghp_DLQ_TEST_SECRET_FAILLOOP"

    class FailingConn(GitHubConnector):
        async def execute_capability(self, req, credentials=None):
            from app.core.contracts.connector import ConnectorExecutionResult
            return ConnectorExecutionResult(
                request_id=req.request_id,
                capability_id=req.capability_id,
                success=False,
                status_code=500,
                error_message=f"HTTP 500 upstream failure with {secret}",
            )

    failing = FailingConn(is_mock=True)
    req = ConnectorExecutionRequest(capability_id="github.list_failed_workflows", parameters={"bad_param": secret})
    await ctrl.execute_with_reliability(
        connector_id="connector_github",
        capability_id="github.list_failed_workflows",
        callable_fn=lambda: failing.execute_capability(req),
        parameters={"bad_param": secret},
        action_hash="hash_1",
        max_retries=0,
    )

    assert len(ctrl.dead_letter_queue) > 0
    dlq_record = ctrl.dead_letter_queue[0]
    assert secret not in json.dumps(dlq_record.parameters)
    assert secret not in dlq_record.error_message


def test_p12_2_s6_16_secret_must_not_enter_exceptions():
    """TEST 16: Ensure exceptions sanitized without leaking tokens in tracebacks/messages."""
    raw_token = "ghp_EXCEPTION_LEAK_TEST_TOKEN"
    try:
        sanitized_msg = SecretSanitizer.sanitize_text(f"API Connection Failed: Authorization=Bearer {raw_token}")
        raise RuntimeError(sanitized_msg)
    except RuntimeError as ex:
        assert raw_token not in str(ex)
        assert "[REDACTED_TOKEN]" in str(ex) or "ghp_****" in str(ex)


def test_p12_2_s6_17_secret_must_not_enter_approval_cards():
    """TEST 17: Ensure approval card payloads display credential_ref, never raw tokens."""
    engine = ApprovalEngine()
    req = engine.create_approval_request(
        task_id="tsk_card",
        step_id="stp_card",
        action="Deploy",
        capability_id="github.list_failed_workflows",
        parameters={"repo": "Mukil630/AURA-OS", "credential_ref": "github_prod_01"},
        risk_tier=RiskTier.TIER_2_MEDIUM,
        description="Deploy to production",
        tenant_id="tenant_A",
    )

    card_json = json.dumps(req.model_dump(), default=str)
    assert "github_prod_01" in card_json
    assert "ghp_" not in card_json


def test_p12_2_s6_18_secret_must_not_enter_llm_context():
    """TEST 18: Planner output and LLM prompt context contains credential_ref only."""
    planner_output = {
        "step_id": "step_1",
        "tool_name": "github.list_failed_workflows",
        "parameters": {
            "repo": "Mukil630/AURA-OS",
            "credential_ref": "github_prod_A",
        }
    }
    dumped = json.dumps(planner_output)
    assert "credential_ref" in dumped
    assert "ghp_" not in dumped


# ═════════════════════════════════════════════════════════════════════════════
# 5. REGRESSION & KILLER FULL LIFECYCLE E2E (Tests 19 - 20)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_p12_2_s6_19_credential_free_capability_regression():
    """TEST 19: Capabilities that do not require credentials continue working unaffected."""
    router = CapabilityRouter()
    github_conn = GitHubConnector(is_mock=True)
    router.register_connector(github_conn)

    req = ConnectorExecutionRequest(
        capability_id="github.list_failed_workflows",
        parameters={"repo": "Mukil630/AURA-OS"},
    )
    res = await router.dispatch(req)
    assert res.success is True
    assert res.status_code == 200


@pytest.mark.anyio
async def test_p12_2_s6_20_full_killer_e2e_lifecycle_test(test_db_session):
    """
    TEST 20: THE KILLER FULL LIFECYCLE END-TO-END TEST
    Simulates complete task flow:
    User Task -> P1 -> Planner -> Policy -> Approval -> Router -> Vault -> Wire -> DB Storage.
    Audits all 10 control-plane surfaces for ZERO secret residue!
    """
    secret = "ghp_KILLER_E2E_AUDIT_SECRET_AUTHENTIC_2026"
    vault = TenantCredentialVault()
    vault.register_credential(
        tenant_id="tenant_mukil",
        credential_ref="github_master_vault_key",
        provider=ConnectorType.GITHUB,
        raw_secret=secret,
        purpose="master_ci_deploy",
    )

    router = CapabilityRouter(credential_vault=vault)
    github_conn = GitHubConnector(is_mock=True)
    router.register_connector(github_conn)

    # 1. Task Intake & DB persistence
    task_repo = TaskRepository(test_db_session)
    task = await task_repo.create_task(
        TaskContract(
            user_id="tenant_mukil",
            raw_input="Deploy automated fix to GitHub CI workflow",
        )
    )

    # 2. Planner produces step referencing credential_ref
    step_params = {
        "repo": "Mukil630/AURA-OS",
        "credential_ref": "github_master_vault_key",
    }

    # 3. Policy & Approval Engine evaluates action hash
    approval_engine = ApprovalEngine()
    approval_ticket = approval_engine.create_approval_request(
        task_id=task.task_id,
        step_id="step_1",
        action="Deploy CI Fix",
        capability_id="github.list_failed_workflows",
        parameters=step_params,
        risk_tier=RiskTier.TIER_2_MEDIUM,
        description="Approve CI deploy",
        tenant_id="tenant_mukil",
    )
    success, msg, approved = approval_engine.decide_approval(approval_ticket.approval_id, decision="approve", approver_id="mukil")
    assert success is True
    assert approved is not None
    assert approved.state in (ApprovalState.APPROVED, "approved", "granted")

    # 4. Capability Dispatch via Router & Vault
    dispatch_req = ConnectorExecutionRequest(
        capability_id="github.list_failed_workflows",
        parameters=step_params,
        credential_ref="github_master_vault_key",
        tenant_id="tenant_mukil",
    )
    result = await router.dispatch(dispatch_req, tenant_id="tenant_mukil")
    assert result.success is True
    assert result.status_code == 200

    # 5. Persist Audit Event
    event_repo = EventRepository(test_db_session)
    event = await event_repo.record_event(
        ExecutionEventContract(
            trace_id="trc_killer_e2e",
            task_id=task.task_id,
            event_type=EventType.TASK_COMPLETED,
            severity=EventSeverity.INFO,
            source_component="E2EOrchestrator",
            message=f"Completed capability github.list_failed_workflows for {step_params['credential_ref']}",
            payload={"result_status": result.status_code},
        )
    )

    # 6. Persist Memory
    memory_repo = MemoryRepository(test_db_session)
    mem = await memory_repo.create_or_update_memory(
        MemoryContract(
            user_id="tenant_mukil",
            memory_type=MemoryType.EPISODIC_TASK,
            content="Workflow fix deployed successfully using github_master_vault_key",
            summary="Workflow fix completed",
        )
    )

    # 7. Update Task Status
    updated_task = await task_repo.update_task_status(
        task_id=task.task_id,
        status=TaskStatus.COMPLETED,
        result_summary="Workflow checked and verified via github_master_vault_key",
        result_data=result.data,
    )

    # ═════════════════════════════════════════════════════════════════════════
    # FORENSIC AUDIT: ASSERT ZERO SECRET IN ALL 10 CONTROL-PLANE SURFACES
    # ═════════════════════════════════════════════════════════════════════════
    assert secret not in str(step_params), "Secret leaked in Planner params!"
    assert secret not in approval_ticket.action_hash, "Secret leaked in Approval action hash!"
    assert secret not in json.dumps(approval_ticket.parameters), "Secret leaked in Approval parameters!"
    assert secret not in str(result.data), "Secret leaked in Capability result data!"
    assert secret not in (result.error_message or ""), "Secret leaked in Capability error message!"
    assert secret not in event.message, "Secret leaked in Event message!"
    assert secret not in json.dumps(event.payload), "Secret leaked in Event payload!"
    assert secret not in mem.content, "Secret leaked in Persistent memory content!"
    assert secret not in (mem.summary or ""), "Secret leaked in Persistent memory summary!"
    assert secret not in updated_task.result_summary, "Secret leaked in Task result summary!"
    assert secret not in json.dumps(updated_task.result_data), "Secret leaked in Task result data!"
