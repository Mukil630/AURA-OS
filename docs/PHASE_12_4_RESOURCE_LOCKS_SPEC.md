# PHASE 12.4 SPECIFICATION: DISTRIBUTED RESOURCE LOCKS & CROSS-WORKER SYNCHRONIZATION

## 📋 EXECUTIVE SUMMARY & MISSION
Phase 12.4 establishes the **Distributed Resource Lock & Concurrency Control Layer** for the Mukil Master Agent Operating Plane. While Phase 12.3 resolved *Task Execution Authority* ("Who may execute Task $T$?"), Phase 12.4 resolves *Shared External Resource Authority* ("Who may access or mutate Resource $R$ across concurrent workers?").

---

## 🔒 1. THE SIX PERMANENT RESOURCE LOCKING INVARIANTS

### Invariant 1: Single Exclusive Write Authority (`EXCLUSIVE` Mode)
At any point in time $t$, at most one worker $W$ within a tenant namespace may hold an `EXCLUSIVE` lock on a canonical resource $R$. All concurrent acquire requests for `EXCLUSIVE` or `SHARED` access to $R$ must wait or be rejected.

### Invariant 2: Concurrent Shared Read Capacity (`SHARED` Mode)
Multiple read-only workers $\{W_1, W_2, \dots, W_k\}$ within the same tenant namespace may hold concurrent `SHARED` locks on resource $R$, provided no worker holds an `EXCLUSIVE` lock.

### Invariant 3: Tenant-Partitioned Resource Namespaces
All resource locks are strictly partitioned by `tenant_id`. A lock on `github://mukil630/aura-os` under `tenant_A` operates in total physical isolation from `tenant_B`. Cross-tenant acquisition, inspection, or release is strictly rejected with `403 Forbidden`.

### Invariant 4: Canonical Resource Identification & Normalization
Resource identifiers must undergo deterministic canonicalization before lock evaluation:
$$\text{canonical\_urn} = \text{scheme} + \text{"://"} + \text{lowercase(path.strip('/'))}$$
Example: `github://Mukil630/AURA-OS/` and `github://mukil630/aura-os` resolve to the exact same canonical lock target `github://mukil630/aura-os`.

### Invariant 5: Canonical Multi-Resource Acquisition (Circular-Wait Elimination)
All multi-resource acquisitions MUST follow the same canonical `ResourceID` lexicographical sort order ($\text{ResourceID}_1 < \text{ResourceID}_2 < \dots < \text{ResourceID}_n$). This eliminates circular-wait deadlocks caused by inconsistent lock acquisition ordering across distributed workers.

### Invariant 6: Resource Lock Generations vs Task Fencing Tokens
Resource locks maintain strictly monotonic **Lock Generations** ($G_1 \rightarrow G_2 \rightarrow G_3$):
$$\text{Task Fencing Token (P12.3)} \neq \text{Resource Lock Generation (P12.4)}$$
If Worker Alpha's lock expires and is acquired by Worker Beta ($G=2$), a late release from Worker Alpha ($G=1$) is rejected with `StaleLockConflictError (409)` to prevent accidental unlocking of Beta's authority.

---

## ⚙️ 2. RE-ENTRANCY & ACQUISITION SEMANTICS

1. **Idempotent Re-entrancy**: If the same worker $W$ holding an active unexpired lock on resource $R$ re-requests the same lock in the same mode, the manager returns the existing `ResourceLockContract` with `reentrant_count` incremented.
2. **Mode Upgrades**: A worker holding a `SHARED` lock requesting an `EXCLUSIVE` lock will succeed only if it is the *sole* reader on resource $R$; otherwise, the upgrade is queued or rejected with `409 Conflict` to prevent upgrade-deadlock loops.
3. **Deterministic TTL & Auto-Scavenging**: All locks carry a mandatory `lock_ttl_seconds > 0`. If a worker crashes or partitions, the lock auto-expires and is scavenged by the lock manager.

---

## 🎯 3. THREAT MODEL & MITIGATION MATRIX

| Threat ID | Threat Description | Attack Vector | Mitigation Invariant |
|---|---|---|---|
| **T-1** | **Dual Write Collision** | 2 workers attempt concurrent git push to same repo | Exclusive Lock Mutex (Invariant 1) |
| **T-2** | **Reader Starvation** | Unbounded stream of readers blocks pending writer | Fair FIFO Wait Queue (Invariant 2) |
| **T-3** | **Inconsistent Ordering Deadlock** | Worker 1 locks A then B; Worker 2 locks B then A | Canonical Sort Ordering (Invariant 5) |
| **T-4** | **Lock Hijack / Forged Release** | Worker B calls `release()` on Worker A's lock | Owner WorkerID + LockID Match (Invariant 1) |
| **T-5** | **Cross-Tenant Lock Contention** | Tenant B locks Tenant A's Drive vault | Tenant Namespace Pinning (Invariant 3) |
| **T-6** | **Zombie Lock Starvation** | Worker crashes while holding lock | Bounded TTL + Auto-Expiry (Invariant 6) |
| **T-7** | **Stale Release Race** | Expired worker sends late release after reclaim | Monotonic Lock Generation Epoch (Invariant 6) |
| **T-8** | **Case-Sensitivity Bypass** | Worker 1 locks `RepoA`, Worker 2 locks `repoa` | Canonical URN Normalizer (Invariant 4) |
| **T-9** | **Credential Leak in Lock Key** | Lock key carries raw GitHub token | Recursive Secret Scanner (422) |
| **T-10**| **Contention Stampede** | 50 workers compete for 1 rate-limit bucket | Mutex Critical Section + Bounded Wait |

---

## 📦 4. DATA CONTRACT BLUEPRINT (Step 2 Preview)

- `LockMode(str, Enum)`: `EXCLUSIVE = "exclusive"`, `SHARED = "shared"`
- `LockStatus(str, Enum)`: `GRANTED = "granted"`, `RELEASED = "released"`, `EXPIRED = "expired"`, `REVOKED = "revoked"`
- `ResourceLockContract`:
  - `lock_id: str`
  - `canonical_resource_id: str`
  - `tenant_id: str`
  - `worker_id: str`
  - `task_id: str`
  - `mode: LockMode`
  - `lock_generation: int` (monotonically increasing $\ge 1$)
  - `status: LockStatus`
  - `granted_at: datetime`
  - `expires_at: datetime`
  - `reentrant_count: int`
  - `lock_ttl_seconds: int`
  - `metadata: Dict[str, Any]`

---

## 🔒 SPECIFICATION STATUS
**FROZEN & RATIFIED FOR PHASE 12.4 IMPLEMENTATION.**
