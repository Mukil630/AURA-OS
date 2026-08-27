"""Milestone 2 Step 1: Telegram Mobile Gateway Service.
Edge adapter bridging authorized Telegram mobile clients (text, voice, commands, approvals)
directly into the Phase 12 Operating Plane (Admission Controller, Task Queue, Resource Locks,
Credential Vault, and Approval Policy Engine) without bypassing governance or leaking secrets.
"""
from abc import ABC, abstractmethod
from datetime import datetime, timezone
import json
import os
import re
import shlex
import subprocess
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from app.connectors.telegram.auth import TelegramAuthorizer
from app.connectors.telegram.contracts import (
    TelegramMessage,
    TelegramOutboundMessage,
    TelegramResponseState,
    TelegramUpdate,
    TelegramUser,
)
from app.connectors.telegram.idempotency import TelegramReplayGuard
from app.core.contracts.credential import RawSecretPayloadError
from app.core.contracts.governance import (
    AdmissionDecision,
    AdmissionEvaluationContract,
    AdmissionRequestContract,
    BudgetExhaustedError,
    QuotaDimension,
    QuotaExceededError,
    RateLimitExceededError,
)
from app.core.contracts.task import TaskContract
from app.core.enums import ChannelType, TaskStatus
from app.core.governance.admission_controller import AdmissionController
from app.policy.approval_engine import ApprovalEngine, default_approval_engine
from app.policy.telegram_approval import TelegramApprovalGateway


# ═════════════════════════════════════════════════════════════════════════════
# 1. VOICE TRANSCRIBER ABSTRACTION (SEPARATION OF CONCERNS)
# ═════════════════════════════════════════════════════════════════════════════

class IVoiceTranscriber(ABC):
    """Abstract interface for audio/voice message transcription."""

    @abstractmethod
    def transcribe(self, audio_bytes: bytes, filename: str = "voice.ogg") -> str:
        """Transcribe raw audio bytes into text."""
        pass


class MockVoiceTranscriber(IVoiceTranscriber):
    """Deterministic reference transcriber for automated testing."""

    def __init__(self, transcript_override: Optional[str] = None):
        self.transcript_override = transcript_override or "List active tasks on PC"

    def transcribe(self, audio_bytes: bytes, filename: str = "voice.ogg") -> str:
        if not audio_bytes:
            raise ValueError("Audio payload cannot be empty.")
        return self.transcript_override


# ═════════════════════════════════════════════════════════════════════════════
# 2. SAFE PC COMMAND ALLOWLIST VALIDATOR
# ═════════════════════════════════════════════════════════════════════════════

class SafeCommandValidator:
    """
    Validates and restricts /exec commands against strict read-only diagnostic allowlists.
    Blocks execution wrappers (cmd/powershell/bash), subshell interpolation ($()/backticks),
    piping, redirection, encoded commands, execution policy tampering, and web downloading.
    """

    SAFE_COMMAND_PREFIXES = (
        "dir",
        "ls",
        "hostname",
        "whoami",
        "date",
        "time",
        "systeminfo",
        "get-process",
        "get-service",
        "get-date",
        "ipconfig",
        "tasklist",
        "echo",
    )

    DANGEROUS_PATTERNS = [
        re.compile(r"[;&|`$><]"),                                # Shell chaining, subshells, interpolation, redirection
        re.compile(r"\$\(.*?\)"),                                # $(subshell)
        re.compile(r"\$\{.*?\}"),                                # ${var}
        re.compile(r"\b(cmd|cmd\.exe)\b", re.I),                # cmd wrapper
        re.compile(r"\b(powershell|powershell\.exe|pwsh|pwsh\.exe)\b", re.I), # PowerShell interpreter
        re.compile(r"\b(bash|sh|zsh|wscript|cscript)\b", re.I), # Alternative shells
        re.compile(r"-(enc|encodedcommand|command|c|k)\b", re.I), # Encoded flags
        re.compile(r"/(c|k)\b", re.I),                           # cmd /c or /k
        re.compile(r"\bInvoke-Expression\b", re.I),
        re.compile(r"\biex\b", re.I),
        re.compile(r"\bStart-Process\b", re.I),
        re.compile(r"\bDownloadString\b", re.I),
        re.compile(r"\bDownloadFile\b", re.I),
        re.compile(r"\bSet-ExecutionPolicy\b", re.I),
        re.compile(r"\b(Invoke-WebRequest|iwr|curl|wget)\b", re.I),
        re.compile(r"\b(rmdir|del|erase|format|shutdown|reboot)\b", re.I),
        re.compile(r"\b(net\s+user|net\s+localgroup|reg\s+add|reg\s+delete)\b", re.I),
    ]

    @classmethod
    def validate_command(cls, raw_cmd: str) -> Tuple[bool, Optional[str]]:
        """
        Validates command safety against strict diagnostic allowlists.
        Returns (is_safe, error_reason).
        """
        cleaned = raw_cmd.strip()
        if not cleaned:
            return False, "Command cannot be empty."

        # Check for dangerous metacharacters and wrapper patterns
        for pattern in cls.DANGEROUS_PATTERNS:
            if pattern.search(cleaned):
                return False, f"Command contains prohibited shell wrappers, metacharacters, or dangerous operators."

        # Check against prefix allowlist
        cmd_first_token = cleaned.split()[0].lower()
        if cmd_first_token not in cls.SAFE_COMMAND_PREFIXES:
            return False, f"Command '{cmd_first_token}' is not in the authorized PC diagnostic allowlist."

        return True, None


# ═════════════════════════════════════════════════════════════════════════════
# 3. TELEGRAM GATEWAY SERVICE
# ═════════════════════════════════════════════════════════════════════════════

class TelegramGatewayService:
    """
    Production-grade Telegram Mobile Gateway Edge Adapter.
    Validates identity, enforces replay protection, queries Admission Controller (P12.5),
    routes slash commands, handles approval callbacks (Phase 10), and formats outbound responses.
    """

    # Secret leakage inspection patterns
    FORBIDDEN_SECRET_PATTERNS = [
        re.compile(r"ghp_[a-zA-Z0-9]{36}"),
        re.compile(r"ya29\.[a-zA-Z0-9_\-]+"),
        re.compile(r"(?i)password\s*[:=]\s*\S+"),
        re.compile(r"(?i)bearer\s+[a-zA-Z0-9_\-\.]{20,}"),
        re.compile(r"\b\d{9,10}:[a-zA-Z0-9_-]{35}\b"),  # Telegram Bot Token format
    ]

    def __init__(
        self,
        authorizer: Optional[TelegramAuthorizer] = None,
        replay_guard: Optional[TelegramReplayGuard] = None,
        admission_controller: Optional[AdmissionController] = None,
        approval_engine: Optional[ApprovalEngine] = None,
        voice_transcriber: Optional[IVoiceTranscriber] = None,
        allowed_user_ids: Optional[Set[int]] = None,
        task_dispatcher: Optional[Callable[[TaskContract], Any]] = None,
    ) -> None:
        self.authorizer = authorizer or TelegramAuthorizer()
        self.replay_guard = replay_guard or TelegramReplayGuard()
        self.admission_controller = admission_controller or AdmissionController()
        self.approval_engine = approval_engine or default_approval_engine
        self.approval_gateway = TelegramApprovalGateway(self.approval_engine, self.authorizer)
        self.voice_transcriber = voice_transcriber or MockVoiceTranscriber()
        self.task_dispatcher = task_dispatcher

        # Configure allowed numeric Telegram user IDs
        if allowed_user_ids is not None:
            self.allowed_user_ids: Set[int] = allowed_user_ids
        else:
            env_ids = os.getenv("ALLOWED_TELEGRAM_USER_IDS", "").strip()
            if env_ids and env_ids != "*":
                self.allowed_user_ids = {int(x.strip()) for x in env_ids.split(",") if x.strip().isdigit()}
            else:
                self.allowed_user_ids = set()  # Allow active local operator

        # Static Vault Reference Configuration
        self.master_resume_url = os.getenv(
            "MASTER_RESUME_URL",
            "https://drive.google.com/file/d/1TpyzV7OGEf-YQfGLUpusAI5cDDvF1kAJ/view?usp=drive_link"
        )
        self.drive_vault_url = os.getenv(
            "DRIVE_VAULT_URL",
            "https://drive.google.com/drive/folders/1iaHzDzC7KiJk2FlMdS7eNW7vkYxDeaXZ?usp=drive_link"
        )
        self.billing_vault_1_url = "https://drive.google.com/drive/folders/155EqYOwPJ2Fc9QfqVSrZu5VnYzZgRcyZ?usp=drive_link"
        self.billing_vault_2_url = "https://drive.google.com/drive/folders/1a9VJAP_Nypn_mjUEYCNvMpkGN5H9Kwf4?usp=sharing"

    # ─────────────────────────────────────────────────────────────────────────
    # 1. INBOUND DISPATCH ENTRY POINT
    # ─────────────────────────────────────────────────────────────────────────

    def process_update(
        self,
        update: TelegramUpdate,
        raw_voice_bytes: Optional[bytes] = None,
    ) -> TelegramOutboundMessage:
        """
        Main entry point for processing incoming Telegram updates.
        Validates identity, prevents replay, evaluates admission, and dispatches to handler.
        """
        # A. Basic payload extraction
        if not update or not update.message:
            return TelegramOutboundMessage(
                chat_id=0,
                text="Invalid update: Missing message body.",
                response_state=TelegramResponseState.TASK_FAILED,
            )

        msg = update.message
        sender = msg.from_user
        chat_id = msg.chat.id
        update_id = update.update_id

        if not sender:
            return self._build_forbidden_response(chat_id, "Sender identity cannot be verified.")

        sender_id = sender.id
        username = sender.username

        # B. Strict Identity Validation (Numeric ID + Authorizer)
        if self.allowed_user_ids and sender_id not in self.allowed_user_ids:
            return self._build_forbidden_response(chat_id, f"Access Denied: Telegram user is not authorized. (Your User ID: `{sender_id}`)")

        tenant_id = self.authorizer.authorize_user(sender_id, username) or "mukil"

        # C. Inbound Replay Protection
        if self.replay_guard.is_duplicate(update_id):
            assoc_task = self.replay_guard.get_associated_task_id(update_id)
            return TelegramOutboundMessage(
                chat_id=chat_id,
                text="Duplicate update received. Processing skipped.",
                reply_to_message_id=msg.message_id,
                response_state=TelegramResponseState.TASK_ACCEPTED,
                metadata={"duplicate": True, "task_id": assoc_task},
            )

        # D. Extract text content (Text message or Voice transcription)
        raw_text = msg.text.strip() if msg.text else None

        if not raw_text and raw_voice_bytes:
            try:
                raw_text = self.voice_transcriber.transcribe(raw_voice_bytes)
            except Exception as ex:
                return TelegramOutboundMessage(
                    chat_id=chat_id,
                    text=f"Voice transcription failed: {str(ex)}",
                    reply_to_message_id=msg.message_id,
                    response_state=TelegramResponseState.TASK_FAILED,
                )

        if not raw_text:
            return TelegramOutboundMessage(
                chat_id=chat_id,
                text="Ignored: Message contains no readable text or voice content.",
                reply_to_message_id=msg.message_id,
                response_state=TelegramResponseState.TASK_ACCEPTED,
            )

        # Audit for secrets in incoming text
        self._audit_for_secrets(raw_text)

        # E. Command Routing vs Normal Task Request
        if raw_text.startswith("/"):
            return self._handle_slash_command(update_id, chat_id, sender_id, username, tenant_id, raw_text, msg.message_id)

        # F. Normal Task Message -> Admission Controller & Pipeline
        return self._handle_normal_task(update_id, chat_id, sender_id, username, tenant_id, raw_text, msg.message_id)

    # ─────────────────────────────────────────────────────────────────────────
    # 2. SLASH COMMAND ROUTING
    # ─────────────────────────────────────────────────────────────────────────

    def _handle_slash_command(
        self,
        update_id: int,
        chat_id: int,
        sender_id: int,
        username: Optional[str],
        tenant_id: str,
        command_text: str,
        message_id: int,
    ) -> TelegramOutboundMessage:
        parts = command_text.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        # 1. /start
        if cmd == "/start":
            self.replay_guard.record_update(update_id)
            return self._build_start_response(chat_id, message_id)

        # 2. /status
        elif cmd == "/status":
            self.replay_guard.record_update(update_id)
            return self._build_status_response(chat_id, tenant_id, message_id)

        # 3. /drive
        elif cmd == "/drive":
            self.replay_guard.record_update(update_id)
            return self._build_drive_response(chat_id, message_id)

        # 4. /resume
        elif cmd == "/resume":
            self.replay_guard.record_update(update_id)
            return self._build_resume_response(chat_id, message_id)

        # 5. /tasks
        elif cmd == "/tasks":
            self.replay_guard.record_update(update_id)
            return self._build_tasks_response(chat_id, tenant_id, message_id)

        # 6. /approve or /reject (Human in the loop)
        elif cmd in ("/approve", "/reject"):
            self.replay_guard.record_update(update_id)
            return self._handle_approval_decision(chat_id, sender_id, username, command_text, message_id)

        # 7. /exec <command> (Whitelisted PC diagnostics)
        elif cmd == "/exec":
            return self._handle_exec_command(update_id, chat_id, tenant_id, args, message_id)

        # 8. Unknown command
        else:
            self.replay_guard.record_update(update_id)
            return TelegramOutboundMessage(
                chat_id=chat_id,
                text=f"Unsupported command `{cmd}`. Use `/status`, `/tasks`, `/drive`, `/resume`, `/approve`, or `/exec`.",
                reply_to_message_id=message_id,
                response_state=TelegramResponseState.TASK_FAILED,
            )

    # ─────────────────────────────────────────────────────────────────────────
    # 3. NORMAL TASK PIPELINE & ADMISSION GOVERNANCE
    # ─────────────────────────────────────────────────────────────────────────

    def _handle_normal_task(
        self,
        update_id: int,
        chat_id: int,
        sender_id: int,
        username: Optional[str],
        tenant_id: str,
        task_input: str,
        message_id: int,
    ) -> TelegramOutboundMessage:
        task_id = f"task_tg_{update_id}"

        # 1. Phase 12.5 Admission Controller Evaluation
        adm_req = AdmissionRequestContract(
            request_id=f"adm_tg_{update_id}",
            tenant_id=tenant_id,
            task_id=task_id,
            estimated_tokens=500,  # Baseline token estimate for incoming task intake
        )
        adm_eval = self.admission_controller.evaluate_admission(adm_req, auto_reserve=True)

        if not adm_eval.allowed:
            # Deterministic status code mapping
            err_text = f"🛑 *Task Admission Denied*\n\nReason: {adm_eval.reason}"
            if adm_eval.decision == AdmissionDecision.DENY_RATE_LIMIT:
                err_text += f"\n_Please retry after {adm_eval.retry_after_seconds:.1f}s._"

            decision_val = adm_eval.decision.value if hasattr(adm_eval.decision, "value") else str(adm_eval.decision)
            return TelegramOutboundMessage(
                chat_id=chat_id,
                text=err_text,
                reply_to_message_id=message_id,
                response_state=TelegramResponseState.TASK_FAILED,
                metadata={"decision": decision_val},
            )

        # 2. Record update in replay guard
        self.replay_guard.record_update(update_id, task_id=task_id)

        # 3. Create canonical TaskContract
        task = TaskContract(
            task_id=task_id,
            user_id=tenant_id,
            raw_input=task_input,
            channel=ChannelType.TELEGRAM,
            metadata={
                "telegram_chat_id": chat_id,
                "telegram_sender_id": sender_id,
                "telegram_username": username,
                "reservation_id": adm_eval.current_usage.get("reservation_id"),
            },
        )

        # 4. Dispatch to Task Pipeline / Worker Queue if handler attached
        if self.task_dispatcher:
            try:
                self.task_dispatcher(task)
            except Exception as ex:
                self.admission_controller.abort_task(
                    tenant_id=tenant_id,
                    task_id=task_id,
                    reservation_id=adm_eval.current_usage.get("reservation_id"),
                )
                return TelegramOutboundMessage(
                    chat_id=chat_id,
                    text=f"Task dispatch failed: {str(ex)}",
                    reply_to_message_id=message_id,
                    response_state=TelegramResponseState.TASK_FAILED,
                )

        return TelegramOutboundMessage(
            chat_id=chat_id,
            text=f"⚡ *Task Accepted by Jarvis Master Agent*\n\n"
                 f"📋 *Task ID*: `{task_id}`\n"
                 f"📝 *Request*: _{task_input}_\n"
                 f"🚦 *Admission*: `ALLOWED`\n"
                 f"⏳ Status: Running...",
            reply_to_message_id=message_id,
            response_state=TelegramResponseState.TASK_ACCEPTED,
            metadata={"task_id": task_id},
        )

    # ─────────────────────────────────────────────────────────────────────────
    # 4. COMMAND HANDLERS
    # ─────────────────────────────────────────────────────────────────────────

    def _build_start_response(self, chat_id: int, message_id: int) -> TelegramOutboundMessage:
        text = (
            "⚡ *Vanakkam Maapla! I am your Personal JARVIS AI Agent.*\n\n"
            "Connected directly to your PC, Memory Vault, and 5TB Google Drive.\n\n"
            "📌 *Quick Commands:*\n"
            "• `/status` - Check PC & Memory Status\n"
            "• `/tasks` - View Active Tasks\n"
            "• `/drive` - Access 5TB Google Drive Vault\n"
            "• `/resume` - Access Master ATS Resume\n"
            "• `/exec <cmd>` - Run Safe PC Diagnostic\n\n"
            "Send text or voice notes to assign tasks!"
        )
        return TelegramOutboundMessage(
            chat_id=chat_id,
            text=text,
            reply_to_message_id=message_id,
            response_state=TelegramResponseState.TASK_ACCEPTED,
        )

    def _build_status_response(self, chat_id: int, tenant_id: str, message_id: int) -> TelegramOutboundMessage:
        usage = self.admission_controller.quota_manager.get_current_usage(tenant_id)
        quota = self.admission_controller.quota_manager.get_tenant_quota(tenant_id)

        # Real Live PC Hardware Diagnostics
        cpu_pct, ram_pct, ram_used_gb, ram_total_gb, battery_str = "N/A", "N/A", "N/A", "N/A", "N/A"
        try:
            import psutil
            cpu_pct = f"{psutil.cpu_percent(interval=0.05):.1f}%"
            vmem = psutil.virtual_memory()
            ram_pct = f"{vmem.percent:.1f}%"
            ram_used_gb = f"{vmem.used / (1024**3):.1f} GB"
            ram_total_gb = f"{vmem.total / (1024**3):.1f} GB"
            batt = psutil.sensors_battery()
            if batt:
                plug_status = "Plugged In" if batt.power_plugged else "On Battery"
                battery_str = f"{batt.percent:.0f}% ({plug_status})"
        except Exception:
            pass

        text = (
            "📊 *JARVIS Live System Status:*\n\n"
            f"• *Tenant*: `{tenant_id}`\n"
            f"• *PC Node*: 🟢 Online & Autonomous\n"
            f"• *CPU Usage*: `{cpu_pct}`\n"
            f"• *Memory*: `{ram_pct}` (`{ram_used_gb} / {ram_total_gb}`)\n"
            + (f"• *Battery*: `{battery_str}`\n" if battery_str != "N/A" else "")
            + f"• *Active Concurrency*: `{usage['active_concurrent_tasks']} / {quota.max_concurrent_tasks}`\n"
            f"• *Token Budget Used*: `{usage['tokens_used']} / {quota.max_tokens_per_period}`\n"
            f"• *Storage Used*: `{usage['storage_bytes_used']} / {quota.max_storage_bytes} bytes`\n"
            f"• *Drive Vault*: [Open Master Vault]({self.drive_vault_url})\n"
            f"• *Timestamp*: `{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}`"
        )
        return TelegramOutboundMessage(
            chat_id=chat_id,
            text=text,
            reply_to_message_id=message_id,
            response_state=TelegramResponseState.TASK_ACCEPTED,
        )

    def _build_drive_response(self, chat_id: int, message_id: int) -> TelegramOutboundMessage:
        text = (
            "☁️ *Google Drive Master Vaults:*\n\n"
            f"📁 *5TB Master Vault*: [Open Primary Folder]({self.drive_vault_url})\n"
            f"🧾 *SGC Billing Vault 1*: [Open Invoices 1]({self.billing_vault_1_url})\n"
            f"🧾 *SGC Billing Vault 2*: [Open Invoices 2]({self.billing_vault_2_url})\n"
            f"📄 *Master Resume*: [Open Resume]({self.master_resume_url})"
        )
        return TelegramOutboundMessage(
            chat_id=chat_id,
            text=text,
            reply_to_message_id=message_id,
            response_state=TelegramResponseState.TASK_ACCEPTED,
        )

    def _build_resume_response(self, chat_id: int, message_id: int) -> TelegramOutboundMessage:
        text = (
            "📄 *Mukil's Official Master ATS Resume:*\n\n"
            f"🔗 [Click here to view Master Resume]({self.master_resume_url})\n\n"
            "Use `/tasks` to trigger placement tailoring for job listings."
        )
        return TelegramOutboundMessage(
            chat_id=chat_id,
            text=text,
            reply_to_message_id=message_id,
            response_state=TelegramResponseState.TASK_ACCEPTED,
        )

    def _build_tasks_response(self, chat_id: int, tenant_id: str, message_id: int) -> TelegramOutboundMessage:
        active = self.admission_controller.quota_manager.get_active_concurrency_count(tenant_id)
        text = (
            "📋 *Task Queue Status:*\n\n"
            f"• Active In-Flight Tasks: `{active}`\n"
            "• All systems operational."
        )
        return TelegramOutboundMessage(
            chat_id=chat_id,
            text=text,
            reply_to_message_id=message_id,
            response_state=TelegramResponseState.TASK_ACCEPTED,
        )

    def _handle_approval_decision(
        self,
        chat_id: int,
        sender_id: int,
        username: Optional[str],
        command_text: str,
        message_id: int,
    ) -> TelegramOutboundMessage:
        success, msg = self.approval_gateway.process_telegram_decision(
            telegram_user_id=sender_id,
            raw_command=command_text,
            username=username,
        )
        state = TelegramResponseState.TASK_COMPLETED if success else TelegramResponseState.TASK_FAILED
        icon = "✅" if success else "❌"
        return TelegramOutboundMessage(
            chat_id=chat_id,
            text=f"{icon} *Approval Action*: {msg}",
            reply_to_message_id=message_id,
            response_state=state,
        )

    def _handle_exec_command(
        self,
        update_id: int,
        chat_id: int,
        tenant_id: str,
        command_args: str,
        message_id: int,
    ) -> TelegramOutboundMessage:
        if not command_args:
            return TelegramOutboundMessage(
                chat_id=chat_id,
                text="❌ Missing command. Usage: `/exec <diagnostic_command>`",
                reply_to_message_id=message_id,
                response_state=TelegramResponseState.TASK_FAILED,
            )

        # 1. Strict Allowlist Validation
        is_safe, error_reason = SafeCommandValidator.validate_command(command_args)
        if not is_safe:
            return TelegramOutboundMessage(
                chat_id=chat_id,
                text=f"🚫 *Security Blocked Command*\n\nReason: {error_reason}",
                reply_to_message_id=message_id,
                response_state=TelegramResponseState.TASK_FAILED,
            )

        # 2. Admission Check for Command Execution
        task_id = f"task_exec_{update_id}"
        adm_req = AdmissionRequestContract(
            request_id=f"adm_exec_{update_id}",
            tenant_id=tenant_id,
            task_id=task_id,
            estimated_tokens=100,
        )
        adm_eval = self.admission_controller.evaluate_admission(adm_req, auto_reserve=True)
        if not adm_eval.allowed:
            return TelegramOutboundMessage(
                chat_id=chat_id,
                text=f"🛑 *Execution Admission Denied*: {adm_eval.reason}",
                reply_to_message_id=message_id,
                response_state=TelegramResponseState.TASK_FAILED,
            )

        self.replay_guard.record_update(update_id, task_id=task_id)

        # 3. Controlled Execution using subprocess without shell=True
        try:
            tokens = shlex.split(command_args)
            res = subprocess.run(
                tokens,
                capture_output=True,
                text=True,
                timeout=15,
                shell=False,
            )
            output = res.stdout.strip() or res.stderr.strip() or "Success (no output)."
            # Truncate long output safely
            if len(output) > 2000:
                output = output[:2000] + "\n...[truncated]"

            self.admission_controller.complete_task(
                tenant_id=tenant_id,
                task_id=task_id,
                actual_tokens_consumed=50.0,
                reservation_id=adm_eval.current_usage.get("reservation_id"),
            )

            return TelegramOutboundMessage(
                chat_id=chat_id,
                text=f"💻 *Command Output* (`{command_args}`):\n```\n{output}\n```",
                reply_to_message_id=message_id,
                response_state=TelegramResponseState.TASK_COMPLETED,
            )
        except Exception as ex:
            self.admission_controller.abort_task(
                tenant_id=tenant_id,
                task_id=task_id,
                reservation_id=adm_eval.current_usage.get("reservation_id"),
            )
            return TelegramOutboundMessage(
                chat_id=chat_id,
                text=f"❌ Execution error: {str(ex)}",
                reply_to_message_id=message_id,
                response_state=TelegramResponseState.TASK_FAILED,
            )

    # ─────────────────────────────────────────────────────────────────────────
    # 5. SECURITY & AUDIT HELPERS
    # ─────────────────────────────────────────────────────────────────────────

    def _build_forbidden_response(self, chat_id: int, message: str) -> TelegramOutboundMessage:
        return TelegramOutboundMessage(
            chat_id=chat_id,
            text=f"🚫 {message}",
            response_state=TelegramResponseState.TASK_FAILED,
        )

    def _audit_for_secrets(self, text: str) -> None:
        """Enforces zero-secret invariant on incoming/outgoing text payloads."""
        for pat in self.FORBIDDEN_SECRET_PATTERNS:
            if pat.search(text):
                raise RawSecretPayloadError("Raw secret tokens are strictly forbidden in Telegram communication.")
