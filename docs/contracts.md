# MUKIL MASTER AGENT — Contracts & Data Specifications (v1)

## 1. Overview & Versioning Strategy

All data moving through the MUKIL MASTER AGENT OS adheres to **Versioned Pydantic Contracts** located in `app.core.contracts`.

### 🏷️ Versioning Strategy:
- **Contract Schema Version**: Every contract inherits from `VersionedContractBase` and carries a `schema_version` attribute (defaulting to `"v1"`).
- **Extensibility without Breaking Changes**: Minor additions must be optional fields with defaults or stored in the `metadata: Dict[str, Any]` container.
- **Breaking Changes & Upgrades**: Breaking changes must increment the schema version (`"v2"`), introduce migration transformers, and maintain backward compatibility during phase rollouts.

---

## 2. Core Entities & Separation of Responsibilities

```text
┌─────────────────────────────────────────────────────────────┐
│                            TASK                             │
│                  "What the user wants"                      │
│        (Goal, Channel, Priority, Risk Level, Status)        │
└──────────────────────────────┬──────────────────────────────┘
                               │ 1 : 1
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                          WORKFLOW                           │
│                "How the goal is executed"                   │
│      (State Machine, Execution Mode, Checkpoints)           │
└──────────────────────────────┬──────────────────────────────┘
                               │ 1 : N
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                          TASK STEP                          │
│               "One atomic unit of work"                     │
│    (Step Index, Tool Name, Agent Type, Input, Output)       │
└──────────────┬──────────────────────────────┬───────────────┘
               │ Dispatches to                │ Assessed by
               ▼                              ▼
┌─────────────────────────────┐┌──────────────────────────────┐
│       AGENT & TOOL          ││      PERMISSION ENGINE       │
│ Reasoning & Discrete Action ││   Risk Tier & Human Approval │
└──────────────┬──────────────┘└──────────────────────────────┘
               │ Produces Result
               ▼
┌─────────────────────────────┐
│     VERIFICATION ENGINE     │
│   Independent State Probe   │
└──────────────┬──────────────┘
               │ Emits
               ▼
┌─────────────────────────────┐
│     EVENTS & MEMORY         │
│  Audit Trail & Distillation │
└─────────────────────────────┘
```

---

## 3. Version 1 Contract Catalog

### 🎯 TaskContract (`app.core.contracts.task`)
Represents the user's high-level goal and execution outcome.
- `task_id`: `str` (Unique ID, e.g. `task_a1b2c3d4e5f6`)
- `user_id`: `str`
- `session_id`: `Optional[str]`
- `channel`: `ChannelType` (`voice`, `telegram`, `web`, `mobile`, `desktop`, `api`)
- `raw_input`: `str`
- `intent`: `Optional[IntentCategory]`
- `task_type`: `TaskType`
- `priority`: `PriorityLevel`
- `risk_level`: `RiskLevel`
- `status`: `TaskStatus` (`created`, `planning`, `running`, `completed`, `failed`, etc.)
- `workflow_id`: `Optional[str]`
- `result_summary`: `Optional[str]`
- `result_data`: `Optional[Dict[str, Any]]`
- `error_message`: `Optional[str]`
- `tags`: `List[str]`
- `updated_at`: `datetime`
- `completed_at`: `Optional[datetime]`

---

### 🗺️ TaskStepContract (`app.core.contracts.task_step`)
Represents an atomic, executable step in a workflow plan.
- `step_id`: `str` (Unique ID, e.g. `step_123456789abc`)
- `workflow_id`: `str`
- `step_index`: `int`
- `name`: `str`
- `description`: `str`
- `agent_type`: `AgentType` (`research`, `coding`, `cloud_file`, `browser`, `communication`, `pc`)
- `tool_name`: `str`
- `input_payload`: `Dict[str, Any]`
- `output_payload`: `Optional[Dict[str, Any]]`
- `status`: `StepStatus` (`pending`, `ready`, `running`, `completed`, `failed`, `skipped`)
- `risk_tier`: `RiskTier` (`tier_1_low`, `tier_2_medium`, `tier_3_high`, `tier_4_critical`)
- `requires_approval`: `bool`
- `approval_state`: `ApprovalState`
- `dependencies`: `List[str]` (Prerequisite step IDs)
- `timeout_seconds`: `int`
- `retry_count`: `int`
- `max_retries`: `int`
- `error_message`: `Optional[str]`
- `started_at`: `Optional[datetime]`
- `completed_at`: `Optional[datetime]`

---

### ⚙️ WorkflowContract & WorkflowStateContract (`app.core.contracts.workflow`)
Represents the stateful execution plan and durable checkpoints.
- **WorkflowContract**:
  - `workflow_id`: `str`
  - `task_id`: `str`
  - `name`: `str`
  - `execution_mode`: `ExecutionMode` (`sequential`, `parallel`, `graph_directed`)
  - `status`: `WorkflowStatus`
  - `steps`: `List[TaskStepContract]`
  - `current_step_index`: `int`
  - `context_variables`: `Dict[str, Any]`
  - `max_execution_time_seconds`: `int`
- **WorkflowStateContract**:
  - `workflow_id`: `str`
  - `status`: `WorkflowStatus`
  - `active_step_id`: `Optional[str]`
  - `completed_step_ids`: `List[str]`
  - `failed_step_ids`: `List[str]`
  - `step_outputs`: `Dict[str, Any]`
  - `accumulated_context`: `Dict[str, Any]`
  - `checkpoint_timestamp`: `datetime`

---

### 🤖 AgentContract (`app.core.contracts.agent`)
Defines specialist reasoning agents and their declared capabilities.
- `agent_id`: `str`
- `name`: `str`
- `agent_type`: `AgentType`
- `description`: `str`
- `version`: `str`
- `status`: `AgentStatus`
- `capabilities`: `List[AgentCapabilityContract]`
- `allowed_tools`: `List[str]`
- `max_concurrency`: `int`
- `health_status`: `str`

---

### 🔌 ToolContract (`app.core.contracts.tool`)
Defines discrete executable tools and their strict schemas.
- `tool_id`: `str` (e.g. `github.list_failed_workflows`)
- `name`: `str`
- `category`: `ToolCategory`
- `description`: `str`
- `version`: `str`
- `execution_mode`: `ToolExecutionMode`
- `connector_id`: `Optional[str]`
- `risk_tier`: `RiskTier`
- `input_schema`: `Dict[str, Any]`
- `output_schema`: `Dict[str, Any]`
- `timeout_seconds`: `int`
- `is_idempotent`: `bool`
- `requires_approval`: `bool`
- `verification_method`: `VerificationMethod`

---

### 🧩 ConnectorContract (`app.core.contracts.connector`)
Defines external integration bridges.
- `connector_id`: `str`
- `name`: `str`
- `connector_type`: `ConnectorType`
- `auth_type`: `AuthType`
- `status`: `ConnectorStatus`
- `base_url`: `Optional[str]`
- `supported_tools`: `List[str]`
- `is_mcp`: `bool`

---

### 🧠 MemoryContract & MemoryQueryContract (`app.core.contracts.memory`)
Defines structured memory units across working, episodic, and semantic tiers.
- `memory_id`: `str`
- `memory_type`: `MemoryType` (`working`, `episodic_task`, `semantic_fact`, `user_preference`, etc.)
- `scope`: `MemoryScope` (`session`, `user`, `project`, `global`)
- `user_id`: `str`
- `project_id`: `Optional[str]`
- `content`: `str`
- `summary`: `Optional[str]`
- `importance_score`: `float` (0.0 – 1.0)
- `source_task_id`: `Optional[str]`
- `tags`: `List[str]`

---

### 🔐 PermissionPolicyContract & ApprovalRequestContract (`app.core.contracts.permission`)
Governs authorization and human-in-the-loop tickets.
- **PermissionPolicyContract**: `policy_id`, `role`, `action`, `resource_pattern`, `risk_tier`, `requires_explicit_approval`, `is_allowed`.
- **ApprovalRequestContract**: `approval_id`, `task_id`, `step_id`, `action`, `risk_tier`, `description`, `parameters`, `state`, `approved_by`, `decided_at`, `expires_at`.

---

### ✅ VerificationSpecContract & VerificationResultContract (`app.core.contracts.verification`)
Defines ground-truth validation criteria and conclusive outcomes.
- **VerificationSpecContract**: `spec_id`, `method`, `target_resource`, `expected_condition`, `timeout_seconds`.
- **VerificationResultContract**: `result_id`, `spec_id`, `step_id`, `status` (`verified`, `failed`, `inconclusive`), `details`, `evidence`, `verified_at`.

---

### 📊 ExecutionEventContract (`app.core.contracts.execution_event`)
Immutable audit log and telemetry packet.
- `event_id`: `str`
- `trace_id`: `str`
- `task_id`: `str`
- `workflow_id`: `Optional[str]`
- `step_id`: `Optional[str]`
- `event_type`: `EventType`
- `severity`: `EventSeverity`
- `source_component`: `str`
- `message`: `str`
- `payload`: `Dict[str, Any]`
- `timestamp`: `datetime`
