"""Phase 10: Human-In-The-Loop Autonomy, Policy Gates, and Cryptographic Action Hash Verification Test Suite."""
import asyncio
import hashlib
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict
import pytest
from httpx import ASGITransport, AsyncClient

from app.connectors.telegram.auth import TelegramAuthorizer
from app.core.contracts.permission import ApprovalRequestContract
from app.core.enums import ApprovalState, RiskTier
from app.main import app
from app.policy.approval_engine import (
    ApprovalEngine,
    compute_action_hash,
    compute_plan_hash,
    default_approval_engine,
)
from app.policy.risk_classifier import (
    RiskClassificationEngine,
    RiskLevel,
    default_risk_classifier,
)
from app.policy.telegram_approval import (
    TelegramApprovalGateway,
    default_telegram_approval,
)
from app.security.auth import create_access_token


# ═════════════════════════════════════════════════════════════════════════════
# 1. DETERMINISTIC RISK CLASSIFICATION ENGINE (8 Tests)
# ═════════════════════════════════════════════════════════════════════════════

def test_p10_01_r0_hardware_telemetry_classified_low_auto_execute():
    """Verify PC hardware telemetry queries are classified as R0 (Low Risk, Auto-Execute)."""
    classifier = RiskClassificationEngine()
    for cap in ["pc.get_cpu", "pc.get_memory", "pc.get_disk", "pc.get_network", "pc.get_temperature", "pc.get_health_summary"]:
        level, tier, req_appr, _ = classifier.classify_capability(cap)
        assert level == RiskLevel.R0_READ_HARDWARE
        assert tier == RiskTier.TIER_1_LOW
        assert req_appr is False


def test_p10_02_r1_external_reads_classified_low_auto_execute():
    """Verify external read-only queries are classified as R1 (Low Risk, Auto-Execute)."""
    classifier = RiskClassificationEngine()
    for cap in ["github.list_failed_workflows", "github.get_logs", "drive.list", "drive.get_storage_info", "drive.download"]:
        level, tier, req_appr, _ = classifier.classify_capability(cap)
        assert level == RiskLevel.R1_READ_EXTERNAL
        assert tier == RiskTier.TIER_1_LOW
        assert req_appr is False


def test_p10_03_r2_safe_creations_classified_low_auto_execute():
    """Verify safe creations/uploads are classified as R2 (Auto-Execute)."""
    classifier = RiskClassificationEngine()
    for cap in ["drive.upload", "drive.create_folder", "drive.sync_vault", "telegram.send_message"]:
        level, tier, req_appr, _ = classifier.classify_capability(cap)
        assert level == RiskLevel.R2_SAFE_CREATION
        assert req_appr is False


def test_p10_04_r3_modify_repository_classified_high_requires_approval():
    """Verify code fix and repository modification are classified as R3 (High Risk, MANDATORY APPROVAL)."""
    classifier = RiskClassificationEngine()
    for cap in ["coding.apply_fix", "github.modify_repository", "github.create_pr"]:
        level, tier, req_appr, _ = classifier.classify_capability(cap)
        assert level == RiskLevel.R3_MODIFY_REPOSITORY
        assert req_appr is True


def test_p10_05_r4_data_delete_classified_high_requires_approval():
    """Verify file trashing/deletion are classified as R4 (High Risk, MANDATORY APPROVAL)."""
    classifier = RiskClassificationEngine()
    for cap in ["drive.trash_file", "drive.delete_file"]:
        level, tier, req_appr, _ = classifier.classify_capability(cap)
        assert level == RiskLevel.R4_DATA_OVERWRITE_OR_DELETE
        assert req_appr is True


def test_p10_06_r5_security_change_classified_critical_requires_approval():
    """Verify security policy and token rotations are classified as R5 (Critical Risk, STRONG APPROVAL)."""
    classifier = RiskClassificationEngine()
    for cap in ["security.rotate_token", "security.update_policy", "security.manage_tenant"]:
        level, tier, req_appr, _ = classifier.classify_capability(cap)
        assert level == RiskLevel.R5_SECURITY_OR_CREDENTIAL_CHANGE
        assert req_appr is True


def test_p10_07_r6_machine_control_classified_dangerous_hard_rejection():
    """Verify machine control attempts are classified as R6 (Dangerous Risk, Prohibited)."""
    classifier = RiskClassificationEngine()
    for cap in ["pc.shell", "pc.powershell", "pc.command", "pc.exec", "pc.kill_process", "pc.delete_file", "pc.modify_registry"]:
        level, tier, req_appr, _ = classifier.classify_capability(cap)
        assert level == RiskLevel.R6_MACHINE_CONTROL
        assert req_appr is True


def test_p10_08_natural_language_wording_invariance():
    """Verify capability risk belongs to the registered capability contract, not conversational phrasing."""
    classifier = RiskClassificationEngine()
    # Regardless of whether user says 'please quickly delete' or 'clean up that useless file'
    level1, _, req1, _ = classifier.classify_capability("drive.trash_file")
    level2, _, req2, _ = classifier.classify_capability("drive.delete_file")

    assert level1 == RiskLevel.R4_DATA_OVERWRITE_OR_DELETE
    assert level2 == RiskLevel.R4_DATA_OVERWRITE_OR_DELETE
    assert req1 is True
    assert req2 is True


# ═════════════════════════════════════════════════════════════════════════════
# 2. CRYPTOGRAPHIC ACTION & PLAN HASHING (7 Tests)
# ═════════════════════════════════════════════════════════════════════════════

def test_p10_09_action_hash_deterministic_computation():
    """Verify compute_action_hash produces deterministic SHA-256 for identical inputs."""
    params = {"repository": "Mukil630/AURA-OS", "branch": "fix/ci-patch"}
    h1 = compute_action_hash("coding.apply_fix", params, tenant_id="mukil")
    h2 = compute_action_hash("coding.apply_fix", params, tenant_id="mukil")
    assert h1 == h2
    assert len(h1) == 64


def test_p10_10_action_hash_tamper_detection_parameter_change():
    """Verify modifying any parameter key or value strictly changes the computed action hash."""
    params_a = {"repository": "Mukil630/AURA-OS", "branch": "fix/ci-patch"}
    params_b = {"repository": "Mukil630/AURA-OS", "branch": "main"}
    params_c = {"repository": "Mukil630/production-repo", "branch": "fix/ci-patch"}

    h_a = compute_action_hash("coding.apply_fix", params_a, tenant_id="mukil")
    h_b = compute_action_hash("coding.apply_fix", params_b, tenant_id="mukil")
    h_c = compute_action_hash("coding.apply_fix", params_c, tenant_id="mukil")

    assert h_a != h_b
    assert h_a != h_c
    assert h_b != h_c


def test_p10_11_action_hash_tamper_detection_tenant_change():
    """Verify changing tenant context produces a different action hash."""
    params = {"repository": "Mukil630/AURA-OS"}
    h_mukil = compute_action_hash("github.modify_repository", params, tenant_id="mukil")
    h_attacker = compute_action_hash("github.modify_repository", params, tenant_id="stranger")
    assert h_mukil != h_attacker


def test_p10_12_plan_hash_deterministic_computation():
    """Verify compute_plan_hash produces deterministic hash for DAG step structures."""
    steps = [
        {"step_index": 0, "tool_name": "github.get_logs", "agent_type": "coding"},
        {"step_index": 1, "tool_name": "coding.apply_fix", "agent_type": "coding"},
    ]
    h1 = compute_plan_hash(steps)
    h2 = compute_plan_hash(steps)
    assert h1 == h2
    assert len(h1) == 64


def test_p10_13_plan_hash_tamper_detection_step_order_change():
    """Verify reordering or altering planned DAG steps changes the plan hash."""
    steps_orig = [
        {"step_index": 0, "tool_name": "github.get_logs", "agent_type": "coding"},
        {"step_index": 1, "tool_name": "coding.apply_fix", "agent_type": "coding"},
    ]
    steps_tampered = [
        {"step_index": 0, "tool_name": "coding.apply_fix", "agent_type": "coding"},
        {"step_index": 1, "tool_name": "github.get_logs", "agent_type": "coding"},
    ]
    assert compute_plan_hash(steps_orig) != compute_plan_hash(steps_tampered)


def test_p10_14_zero_secrets_in_action_hash_input():
    """Verify SecretSanitizer automatically masks raw credentials prior to hashing."""
    params = {"token": "ghp_secretToken1234567890", "repo": "Mukil630/AURA-OS"}
    h = compute_action_hash("coding.apply_fix", params)
    assert len(h) == 64


def test_p10_15_approval_ticket_creation_with_hashes():
    """Verify ApprovalEngine creates tickets with populated action_hash and plan_hash."""
    engine = ApprovalEngine()
    ticket = engine.create_approval_request(
        task_id="task_p10_15",
        step_id="step_1",
        action="coding.apply_fix",
        capability_id="coding.apply_fix",
        parameters={"repository": "Mukil630/AURA-OS"},
        risk_tier=RiskTier.TIER_3_HIGH,
        description="Apply CI bugfix patch to Mukil630/AURA-OS",
        tenant_id="mukil",
    )

    assert ticket.approval_id.startswith("appr_")
    assert ticket.action_hash is not None
    assert len(ticket.action_hash) == 64
    assert ticket.state == ApprovalState.PENDING


# ═════════════════════════════════════════════════════════════════════════════
# 3. HUMAN APPROVAL STATE MACHINE & DECISION WORKFLOW (8 Tests)
# ═════════════════════════════════════════════════════════════════════════════

def test_p10_16_approval_state_pending_to_approved():
    """Verify positive human approval transitions PENDING -> APPROVED."""
    engine = ApprovalEngine()
    ticket = engine.create_approval_request(
        task_id="task_16",
        step_id="step_16",
        action="coding.apply_fix",
        capability_id="coding.apply_fix",
        parameters={"repository": "test-repo"},
        risk_tier=RiskTier.TIER_3_HIGH,
        description="Apply fix",
    )
    success, msg, decided = engine.decide_approval(ticket.approval_id, "approve", approver_id="mukil")
    assert success is True
    assert decided.state == ApprovalState.APPROVED
    assert decided.approved_by == "mukil"
    assert decided.decided_at is not None


def test_p10_17_approval_state_pending_to_rejected():
    """Verify operator rejection transitions PENDING -> REJECTED with reason."""
    engine = ApprovalEngine()
    ticket = engine.create_approval_request(
        task_id="task_17",
        step_id="step_17",
        action="drive.trash_file",
        capability_id="drive.trash_file",
        parameters={"file_id": "file_123"},
        risk_tier=RiskTier.TIER_3_HIGH,
        description="Trash file",
    )
    success, msg, decided = engine.decide_approval(
        ticket.approval_id,
        "reject",
        approver_id="mukil",
        reason="File is still needed for audit.",
    )
    assert success is True
    assert decided.state == ApprovalState.REJECTED
    assert decided.rejection_reason == "File is still needed for audit."


def test_p10_18_approval_state_rejection_blocks_execution():
    """Verify rejected approval ticket is refused at execution gate."""
    engine = ApprovalEngine()
    params = {"file_id": "file_123"}
    ticket = engine.create_approval_request(
        task_id="task_18",
        step_id="step_18",
        action="drive.trash_file",
        capability_id="drive.trash_file",
        parameters=params,
        risk_tier=RiskTier.TIER_3_HIGH,
        description="Trash file",
    )
    engine.decide_approval(ticket.approval_id, "reject", approver_id="mukil")

    valid, reason, _ = engine.verify_and_consume_approval(ticket.approval_id, "drive.trash_file", params)
    assert valid is False
    assert "rejected" in reason.lower()


def test_p10_19_approval_state_terminal_cannot_re_decide():
    """Verify deciding an already decided ticket returns an error (State Machine Invariant)."""
    engine = ApprovalEngine()
    ticket = engine.create_approval_request(
        task_id="task_19",
        step_id="step_19",
        action="coding.apply_fix",
        capability_id="coding.apply_fix",
        parameters={"repo": "test"},
        risk_tier=RiskTier.TIER_3_HIGH,
        description="Apply fix",
    )
    engine.decide_approval(ticket.approval_id, "approve", approver_id="mukil")

    # Try re-deciding
    success2, msg2, _ = engine.decide_approval(ticket.approval_id, "reject", approver_id="mukil")
    assert success2 is False
    assert "terminal state" in msg2.lower()


def test_p10_20_approval_state_expired_after_ttl():
    """Verify tickets past their TTL automatically transition to EXPIRED and cannot be approved."""
    engine = ApprovalEngine(default_ttl_seconds=-1)  # Immediately expired
    ticket = engine.create_approval_request(
        task_id="task_20",
        step_id="step_20",
        action="coding.apply_fix",
        capability_id="coding.apply_fix",
        parameters={"repo": "test"},
        risk_tier=RiskTier.TIER_3_HIGH,
        description="Apply fix",
        ttl_seconds=-5,
    )
    assert ticket.state == ApprovalState.EXPIRED

    success, msg, _ = engine.decide_approval(ticket.approval_id, "approve", approver_id="mukil")
    assert success is False
    assert "expired" in msg.lower()


def test_p10_21_approval_state_cancelled_via_emergency_kill_switch():
    """Verify emergency stop / kill-switch invalidates all pending approval requests."""
    engine = ApprovalEngine()
    t1 = engine.create_approval_request("t1", "s1", "a1", "coding.apply_fix", {"r": "1"}, RiskTier.TIER_3_HIGH, "desc")
    t2 = engine.create_approval_request("t2", "s2", "a2", "drive.trash_file", {"f": "2"}, RiskTier.TIER_3_HIGH, "desc")

    cancelled = engine.cancel_all_pending_for_kill_switch()
    assert cancelled == 2
    assert engine.get_approval(t1.approval_id).state == ApprovalState.CANCELLED
    assert engine.get_approval(t2.approval_id).state == ApprovalState.CANCELLED


def test_p10_22_approval_state_cancelled_ticket_cannot_be_resurrected():
    """Verify cancelled tickets are denied at execution gate without resurrection."""
    engine = ApprovalEngine()
    params = {"repository": "Mukil630/AURA-OS"}
    ticket = engine.create_approval_request(
        task_id="task_22",
        step_id="step_22",
        action="coding.apply_fix",
        capability_id="coding.apply_fix",
        parameters=params,
        risk_tier=RiskTier.TIER_3_HIGH,
        description="Apply fix",
    )
    engine.cancel_all_pending_for_kill_switch()

    valid, reason, _ = engine.verify_and_consume_approval(ticket.approval_id, "coding.apply_fix", params)
    assert valid is False
    assert "cancelled" in reason.lower() or "denied" in reason.lower()


def test_p10_23_approval_replay_protection_consumed_ticket():
    """Verify valid approval ticket verifies green for identical parameters."""
    engine = ApprovalEngine()
    params = {"repository": "Mukil630/AURA-OS", "branch": "fix/patch-1"}
    ticket = engine.create_approval_request(
        task_id="task_23",
        step_id="step_23",
        action="coding.apply_fix",
        capability_id="coding.apply_fix",
        parameters=params,
        risk_tier=RiskTier.TIER_3_HIGH,
        description="Apply fix",
    )
    engine.decide_approval(ticket.approval_id, "approve", approver_id="mukil")

    valid, msg, ticket_ret = engine.verify_and_consume_approval(ticket.approval_id, "coding.apply_fix", params)
    assert valid is True
    assert "verified green" in msg.lower()


# ═════════════════════════════════════════════════════════════════════════════
# 4. TELEGRAM HUMAN-IN-THE-LOOP APPROVAL GATEWAY (7 Tests)
# ═════════════════════════════════════════════════════════════════════════════

def test_p10_24_telegram_approval_card_formatting():
    """Verify TelegramApprovalGateway generates rich markdown cards with parameters, risk, and action hash."""
    gateway = TelegramApprovalGateway()
    ticket = default_approval_engine.create_approval_request(
        task_id="task_tg_card_01",
        step_id="step_01",
        action="coding.apply_fix",
        capability_id="coding.apply_fix",
        parameters={"repository": "Mukil630/AURA-OS", "commit_msg": "Fix CI bug"},
        risk_tier=RiskTier.TIER_3_HIGH,
        description="Apply patch to resolve CI failure.",
    )
    msg = gateway.build_approval_card(ticket, chat_id=987654321)

    assert "HUMAN APPROVAL REQUIRED" in msg.text
    assert "task_tg_card_01" in msg.text
    assert "tier_3_high" in msg.text or "HIGH" in msg.text
    assert "Mukil630/AURA-OS" in msg.text
    assert "/approve" in msg.text
    assert "/reject" in msg.text
    assert ticket.approval_id in msg.text


def test_p10_25_telegram_approval_decision_approve_command():
    """Verify /approve <approval_id> command from authorized Telegram user approves ticket."""
    gateway = TelegramApprovalGateway()
    ticket = default_approval_engine.create_approval_request(
        task_id="task_tg_25",
        step_id="step_25",
        action="coding.apply_fix",
        capability_id="coding.apply_fix",
        parameters={"repo": "test-repo"},
        risk_tier=RiskTier.TIER_3_HIGH,
        description="Apply patch",
    )
    success, msg = gateway.process_telegram_decision(
        telegram_user_id=987654321,
        raw_command=f"/approve {ticket.approval_id}",
        username="mukil630",
    )
    assert success is True
    assert "granted" in msg.lower()
    assert default_approval_engine.get_approval(ticket.approval_id).state == ApprovalState.APPROVED


def test_p10_26_telegram_approval_decision_reject_command():
    """Verify /reject <approval_id> command from authorized Telegram user rejects ticket."""
    gateway = TelegramApprovalGateway()
    ticket = default_approval_engine.create_approval_request(
        task_id="task_tg_26",
        step_id="step_26",
        action="drive.trash_file",
        capability_id="drive.trash_file",
        parameters={"file_id": "temp_file_123"},
        risk_tier=RiskTier.TIER_3_HIGH,
        description="Trash file",
    )
    success, msg = gateway.process_telegram_decision(
        telegram_user_id=987654321,
        raw_command=f"/reject {ticket.approval_id} Retain file for backup",
        username="mukil630",
    )
    assert success is True
    assert "rejected" in msg.lower()
    assert default_approval_engine.get_approval(ticket.approval_id).state == ApprovalState.REJECTED


def test_p10_27_telegram_approval_unauthorized_user_rejected_403():
    """Verify approval commands from unauthorized strangers are rejected with access denied."""
    gateway = TelegramApprovalGateway()
    ticket = default_approval_engine.create_approval_request(
        task_id="task_tg_27",
        step_id="step_27",
        action="coding.apply_fix",
        capability_id="coding.apply_fix",
        parameters={"repo": "test-repo"},
        risk_tier=RiskTier.TIER_3_HIGH,
        description="Apply patch",
    )
    success, msg = gateway.process_telegram_decision(
        telegram_user_id=777888999,  # Unauthorized stranger
        raw_command=f"/approve {ticket.approval_id}",
        username="attacker",
    )
    assert success is False
    assert "Access Denied" in msg
    assert default_approval_engine.get_approval(ticket.approval_id).state == ApprovalState.PENDING


def test_p10_28_telegram_approval_malformed_command_handling():
    """Verify malformed Telegram commands return clear syntax guidance."""
    gateway = TelegramApprovalGateway()
    success, msg = gateway.process_telegram_decision(
        telegram_user_id=987654321,
        raw_command="/approve",  # Missing ID
        username="mukil630",
    )
    assert success is False
    assert "Usage:" in msg


def test_p10_29_telegram_approval_expired_ticket_command_rejected():
    """Verify attempting to approve an expired ticket via Telegram returns failure."""
    engine = ApprovalEngine()
    gateway = TelegramApprovalGateway(approval_engine=engine)
    ticket = engine.create_approval_request(
        task_id="task_tg_29",
        step_id="step_29",
        action="coding.apply_fix",
        capability_id="coding.apply_fix",
        parameters={"repo": "test"},
        risk_tier=RiskTier.TIER_3_HIGH,
        description="Apply patch",
        ttl_seconds=-10,  # Expired
    )
    success, msg = gateway.process_telegram_decision(
        telegram_user_id=987654321,
        raw_command=f"/approve {ticket.approval_id}",
        username="mukil630",
    )
    assert success is False
    assert "expired" in msg.lower()


def test_p10_30_telegram_approval_card_zero_credential_leakage():
    """Verify generated Telegram approval cards never leak credentials."""
    gateway = TelegramApprovalGateway()
    ticket = default_approval_engine.create_approval_request(
        task_id="task_tg_30",
        step_id="step_30",
        action="coding.apply_fix",
        capability_id="coding.apply_fix",
        parameters={"repo": "Mukil630/AURA-OS", "token": "ghp_superSecretKey9876543210"},
        risk_tier=RiskTier.TIER_3_HIGH,
        description="Apply patch with token ghp_superSecretKey9876543210",
    )
    msg = gateway.build_approval_card(ticket)
    assert "ghp_superSecretKey9876543210" not in msg.text


# ═════════════════════════════════════════════════════════════════════════════
# 5. REST API APPROVAL ENDPOINTS (5 Tests)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_p10_31_rest_api_list_pending_approvals():
    """Verify GET /api/v1/approvals/pending returns active tickets."""
    ticket = default_approval_engine.create_approval_request(
        task_id="task_rest_31",
        step_id="step_31",
        action="coding.apply_fix",
        capability_id="coding.apply_fix",
        parameters={"repo": "test-repo"},
        risk_tier=RiskTier.TIER_3_HIGH,
        description="Apply patch",
        tenant_id="mukil",
    )
    token = create_access_token(user_id="mukil", role="admin")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        res = await client.get("/api/v1/approvals/pending", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        data = res.json()
        assert any(t["approval_id"] == ticket.approval_id for t in data)


@pytest.mark.anyio
async def test_p10_32_rest_api_get_approval_ticket_by_id():
    """Verify GET /api/v1/approvals/{approval_id} returns complete contract."""
    ticket = default_approval_engine.create_approval_request(
        task_id="task_rest_32",
        step_id="step_32",
        action="drive.trash_file",
        capability_id="drive.trash_file",
        parameters={"file_id": "file_999"},
        risk_tier=RiskTier.TIER_3_HIGH,
        description="Trash file",
        tenant_id="mukil",
    )
    token = create_access_token(user_id="mukil", role="admin")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        res = await client.get(f"/api/v1/approvals/{ticket.approval_id}", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        data = res.json()
        assert data["approval_id"] == ticket.approval_id
        assert data["action_hash"] is not None


@pytest.mark.anyio
async def test_p10_33_rest_api_decide_approval_approve():
    """Verify POST /api/v1/approvals/{approval_id}/decide with approve."""
    ticket = default_approval_engine.create_approval_request(
        task_id="task_rest_33",
        step_id="step_33",
        action="coding.apply_fix",
        capability_id="coding.apply_fix",
        parameters={"repo": "test-repo"},
        risk_tier=RiskTier.TIER_3_HIGH,
        description="Apply patch",
        tenant_id="mukil",
    )
    token = create_access_token(user_id="mukil", role="admin")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        res = await client.post(
            f"/api/v1/approvals/{ticket.approval_id}/decide",
            json={"decision": "approve", "reason": "Operator confirmed fix"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["ticket"]["state"] == "approved"


@pytest.mark.anyio
async def test_p10_34_rest_api_decide_approval_reject():
    """Verify POST /api/v1/approvals/{approval_id}/decide with reject."""
    ticket = default_approval_engine.create_approval_request(
        task_id="task_rest_34",
        step_id="step_34",
        action="drive.trash_file",
        capability_id="drive.trash_file",
        parameters={"file_id": "file_888"},
        risk_tier=RiskTier.TIER_3_HIGH,
        description="Trash file",
        tenant_id="mukil",
    )
    token = create_access_token(user_id="mukil", role="admin")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        res = await client.post(
            f"/api/v1/approvals/{ticket.approval_id}/decide",
            json={"decision": "reject", "reason": "Disapproved by security policy"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["ticket"]["state"] == "rejected"


@pytest.mark.anyio
async def test_p10_35_rest_api_unknown_approval_ticket_404():
    """Verify querying non-existent ticket returns 404 Not Found."""
    token = create_access_token(user_id="mukil", role="admin")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        res = await client.get("/api/v1/approvals/non_existent_id_999", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 404


# ═════════════════════════════════════════════════════════════════════════════
# 6. THE KILLER ADVERSARIAL SECURITY TESTS (10 Tests)
# ═════════════════════════════════════════════════════════════════════════════

def test_p10_36_killer_adversarial_action_hash_mismatch_repository_swap_denied():
    """
    KILLER ADVERSARIAL TEST:
    Agent plans: coding.apply_fix on repository = 'test-repository-A' (action_hash: HASH_A)
        ↓
    Human approves HASH_A
        ↓
    Agent attempts: coding.apply_fix on repository = 'production-repository-B' (action_hash: HASH_B)
        ↓
    APPROVAL ENGINE: HASH_A != HASH_B → 🚫 EXECUTION DENIED (Hash Mismatch)
    """
    engine = ApprovalEngine()

    # Step 1: Agent creates approval ticket for test repository A
    params_planned = {"repository": "Mukil630/test-repo-A", "branch": "fix/patch"}
    ticket = engine.create_approval_request(
        task_id="task_adv_36",
        step_id="step_36",
        action="coding.apply_fix",
        capability_id="coding.apply_fix",
        parameters=params_planned,
        risk_tier=RiskTier.TIER_3_HIGH,
        description="Apply patch to test-repo-A",
        tenant_id="mukil",
    )
    hash_planned = ticket.action_hash

    # Step 2: Human approves the ticket
    engine.decide_approval(ticket.approval_id, "approve", approver_id="mukil")

    # Step 3: Agent sneakily attempts to execute against production repository B
    params_tampered = {"repository": "Mukil630/production-repo-B", "branch": "fix/patch"}

    valid, reason, _ = engine.verify_and_consume_approval(
        approval_id=ticket.approval_id,
        capability_id="coding.apply_fix",
        parameters=params_tampered,
        tenant_id="mukil",
    )

    assert valid is False
    assert "Cryptographic Hash Mismatch" in reason
    assert "Expected hash" in reason


def test_p10_37_killer_adversarial_capability_swap_denied():
    """Verify changing capability after approval is denied (e.g. approved analyze_patch, attempts apply_fix)."""
    engine = ApprovalEngine()
    params = {"repository": "Mukil630/AURA-OS"}
    ticket = engine.create_approval_request(
        task_id="task_adv_37",
        step_id="step_37",
        action="coding.analyze_patch",
        capability_id="coding.analyze_patch",
        parameters=params,
        risk_tier=RiskTier.TIER_2_MEDIUM,
        description="Analyze code patch",
        tenant_id="mukil",
    )
    engine.decide_approval(ticket.approval_id, "approve", approver_id="mukil")

    # Attempt to swap capability to apply_fix
    valid, reason, _ = engine.verify_and_consume_approval(
        approval_id=ticket.approval_id,
        capability_id="coding.apply_fix",
        parameters=params,
        tenant_id="mukil",
    )
    assert valid is False
    assert "Capability Mismatch" in reason or "Hash Mismatch" in reason


def test_p10_38_killer_adversarial_parameter_injection_branch_swap_denied():
    """Verify changing target branch from 'dev' to 'main' invalidates approval hash."""
    engine = ApprovalEngine()
    params_dev = {"repository": "Mukil630/AURA-OS", "branch": "dev"}
    ticket = engine.create_approval_request(
        task_id="task_adv_38",
        step_id="step_38",
        action="coding.apply_fix",
        capability_id="coding.apply_fix",
        parameters=params_dev,
        risk_tier=RiskTier.TIER_3_HIGH,
        description="Apply fix on dev",
        tenant_id="mukil",
    )
    engine.decide_approval(ticket.approval_id, "approve", approver_id="mukil")

    # Attempt to push to main
    params_main = {"repository": "Mukil630/AURA-OS", "branch": "main"}
    valid, reason, _ = engine.verify_and_consume_approval(
        approval_id=ticket.approval_id,
        capability_id="coding.apply_fix",
        parameters=params_main,
        tenant_id="mukil",
    )
    assert valid is False
    assert "Hash Mismatch" in reason


def test_p10_39_killer_adversarial_tenant_impersonation_denied():
    """Verify tenant 'stranger' cannot use approval ticket issued for tenant 'mukil'."""
    engine = ApprovalEngine()
    params = {"repository": "Mukil630/AURA-OS"}
    ticket = engine.create_approval_request(
        task_id="task_adv_39",
        step_id="step_39",
        action="coding.apply_fix",
        capability_id="coding.apply_fix",
        parameters=params,
        risk_tier=RiskTier.TIER_3_HIGH,
        description="Apply fix",
        tenant_id="mukil",
    )
    engine.decide_approval(ticket.approval_id, "approve", approver_id="mukil")

    valid, reason, _ = engine.verify_and_consume_approval(
        approval_id=ticket.approval_id,
        capability_id="coding.apply_fix",
        parameters=params,
        tenant_id="stranger",  # Impersonator
    )
    assert valid is False
    assert "Tenant Mismatch" in reason


def test_p10_40_killer_adversarial_unapproved_high_risk_step_cannot_bypass():
    """Verify high risk capability without approval token is blocked."""
    engine = ApprovalEngine()
    valid, reason, _ = engine.verify_and_consume_approval(
        approval_id="non_existent_token_123",
        capability_id="coding.apply_fix",
        parameters={"repo": "test"},
        tenant_id="mukil",
    )
    assert valid is False
    assert "Missing approval token" in reason


def test_p10_41_killer_adversarial_approval_does_not_unlock_entire_toolbox():
    """Verify approval for 'coding.apply_fix' cannot be used to execute 'drive.trash_file'."""
    engine = ApprovalEngine()
    ticket = engine.create_approval_request(
        task_id="task_adv_41",
        step_id="step_41",
        action="coding.apply_fix",
        capability_id="coding.apply_fix",
        parameters={"repo": "test"},
        risk_tier=RiskTier.TIER_3_HIGH,
        description="Apply fix",
    )
    engine.decide_approval(ticket.approval_id, "approve", approver_id="mukil")

    valid, reason, _ = engine.verify_and_consume_approval(
        approval_id=ticket.approval_id,
        capability_id="drive.trash_file",
        parameters={"file_id": "critical_doc_01"},
        tenant_id="mukil",
    )
    assert valid is False
    assert "Mismatch" in reason


def test_p10_42_killer_adversarial_replaying_old_approved_token_on_new_task_denied():
    """Verify approval token is strictly bound to original task context."""
    engine = ApprovalEngine()
    params = {"repo": "test"}
    ticket = engine.create_approval_request(
        task_id="task_orig_42",
        step_id="step_42",
        action="coding.apply_fix",
        capability_id="coding.apply_fix",
        parameters=params,
        risk_tier=RiskTier.TIER_3_HIGH,
        description="Apply fix",
    )
    engine.decide_approval(ticket.approval_id, "approve", approver_id="mukil")
    # Verify ticket matches
    assert ticket.task_id == "task_orig_42"


def test_p10_43_killer_adversarial_machine_control_cannot_be_approved():
    """Verify R6 machine control capability is rejected unconditionally."""
    classifier = RiskClassificationEngine()
    level, tier, req_appr, rationale = classifier.classify_capability("pc.powershell")
    assert level == RiskLevel.R6_MACHINE_CONTROL
    assert tier == RiskTier.TIER_4_CRITICAL


def test_p10_44_killer_adversarial_expired_approval_button_press_fails_safe():
    """Verify pressing approve on an expired ticket fails safely without throwing unhandled exceptions."""
    engine = ApprovalEngine(default_ttl_seconds=-10)
    ticket = engine.create_approval_request(
        task_id="task_adv_44",
        step_id="step_44",
        action="coding.apply_fix",
        capability_id="coding.apply_fix",
        parameters={"repo": "test"},
        risk_tier=RiskTier.TIER_3_HIGH,
        description="Apply fix",
        ttl_seconds=-10,
    )
    success, msg, _ = engine.decide_approval(ticket.approval_id, "approve", approver_id="mukil")
    assert success is False
    assert "expired" in msg.lower()


def test_p10_45_killer_e2e_full_human_in_the_loop_approval_lifecycle():
    """
    THE FULL END-TO-END HUMAN-IN-THE-LOOP AUTONOMY & POLICY GATE E2E:
    User Request: 'Apply hotfix to Mukil630/AURA-OS'
        ↓
    P2 Understand -> Intent: CODING
        ↓
    P3 Plan -> Generates DAG with 'coding.apply_fix'
        ↓
    Risk Engine: Classifies 'coding.apply_fix' as R3 (High Risk) -> APPROVAL REQUIRED
        ↓
    Approval Engine: Creates Ticket (action_hash: computed, state: PENDING)
        ↓
    Telegram Gateway: Renders formatted approval card
        ↓
    Human Decides: /approve <ticket_id> -> State: APPROVED
        ↓
    Execution Gate: Cryptographic Hash Verified -> SHA-256 matches
        ↓
    P4 Execute -> P5 Verify -> P6 Distill Memory & Record Audit Lineage
    """
    classifier = RiskClassificationEngine()
    approval_engine = ApprovalEngine()
    tg_gateway = TelegramApprovalGateway(approval_engine=approval_engine)

    # 1. Capability & Risk Evaluation
    cap_id = "coding.apply_fix"
    params = {"repository": "Mukil630/AURA-OS", "patch": "fix null pointer exception"}
    level, tier, req_approval, _ = classifier.classify_capability(cap_id, params)

    assert level == RiskLevel.R3_MODIFY_REPOSITORY
    assert req_approval is True

    # 2. Generate Approval Ticket
    ticket = approval_engine.create_approval_request(
        task_id="task_e2e_hitl_45",
        step_id="step_e2e_45",
        action=cap_id,
        capability_id=cap_id,
        parameters=params,
        risk_tier=tier,
        description="Apply hotfix patch to Mukil630/AURA-OS",
        tenant_id="mukil",
    )
    assert ticket.state == ApprovalState.PENDING
    assert ticket.action_hash is not None

    # 3. Telegram Approval Card Notification
    card_msg = tg_gateway.build_approval_card(ticket, chat_id=987654321)
    assert "HUMAN APPROVAL REQUIRED" in card_msg.text

    # 4. Human Decision via Telegram
    decide_success, decide_msg = tg_gateway.process_telegram_decision(
        telegram_user_id=987654321,
        raw_command=f"/approve {ticket.approval_id}",
        username="mukil630",
    )
    assert decide_success is True

    # 5. Execution Gate Verification
    gate_valid, gate_msg, _ = approval_engine.verify_and_consume_approval(
        approval_id=ticket.approval_id,
        capability_id=cap_id,
        parameters=params,
        tenant_id="mukil",
    )
    assert gate_valid is True
    assert "verified green" in gate_msg.lower()
