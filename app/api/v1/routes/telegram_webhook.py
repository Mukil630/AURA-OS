"""Telegram Inbound Webhook Gateway and Normalized Task Pipeline."""
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.master.master_agent import MasterAgent
from app.connectors.policy import default_policy_engine
from app.connectors.telegram.auth import TelegramAuthorizer
from app.connectors.telegram.connector import TelegramConnector
from app.connectors.telegram.contracts import (
    TelegramOutboundMessage,
    TelegramResponseState,
    TelegramUpdate,
)
from app.connectors.telegram.idempotency import TelegramReplayGuard
from app.connectors.telegram.response_builder import TelegramResponseBuilder
from app.core.contracts.connector import ConnectorExecutionRequest
from app.core.contracts.execution_event import ExecutionEventContract
from app.core.contracts.task import TaskContract
from app.core.enums import ChannelType, EventSeverity, EventType, TaskStatus
from app.core.planner import TaskPlanner
from app.database.repositories.event_repo import EventRepository
from app.database.repositories.task_repo import TaskRepository
from app.database.repositories.workflow_repo import WorkflowRepository
from app.database.session import get_db
from app.engine.workflow_engine import WorkflowEngine
from app.memory.manager import MemoryManager


router = APIRouter(prefix="/telegram", tags=["Telegram Channel Gateway"])

# Singleton Components
_authorizer = TelegramAuthorizer()
_replay_guard = TelegramReplayGuard()
_policy_engine = default_policy_engine
_telegram_connector = TelegramConnector()
_master_agent = MasterAgent()
_task_planner = TaskPlanner()


class TelegramWebhookResponse(BaseModel):
    """Response returned to Telegram server."""
    ok: bool
    status: str
    task_id: Optional[str] = None
    response_delivered: bool = False
    message: Optional[str] = None


@router.post(
    "/webhook",
    response_model=TelegramWebhookResponse,
    summary="Telegram Inbound Webhook Endpoint",
    description="Authenticates Telegram webhook updates, authorizes users, enforces idempotency & rate limits, maps to P1 Intake, and dispatches full Agent pipeline to response.",
)
async def receive_telegram_webhook(
    update: TelegramUpdate,
    x_telegram_bot_api_secret_token: Optional[str] = Header(None, alias="X-Telegram-Bot-Api-Secret-Token"),
    db: AsyncSession = Depends(get_db),
) -> TelegramWebhookResponse:
    """Process incoming Telegram update."""
    event_repo = EventRepository(db)
    task_repo = TaskRepository(db)
    wf_repo = WorkflowRepository(db)
    mem_mgr = MemoryManager(db)

    # 1. Emergency Kill-Switch Check
    if not _policy_engine.is_connector_enabled("connector_telegram"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telegram Channel is temporarily disabled by emergency kill-switch.",
        )

    # 2. Webhook Authentication
    if not _authorizer.verify_webhook_secret(x_telegram_bot_api_secret_token):
        await event_repo.record_event(
            ExecutionEventContract(
                trace_id=f"tr_tg_auth_fail_{update.update_id}",
                task_id=f"tg_update_{update.update_id}",
                event_type=EventType.TELEGRAM_REJECTED,
                severity=EventSeverity.WARNING,
                source_component="TelegramGateway",
                message=f"Rejected unauthenticated Telegram webhook update {update.update_id}.",
            )
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized webhook payload: Invalid secret token.",
        )

    # 3. Payload Integrity Check
    if not update.message or not update.message.text:
        return TelegramWebhookResponse(ok=True, status="ignored_empty_message")

    sender = update.message.from_user
    sender_id = sender.id if sender else update.message.chat.id
    sender_username = sender.username if sender else None
    chat_id = update.message.chat.id
    raw_text = update.message.text.strip()
    update_id = update.update_id

    # 4. Sender Authorization & Tenant Mapping
    tenant_user_id = _authorizer.authorize_user(sender_id, sender_username)
    if not tenant_user_id:
        await event_repo.record_event(
            ExecutionEventContract(
                trace_id=f"tr_tg_{update_id}",
                task_id=f"tg_update_{update_id}",
                event_type=EventType.TELEGRAM_REJECTED,
                severity=EventSeverity.WARNING,
                source_component="TelegramGateway",
                message=f"Rejected unauthorized Telegram user {sender_id} (@{sender_username}).",
            )
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access Denied: Telegram identity is not mapped to an authorized tenant.",
        )

    # 5. Replay Protection / Idempotency Check
    if _replay_guard.is_duplicate(update_id):
        existing_task = _replay_guard.get_associated_task_id(update_id)
        await event_repo.record_event(
            ExecutionEventContract(
                trace_id=f"tr_tg_{update_id}",
                task_id=existing_task or f"tg_{update_id}",
                event_type=EventType.TELEGRAM_UPDATE_DUPLICATE,
                severity=EventSeverity.INFO,
                source_component="TelegramGateway",
                message=f"Duplicate Telegram update {update_id} received and safely ignored.",
            )
        )
        await db.commit()
        return TelegramWebhookResponse(
            ok=True,
            status="duplicate_ignored",
            task_id=existing_task,
            message="Duplicate update ignored.",
        )

    # 6. Rate Limiting Check
    rate_key = f"telegram_user_{sender_id}"
    if not _policy_engine.check_and_consume_rate_limit(rate_key, max_per_minute=20):
        await event_repo.record_event(
            ExecutionEventContract(
                trace_id=f"tr_tg_{update_id}",
                task_id=f"tg_{update_id}",
                event_type=EventType.TELEGRAM_RATE_LIMITED,
                severity=EventSeverity.WARNING,
                source_component="TelegramGateway",
                message=f"Telegram rate limit exceeded for user {sender_id}.",
            )
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please wait before sending more Telegram requests.",
        )

    # 7. Record Authentication Event
    await event_repo.record_event(
        ExecutionEventContract(
            trace_id=f"tr_tg_{update_id}",
            task_id=f"tg_{update_id}",
            event_type=EventType.TELEGRAM_AUTHENTICATED,
            severity=EventSeverity.INFO,
            source_component="TelegramGateway",
            message=f"Authenticated Telegram user {sender_id} (@{sender_username}) mapped to tenant '{tenant_user_id}'.",
        )
    )

    # ── P1 INTAKE ─────────────────────────────────────────────────────────────
    task_contract = TaskContract(
        user_id=tenant_user_id,
        raw_input=raw_text,
        channel=ChannelType.TELEGRAM,
        metadata={"telegram_chat_id": chat_id, "telegram_update_id": update_id, "sender_id": sender_id},
    )
    saved_task = await task_repo.create_task(task_contract)
    _replay_guard.record_update(update_id, saved_task.task_id)

    trace_id = f"tr_{saved_task.task_id}"

    await event_repo.record_event(
        ExecutionEventContract(
            trace_id=trace_id,
            task_id=saved_task.task_id,
            event_type=EventType.TELEGRAM_TASK_CREATED,
            severity=EventSeverity.INFO,
            source_component="TelegramGateway",
            message=f"Created Task '{saved_task.task_id}' from Telegram message: {raw_text}",
        )
    )

    # ── P2 UNDERSTAND + P6 MEMORY RETRIEVAL ───────────────────────────────────
    mem_context = await mem_mgr.build_context(user_id=tenant_user_id, raw_input=raw_text)
    enriched_task, context = _master_agent.enrich_task_with_understanding(saved_task, memory_context=mem_context)

    # ── P3 TASK PLANNER ───────────────────────────────────────────────────────
    plan, workflow = _task_planner.plan(context)
    saved_wf = await wf_repo.create_workflow_with_steps(workflow)
    await task_repo.update_task_status(saved_task.task_id, TaskStatus.PLANNING, workflow_id=saved_wf.workflow_id)

    # ── P4 EXECUTE & P5 VERIFY ───────────────────────────────────────────────
    engine = WorkflowEngine(db_session=db)
    final_wf, final_task = await engine.execute_workflow(saved_wf.workflow_id)

    # ── P6 OUTBOUND RESPONSE BUILDER & DISPATCH ───────────────────────────────
    resp_state = TelegramResponseState.TASK_COMPLETED
    summary_msg = final_task.result_summary if final_task else "Task executed successfully."
    err_msg = None

    if final_task and final_task.status == TaskStatus.WAITING_FOR_APPROVAL:
        resp_state = TelegramResponseState.WAITING_FOR_APPROVAL
    elif final_task and final_task.status == TaskStatus.FAILED:
        resp_state = TelegramResponseState.TASK_FAILED
        err_msg = final_task.error_message

    outbound_msg = TelegramResponseBuilder.build_response(
        chat_id=chat_id,
        state=resp_state,
        task_id=saved_task.task_id,
        summary=summary_msg,
        error_message=err_msg,
        reply_to_message_id=update.message.message_id,
    )

    exec_req = ConnectorExecutionRequest(
        capability_id="telegram.send_message",
        parameters={
            "chat_id": chat_id,
            "text": outbound_msg.text,
            "parse_mode": outbound_msg.parse_mode,
            "response_state": resp_state,
        },
        task_id=saved_task.task_id,
    )
    disp_res = await _telegram_connector.execute_capability(
        request=exec_req,
        credentials=None,
    )

    await event_repo.record_event(
        ExecutionEventContract(
            trace_id=trace_id,
            task_id=saved_task.task_id,
            event_type=EventType.TELEGRAM_RESPONSE_SENT,
            severity=EventSeverity.INFO,
            source_component="TelegramGateway",
            message=f"Dispatched Telegram response ({resp_state.value}) to chat {chat_id}.",
            payload={"response_text": outbound_msg.text},
        )
    )
    await db.commit()

    return TelegramWebhookResponse(
        ok=True,
        status="processed",
        task_id=saved_task.task_id,
        response_delivered=True,
        message=summary_msg,
    )
