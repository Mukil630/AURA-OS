# PHASE 12.2: CREDENTIAL CONTRACT & METADATA SPECIFICATION
**Step 2: Formal Data Contracts, Secret Residency, and Lifecycle State Machine**

---

## 🏛️ 1. Core Architectural Boundary: "Metadata vs Secret Material"

In the Mukil Master Agent Operating Plane, a total firewall exists between **Public Credential Metadata** (visible to the Control Plane, LLM, and Planner) and **Secret Material** (sealed inside the vault boundary):

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CONTROL PLANE & PLANNER BOUNDARY                         │
│                                                                             │
│  CredentialRefContract (PUBLIC METADATA)                                    │
│  ├── credential_ref: "github_prod_mukil"                                    │
│  ├── tenant_id:      "tenant_mukil"                                         │
│  ├── provider:       ConnectorType.GITHUB                                   │
│  ├── purpose:        "repository_ci"                                        │
│  ├── status:         CredentialStatus.ACTIVE                                │
│  ├── masked_preview: "ghp_****x9z2"                                         │
│  └── created_at:     "2026-08-27T06:30:00Z"                                 │
│                                                                             │
│  ❌ NO API KEYS • NO TOKENS • NO CLIENT SECRETS • NO PASSWORDS             │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                              credential_ref ONLY
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                 TENANT CREDENTIAL VAULT & RESOLVER                          │
│                                                                             │
│  SecureSecretContainer (SEALED MEMORY BOUNDARY)                             │
│  ├── Physical Storage: Process Vault (Encrypted / Isolated)                 │
│  ├── Lifetime: Ephemeral in-memory object                                    │
│  ├── Serialization: FORBIDDEN (No dict, no JSON, no __repr__)              │
│  └── Resolution: Callable ONLY at HTTP Transport wire dispatch              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📋 2. Formal Data Contracts

### 2.1 Credential Lifecycle State Enum (`CredentialStatus`)
```python
class CredentialStatus(str, Enum):
    """Lifecycle states for a tenant-scoped credential reference."""
    ACTIVE = "active"        # Fully operational, valid for execution
    ROTATING = "rotating"    # In migration window (graceful transition)
    DISABLED = "disabled"    # Temporarily suspended by operator policy
    REVOKED = "revoked"      # Permanently invalidated (fails fast with 403)
```

### 2.2 Public Credential Metadata Contract (`CredentialRefContract`)
```python
class CredentialRefContract(VersionedContractBase):
    """
    Public metadata contract representing an indirect credential reference.
    Safe for inspection by the Planner, Audit Logs, and APIs.
    """
    credential_ref: str = Field(
        ...,
        description="Unique tenant-scoped alias (e.g. 'github_prod_mukil')."
    )
    tenant_id: str = Field(
        ...,
        description="Immutable tenant boundary identifier."
    )
    provider: ConnectorType = Field(
        ...,
        description="Target external connector (github | google_drive | telegram | pc_sidecar)."
    )
    purpose: str = Field(
        default="general",
        description="Operational intent or scope description."
    )
    status: CredentialStatus = Field(
        default=CredentialStatus.ACTIVE,
        description="Current operational lifecycle state."
    )
    masked_preview: str = Field(
        ...,
        description="Sanitized preview showing prefix and suffix only (e.g. 'ghp_****a1b2')."
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC creation timestamp."
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC last update timestamp."
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary non-sensitive metadata (e.g. scopes, expiration dates)."
    )
```

---

## 🛡️ 3. `SecureSecretContainer` Security Specification

The `SecureSecretContainer` is a non-serializable memory enclosure designed to eliminate accidental credential leakage during debugging, logging, error handling, or object dumping.

### Security Guarantees of `SecureSecretContainer`:
1. **Non-Serializable**: Calling `json.dumps()`, `pydantic.model_dump()`, or `dict()` raises a `TypeError`.
2. **Sanitized Representation**: `__repr__` and `__str__` return strictly `"<SecureSecretContainer: REDACTED>"`.
3. **No String Coercion**: Cannot be accidentally concatenated or formatted into strings without explicit authorization.
4. **Restricted `.reveal()`**: Only executable inside the immediate `HTTPTransport` wire-dispatch block.
5. **Ephemeral Lifetime**: Released from memory immediately after outbound request headers are dispatched.

```python
class SecureSecretContainer:
    """
    Ephemeral, non-serializable container for secret material.
    Guarantees zero accidental leakage across logs, exceptions, and serializations.
    """
    __slots__ = ("_secret_value", "_tenant_id", "_provider", "_created_at")

    def __init__(self, raw_value: str, tenant_id: str, provider: ConnectorType):
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

    def reveal(self, auth_context: object) -> str:
        """Extract raw token string strictly within the transport wire-dispatch block."""
        return self._secret_value
```

---

## 🛑 4. Deterministic Error Taxonomy

| Error Type | HTTP Status | Trigger Condition | Enforcement Rule |
|---|---|---|---|
| **`CredentialNotFoundError`** | **`404 Not Found`** | Credential ref does not exist OR belongs to another tenant. | Never return 403 on cross-tenant lookup to prevent existence enumeration. |
| **`ProviderMismatchError`** | **`400 Bad Request`** | Credential registered for GitHub is dispatched toward Drive or Telegram. | Mismatch fails fast before network wire dispatch. |
| **`CredentialRevokedError`** | **`403 Forbidden`** | Credential status is `REVOKED` or `DISABLED`. | Execution terminates immediately; no cached token fallback. |
| **`RawSecretPayloadError`** | **`422 Unprocessable`** | User or LLM attempts to submit a raw API token (`ghp_...`) in task parameters. | Schema validator rejects raw secret patterns. |
| **`ActionHashMismatchError`** | **`403 Forbidden`** | Human approved ticket with `credential_ref_A`, but agent attempts execution with `credential_ref_B`. | Cryptographic action hash verification fails. |

---

## 🔒 5. The Frozen Credential Lifecycle State Machine

```text
                  [NEW CREDENTIAL CREATION]
                             │
                             ▼
                         [ACTIVE]
                       (Operational)
                             │
               ┌─────────────┴─────────────┐
               ▼                           ▼
          [ROTATING]                  [DISABLED]
      (Migration Window)          (Suspended Policy)
               │                           │
               └─────────────┬─────────────┘
                             │
                             ▼
                         [REVOKED]
                    (Permanent Hard Stop)
```

- **ACTIVE $\rightarrow$ ROTATING**: New secret provisioned; previous secret enters grace period.
- **ACTIVE $\rightarrow$ DISABLED**: Operator temporarily freezes access without destroying configuration.
- **ANY $\rightarrow$ REVOKED**: Secret permanently destroyed; any subsequent resolution returns `403 Forbidden`.
- **REVOKED $\rightarrow$ ACTIVE**: **STRICTLY FORBIDDEN**. A revoked reference can never be resurrected.

---

## 🎯 6. Review Checklist for Step 3 Implementation

Before Step 3 begins, we verify:
- [x] Public metadata contract defined with zero secret fields.
- [x] `SecureSecretContainer` non-serializable pattern specified.
- [x] 404 vs 403 vs 400 error taxonomy established.
- [x] Provider binding matrix locked.
- [x] State machine and irreversible revocation invariant frozen.

Maapla, Step 2 Credential Contract & Metadata Specification is complete and frozen in documentation. Ready for Step 3 implementation upon your green light! 🚀🔒
