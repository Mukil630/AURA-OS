"""Dedicated Integration and Adversarial Test Suite for Phase 12.2 Step 4: CapabilityRouter & TenantCredentialVault Integration."""
import pytest

from app.connectors.github.connector import GitHubConnector
from app.connectors.drive.connector import GoogleDriveConnector
from app.connectors.telegram.connector import TelegramConnector
from app.connectors.router import CapabilityRouter
from app.core.contracts.connector import ConnectorExecutionRequest
from app.core.contracts.credential import CredentialStatus
from app.core.enums import ConnectorType
from app.security.vault import TenantCredentialVault


# ═════════════════════════════════════════════════════════════════════════════
# 1. CAPABILITY ROUTER & VAULT INTEGRATION TESTS (Tests 1 - 7)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_p12_2_s4_01_github_capability_resolves_correct_vault_credential():
    """Verify GitHub capability dispatches using secret resolved from TenantCredentialVault."""
    vault = TenantCredentialVault()
    vault.register_credential(
        tenant_id="tenant_A",
        credential_ref="github_prod_01",
        provider=ConnectorType.GITHUB,
        raw_secret="ghp_real_secret_token_12345",
    )

    router = CapabilityRouter(credential_vault=vault)
    github_conn = GitHubConnector(is_mock=True)
    router.register_connector(github_conn)

    request = ConnectorExecutionRequest(
        capability_id="github.list_failed_workflows",
        parameters={"repo": "Mukil630/AURA-OS"},
        credential_ref="github_prod_01",
        tenant_id="tenant_A",
    )

    res = await router.dispatch(request, tenant_id="tenant_A")
    assert res.success is True
    assert res.status_code == 200
    assert "ghp_real_secret_token_12345" not in str(res.data)


@pytest.mark.anyio
async def test_p12_2_s4_02_drive_capability_resolves_correct_vault_credential():
    """Verify Google Drive capability dispatches using Drive secret from vault."""
    vault = TenantCredentialVault()
    vault.register_credential(
        tenant_id="tenant_A",
        credential_ref="drive_vault_01",
        provider=ConnectorType.GOOGLE_DRIVE,
        raw_secret="ya29.google_oauth_token_secret_123",
    )

    router = CapabilityRouter(credential_vault=vault)
    drive_conn = GoogleDriveConnector(is_mock=True)
    router.register_connector(drive_conn)

    request = ConnectorExecutionRequest(
        capability_id="drive.get_storage_info",
        parameters={},
        credential_ref="drive_vault_01",
        tenant_id="tenant_A",
    )

    res = await router.dispatch(request, tenant_id="tenant_A")
    assert res.success is True
    assert res.status_code == 200
    assert "ya29.google_oauth_token_secret_123" not in str(res.data)


@pytest.mark.anyio
async def test_p12_2_s4_03_telegram_capability_resolves_correct_vault_credential():
    """Verify Telegram capability dispatches using Telegram bot token from vault."""
    vault = TenantCredentialVault()
    vault.register_credential(
        tenant_id="tenant_A",
        credential_ref="telegram_bot_01",
        provider=ConnectorType.TELEGRAM,
        raw_secret="123456789:ABCDEF_secret_bot_token_999",
    )

    router = CapabilityRouter(credential_vault=vault)
    tg_conn = TelegramConnector(is_mock=True)
    router.register_connector(tg_conn)

    request = ConnectorExecutionRequest(
        capability_id="telegram.send_message",
        parameters={"chat_id": 12345, "text": "Hello Mukil!"},
        credential_ref="telegram_bot_01",
        tenant_id="tenant_A",
    )

    res = await router.dispatch(request, tenant_id="tenant_A")
    assert res.success is True
    assert res.status_code == 200
    assert "123456789:ABCDEF" not in str(res.data)


@pytest.mark.anyio
async def test_p12_2_s4_04_wrong_provider_fails_fast_400():
    """Verify attempting to dispatch a GitHub credential to a Drive capability returns 400."""
    vault = TenantCredentialVault()
    vault.register_credential(
        tenant_id="tenant_A",
        credential_ref="github_key_01",
        provider=ConnectorType.GITHUB,
        raw_secret="ghp_github_token_xyz",
    )

    router = CapabilityRouter(credential_vault=vault)
    drive_conn = GoogleDriveConnector(is_mock=True)
    router.register_connector(drive_conn)

    # Request drive capability using github credential
    request = ConnectorExecutionRequest(
        capability_id="drive.get_storage_info",
        parameters={},
        credential_ref="github_key_01",
        tenant_id="tenant_A",
    )

    res = await router.dispatch(request, tenant_id="tenant_A")
    assert res.success is False
    assert res.status_code == 400
    assert "cannot be used for 'google_drive'" in res.error_message


@pytest.mark.anyio
async def test_p12_2_s4_05_cross_tenant_credential_ref_fails_404():
    """
    CRITICAL ISOLATION TEST:
    Tenant A attempting to dispatch with Tenant B's credential_ref returns 404 (zero leakage).
    """
    vault = TenantCredentialVault()
    vault.register_credential(
        tenant_id="tenant_B",
        credential_ref="secret_key_b",
        provider=ConnectorType.GITHUB,
        raw_secret="ghp_tenant_b_key",
    )

    router = CapabilityRouter(credential_vault=vault)
    github_conn = GitHubConnector(is_mock=True)
    router.register_connector(github_conn)

    request = ConnectorExecutionRequest(
        capability_id="github.list_failed_workflows",
        parameters={"repo": "Mukil630/AURA-OS"},
        credential_ref="secret_key_b",
        tenant_id="tenant_A",  # Tenant A attempts to use Tenant B's ref
    )

    res = await router.dispatch(request, tenant_id="tenant_A")
    assert res.success is False
    assert res.status_code == 404
    assert "not found for tenant 'tenant_A'" in res.error_message


@pytest.mark.anyio
async def test_p12_2_s4_06_revoked_credential_fails_fast_403():
    """Verify dispatching with a REVOKED credential returns 403 Forbidden."""
    vault = TenantCredentialVault()
    vault.register_credential(
        tenant_id="tenant_A",
        credential_ref="compromised_key",
        provider=ConnectorType.GITHUB,
        raw_secret="ghp_compromised_pat",
        status=CredentialStatus.REVOKED,
    )

    router = CapabilityRouter(credential_vault=vault)
    github_conn = GitHubConnector(is_mock=True)
    router.register_connector(github_conn)

    request = ConnectorExecutionRequest(
        capability_id="github.list_failed_workflows",
        parameters={"repo": "Mukil630/AURA-OS"},
        credential_ref="compromised_key",
        tenant_id="tenant_A",
    )

    res = await router.dispatch(request, tenant_id="tenant_A")
    assert res.success is False
    assert res.status_code == 403
    assert "revoked" in res.error_message.lower()


@pytest.mark.anyio
async def test_p12_2_s4_07_disabled_credential_fails_fast_403():
    """Verify dispatching with a DISABLED credential returns 403 Forbidden."""
    vault = TenantCredentialVault()
    vault.register_credential(
        tenant_id="tenant_A",
        credential_ref="frozen_key",
        provider=ConnectorType.GITHUB,
        raw_secret="ghp_frozen_pat",
        status=CredentialStatus.DISABLED,
    )

    router = CapabilityRouter(credential_vault=vault)
    github_conn = GitHubConnector(is_mock=True)
    router.register_connector(github_conn)

    request = ConnectorExecutionRequest(
        capability_id="github.list_failed_workflows",
        parameters={"repo": "Mukil630/AURA-OS"},
        credential_ref="frozen_key",
        tenant_id="tenant_A",
    )

    res = await router.dispatch(request, tenant_id="tenant_A")
    assert res.success is False
    assert res.status_code == 403
    assert "disabled" in res.error_message.lower()


# ═════════════════════════════════════════════════════════════════════════════
# 2. ADVERSARIAL LEAKAGE & PARAMETER DEFENSE TESTS (Tests 8 - 13)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
async def test_p12_2_s4_08_missing_unregistered_credential_ref_fails_404():
    """Verify dispatch with non-existent credential_ref returns 404."""
    vault = TenantCredentialVault()
    router = CapabilityRouter(credential_vault=vault)
    github_conn = GitHubConnector(is_mock=True)
    router.register_connector(github_conn)

    request = ConnectorExecutionRequest(
        capability_id="github.list_failed_workflows",
        parameters={"repo": "Mukil630/AURA-OS"},
        credential_ref="non_existent_ref_123",
        tenant_id="tenant_A",
    )

    res = await router.dispatch(request, tenant_id="tenant_A")
    assert res.success is False
    assert res.status_code == 404


@pytest.mark.anyio
async def test_p12_2_s4_09_llm_supplied_tenant_in_param_cannot_override_trusted_context():
    """
    Verify caller's trusted TenantContext prevails over any LLM-injected tenant parameter.
    """
    vault = TenantCredentialVault()
    vault.register_credential("tenant_A", "valid_key", ConnectorType.GITHUB, "ghp_secret_A")
    vault.register_credential("tenant_B", "valid_key", ConnectorType.GITHUB, "ghp_secret_B")

    router = CapabilityRouter(credential_vault=vault)
    github_conn = GitHubConnector(is_mock=True)
    router.register_connector(github_conn)

    # LLM crafts parameters claiming tenant_id = tenant_B, but caller is tenant_A
    request = ConnectorExecutionRequest(
        capability_id="github.list_failed_workflows",
        parameters={"repo": "Mukil630/AURA-OS", "tenant_id": "tenant_B"},
        credential_ref="valid_key",
    )

    res = await router.dispatch(request, tenant_id="tenant_A")
    # Must execute under tenant_A authority
    assert res.success is True
    assert res.status_code == 200


@pytest.mark.anyio
async def test_p12_2_s4_10_llm_supplied_raw_token_in_params_rejected_422():
    """
    THE KILLER PARAMETER TEST:
    If a user prompt or LLM hallucination passes a raw secret token in parameters:
    {"api_key": "ghp_123456789012345678901234567890"}
    Router must reject before dispatch with 422 Unprocessable Entity!
    """
    vault = TenantCredentialVault()
    router = CapabilityRouter(credential_vault=vault)
    github_conn = GitHubConnector(is_mock=True)
    router.register_connector(github_conn)

    request = ConnectorExecutionRequest(
        capability_id="github.list_failed_workflows",
        parameters={"repo": "Mukil630/AURA-OS", "api_key": "ghp_123456789012345678901234567890"},
    )

    res = await router.dispatch(request, tenant_id="tenant_A")
    assert res.success is False
    assert res.status_code == 422
    assert "Raw secrets are forbidden" in res.error_message


@pytest.mark.anyio
async def test_p12_2_s4_11_raw_secret_never_appears_in_capability_result():
    """Verify result payload and summary contain zero raw secret tokens."""
    vault = TenantCredentialVault()
    vault.register_credential("tenant_A", "key_1", ConnectorType.GITHUB, "ghp_super_secret_token_12345")

    router = CapabilityRouter(credential_vault=vault)
    github_conn = GitHubConnector(is_mock=True)
    router.register_connector(github_conn)

    request = ConnectorExecutionRequest(
        capability_id="github.list_failed_workflows",
        parameters={"repo": "Mukil630/AURA-OS"},
        credential_ref="key_1",
    )

    res = await router.dispatch(request, tenant_id="tenant_A")
    assert "ghp_super_secret_token_12345" not in str(res.data)
    assert "ghp_super_secret_token_12345" not in str(res.error_message or "")


@pytest.mark.anyio
async def test_p12_2_s4_12_raw_secret_sanitized_in_error_messages():
    """Verify that if an error message echoes a raw token, router sanitizes it."""
    vault = TenantCredentialVault()
    router = CapabilityRouter(credential_vault=vault)

    class FlakyConnector(GitHubConnector):
        async def execute_capability(self, request, credentials=None):
            from app.core.contracts.connector import ConnectorExecutionResult
            # Mock upstream error echoing token
            return ConnectorExecutionResult(
                request_id=request.request_id,
                capability_id=request.capability_id,
                success=False,
                status_code=500,
                error_message="Upstream failed with token: ghp_leakedtoken1234567890abcdef",
            )

    flaky = FlakyConnector(is_mock=True)
    router.register_connector(flaky)

    request = ConnectorExecutionRequest(capability_id="github.list_failed_workflows", parameters={"repo": "Mukil630/AURA-OS"})
    res = await router.dispatch(request, tenant_id="tenant_A")
    assert res.success is False
    assert "ghp_leakedtoken1234567890abcdef" not in res.error_message
    assert "[REDACTED_GITHUB_TOKEN]" in res.error_message or "ghp_****cdef" in res.error_message


@pytest.mark.anyio
async def test_p12_2_s4_13_existing_capabilities_without_explicit_ref_continue_working():
    """Verify backward compatibility for mock tests where credential_ref is omitted."""
    router = CapabilityRouter()
    github_conn = GitHubConnector(is_mock=True)
    router.register_connector(github_conn)

    request = ConnectorExecutionRequest(
        capability_id="github.list_failed_workflows",
        parameters={"repo": "Mukil630/AURA-OS"},
    )
    res = await router.dispatch(request)
    assert res.success is True
    assert res.status_code == 200
