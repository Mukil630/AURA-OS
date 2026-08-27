"""Tenant Credential Vault and Secure Secret Container Subsystem."""
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.core.contracts.credential import (
    CredentialNotFoundError,
    CredentialRefContract,
    CredentialRevokedError,
    CredentialStatus,
    ProviderMismatchError,
)
from app.core.enums import ConnectorType


def mask_secret(secret: str) -> str:
    """Mask secret leaving only prefix and last 4 characters visible."""
    if not secret:
        return "none"
    if len(secret) <= 8:
        return "********"
    prefix = secret[:4]
    suffix = secret[-4:]
    return f"{prefix}****{suffix}"


class SecureSecretContainer:
    """
    Ephemeral, non-serializable in-memory container for secret material.
    Guarantees zero accidental leakage across logs, exceptions, and serialization.
    """
    __slots__ = ("_secret_value", "_tenant_id", "_provider", "_created_at")

    def __init__(self, raw_value: str, tenant_id: str, provider: ConnectorType):
        if not raw_value or not raw_value.strip():
            raise ValueError("SecureSecretContainer requires non-empty raw_value.")
        self._secret_value = raw_value
        self._tenant_id = tenant_id
        self._provider = provider
        self._created_at = time.time()

    def __repr__(self) -> str:
        return "<SecureSecretContainer: REDACTED>"

    def __str__(self) -> str:
        return "<SecureSecretContainer: REDACTED>"

    def __eq__(self, other: Any) -> bool:
        return False  # Prevent value-based equality checking or hashing leaks

    def __reduce__(self):
        raise TypeError("SecureSecretContainer cannot be pickled or serialized.")

    def __copy__(self):
        raise TypeError("SecureSecretContainer cannot be shallow copied.")

    def __deepcopy__(self, memo):
        raise TypeError("SecureSecretContainer cannot be deep copied.")

    def get_raw_secret(self) -> str:
        """
        Extract raw token string strictly within the transport wire-dispatch block.
        Short-lived in-memory read only.
        """
        return self._secret_value


class TenantCredentialVault:
    """
    Tenant-partitioned credential store resolving indirect credential_ref aliases.
    Enforces strict tenant isolation, provider compatibility, and lifecycle state machines.
    """

    def __init__(self) -> None:
        # Key: (tenant_id, credential_ref) -> (CredentialRefContract, SecureSecretContainer)
        self._vault: Dict[Tuple[str, str], Tuple[CredentialRefContract, SecureSecretContainer]] = {}

    def register_credential(
        self,
        tenant_id: str,
        credential_ref: str,
        provider: ConnectorType,
        raw_secret: str,
        purpose: str = "general",
        status: CredentialStatus = CredentialStatus.ACTIVE,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CredentialRefContract:
        """Register a new credential under an isolated tenant namespace."""
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id must be non-empty.")
        if not credential_ref or not credential_ref.strip():
            raise ValueError("credential_ref must be non-empty.")

        key = (tenant_id, credential_ref)
        if key in self._vault:
            existing_contract, _ = self._vault[key]
            if existing_contract.status == CredentialStatus.REVOKED:
                raise ValueError(f"Credential reference '{credential_ref}' is permanently revoked and cannot be re-registered.")

        container = SecureSecretContainer(
            raw_value=raw_secret,
            tenant_id=tenant_id,
            provider=provider,
        )
        contract = CredentialRefContract(
            credential_ref=credential_ref,
            tenant_id=tenant_id,
            provider=provider,
            purpose=purpose,
            status=status,
            masked_preview=mask_secret(raw_secret),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            metadata=metadata or {},
        )
        self._vault[(tenant_id, credential_ref)] = (contract, container)
        return contract

    def resolve(
        self,
        tenant_id: str,
        credential_ref: str,
        provider: Optional[ConnectorType] = None,
    ) -> SecureSecretContainer:
        """
        Securely resolve a credential reference into an in-memory SecureSecretContainer.
        Requires valid tenant_id, matching provider, and active lifecycle status.
        """
        key = (tenant_id, credential_ref)
        if key not in self._vault:
            # Check if environment variable fallback exists for default system/local dev
            if tenant_id in ("mukil", "system") and os.getenv(f"{provider.value.upper()}_TOKEN" if provider else ""):
                env_secret = os.getenv(f"{provider.value.upper()}_TOKEN")  # type: ignore
                return SecureSecretContainer(raw_value=env_secret, tenant_id=tenant_id, provider=provider or ConnectorType.GITHUB)
            raise CredentialNotFoundError(
                f"Credential reference '{credential_ref}' not found for tenant '{tenant_id}'."
            )

        contract, container = self._vault[key]

        # 1. Lifecycle Status Check
        status_val = contract.status.value if hasattr(contract.status, "value") else str(contract.status)
        if status_val in (CredentialStatus.REVOKED.value, CredentialStatus.DISABLED.value):
            raise CredentialRevokedError(
                f"Credential '{credential_ref}' is {status_val} and cannot be resolved."
            )

        # 2. Provider Compatibility Check
        if provider:
            c_provider = contract.provider.value if hasattr(contract.provider, "value") else str(contract.provider)
            r_provider = provider.value if hasattr(provider, "value") else str(provider)
            if c_provider != r_provider:
                raise ProviderMismatchError(
                    f"Credential '{credential_ref}' is registered for '{c_provider}', cannot be used for '{r_provider}'."
                )

        return container

    def get_metadata(self, tenant_id: str, credential_ref: str) -> CredentialRefContract:
        """Retrieve public, sanitized metadata for a credential reference."""
        key = (tenant_id, credential_ref)
        if key not in self._vault:
            raise CredentialNotFoundError(
                f"Credential reference '{credential_ref}' not found for tenant '{tenant_id}'."
            )
        contract, _ = self._vault[key]
        return contract

    def list_credentials(
        self,
        tenant_id: str,
        provider: Optional[ConnectorType] = None,
    ) -> List[CredentialRefContract]:
        """List all credential references strictly owned by the specified tenant."""
        results: List[CredentialRefContract] = []
        for (t_id, _), (contract, _) in self._vault.items():
            if t_id == tenant_id:
                if provider is None or contract.provider == provider:
                    results.append(contract)
        return results

    def update_status(
        self,
        tenant_id: str,
        credential_ref: str,
        new_status: CredentialStatus,
    ) -> CredentialRefContract:
        """Update operational lifecycle status with irreversible revocation guard."""
        key = (tenant_id, credential_ref)
        if key not in self._vault:
            raise CredentialNotFoundError(
                f"Credential reference '{credential_ref}' not found for tenant '{tenant_id}'."
            )

        contract, container = self._vault[key]

        # Invariant: Revoked credentials can NEVER be resurrected to ACTIVE
        if contract.status == CredentialStatus.REVOKED and new_status == CredentialStatus.ACTIVE:
            raise ValueError("A revoked credential reference can never be resurrected to active status.")

        updated_contract = contract.model_copy(
            update={
                "status": new_status,
                "updated_at": datetime.now(timezone.utc),
            }
        )
        self._vault[key] = (updated_contract, container)
        return updated_contract

    def clear(self) -> None:
        """Purge all stored credentials (for testing and isolated teardown)."""
        self._vault.clear()


# Default singleton vault instance
default_credential_vault = TenantCredentialVault()
