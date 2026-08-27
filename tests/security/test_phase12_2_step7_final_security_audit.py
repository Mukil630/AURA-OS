"""Phase 12.2 Step 7: Final Security Audit, Adversarial Attack & Bypass Verification Suite.
Attacks every dimension: Pickle/Serialization, Introspection, Path Traversal, Re-registration, Provider Confusion,
Deep Fuzzing, Synthetic Secret Diversity, Multi-Dimensional Approval Tampering, and Caller Boundaries.
"""
import copy
import json
import pickle
import pytest

from app.connectors.github.connector import GitHubConnector
from app.connectors.drive.connector import GoogleDriveConnector
from app.connectors.telegram.connector import TelegramConnector
from app.connectors.router import CapabilityRouter
from app.core.contracts.connector import ConnectorExecutionRequest
from app.core.contracts.credential import CredentialStatus, ProviderMismatchError
from app.core.enums import ConnectorType, RiskTier
from app.policy.approval_engine import compute_action_hash, ApprovalEngine
from app.security.sanitizer import SecretSanitizer
from app.security.vault import SecureSecretContainer, TenantCredentialVault


# ═════════════════════════════════════════════════════════════════════════════
# 1. SERIALIZATION, PICKLE & DEEPCOPY BYPASS ATTACKS (Tests 1 - 2)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_2_s7_01_pickle_and_copy_attacks_blocked():
    """ATTACK 1: Verify pickle.dumps, copy.copy, and copy.deepcopy permanently fail on SecureSecretContainer."""
    container = SecureSecretContainer(raw_value="ghp_super_confidential_token_999", tenant_id="tenant_A", provider=ConnectorType.GITHUB)

    with pytest.raises(TypeError) as exc_pickle:
        pickle.dumps(container)
    assert "cannot be pickled" in str(exc_pickle.value).lower()

    with pytest.raises(TypeError) as exc_copy:
        copy.copy(container)
    assert "cannot be shallow copied" in str(exc_copy.value).lower()

    with pytest.raises(TypeError) as exc_deepcopy:
        copy.deepcopy(container)
    assert "cannot be deep copied" in str(exc_deepcopy.value).lower()


def test_p12_2_s7_02_introspection_attack_model_dump_has_zero_secrets():
    """ATTACK 2: Object introspection via model_dump and __dict__ exposes zero secrets."""
    vault = TenantCredentialVault()
    contract = vault.register_credential(
        tenant_id="tenant_A",
        credential_ref="safe_metadata_ref",
        provider=ConnectorType.GITHUB,
        raw_secret="ghp_sensitive_raw_pat_111222",
    )

    dumped = contract.model_dump()
    assert "raw_secret" not in dumped
    assert "ghp_sensitive_raw_pat_111222" not in contract.model_dump_json()
    assert not hasattr(contract, "_secret_value")


# ═════════════════════════════════════════════════════════════════════════════
# 2. PATH TRAVERSAL & LIFECYCLE RE-REGISTRATION ATTACKS (Tests 3 - 4)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_p12_2_s7_03_path_traversal_ref_attacks_isolated():
    """ATTACK 3: Path traversal characters in credential_ref cannot escape tenant namespace."""
    vault = TenantCredentialVault()
    vault.register_credential("tenant_B", "github_key", ConnectorType.GITHUB, "ghp_target_secret_b")

    router = CapabilityRouter(credential_vault=vault)
    github_conn = GitHubConnector(is_mock=True)
    router.register_connector(github_conn)

    traversal_attacks = [
        "../../tenant_B/github_key",
        "../tenant_B/github_key",
        "tenant_B/github_key",
        "..%2F..%2Ftenant_B%2Fgithub_key",
    ]

    for attack_ref in traversal_attacks:
        req = ConnectorExecutionRequest(
            capability_id="github.list_failed_workflows",
            parameters={"repo": "Mukil630/AURA-OS"},
            credential_ref=attack_ref,
        )
        res = await router.dispatch(req, tenant_id="tenant_A")
        assert res.success is False
        assert res.status_code == 404
        assert "ghp_target_secret_b" not in (res.error_message or "")


def test_p12_2_s7_04_revoked_alias_re_registration_forbidden():
    """ATTACK 4: Once revoked, an alias cannot be re-registered to bypass revocation."""
    vault = TenantCredentialVault()
    vault.register_credential("tenant_A", "stolen_key", ConnectorType.GITHUB, "ghp_original_token")
    vault.update_status("tenant_A", "stolen_key", CredentialStatus.REVOKED)

    # Attempting to re-register the same alias with a new token must fail!
    with pytest.raises(ValueError) as exc_info:
        vault.register_credential("tenant_A", "stolen_key", ConnectorType.GITHUB, "ghp_new_replacement_token")
    assert "permanently revoked" in str(exc_info.value).lower()


# ═════════════════════════════════════════════════════════════════════════════
# 3. PROVIDER CONFUSION PERMUTATION MATRIX (Test 5)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_p12_2_s7_05_provider_confusion_permutation_matrix():
    """ATTACK 5: Full permutation matrix of cross-provider credential mismatch attempts."""
    vault = TenantCredentialVault()
    vault.register_credential("tenant_A", "gh_key", ConnectorType.GITHUB, "ghp_gh_token")
    vault.register_credential("tenant_A", "gd_key", ConnectorType.GOOGLE_DRIVE, "ya29.gd_token")
    vault.register_credential("tenant_A", "tg_key", ConnectorType.TELEGRAM, "12345:tg_token")

    router = CapabilityRouter(credential_vault=vault)
    github_conn = GitHubConnector(is_mock=True)
    drive_conn = GoogleDriveConnector(is_mock=True)
    tg_conn = TelegramConnector(is_mock=True)

    router.register_connector(github_conn)
    router.register_connector(drive_conn)
    router.register_connector(tg_conn)

    # Matrix of (capability, invalid_ref, expected_error_substring)
    mismatches = [
        ("github.list_failed_workflows", "gd_key", "cannot be used for 'github'"),
        ("github.list_failed_workflows", "tg_key", "cannot be used for 'github'"),
        ("drive.get_storage_info", "gh_key", "cannot be used for 'google_drive'"),
        ("drive.get_storage_info", "tg_key", "cannot be used for 'google_drive'"),
        ("telegram.send_message", "gh_key", "cannot be used for 'telegram'"),
        ("telegram.send_message", "gd_key", "cannot be used for 'telegram'"),
    ]

    for cap_id, ref, expected_err in mismatches:
        req = ConnectorExecutionRequest(
            capability_id=cap_id,
            parameters={"repo": "Mukil630/AURA-OS", "chat_id": 123, "text": "hi"},
            credential_ref=ref,
        )
        res = await router.dispatch(req, tenant_id="tenant_A")
        assert res.success is False
        assert res.status_code == 400
        assert expected_err in res.error_message


# ═════════════════════════════════════════════════════════════════════════════
# 4. DEEP FUZZING & SYNTHETIC SECRET DIVERSITY (Tests 6 - 7)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_p12_2_s7_06_fuzz_nested_injection_deep_arrays_and_dicts():
    """ATTACK 6: Fuzzing deeply nested dictionary, list, and tuple payloads."""
    vault = TenantCredentialVault()
    router = CapabilityRouter(credential_vault=vault)
    github_conn = GitHubConnector(is_mock=True)
    router.register_connector(github_conn)

    fuzz_payloads = [
        {"lvl1": {"lvl2": {"lvl3": {"lvl4": {"token": "ghp_deeply_nested_12345"}}}}},
        {"items": [[{"auth": "ya29.deep_array_token"}]]},
        {"settings": {"headers": [{"name": "Auth", "value": "Bearer ghp_token_in_list"}]}},
        {"query": {"filters": {"secret_access": "some_secret_key"}}},
    ]

    for payload in fuzz_payloads:
        req = ConnectorExecutionRequest(
            capability_id="github.list_failed_workflows",
            parameters=payload,
            credential_ref="github_prod_A",
        )
        res = await router.dispatch(req, tenant_id="tenant_A")
        assert res.success is False
        assert res.status_code == 422
        assert "Raw secrets are forbidden" in res.error_message


def test_p12_2_s7_07_synthetic_token_formats_sanitization_matrix():
    """ATTACK 7: Sanitization matrix covering diverse synthetic token formats."""
    synthetic_secrets = [
        "ghp_TEST_SECRET_AAAAAAAAAA_111111",
        "gho_TEST_SECRET_BBBBBBBBBB_222222",
        "ya29.TEST_SECRET_CCCCCCCCCC_333333",
        "987654321:TEST_SECRET_TELEGRAM_DDDDDDDDDDDDDDDDDDDDDDDDDDDDDD",
        "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.TEST_SECRET_EEEEEEEEEE.SIGNATURE",
    ]

    for sec in synthetic_secrets:
        raw_text = f"Error processing task: Authorization failed with {sec} on remote wire."
        clean = SecretSanitizer.sanitize_text(raw_text)
        assert sec not in clean, f"Secret {sec} was not redacted!"


# ═════════════════════════════════════════════════════════════════════════════
# 5. MULTI-DIMENSIONAL APPROVAL INTEGRITY & BOUNDARY AUDITS (Tests 8 - 10)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_2_s7_08_approval_tampering_all_dimensions_denied():
    """ATTACK 8: Tampering capability, params, ref, or tenant invalidates action hash."""
    engine = ApprovalEngine()
    req = engine.create_approval_request(
        task_id="tsk_01",
        step_id="stp_01",
        action="Deploy Fix",
        capability_id="github.list_failed_workflows",
        parameters={"repo": "Mukil630/AURA-OS", "credential_ref": "github_read_01"},
        risk_tier=RiskTier.TIER_2_MEDIUM,
        description="Deploy",
        tenant_id="tenant_A",
    )
    success, msg, approved = engine.decide_approval(req.approval_id, decision="approve", approver_id="mukil")
    assert success is True

    # 1. Tamper credential_ref
    hash_tampered_ref = compute_action_hash(
        "github.list_failed_workflows",
        {"repo": "Mukil630/AURA-OS", "credential_ref": "github_admin_01"},
        tenant_id="tenant_A",
    )
    assert hash_tampered_ref != approved.action_hash

    # 2. Tamper tenant_id
    hash_tampered_tenant = compute_action_hash(
        "github.list_failed_workflows",
        {"repo": "Mukil630/AURA-OS", "credential_ref": "github_read_01"},
        tenant_id="tenant_B",
    )
    assert hash_tampered_tenant != approved.action_hash

    # 3. Tamper capability
    hash_tampered_cap = compute_action_hash(
        "coding.apply_fix",
        {"repo": "Mukil630/AURA-OS", "credential_ref": "github_read_01"},
        tenant_id="tenant_A",
    )
    assert hash_tampered_cap != approved.action_hash


def test_p12_2_s7_09_caller_dependency_boundary_audit():
    """ATTACK 9: Architectural verification that get_raw_secret is called only inside CapabilityRouter."""
    import inspect
    from app.connectors.router import CapabilityRouter
    from app.security.vault import TenantCredentialVault

    # CapabilityRouter.dispatch contains get_raw_secret
    router_src = inspect.getsource(CapabilityRouter.dispatch)
    assert "container.get_raw_secret()" in router_src

    # TenantCredentialVault itself does not call get_raw_secret (returns container)
    vault_src = inspect.getsource(TenantCredentialVault.resolve)
    assert "get_raw_secret" not in vault_src


@pytest.mark.anyio
async def test_p12_2_s7_10_immutable_tenant_context_authority_invariance():
    """ATTACK 10: Invariant verification that authenticated TenantContext is the sole authority."""
    vault = TenantCredentialVault()
    vault.register_credential("tenant_A", "k1", ConnectorType.GITHUB, "ghp_sec_A")
    vault.register_credential("tenant_B", "k1", ConnectorType.GITHUB, "ghp_sec_B")

    router = CapabilityRouter(credential_vault=vault)
    github_conn = GitHubConnector(is_mock=True)
    router.register_connector(github_conn)

    # Regardless of what request headers/params say, caller tenant_id="tenant_A" resolves tenant_A key
    req = ConnectorExecutionRequest(
        capability_id="github.list_failed_workflows",
        parameters={"repo": "test", "tenant_id": "tenant_B", "user_id": "tenant_B"},
        credential_ref="k1",
    )
    res_a = await router.dispatch(req, tenant_id="tenant_A")
    assert res_a.success is True
    assert res_a.status_code == 200
