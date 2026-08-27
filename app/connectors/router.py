"""Capability Router and Dispatch Coordinator across External Connectors."""
from typing import Any, Dict, List, Optional

from app.connectors.credential_manager import CredentialManager
from app.connectors.policy import ConnectorPolicyEngine
from app.core.contracts.connector import (
    CapabilityContract,
    ConnectorContract,
    ConnectorExecutionRequest,
    ConnectorExecutionResult,
)
from app.core.contracts.credential import (
    CredentialNotFoundError,
    CredentialRevokedError,
    ProviderMismatchError,
)
from app.core.interfaces.connector import IConnector, IConnectorRegistry
from app.security.sanitizer import SecretSanitizer
from app.security.vault import TenantCredentialVault, default_credential_vault


def _contains_raw_secrets(data: Any) -> bool:
    """Recursively check whether a parameter payload contains raw secret tokens or forbidden key names."""
    sensitive_substrings = ["secret", "token", "password", "api_key", "access_token", "auth_token", "private_key"]
    if isinstance(data, dict):
        for k, v in data.items():
            k_lower = str(k).lower()
            if any(sub in k_lower for sub in sensitive_substrings):
                return True
            if _contains_raw_secrets(v):
                return True
    elif isinstance(data, (list, tuple, set)):
        for item in data:
            if _contains_raw_secrets(item):
                return True
    elif isinstance(data, str):
        if (
            data.startswith("ghp_")
            or data.startswith("gho_")
            or data.startswith("ghu_")
            or data.startswith("ghs_")
            or data.startswith("ghr_")
            or data.startswith("ya29.")
            or data.startswith("Bearer ")
        ):
            return True
    return False


class CapabilityRouter(IConnectorRegistry):
    """
    Central Capability Router and Security Gateway.
    Maps high-level agent capability requests to physical connectors,
    enforcing kill-switch policies, rate limiting, and credential isolation.
    """

    def __init__(
        self,
        credential_manager: Optional[CredentialManager] = None,
        credential_vault: Optional[TenantCredentialVault] = None,
        policy_engine: Optional[ConnectorPolicyEngine] = None,
    ):
        self._connectors: Dict[str, IConnector] = {}
        self._capability_map: Dict[str, IConnector] = {}
        self.credential_manager = credential_manager or CredentialManager()
        self.credential_vault = credential_vault or default_credential_vault
        self.policy_engine = policy_engine or ConnectorPolicyEngine()

    def register_connector(self, connector: IConnector) -> None:
        """Register a connector and index its capabilities."""
        self._connectors[connector.connector_id] = connector
        for cap in connector.list_capabilities():
            self._capability_map[cap.capability_id] = connector

    def get_connector(self, connector_id: str) -> Optional[IConnector]:
        return self._connectors.get(connector_id)

    def get_connector_for_capability(self, capability_id: str) -> Optional[IConnector]:
        return self._capability_map.get(capability_id)

    def list_connectors(self) -> List[ConnectorContract]:
        return [c.get_contract() for c in self._connectors.values()]

    def list_capabilities(self) -> List[CapabilityContract]:
        all_caps = []
        for conn in self._connectors.values():
            all_caps.extend(conn.list_capabilities())
        return all_caps

    async def dispatch(
        self,
        request: ConnectorExecutionRequest,
        user_id: str = "system",
        tenant_id: Optional[str] = None,
        credential_ref: Optional[str] = None,
    ) -> ConnectorExecutionResult:
        """
        Securely dispatch capability request through policy checks and credential injection.
        Guarantees raw secret isolation and provider validation.
        """
        cap_id = request.capability_id

        # 0. Raw Secret Invariant Check (Reject raw secret tokens in parameters, including nested structures)
        if _contains_raw_secrets(request.parameters):
            return ConnectorExecutionResult(
                request_id=request.request_id,
                capability_id=cap_id,
                success=False,
                status_code=422,
                error_message="Raw secrets are forbidden in task parameters. Use credential_ref.",
            )

        # 1. Capability Resolution
        connector = self.get_connector_for_capability(cap_id)
        if not connector:
            return ConnectorExecutionResult(
                request_id=request.request_id,
                capability_id=cap_id,
                success=False,
                status_code=404,
                error_message=f"No connector registered for capability '{cap_id}'.",
            )

        # 2. Emergency Kill-Switch Check
        if not self.policy_engine.is_connector_enabled(connector.connector_id):
            return ConnectorExecutionResult(
                request_id=request.request_id,
                capability_id=cap_id,
                success=False,
                status_code=503,
                error_message=f"Connector '{connector.connector_id}' is disabled by emergency kill-switch policy.",
            )

        # 3. Capability Blocklist Check
        if not self.policy_engine.is_capability_allowed(cap_id):
            return ConnectorExecutionResult(
                request_id=request.request_id,
                capability_id=cap_id,
                success=False,
                status_code=403,
                error_message=f"Capability '{cap_id}' is restricted by security policy.",
            )

        # 4. Rate Limiting Check
        cap_def = next((c for c in connector.list_capabilities() if c.capability_id == cap_id), None)
        max_rate = cap_def.rate_limit_per_minute if cap_def else 60
        if not self.policy_engine.check_and_consume_rate_limit(cap_id, max_per_minute=max_rate):
            return ConnectorExecutionResult(
                request_id=request.request_id,
                capability_id=cap_id,
                success=False,
                status_code=429,
                error_message=f"Rate limit exceeded for capability '{cap_id}'.",
            )

        # 5. Credential Resolution (Isolated from LLM context)
        actual_tenant = tenant_id or request.tenant_id or user_id or "system"
        ref = credential_ref or request.credential_ref or request.parameters.get("credential_ref")
        credentials = None

        if ref:
            try:
                container = self.credential_vault.resolve(
                    tenant_id=actual_tenant,
                    credential_ref=ref,
                    provider=connector.connector_type,
                )
                credentials = container.get_raw_secret()
            except CredentialNotFoundError as e:
                return ConnectorExecutionResult(
                    request_id=request.request_id,
                    capability_id=cap_id,
                    success=False,
                    status_code=404,
                    error_message=e.detail,
                )
            except ProviderMismatchError as e:
                return ConnectorExecutionResult(
                    request_id=request.request_id,
                    capability_id=cap_id,
                    success=False,
                    status_code=400,
                    error_message=e.detail,
                )
            except CredentialRevokedError as e:
                return ConnectorExecutionResult(
                    request_id=request.request_id,
                    capability_id=cap_id,
                    success=False,
                    status_code=403,
                    error_message=e.detail,
                )
        else:
            credentials = self.credential_manager.get_credential(connector.connector_type, user_id=user_id)

        # 6. Physical Wire Dispatch
        result = await connector.execute_capability(request, credentials=credentials)

        # 7. Output Sanitization Guard (Guarantee zero raw secret leakage in errors)
        if result.error_message:
            result.error_message = SecretSanitizer.sanitize_text(result.error_message)

        return result
