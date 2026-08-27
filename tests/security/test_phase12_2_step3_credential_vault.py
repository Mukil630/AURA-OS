"""Dedicated Unit and Adversarial Test Suite for Phase 12.2 Step 3: TenantCredentialVault & SecureSecretContainer."""
import json
import pytest

from app.core.contracts.credential import (
    CredentialNotFoundError,
    CredentialRefContract,
    CredentialRevokedError,
    CredentialStatus,
    ProviderMismatchError,
)
from app.core.enums import ConnectorType
from app.security.vault import SecureSecretContainer, TenantCredentialVault, mask_secret


# ═════════════════════════════════════════════════════════════════════════════
# 1. SECURE SECRET CONTAINER ANTI-LEAK TESTS (Tests 1 - 5)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_2_s3_01_secure_secret_container_repr_and_str_redacted():
    """Verify that SecureSecretContainer.__repr__ and __str__ NEVER expose raw secrets."""
    raw_token = "ghp_1234567890abcdef1234567890abcdef"
    container = SecureSecretContainer(raw_value=raw_token, tenant_id="tenant_A", provider=ConnectorType.GITHUB)

    assert str(container) == "<SecureSecretContainer: REDACTED>"
    assert repr(container) == "<SecureSecretContainer: REDACTED>"
    assert raw_token not in str(container)
    assert raw_token not in repr(container)


def test_p12_2_s3_02_secure_secret_container_cannot_be_json_serialized():
    """Verify that json.dumps rejects SecureSecretContainer with a TypeError."""
    container = SecureSecretContainer(raw_value="ya29.secret_oauth_token", tenant_id="tenant_A", provider=ConnectorType.GOOGLE_DRIVE)
    with pytest.raises(TypeError):
        json.dumps(container)


def test_p12_2_s3_03_secure_secret_container_equality_fails_safe():
    """Verify value-based equality is permanently disabled on containers."""
    c1 = SecureSecretContainer(raw_value="secret_key_1", tenant_id="tenant_A", provider=ConnectorType.GITHUB)
    c2 = SecureSecretContainer(raw_value="secret_key_1", tenant_id="tenant_A", provider=ConnectorType.GITHUB)
    assert (c1 == c2) is False


def test_p12_2_s3_04_secure_secret_container_empty_raw_value_rejected():
    """Verify container rejects empty or whitespace-only raw secret values."""
    with pytest.raises(ValueError):
        SecureSecretContainer(raw_value="", tenant_id="tenant_A", provider=ConnectorType.GITHUB)
    with pytest.raises(ValueError):
        SecureSecretContainer(raw_value="   ", tenant_id="tenant_A", provider=ConnectorType.GITHUB)


def test_p12_2_s3_05_secure_secret_container_get_raw_secret_returns_value():
    """Verify get_raw_secret extracts the exact in-memory token string for wire transport."""
    raw = "123456789:ABCDefGhIjKlMnOpQrStUvWxYz_123456"
    container = SecureSecretContainer(raw_value=raw, tenant_id="tenant_A", provider=ConnectorType.TELEGRAM)
    assert container.get_raw_secret() == raw


# ═════════════════════════════════════════════════════════════════════════════
# 2. TENANT VAULT ISOLATION & PROVIDER BINDING (Tests 6 - 10)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_2_s3_06_tenant_a_registers_and_resolves_own_credential():
    """Verify Tenant A can register a reference alias and resolve its secret."""
    vault = TenantCredentialVault()
    contract = vault.register_credential(
        tenant_id="tenant_A",
        credential_ref="github_prod_01",
        provider=ConnectorType.GITHUB,
        raw_secret="ghp_my_secret_token_12345",
        purpose="repo_ci",
    )
    assert contract.credential_ref == "github_prod_01"
    assert contract.tenant_id == "tenant_A"
    assert contract.status == CredentialStatus.ACTIVE
    assert "ghp_****2345" in contract.masked_preview

    container = vault.resolve("tenant_A", "github_prod_01", provider=ConnectorType.GITHUB)
    assert container.get_raw_secret() == "ghp_my_secret_token_12345"


def test_p12_2_s3_07_tenant_a_attempts_to_resolve_tenant_b_credential_returns_404():
    """
    CRITICAL ISOLATION TEST:
    Tenant A querying Tenant B's credential_ref raises 404 (zero existence leakage).
    """
    vault = TenantCredentialVault()
    vault.register_credential(
        tenant_id="tenant_B",
        credential_ref="github_secret_b",
        provider=ConnectorType.GITHUB,
        raw_secret="ghp_tenant_b_confidential_key",
    )

    with pytest.raises(CredentialNotFoundError) as exc_info:
        vault.resolve("tenant_A", "github_secret_b", provider=ConnectorType.GITHUB)
    assert exc_info.value.status_code == 404


def test_p12_2_s3_08_unknown_credential_ref_returns_404():
    """Verify querying an unconfigured reference raises 404."""
    vault = TenantCredentialVault()
    with pytest.raises(CredentialNotFoundError) as exc_info:
        vault.resolve("tenant_A", "non_existent_ref", provider=ConnectorType.GITHUB)
    assert exc_info.value.status_code == 404


def test_p12_2_s3_09_provider_mismatch_github_token_used_for_drive_returns_400():
    """Verify resolving a GitHub credential when asking for Google Drive raises 400."""
    vault = TenantCredentialVault()
    vault.register_credential(
        tenant_id="tenant_A",
        credential_ref="github_prod_01",
        provider=ConnectorType.GITHUB,
        raw_secret="ghp_github_token_abc",
    )

    with pytest.raises(ProviderMismatchError) as exc_info:
        vault.resolve("tenant_A", "github_prod_01", provider=ConnectorType.GOOGLE_DRIVE)
    assert exc_info.value.status_code == 400
    assert "cannot be used for 'google_drive'" in exc_info.value.detail


def test_p12_2_s3_10_cross_tenant_collision_identical_ref_names_resolve_isolated():
    """
    Verify Tenant A and Tenant B can both use 'prod_key' without namespace collisions.
    Each resolves strictly their own isolated secret.
    """
    vault = TenantCredentialVault()
    vault.register_credential("tenant_A", "prod_key", ConnectorType.GITHUB, "ghp_secret_A_999")
    vault.register_credential("tenant_B", "prod_key", ConnectorType.GITHUB, "ghp_secret_B_888")

    cont_a = vault.resolve("tenant_A", "prod_key", ConnectorType.GITHUB)
    cont_b = vault.resolve("tenant_B", "prod_key", ConnectorType.GITHUB)

    assert cont_a.get_raw_secret() == "ghp_secret_A_999"
    assert cont_b.get_raw_secret() == "ghp_secret_B_888"
    assert cont_a.get_raw_secret() != cont_b.get_raw_secret()


# ═════════════════════════════════════════════════════════════════════════════
# 3. CREDENTIAL LIFECYCLE & METADATA PURITY (Tests 11 - 15)
# ═════════════════════════════════════════════════════════════════════════════

def test_p12_2_s3_11_revoked_credential_resolution_raises_403():
    """Verify resolving a REVOKED credential raises 403 immediately."""
    vault = TenantCredentialVault()
    vault.register_credential(
        tenant_id="tenant_A",
        credential_ref="compromised_key",
        provider=ConnectorType.GITHUB,
        raw_secret="ghp_compromised_token",
        status=CredentialStatus.REVOKED,
    )

    with pytest.raises(CredentialRevokedError) as exc_info:
        vault.resolve("tenant_A", "compromised_key", ConnectorType.GITHUB)
    assert exc_info.value.status_code == 403


def test_p12_2_s3_12_disabled_credential_resolution_raises_403():
    """Verify resolving a DISABLED credential raises 403."""
    vault = TenantCredentialVault()
    vault.register_credential(
        tenant_id="tenant_A",
        credential_ref="suspended_key",
        provider=ConnectorType.GOOGLE_DRIVE,
        raw_secret="ya29.suspended_oauth",
        status=CredentialStatus.DISABLED,
    )

    with pytest.raises(CredentialRevokedError) as exc_info:
        vault.resolve("tenant_A", "suspended_key", ConnectorType.GOOGLE_DRIVE)
    assert exc_info.value.status_code == 403


def test_p12_2_s3_13_revoked_credential_resurrection_forbidden():
    """Verify that a revoked credential can NEVER be transitioned back to ACTIVE."""
    vault = TenantCredentialVault()
    vault.register_credential("tenant_A", "key_x", ConnectorType.GITHUB, "ghp_token_x")

    # Revoke it
    vault.update_status("tenant_A", "key_x", CredentialStatus.REVOKED)

    # Attempt resurrection
    with pytest.raises(ValueError) as exc_info:
        vault.update_status("tenant_A", "key_x", CredentialStatus.ACTIVE)
    assert "resurrected" in str(exc_info.value).lower()


def test_p12_2_s3_14_public_metadata_contract_contains_zero_raw_secrets():
    """Verify metadata model dump contains only masked preview and zero raw secret strings."""
    vault = TenantCredentialVault()
    contract = vault.register_credential(
        tenant_id="tenant_A",
        credential_ref="public_ref",
        provider=ConnectorType.GITHUB,
        raw_secret="ghp_very_confidential_raw_pat_12345",
    )
    dumped = contract.model_dump()
    assert "raw_secret" not in dumped
    assert "ghp_very_confidential_raw_pat_12345" not in contract.model_dump_json()
    assert dumped["masked_preview"] == "ghp_****2345"


def test_p12_2_s3_15_list_credentials_strictly_scoped_to_tenant():
    """Verify listing credentials for Tenant A leaks zero Tenant B references."""
    vault = TenantCredentialVault()
    vault.register_credential("tenant_A", "ref_a1", ConnectorType.GITHUB, "ghp_a1")
    vault.register_credential("tenant_A", "ref_a2", ConnectorType.GOOGLE_DRIVE, "ya29_a2")
    vault.register_credential("tenant_B", "ref_b1", ConnectorType.GITHUB, "ghp_b1")

    list_a = vault.list_credentials("tenant_A")
    list_b = vault.list_credentials("tenant_B")

    assert len(list_a) == 2
    assert all(c.tenant_id == "tenant_A" for c in list_a)
    assert len(list_b) == 1
    assert list_b[0].credential_ref == "ref_b1"
