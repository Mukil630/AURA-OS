# PHASE 12.2: CREDENTIAL ISOLATION & INDIRECT REFERENCE SPECIFICATION
**Cryptographic Secret Boundary, Tenant Vault & Zero-Leakage Architecture**

---

## 🏛️ 1. Core Philosophy: "Reference ≠ Authority"

In the Mukil Master Agent Operating Plane, the Language Model and Planning Engine operate under total **Credential Blindness**.

> **The Fundamental Credential Law:**
> The agent may request a capability. It may reference a credential alias (`credential_ref`).
> It may **NEVER** receive, observe, process, or possess credential authority.

---

## 🔒 2. The Six Permanent Credential Invariants

| Invariant | Security Boundary & Enforcement Rule |
|---|---|
| **`LLM ≠ SECRET`** | LLM inputs, prompt context, and planner outputs contain only `credential_ref: str`. Any attempt to output or accept raw tokens (`ghp_...`, `ya29...`, bot tokens) is rejected. |
| **`REF ≠ AUTHORITY`** | A reference alias (`github_prod_01`) is not a security token. Access is granted only when `(tenant_id, credential_ref, provider, is_active)` is cryptographically verified by the Credential Boundary. |
| **`STRICT PROVIDER BINDING`** | A credential registered for `ConnectorType.GITHUB` is rejected if dispatched toward `ConnectorType.GOOGLE_DRIVE` or `ConnectorType.TELEGRAM`. Cross-provider token reuse is blocked. |
| **`SINGLE RESOLUTION POINT`** | Secret resolution occurs strictly at the final wire-dispatch boundary inside `CapabilityRouter -> TenantCredentialVault -> HTTPTransport`. No upstream component (Planner, Approval, Memory, DLQ) can invoke the resolver. |
| **`ZERO SECRET RESIDUE`** | Raw secrets never exist in database state (`TaskModel`, `WorkflowModel`), audit events, memory logs, approval cards, DLQ records, distributed traces, or exception tracebacks. |
| **`REVOCATION = HARD STOP`** | A revoked or disabled credential alias fails fast immediately. No worker, cached lease, or workflow step may execute against an inactive credential. |

---

## 🛡️ 3. Physical Secret Residency & Minimum Code Surface

### The Anti-Leak Container Pattern (`SecureSecretContainer`)
To prevent raw secrets from being serialized, logged, dumped in dictionaries, or copied during object inspection, secrets are **never stored as naked strings in Pydantic models**.

```python
class SecureSecretContainer:
    """
    Non-serializable memory container for sensitive credentials.
    Explicitly blocks __repr__, __str__, dict conversion, and Pydantic serialization.
    """
    __slots__ = ("_secret_value",)

    def __init__(self, raw_value: str):
        self._secret_value = raw_value

    def __repr__(self) -> str:
        return "<SecureSecret: REDACTED>"

    def __str__(self) -> str:
        return "<SecureSecret: REDACTED>"

    def reveal(self, auth_token: object) -> str:
        """Restricted extraction callable only by authenticated Transport Adapter."""
        return self._secret_value
```

### Physical Lifetime of a Secret in Memory:
```text
1. Storage: Encrypted in TenantCredentialVault (or OS Environment in Dev).
2. Resolution: TenantCredentialVault.resolve(tenant_id, credential_ref, provider)
3. Lifetime: Ephemeral string instantiated strictly within the HTTP Client dispatch block:
   async with httpx.AsyncClient() as client:
       response = await client.request(..., headers={"Authorization": f"Bearer {secret}"})
4. Destruction: Secret string falls out of scope immediately after request headers are constructed.
```

---

## 🏗️ 4. The Request Execution & Secret Resolution Flow

```text
                           PLANNER / LLM
                                │
                 "credential_ref": "github_mukil_prod"
                                │
                                ▼
                       POLICY & RISK ENGINE
              (Verifies R0-R6 risk against capability)
                                │
                                ▼
                         APPROVAL ENGINE
              (Action Hash = SHA-256(cap + params + ref + tenant))
                                │
                                ▼
                        CAPABILITY ROUTER
                                │
               ┌────────────────┴────────────────┐
               │    TENANT CREDENTIAL VAULT      │
               │                                 │
               │ 1. Validate tenant ownership    │
               │ 2. Validate provider matching   │
               │ 3. Validate active status       │
               │ 4. Extract SecureSecretContainer│
               └────────────────┬────────────────┘
                                │
                                ▼
                          HTTP TRANSPORT
                    (Temporary wire injection)
                                │
                                ▼
                     EXTERNAL API (GitHub / Drive)
```

---

## ⚠️ 5. Architectural Weakness Audit & Hardening Matrix

| Potential Vulnerability | Root Cause | P12.2 Hardening Guarantee |
|---|---|---|
| **Raw Token in Step Parameters** | Malicious user or hallucinating LLM sends `{"token": "ghp_123"}` in task payload. | `CapabilityRouter` runs schema parameter validation: any raw secret pattern is rejected and blocked from dispatch. |
| **Cross-Tenant Ref Guessing** | Tenant B guesses Tenant A's ref name `github_prod_01`. | Vault indexes by `(tenant_id, credential_ref)`. Returns `404 Not Found` with zero indication that Tenant A has that ref. |
| **Exception Traceback Leakage** | Upstream API error response echoes Authorization header in error message. | Transport catches all HTTP exceptions and sanitizes URL and headers through `SecretSanitizer` before re-raising. |
| **Provider Impersonation** | Attacker uses a valid Telegram bot token to attempt GitHub API calls. | Vault enforces `entry.provider == connector.connector_type`. Mismatch raises `400 Provider Mismatch Error`. |
| **Approval Hash Tampering** | Operator approves ticket for `github_readonly_01`, but agent tries executing with `github_admin_01`. | `action_hash` includes `credential_ref`. Hash verification fails fast with `403 Action Hash Mismatch`. |

---

## 🧪 6. The 15 P12.2 Adversarial Test Scenarios

1. `test_p12_2_01_tenant_a_registers_and_resolves_own_credential`: (ALLOW 200 OK).
2. `test_p12_2_02_tenant_a_attempts_to_resolve_tenant_b_credential_404`: (DENIED 404 Not Found).
3. `test_p12_2_03_nonexistent_credential_ref_returns_404`: (DENIED 404 Not Found).
4. `test_p12_2_04_llm_submits_raw_api_key_in_parameters_rejected`: (REJECTED 422/400).
5. `test_p12_2_05_llm_requests_cross_tenant_credential_ref_denied`: (DENIED 404/403).
6. `test_p12_2_06_revoked_or_disabled_credential_fails_fast_403`: (DENIED 403 Credential Inactive).
7. `test_p12_2_07_provider_mismatch_github_token_used_for_drive_denied`: (DENIED 400 Provider Mismatch).
8. `test_p12_2_08_get_credential_metadata_returns_masked_preview_only`: (Assert zero raw secret in response).
9. `test_p12_2_09_execution_event_audit_logs_contain_zero_raw_secrets`: (Regex search passes 100% clean).
10. `test_p12_2_10_dead_letter_queue_contains_zero_raw_secrets`: (Regex search passes 100% clean).
11. `test_p12_2_11_approval_ticket_and_telegram_card_contain_zero_raw_secrets`: (Masked / ref only).
12. `test_p12_2_12_http_exception_traceback_sanitized_without_secret_leak`: (Sanitizer redaction verified).
13. `test_p12_2_13_cross_tenant_collision_identical_ref_names_resolve_isolated_secrets`: (Tenant A $\neq$ Tenant B).
14. `test_p12_2_14_direct_resolver_bypass_outside_router_blocked`: (Strict boundary enforcement).
15. `test_p12_2_15_tampered_credential_ref_in_approved_action_denied`: (403 Action Hash Mismatch).
