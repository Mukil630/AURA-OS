"""Task Decomposition and Execution Plan Generation Engine."""
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from app.core.contracts.intent import NormalizedTaskContext
from app.core.contracts.task_step import TaskStepContract
from app.core.contracts.workflow import WorkflowContract
from app.core.dag import DAGValidator
from app.core.enums import (
    AgentType,
    ExecutionMode,
    IntentCategory,
    RiskTier,
    TaskType,
    WorkflowStatus,
)
from app.core.models.plan import ExecutionPlan, StepDependency


class TaskPlanner:
    """
    Transforms understood user intent into a structured, dependency-ordered DAG ExecutionPlan.
    Does NOT execute tools or make API calls—only generates plans.
    """

    def plan(
        self,
        context: NormalizedTaskContext,
        workflow_id: Optional[str] = None,
    ) -> Tuple[ExecutionPlan, WorkflowContract]:
        """
        Decompose a NormalizedTaskContext into an ExecutionPlan and WorkflowContract.
        """
        wf_id = workflow_id or f"wf_{uuid4().hex[:12]}"
        intent = context.parsed_intent.intent
        task_type = context.parsed_intent.task_type
        entities = context.parsed_intent.extracted_entities

        # 1. Decompose by Intent Category
        if intent == IntentCategory.AUTOMATION_SCHEDULE:
            steps, deps = self._plan_reminder_schedule(wf_id, context)
        elif intent == IntentCategory.CODE_ASSISTANCE or task_type == TaskType.CODING:
            steps, deps = self._plan_coding_ci(wf_id, context)
        elif intent == IntentCategory.FILE_SYNC or task_type == TaskType.FILE_OPERATION:
            steps, deps = self._plan_file_sync(wf_id, context)
        elif intent == IntentCategory.COMMUNICATION_DISPATCH or task_type == TaskType.COMMUNICATION:
            steps, deps = self._plan_communication(wf_id, context)
        elif intent == IntentCategory.PC_HARDWARE_CONTROL or task_type == TaskType.SYSTEM_CONTROL:
            steps, deps = self._plan_pc_control(wf_id, context)
        elif intent == IntentCategory.QUERY or task_type == TaskType.RESEARCH:
            steps, deps = self._plan_research_query(wf_id, context)
        else:
            steps, deps = self._plan_general_action(wf_id, context)

        # 2. Validate DAG and establish topological sort order
        sorted_steps = DAGValidator.validate_and_sort(steps, deps)

        # 3. Assess overall plan risk and duration
        max_risk = RiskTier.TIER_1_LOW
        for step in sorted_steps:
            if step.risk_tier == RiskTier.TIER_4_CRITICAL:
                max_risk = RiskTier.TIER_4_CRITICAL
                break
            elif step.risk_tier == RiskTier.TIER_3_HIGH and max_risk != RiskTier.TIER_4_CRITICAL:
                max_risk = RiskTier.TIER_3_HIGH
            elif step.risk_tier == RiskTier.TIER_2_MEDIUM and max_risk == RiskTier.TIER_1_LOW:
                max_risk = RiskTier.TIER_2_MEDIUM

        requires_approval = max_risk in (RiskTier.TIER_3_HIGH, RiskTier.TIER_4_CRITICAL) or any(s.requires_approval for s in sorted_steps)
        estimated_duration = sum(s.timeout_seconds for s in sorted_steps)

        # 4. Construct ExecutionPlan model
        plan = ExecutionPlan(
            task_id=context.task_id,
            goal=context.parsed_intent.normalized_input,
            execution_mode=ExecutionMode.SEQUENTIAL if len(deps) >= len(sorted_steps) - 1 else ExecutionMode.GRAPH_DIRECTED,
            steps=sorted_steps,
            dependencies=deps,
            estimated_duration_seconds=estimated_duration,
            max_risk_tier=max_risk,
            requires_overall_approval=requires_approval,
            plan_metadata={
                "intent": intent.value if hasattr(intent, "value") else str(intent),
                "task_type": task_type.value if hasattr(task_type, "value") else str(task_type),
                "confidence": context.parsed_intent.confidence_score,
            },
        )

        # 5. Construct WorkflowContract
        workflow = WorkflowContract(
            workflow_id=wf_id,
            task_id=context.task_id,
            name=f"{intent.value}_workflow" if hasattr(intent, "value") else f"{intent}_workflow",
            description=f"Automated execution plan for: {context.parsed_intent.normalized_input}",
            execution_mode=plan.execution_mode,
            status=WorkflowStatus.PENDING,
            steps=sorted_steps,
            context_variables={
                "task_id": context.task_id,
                "user_id": context.user_id,
                "channel": context.channel.value if hasattr(context.channel, "value") else str(context.channel),
                "raw_input": context.parsed_intent.raw_input,
                "entities": entities.model_dump(),
            },
            max_execution_time_seconds=estimated_duration + 60,
        )

        return plan, workflow

    # ── Specialized Intent Decomposers ────────────────────────────────────────────────

    def _plan_reminder_schedule(
        self,
        wf_id: str,
        context: NormalizedTaskContext,
    ) -> Tuple[List[TaskStepContract], List[StepDependency]]:
        """Decompose scheduled task or reminder."""
        entities = context.parsed_intent.extracted_entities
        step1 = TaskStepContract(
            workflow_id=wf_id,
            step_index=0,
            name="create_schedule_timer",
            description=f"Register reminder for '{entities.subject}' at {entities.time} ({entities.relative_day})",
            agent_type=AgentType.COMMUNICATION,
            tool_name="scheduler.create_timer",
            input_payload={
                "time": entities.time or "09:00",
                "relative_day": entities.relative_day or "today",
                "subject": entities.subject or context.parsed_intent.normalized_input,
            },
            risk_tier=RiskTier.TIER_1_LOW,
            timeout_seconds=10,
        )
        return [step1], []

    def _plan_coding_ci(
        self,
        wf_id: str,
        context: NormalizedTaskContext,
    ) -> Tuple[List[TaskStepContract], List[StepDependency]]:
        """Decompose GitHub CI inspection, log analysis, patch application, and testing."""
        entities = context.parsed_intent.extracted_entities
        repo = entities.target_repo or "default_repo"

        # Step 1: Read CI status
        s1 = TaskStepContract(
            workflow_id=wf_id,
            step_index=0,
            name="read_ci_status",
            description="Inspect GitHub repository for active and failed CI workflows",
            agent_type=AgentType.CODING,
            tool_name="github.list_failed_workflows",
            input_payload={"repository": repo},
            risk_tier=RiskTier.TIER_1_LOW,
            timeout_seconds=30,
        )

        # Step 2: Inspect failure logs
        s2 = TaskStepContract(
            workflow_id=wf_id,
            step_index=1,
            name="inspect_error_logs",
            description="Fetch and extract tracebacks from failed workflow runs",
            agent_type=AgentType.CODING,
            tool_name="github.get_logs",
            input_payload={"repository": repo},
            risk_tier=RiskTier.TIER_1_LOW,
            dependencies=[s1.step_id],
            timeout_seconds=45,
        )

        # Step 3: Determine fix
        s3 = TaskStepContract(
            workflow_id=wf_id,
            step_index=2,
            name="determine_patch_strategy",
            description="Analyze traceback to formulate minimal, safe code fix",
            agent_type=AgentType.CODING,
            tool_name="coding.analyze_patch",
            input_payload={"repository": repo},
            risk_tier=RiskTier.TIER_1_LOW,
            dependencies=[s2.step_id],
            timeout_seconds=60,
        )

        # Step 4: Apply fix
        s4 = TaskStepContract(
            workflow_id=wf_id,
            step_index=3,
            name="apply_code_fix",
            description="Apply safe patch to repository workspace",
            agent_type=AgentType.CODING,
            tool_name="coding.apply_fix",
            input_payload={"repository": repo},
            risk_tier=RiskTier.TIER_2_MEDIUM,
            dependencies=[s3.step_id],
            timeout_seconds=45,
        )

        # Step 5: Run tests
        s5 = TaskStepContract(
            workflow_id=wf_id,
            step_index=4,
            name="run_verification_tests",
            description="Execute automated test suite to confirm patch resolution",
            agent_type=AgentType.CODING,
            tool_name="coding.run_tests",
            input_payload={"repository": repo},
            risk_tier=RiskTier.TIER_1_LOW,
            dependencies=[s4.step_id],
            timeout_seconds=90,
        )

        deps = [
            StepDependency(parent_step_id=s1.step_id, child_step_id=s2.step_id),
            StepDependency(parent_step_id=s2.step_id, child_step_id=s3.step_id),
            StepDependency(parent_step_id=s3.step_id, child_step_id=s4.step_id),
            StepDependency(parent_step_id=s4.step_id, child_step_id=s5.step_id),
        ]
        return [s1, s2, s3, s4, s5], deps

    def _plan_file_sync(
        self,
        wf_id: str,
        context: NormalizedTaskContext,
    ) -> Tuple[List[TaskStepContract], List[StepDependency]]:
        """Decompose Cloud / Google Drive file backup and verification."""
        entities = context.parsed_intent.extracted_entities
        file_target = entities.file_path or "artifact.pdf"

        s1 = TaskStepContract(
            workflow_id=wf_id,
            step_index=0,
            name="verify_local_artifact",
            description=f"Confirm file '{file_target}' exists and calculate hash",
            agent_type=AgentType.CLOUD_FILE,
            tool_name="filesystem.check_file",
            input_payload={"file_path": file_target},
            risk_tier=RiskTier.TIER_1_LOW,
            timeout_seconds=15,
        )

        s2 = TaskStepContract(
            workflow_id=wf_id,
            step_index=1,
            name="upload_to_drive_vault",
            description=f"Upload '{file_target}' to Google Drive Master Vault",
            agent_type=AgentType.CLOUD_FILE,
            tool_name="drive.upload",
            input_payload={"file_path": file_target},
            risk_tier=RiskTier.TIER_2_MEDIUM,
            dependencies=[s1.step_id],
            timeout_seconds=60,
        )

        s3 = TaskStepContract(
            workflow_id=wf_id,
            step_index=2,
            name="verify_drive_upload",
            description="Query Google Drive API to verify file ID and byte size",
            agent_type=AgentType.CLOUD_FILE,
            tool_name="drive.search",
            input_payload={"file_name": file_target},
            risk_tier=RiskTier.TIER_1_LOW,
            dependencies=[s2.step_id],
            timeout_seconds=20,
        )

        deps = [
            StepDependency(parent_step_id=s1.step_id, child_step_id=s2.step_id),
            StepDependency(parent_step_id=s2.step_id, child_step_id=s3.step_id),
        ]
        return [s1, s2, s3], deps

    def _plan_communication(
        self,
        wf_id: str,
        context: NormalizedTaskContext,
    ) -> Tuple[List[TaskStepContract], List[StepDependency]]:
        """Decompose Telegram message or notification dispatch."""
        entities = context.parsed_intent.extracted_entities
        s1 = TaskStepContract(
            workflow_id=wf_id,
            step_index=0,
            name="dispatch_telegram_message",
            description=f"Dispatch notification to {entities.recipient or 'default_chat'}",
            agent_type=AgentType.COMMUNICATION,
            tool_name="telegram.send_message",
            input_payload={
                "recipient": entities.recipient or "default",
                "message": entities.subject or context.parsed_intent.normalized_input,
            },
            risk_tier=RiskTier.TIER_1_LOW,
            timeout_seconds=15,
        )
        return [s1], []

    def _plan_pc_control(
        self,
        wf_id: str,
        context: NormalizedTaskContext,
    ) -> Tuple[List[TaskStepContract], List[StepDependency]]:
        """Decompose Local PC read-only hardware & telemetry query."""
        s1 = TaskStepContract(
            workflow_id=wf_id,
            step_index=0,
            name="query_pc_telemetry",
            description="Query local Windows CPU, RAM, Disk, Network, and thermal sensors",
            agent_type=AgentType.PC,
            tool_name="pc.get_health_summary",
            input_payload={"query": context.parsed_intent.normalized_input},
            risk_tier=RiskTier.TIER_1_LOW,
            timeout_seconds=15,
        )
        return [s1], []

    def _plan_research_query(
        self,
        wf_id: str,
        context: NormalizedTaskContext,
    ) -> Tuple[List[TaskStepContract], List[StepDependency]]:
        """Decompose web research, documentation lookup, and synthesis."""
        entities = context.parsed_intent.extracted_entities
        query = entities.query_text or context.parsed_intent.normalized_input

        s1 = TaskStepContract(
            workflow_id=wf_id,
            step_index=0,
            name="search_web_sources",
            description=f"Search web documentation for '{query}'",
            agent_type=AgentType.RESEARCH,
            tool_name="web.search",
            input_payload={"query": query},
            risk_tier=RiskTier.TIER_1_LOW,
            timeout_seconds=30,
        )

        s2 = TaskStepContract(
            workflow_id=wf_id,
            step_index=1,
            name="synthesize_research_summary",
            description="Aggregate search results into structured findings",
            agent_type=AgentType.RESEARCH,
            tool_name="research.synthesize",
            input_payload={"query": query},
            risk_tier=RiskTier.TIER_1_LOW,
            dependencies=[s1.step_id],
            timeout_seconds=30,
        )

        deps = [StepDependency(parent_step_id=s1.step_id, child_step_id=s2.step_id)]
        return [s1, s2], deps

    def _plan_general_action(
        self,
        wf_id: str,
        context: NormalizedTaskContext,
    ) -> Tuple[List[TaskStepContract], List[StepDependency]]:
        """Fallback decomposition for general action."""
        s1 = TaskStepContract(
            workflow_id=wf_id,
            step_index=0,
            name="execute_general_action",
            description=context.parsed_intent.normalized_input,
            agent_type=AgentType.MASTER,
            tool_name="system.general_action",
            input_payload={"instruction": context.parsed_intent.normalized_input},
            risk_tier=RiskTier.TIER_1_LOW,
            timeout_seconds=30,
        )
        return [s1], []
