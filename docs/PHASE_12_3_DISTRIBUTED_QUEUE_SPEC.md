# PHASE 12.3: DISTRIBUTED TASK QUEUE & WORKER LEASING SPECIFICATION
**Exclusive Leasing, Fencing Tokens, Crash Recovery & Concurrency Invariant Architecture**

---

## 🏛️ 1. Core Philosophy: "Execution Requires Monotonic Exclusive Leasing"

In the Mukil Master Agent Operating Plane, scaling capacity across multiple distributed workers must never weaken consistency, multi-tenant isolation, or execution integrity.

> **The Fundamental Queue Law:**
> A worker cannot execute a task simply because it polled it from a queue.
> Execution is permitted **if and only if** the worker holds an **active, cryptographically verifiable, non-expired Lease Token** backed by a **strictly monotonic fencing counter**.

---

## 🔒 2. The Six Permanent Queue & Worker Leasing Invariants

| Invariant | Concurrency Boundary & Enforcement Rule |
|---|---|
| **1. `SINGLE EXCLUSIVE LEASE`** | At any given timestamp $t$, at most one worker $W$ may possess an active lease for task $T$. Dual ownership is an invariant violation. |
| **2. `ATOMIC ACQUIRE RACES`** | When $N$ concurrent workers race to acquire task $T$, exactly $1$ worker succeeds (`200 OK`) and $N-1$ workers are denied (`409 LeaseConflictError`). Zero duplicate execution. |
| **3. `MONOTONIC HEARTBEATING`** | Leases carry an immutable monotonic TTL. A worker must actively extend its lease before `expires_at`. Un-renewed leases expire automatically. |
| **4. `CRASH RECLAIM & RESILIENCE`** | If a worker process crashes, hangs, or partitions, its lease expires deterministically. The task automatically transitions to `RETRY_QUEUED` for immediate pickup by healthy workers. |
| **5. `STALE WRITE REJECTION (FENCING)`**| Every lease acquisition increments a monotonic `fencing_token`. Any task result or state write submitted with a stale, expired, or superseded lease token is rejected with `409 StaleLeaseConflict`. |
| **6. `TENANT EXECUTION PINNING`** | A task's `tenant_id` is cryptographically immutable. The acquiring worker MUST instantiate the runtime under the task's trusted `TenantContext`. Cross-tenant execution is impossible. |

---

## 🛡️ 3. Distributed Lifecycle & State Machine

```text
                  TASK CREATED (Tenant A)
                            │
                            ▼
                    TASK STORE (DB)
                            │
                            ▼
                    TASK QUEUE (Enqueued)
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
        Worker 1 (Race)             Worker 2 (Race)
              │                           │
        acquire(task_1)             acquire(task_1)
              │                           │
        ┌─────┴─────┐               ┌─────┴─────┐
        ▼           ▼               ▼           ▼
     ACQUIRED    CONFLICT        ACQUIRED    CONFLICT
     (Winner)    (Denied)        (Winner)    (Denied)
        │                           │
        ▼                           ▼
  [Lease Active]              [Backoff/Poll]
  fencing_token: 1
        │
   Heartbeat /
   renew(lease_1)
        │
   ┌────┴──────────────────────────┐
   │                               │
[Success]                      [Crash / Hang]
   │                               │
   ▼                               ▼
Complete Task                 Lease Expires (TTL)
Release Lease                      │
                                   ▼
                             Standby Worker Reclaims
                             fencing_token: 2
```

---

## 🔬 4. Stale Write & Zombie Worker Defense (Fencing Token Pattern)

### The Zombie Worker Scenario:
1. `Worker A` acquires `Task 101` with `fencing_token = 1`, `lease_ttl = 10s`.
2. `Worker A` experiences an OS freeze / long garbage collection pause for 15 seconds.
3. At $t = 10s$, `Lease 1` expires.
4. `Worker B` detects the expired lease, reclaims `Task 101` with `fencing_token = 2`, and executes it successfully to completion.
5. At $t = 16s$, `Worker A` unfreezes and attempts to write its completed task result to the database.

### The Defense Contract:
- The persistence layer checks: `assert task.active_fencing_token == request.fencing_token`.
- `Worker A` provides `fencing_token = 1`, but the database holds `fencing_token = 2`.
- **Verdict**: `Worker A`'s write is **REJECTED** with `409 StaleLeaseConflict`.
- **Result**: Zero split-brain state corruption, zero duplicate task writes.

---

## 📊 5. Threat Model & Adversarial Vector Analysis (10 Attack Scenarios)

| Threat ID | Adversarial Scenario | Expected Defense / Security Gate |
|---|---|---|
| **`THREAT-12.3-01`** | **Concurrent Acquire Race**: Multiple distributed workers attempt to acquire the same queued task simultaneously. | Atomic test-and-set / conditional CAS. Exactly 1 winner; $N-1$ receive 409 conflict. |
| **`THREAT-12.3-02`** | **Zombie Worker Stale Write**: Frozen worker wakes up after lease expiry and tries to commit results. | Fencing token validation rejects stale writes with `409 StaleLeaseConflict`. |
| **`THREAT-12.3-03`** | **Forged Worker Identity**: Malicious worker attempts to renew or release a lease owned by another worker. | Lease ownership verification (`lease.worker_id == request.worker_id`) enforced. |
| **`THREAT-12.3-04`** | **Forged / Guessed Lease ID**: Attacker generates random UUIDs to manipulate lease state. | Cryptographic UUIDv4 + database tenant validation. |
| **`THREAT-12.3-05`** | **Stale Renewal after Expiry**: Worker attempts to renew a lease that has already timed out. | Renewal fails fast (`410 Gone / LeaseExpiredError`). Task cannot be revived by stale owner. |
| **`THREAT-12.3-06`** | **Cross-Tenant Task Theft**: Worker provisioned for Tenant A attempts to acquire Tenant B tasks. | Worker tenant-matching constraint (`worker.tenant_id == task.tenant_id` or global pool with strict context binding). |
| **`THREAT-12.3-07`** | **Poison Task Infinite Retry Loop**: Malicious or crashing task crashes workers continuously. | Strict exponential backoff with `max_attempts` cutoff; routes to Dead-Letter Queue (DLQ). |
| **`THREAT-12.3-08`** | **Completion after Lease Revocation**: Admin revokes lease mid-execution; worker tries to finalize. | Revoked leases set `status = REVOKED`; state transitions fail fast. |
| **`THREAT-12.3-09`** | **Clock Drift / NTP Skew**: Host system clocks differ across distributed nodes. | Monotonic monotonic timers and centralized server timestamp evaluation. |
| **`THREAT-12.3-10`** | **Secret Residue in Queue Payloads**: Queue message contains embedded raw API keys. | Parameter inspection using `_contains_raw_secrets` prior to enqueuing. |

---

## 📦 6. Data Contracts & State Enums

### 1. `LeaseStatus` Enum:
- `ACQUIRED`: Lease is currently active and owned by a live worker.
- `RENEWED`: Lease was extended via heartbeat.
- `EXPIRED`: Lease timed out without renewal; eligible for reclaim.
- `RELEASED`: Task completed normally and lease was voluntarily freed.
- `REVOKED`: Lease was administratively terminated.

### 2. `TaskLeaseContract`:
```python
class TaskLeaseContract(BaseModel):
    lease_id: str
    task_id: str
    tenant_id: str
    worker_id: str
    fencing_token: int
    status: LeaseStatus
    acquired_at: datetime
    expires_at: datetime
    renewal_count: int = 0
    lease_ttl_seconds: int = 30
```

### 3. `QueueMessageContract`:
```python
class QueueMessageContract(BaseModel):
    message_id: str
    task_id: str
    tenant_id: str
    priority: PriorityLevel
    enqueued_at: datetime
    attempt_count: int = 0
    max_attempts: int = 3
    next_attempt_at: datetime
    payload: Dict[str, Any]
```

---

## 🗺️ 7. Phase 12.3 Step-by-Step Implementation Roadmap

```text
STEP 1 — Specification & Threat Model Freeze     🟢 CURRENT
STEP 2 — Lease Data Contracts & Enums            ⏳ NEXT
STEP 3 — Atomic Lease Manager & Store            ⏳ QUEUED
STEP 4 — Distributed Task Queue Core             ⏳ QUEUED
STEP 5 — Heartbeat & Auto-Renewal Daemon         ⏳ QUEUED
STEP 6 — Crash Detection & Standby Reclaim       ⏳ QUEUED
STEP 7 — Fencing Token & Stale-Write Defense     ⏳ QUEUED
STEP 8 — Concurrency & Race-Condition Adversarial Suite ⏳ QUEUED
STEP 9 — Full Platform Regression Suite          ⏳ QUEUED
STEP 10— Security Review & Phase 12.3 Lock       ⏳ QUEUED
```

---

## 🏁 Step 1 Definition of Done
- [x] Specification created at `docs/PHASE_12_3_DISTRIBUTED_QUEUE_SPEC.md`.
- [x] The Six Permanent Queue & Worker Leasing Invariants formally defined.
- [x] Fencing token and zombie worker defense pattern specified.
- [x] 10 adversarial concurrency and failure threats documented.
- [x] Zero premature implementation code written.
- [x] Baseline test count maintained (507 / 507 passing).
