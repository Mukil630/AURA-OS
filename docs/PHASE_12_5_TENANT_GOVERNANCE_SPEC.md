# PHASE 12.5 SPECIFICATION: TENANT RESOURCE GOVERNANCE, QUOTAS & ADMISSION CONTROL

## 📋 EXECUTIVE SUMMARY & MISSION
Phase 12.5 establishes the **Tenant Resource Governance, Rate Limiting, Budget Accounting & Admission Control Layer** for the Mukil Master Agent Operating Plane. 

While Phase 12.3 resolved *Task Execution Authority* ("Who may execute Task $T$?"), and Phase 12.4 resolved *Shared Resource Locking* ("Who may access Resource $R$?"), Phase 12.5 resolves *Tenant Capacity & Governance* ("Is Tenant $A$ authorized to consume this quantity of system capacity, and when must the gateway refuse additional work?").

---

## 🏛️ 1. THE SIX PERMANENT GOVERNANCE INVARIANTS

### Invariant 1: Multi-Dimensional Quota Enforcement
Tenant governance tracks four distinct, orthogonal capacity dimensions:
1. **Concurrent Task Quota ($Q_{\text{concurrent}}$)**: Maximum active in-flight task executions.
2. **Rate Limit / Throughput ($R_{\text{rpm}}$)**: Requests per minute / window using Token Bucket with burst capacity.
3. **Compute & Token Budget ($B_{\text{tokens}}$)**: Daily / monthly accumulated LLM tokens (prompt + completion) and compute credits.
4. **Storage & Vault Allocation ($S_{\text{bytes}}$)**: Disk / Google Drive payload byte limits per tenant.

### Invariant 2: Fail-Closed Admission Control & Status Code Taxonomy
When a tenant exceeds capacity thresholds:
- Concurrency limit exceeded $\longrightarrow$ **`429 ConcurrencyQuotaExceededError`**.
- Rate limit exhausted $\longrightarrow$ **`429 RateLimitExceededError`** with `Retry-After: N` header.
- Budget / Credit exhausted $\longrightarrow$ **`402 BudgetExhaustedError`** (Payment Required).
- Storage quota exceeded $\longrightarrow$ **`413 StorageLimitExceededError`** (Payload Too Large).
- Cross-tenant tampering $\longrightarrow$ **`403 UnauthorizedGovernanceError`**.

### Invariant 3: Tenant Boundary Isolation (Zero Cross-Tenant Contamination)
Quotas, rate-limit buckets, and consumption meters are strictly partitioned by `tenant_id`. High contention or quota exhaustion in `tenant_A` has zero impact on `tenant_B`.

### Invariant 4: Atomic Two-Phase Consumption (Reserve $\rightarrow$ Commit / Rollback)
All resource consumptions follow a two-phase protocol:
1. **Reservation ($P_{\text{reserve}}$)**: Atomically reserve estimated budget before execution.
2. **Settlement ($P_{\text{commit}}$ or $P_{\text{rollback}}$)**: Settle exact consumed amount upon task completion, or release reserved capacity back to the tenant if the task fails or aborts.

### Invariant 5: Soft-Limit Warnings & Hard-Limit Rejections
- **Soft Limit (80% default)**: Emits warning events (`TenantQuotaWarningEvent`) to observability telemetry without blocking requests.
- **Hard Limit (100%)**: Enforces immediate rejection or backpressure throttling.

### Invariant 6: Zero Secret Residue in Governance Telemetry
Quota keys, usage accounting records, rate-limit headers, and audit trails must only carry canonical tenant identifiers (`tenant_id`, `task_id`, `dimension`). Raw credentials, API keys, or user tokens must never appear in governance state.

---

## 🎯 2. THREAT MODEL & MITIGATION MATRIX

| Threat ID | Threat Description | Attack Vector | Mitigation Invariant |
|---|---|---|---|
| **T-1** | **DoS / Gateway Stampede** | 10,000 reqs/sec from single tenant | Token Bucket Rate Limiter (Invariant 1) |
| **T-2** | **Noisy Neighbor Starvation** | Tenant A hogs all worker processes | Concurrency Quota Limits (Invariant 1) |
| **T-3** | **Runaway LLM Token Budget Overrun** | Agent enters infinite generation loop | Two-Phase Token Pre-Allocation (Invariant 4) |
| **T-4** | **Distributed Over-Allocation Race** | 20 workers concurrently spend last credit | Atomic CAS Mutex Reservation (Invariant 4) |
| **T-5** | **Storage Exhaustion Bomb** | Tenant uploads 100GB payload | Storage Byte Hard Cap (Invariant 2) |
| **T-6** | **Cross-Tenant Quota Hijacking** | Tenant B claims Tenant A's budget | Tenant-Scoped State Isolation (Invariant 3) |
| **T-7** | **Forged Quota Grants** | Attendant modifies quota records | Signed Admin Update Contracts (Invariant 6) |
| **T-8** | **Burst Drift / Sliding Window Bypass**| Rapid pulses right at window boundaries | Token Bucket with Burst Tokens (Invariant 1) |
| **T-9** | **Orphaned Reservation Leak** | Worker crashes mid-execution | TTL Expiration on Reservations (Invariant 4) |
| **T-10**| **Credential Leak in Governance Logs** | API key passed in quota metadata | Recursive Secret Scanner Check (Invariant 6) |

---

## 📦 3. ARCHITECTURAL PIPELINE POSITION

```text
                  USER REQUEST
                       │
                       ▼
              ┌─────────────────┐
              │  P12.1          │
              │ TENANT AUTH     │
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  P12.5          │
              │ GOVERNANCE      │
              │                 │
              │ • Concurrency   │
              │ • Rate Limit    │
              │ • Token Budget  │
              │ • Admission     │
              └────────┬────────┘
                       │
                  ALLOWED?
                   /     \
                 NO       YES
                 │         │
                 ▼         ▼
              REJECT    P12.4
             (429/402)  RESOURCE LOCK
                           │
                           ▼
                        P12.3
                        TASK LEASE
                           │
                           ▼
                        EXECUTE
```

---

## 🔒 SPECIFICATION STATUS
**FROZEN & RATIFIED FOR PHASE 12.5 IMPLEMENTATION.**
