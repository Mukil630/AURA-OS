"""Master Agent Reasoning and Natural Language Understanding Orchestrator with Multi-Turn Memory Context."""
import re
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from app.core.contracts.agent import AgentCapabilityContract, AgentContract
from app.core.contracts.intent import (
    ExtractedEntitiesContract,
    NormalizedTaskContext,
    ParsedIntentContract,
)
from app.core.contracts.memory import MemoryContract
from app.core.contracts.task import TaskContract
from app.core.contracts.task_step import TaskStepContract
from app.core.enums import (
    AgentStatus,
    AgentType,
    ChannelType,
    IntentCategory,
    RiskLevel,
    TaskStatus,
)
from app.core.interfaces.agent import IAgent
from app.core.intent_classifier import IntentClassifier
from app.core.normalizer import RequestNormalizer


class MasterAgent(IAgent):
    """
    Central reasoning coordinator for MUKIL MASTER AGENT OS.
    Responsible for request intake, normalization, intent understanding, multi-turn entity resolution,
    and planning context prep.
    """

    def __init__(
        self,
        normalizer: Optional[RequestNormalizer] = None,
        classifier: Optional[IntentClassifier] = None,
    ):
        self._normalizer = normalizer or RequestNormalizer()
        self._classifier = classifier or IntentClassifier()
        self._agent_id = "master_agent"
        self._agent_type = AgentType.MASTER

    @property
    def agent_id(self) -> str:
        return self._agent_id

    @property
    def agent_type(self) -> AgentType:
        return self._agent_type

    async def get_contract(self) -> AgentContract:
        """Return Master Agent capability contract."""
        return AgentContract(
            agent_id=self.agent_id,
            name="Master Agent Brain",
            agent_type=self.agent_type,
            description="Central reasoning, intent understanding, and context building engine.",
            version="1.0.0",
            status=AgentStatus.IDLE,
            capabilities=[
                AgentCapabilityContract(
                    capability_id="master.understand_intent",
                    name="Natural Language Intent Understanding",
                    description="Normalizes input, classifies intent, resolves multi-turn pronouns, and maps capabilities.",
                    risk_level=RiskLevel.LOW,
                )
            ],
            allowed_tools=[],
            max_concurrency=20,
        )

    def understand(
        self,
        raw_input: str,
        channel: ChannelType = ChannelType.API,
        user_id: str = "default_user",
        client_context: Optional[Dict[str, Any]] = None,
        task_id: Optional[str] = None,
        memory_context: Optional[List[MemoryContract]] = None,
    ) -> NormalizedTaskContext:
        """
        Transform raw natural language into a validated, capability-mapped NormalizedTaskContext.
        Enriches entities using multi-turn memory context if available.
        """
        # Step 1: Normalize & Sanitize
        normalized_payload = self._normalizer.normalize(
            raw_input=raw_input,
            channel=channel,
            client_context=client_context,
        )

        # Step 2: Classify Intent & Extract Entities
        parsed_intent = self._classifier.classify(normalized_payload)

        # Step 3: Multi-Turn Memory Entity Resolution (Pronoun / Context Binding)
        if memory_context:
            parsed_intent = self._resolve_entities_from_memory(parsed_intent, memory_context)

        # Step 4: Package Context for Planner
        assigned_task_id = task_id or f"task_{uuid4().hex[:12]}"
        return NormalizedTaskContext(
            task_id=assigned_task_id,
            user_id=user_id,
            channel=channel,
            parsed_intent=parsed_intent,
            context_metadata={
                "detected_language": normalized_payload.detected_language,
                "original_raw": raw_input,
                "cleaned_text": normalized_payload.cleaned_text,
                "memory_items_injected": len(memory_context) if memory_context else 0,
            },
        )

    def _resolve_entities_from_memory(
        self,
        parsed_intent: ParsedIntentContract,
        memories: List[MemoryContract],
    ) -> ParsedIntentContract:
        """
        Bind contextual entities from memory when user prompt uses implicit references
        (e.g., 'its CI', 'the repo', 'my repository', 'fix the issue', 'the file').
        """
        entities = parsed_intent.extracted_entities
        text_lower = parsed_intent.normalized_input.lower()
        combined_mem_text = " ".join([m.content for m in memories])

        # Resolve Target Repository
        if not entities.target_repo:
            is_referential = any(
                w in text_lower for w in ["it", "its", "repo", "repository", "project", "main repo", "default repo", "ci", "build"]
            )
            if is_referential:
                repo_match = re.search(r"([a-zA-Z0-9_\-]+/[a-zA-Z0-9_\-]+)", combined_mem_text)
                if repo_match:
                    entities.target_repo = repo_match.group(1)

        # Resolve File Path
        if not entities.file_path:
            is_file_ref = any(w in text_lower for w in ["file", "bill", "invoice", "report", "pdf", "backup", "vault", "drive"])
            if is_file_ref:
                file_match = re.search(r"([a-zA-Z0-9_\-/\\]+\.[a-zA-Z0-9]+)", combined_mem_text)
                if file_match:
                    entities.file_path = file_match.group(1)

        return parsed_intent.model_copy(update={"extracted_entities": entities})

    def enrich_task_with_understanding(
        self,
        task: TaskContract,
        memory_context: Optional[List[MemoryContract]] = None,
    ) -> Tuple[TaskContract, NormalizedTaskContext]:
        """
        Take a stored Phase 1 TaskContract, apply Phase 2 understanding + Phase 6 memory,
        and transition its status to PLANNING with classified metadata.
        """
        context = self.understand(
            raw_input=task.raw_input,
            channel=task.channel,
            user_id=task.user_id,
            task_id=task.task_id,
            memory_context=memory_context,
        )

        parsed = context.parsed_intent
        updated_task = task.model_copy(
            update={
                "intent": parsed.intent,
                "task_type": parsed.task_type,
                "risk_level": parsed.risk_level,
                "status": TaskStatus.PLANNING,
            }
        )
        return updated_task, context

    async def execute_step(self, step: TaskStepContract, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute reasoning step if dispatched directly to Master Agent."""
        return {"status": "understood", "step_id": step.step_id}

    async def health_check(self) -> bool:
        """Diagnostic health check."""
        return True
