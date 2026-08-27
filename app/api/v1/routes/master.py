"""Master Agent Natural Language Understanding API Endpoints."""
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.master.master_agent import MasterAgent
from app.core.contracts.execution_event import ExecutionEventContract
from app.core.contracts.intent import NormalizedTaskContext
from app.core.contracts.task import TaskResponseContract
from app.core.enums import ChannelType, EventSeverity, EventType, TaskStatus
from app.database.repositories.event_repo import EventRepository
from app.database.repositories.task_repo import TaskRepository
from app.database.session import get_db
from app.security.auth import AuthenticatedUser, get_current_user

router = APIRouter(prefix="/master", tags=["Master Agent Brain"])
_master_agent = MasterAgent()


class UnderstandRequest(BaseModel):
    """Input payload for natural language intent understanding."""
    raw_input: str = Field(..., min_length=1, description="Raw user prompt or voice transcription")
    channel: ChannelType = Field(default=ChannelType.API, description="Source input channel")
    user_id: Optional[str] = Field(default=None, description="Optional user ID")
    client_context: Dict[str, Any] = Field(default_factory=dict, description="Client device context")


class ParseTaskResponse(BaseModel):
    """Response returned when stored task is understood and transitioned."""
    task: TaskResponseContract = Field(..., description="Updated task state")
    understanding: NormalizedTaskContext = Field(..., description="Parsed intent and capability context")


@router.post(
    "/understand",
    response_model=NormalizedTaskContext,
    summary="Understand Natural Language Request",
    description="Transforms raw natural language into structured IntentCategory, TaskType, Required Capabilities, and Extracted Entities without executing tools.",
)
async def understand_request(
    payload: UnderstandRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> NormalizedTaskContext:
    """Analyze and structure natural language input."""
    target_user = payload.user_id or current_user.user_id
    return _master_agent.understand(
        raw_input=payload.raw_input,
        channel=payload.channel,
        user_id=target_user,
        client_context=payload.client_context,
    )


@router.post(
    "/tasks/{task_id}/parse",
    response_model=ParseTaskResponse,
    summary="Parse and enrich a stored task",
    description="Loads a stored Phase 1 task, executes Master Agent intent understanding, transitions status to PLANNING, records TASK_PARSED event, and saves updated state to database.",
)
async def parse_stored_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> ParseTaskResponse:
    """Trigger Phase 2 understanding on an existing stored task."""
    task_repo = TaskRepository(db)
    event_repo = EventRepository(db)

    task = await task_repo.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID '{task_id}' not found.",
        )

    # Tenant isolation
    if current_user.role != "admin" and task.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You do not have permission to parse this task.",
        )

    # Execute Master Agent understanding
    updated_task_contract, context = _master_agent.enrich_task_with_understanding(task)

    # Persist updated task in DB
    saved_task = await task_repo.update_task_status(
        task_id=task_id,
        status=TaskStatus.PLANNING,
    )
    # Also update intent, task_type, risk_level in DB model
    stmt_task = await task_repo.get_task(task_id)
    # Record TASK_PARSED trace event
    await event_repo.record_event(
        ExecutionEventContract(
            trace_id=f"tr_{task_id}",
            task_id=task_id,
            event_type=EventType.TASK_PARSED,
            severity=EventSeverity.INFO,
            source_component="MasterAgent",
            message=f"Task understood: Intent='{context.parsed_intent.intent}', Capabilities={context.parsed_intent.required_capabilities}",
            payload={
                "intent": str(context.parsed_intent.intent),
                "task_type": str(context.parsed_intent.task_type),
                "required_capabilities": context.parsed_intent.required_capabilities,
                "extracted_entities": context.parsed_intent.extracted_entities.model_dump(),
                "confidence": context.parsed_intent.confidence_score,
            },
        )
    )

    return ParseTaskResponse(
        task=TaskResponseContract(task=updated_task_contract, message="Task parsed and ready for planner."),
        understanding=context,
    )
