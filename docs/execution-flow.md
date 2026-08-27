# MUKIL MASTER AGENT — Execution Flow & State Transitions

## 1. Complete Request Lifecycle Diagram

```text
               🎙️ Voice / 💬 Telegram / 🌐 Web Request
                                │
                                ▼
                       POST /api/v1/tasks
                                │
                    [NormalizedUserRequest]
                                │
                                ▼
                     ┌─────────────────────┐
                     │ Intent & Task Model │ ──▶ Status: CREATED
                     └──────────┬──────────┘
                                │
                                ▼
                     ┌─────────────────────┐
                     │  Context Retrieval  │ ──▶ Query: Episodic + Facts
                     └──────────┬──────────┘
                                │
                                ▼
                     ┌─────────────────────┐
                     │    Task Planner     │ ──▶ Status: PLANNING
                     │ (Decomposes to DAG) │ ──▶ Produces: ExecutionPlan & WorkflowContract
                     └──────────┬──────────┘
                                │
                                ▼
                     ┌─────────────────────┐
                     │  Permission Engine  │
                     └──────────┬──────────┘
                                │
                   Is High Risk (Tier 3/4)?
                        /              \
                      YES               NO
                      │                  │
                      ▼                  │
            ┌───────────────────┐        │
            │  Approval Gate    │        │
            │ Status: WAITING_  │        │
            │   FOR_APPROVAL    │        │
            └─────────┬─────────┘        │
                      │ (Human Approves) │
                      ▼                  │
                      └─────────┬────────┘
                                │
                                ▼
                     ┌─────────────────────┐
                     │   Workflow Engine   │ ──▶ Status: RUNNING
                     │  (State Machine)    │
                     └──────────┬──────────┘
                                │
                   For each Step in Workflow:
                                │
             ┌──────────────────┴──────────────────┐
             │                                     │
             ▼                                     ▼
      [Specialist Agent]                  [Tool / MCP Executor]
  (Reasoning & Input Mapping)          (Validated ToolExecutionRequest)
             │                                     │
             └──────────────────┬──────────────────┘
                                │
                                ▼
                     ┌─────────────────────┐
                     │ Observation Output  │
                     └──────────┬──────────┘
                                │
                                ▼
                     ┌─────────────────────┐
                     │ Verification Engine │ ──▶ (Independent Ground-Truth Probe)
                     └──────────┬──────────┘
                                │
                         Did it verify?
                            /        \
                          YES         NO
                          │            │
                          │            ▼
                          │    ┌───────────────────┐
                          │    │ Recovery Engine   │
                          │    │ • Retry w/ Backoff│
                          │    │ • Alt Tool        │
                          │    │ • Re-plan         │
                          │    └─────────┬─────────┘
                          │              │
                          │       Recovered?
                          │        /      \
                          │      YES       NO ──▶ Status: FAILED
                          │      │
                          └──────┴─────────▶ Next Step / Complete
                                │
                                ▼
                     ┌─────────────────────┐
                     │ State Checkpoint    │ ──▶ Durable DB Snapshot
                     └──────────┬──────────┘
                                │
                                ▼
                     ┌─────────────────────┐
                     │  Memory Extractor   │ ──▶ Saves: Reusable Facts & Lessons
                     └──────────┬──────────┘
                                │
                                ▼
                     ┌─────────────────────┐
                     │ Audit Log Finalize  │ ──▶ Emits: TASK_COMPLETED Event
                     └──────────┬──────────┘
                                │
                                ▼
                     ┌─────────────────────┐
                     │ Response Generator  │ ──▶ [NormalizedAgentResponse]
                     └──────────┬──────────┘
                                │
                                ▼
                     Text UI + Voice TTS Out
```

---

## 2. Step-by-Step State Transitions

### Phase A: Request Normalization & Intake
1. Incoming voice audio is transcribed via STT; text messages arrive via Telegram or Web Gateway.
2. Gateway packages raw input into `NormalizedUserRequest(request_id, user_id, channel, raw_input, language)`.
3. An immutable `ExecutionEventContract(event_type=TASK_CREATED)` is recorded with a unique distributed `trace_id`.

### Phase B: Understanding & Context Retrieval
1. Intent Classifier categorizes input into `IntentCategory` and `TaskType`.
2. `TaskContract` is persisted in DB with `status = TaskStatus.CREATED`.
3. Memory Retriever queries Episodic task history, semantic facts, and user preferences via `MemoryQueryContract`.
4. Context Package is injected into the Task Planner.

### Phase C: Task Planning & Risk Assessment
1. Task Planner decomposes the goal into an ordered `ExecutionPlan` containing discrete `TaskStepContract` objects.
2. Each step specifies: `agent_type`, `tool_name`, `input_payload`, `risk_tier`, `dependencies`, and `verification_spec`.
3. Permission Engine checks every step against security policies:
   - **Tier 1 (Low)** & **Tier 2 (Medium)**: Permitted automatically.
   - **Tier 3 (High)** & **Tier 4 (Critical)**: Generates `ApprovalRequestContract`.
   - Workflow pauses, transition to `WorkflowStatus.WAITING_FOR_APPROVAL`.
   - User receives notification on Telegram/Web. Once approved, workflow resumes from checkpoint.

### Phase D: Specialist Agent Execution & Tool Invocation
1. Workflow Engine evaluates step dependencies. When a step is ready, it transitions to `StepStatus.RUNNING`.
2. Agent Router dispatches the step to the registered `IAgent` (e.g. `CodingAgent`).
3. The Agent resolves context and issues a `ToolExecutionRequest` to the `ToolExecutor`.
4. Tool parameters are strictly validated against the tool's JSON Schema.
5. Tool runs locally or via MCP client with active timeout monitoring.

### Phase E: Independent Verification & Failure Recovery
1. The `IVerifier` executes an independent probe based on `VerificationMethod`:
   - Checks file exists in Google Drive via ID/hash lookup (not just HTTP 200).
   - Verifies git commit remote SHA on GitHub.
   - Inspects DOM state for confirmation elements.
2. If verification passes: Step transitions to `StepStatus.COMPLETED`.
3. If tool or verification fails:
   - Recovery Engine evaluates `retry_count < max_retries`.
   - Applies exponential backoff and retries.
   - If retries exhausted: attempts alternative tool or falls back to human escalation.

### Phase F: Checkpointing, Memory Update & Client Response
1. Durable checkpoint is saved via `WorkflowStateContract`.
2. Memory Extractor distills successful patterns, failure resolutions, and user preferences into `MemoryContract`.
3. `NormalizedAgentResponse` is synthesized (formatting both markdown text and concise TTS script).
4. Response is dispatched back to originating channel.

---

## 3. Concrete Example: "Check my GitHub CI, fix simple errors, backup to Drive, and notify Telegram"

```text
Step 1: github_agent.list_failed_workflows()
        → Finds repo 'AURA-OS' workflow #45 failed.
        → Verifier: Confirms run ID and failure status.

Step 2: coding_agent.analyze_and_fix(run_id=45)
        → Extracts traceback: Missing env var in test runner.
        → Applies safe patch.
        → Runs local tests.
        → Verifier: Tests pass with exit code 0.

Step 3: cloud_file_agent.upload_backup(files=['tests/test_ci.py'])
        → Uploads to Google Drive vault.
        → Verifier: Drive API search confirms file ID & byte size match.

Step 4: communication_agent.send_telegram_report(chat_id, summary)
        → Dispatches Telegram alert: "CI fixed on AURA-OS and backed up to Drive."
        → Verifier: Telegram message ID confirmed.
```
