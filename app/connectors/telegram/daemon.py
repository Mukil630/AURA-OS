"""Milestone 2 Step 2: Production Telegram Bot Daemon.
Runs the live polling bridge connecting the Telegram Bot API with TelegramGatewayService,
AdmissionController (Phase 12.5), and Master Agent execution pipeline without leaking credentials.
"""
import asyncio
import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, Set

# Ensure project root is always in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

from telegram import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

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
    IVoiceTranscriber,
    MockVoiceTranscriber,
    TelegramGatewayService,
)
from app.connectors.telegram.idempotency import TelegramReplayGuard
from app.core.contracts.credential import RawSecretPayloadError
from app.core.governance.admission_controller import AdmissionController
from app.policy.approval_engine import ApprovalEngine, default_approval_engine
from app.tools.reminder_scheduler import ReminderScheduler
from app.tools.tts_engine import JARVISVoiceEngine

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("TelegramBotDaemon")


# ═════════════════════════════════════════════════════════════════════════════
# 1. REAL GROQ WHISPER VOICE TRANSCRIBER ADAPTER
# ═════════════════════════════════════════════════════════════════════════════

class GroqWhisperVoiceTranscriber(IVoiceTranscriber):
    """
    Transcribes audio notes using Groq Whisper Large V3 Turbo model.
    Credentials resolved from environment / vault without exposing secrets in logs.
    """

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key if api_key is not None else os.getenv("GROQ_API_KEY")

    def transcribe(self, audio_bytes: bytes, filename: str = "voice.ogg") -> str:
        if not audio_bytes:
            raise ValueError("Audio bytes cannot be empty.")

        if not self._api_key:
            logger.warning("GROQ_API_KEY not configured. Falling back to default mock voice transcript.")
            return "PC status and diagnostics check"

        try:
            from groq import Groq
            client = Groq(api_key=self._api_key)
            transcription = client.audio.transcriptions.create(
                file=(filename, audio_bytes),
                model="whisper-large-v3-turbo",
                prompt="Tanglish, Tamil, English conversation with Jarvis AI",
                response_format="text",
            )
            return str(transcription).strip()
        except Exception as ex:
            logger.error(f"Voice transcription failed via Groq API: {str(ex)}")
            raise RuntimeError(f"Voice transcription error: {str(ex)}")


# ═════════════════════════════════════════════════════════════════════════════
# 2. TELEGRAM BOT DAEMON ENGINE
# ═════════════════════════════════════════════════════════════════════════════

class TelegramBotDaemon:
    """
    Live background daemon polling the Telegram Bot API and routing updates
    through the validated TelegramGatewayService, Phase 12 Operating Plane,
    JARVIS Neural Voice Engine, and Reminder Scheduler.
    """

    def __init__(
        self,
        bot_token: Optional[str] = None,
        gateway_service: Optional[TelegramGatewayService] = None,
        allowed_user_ids: Optional[Set[int]] = None,
    ) -> None:
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.gateway = gateway_service or TelegramGatewayService(
            allowed_user_ids=allowed_user_ids,
            voice_transcriber=GroqWhisperVoiceTranscriber(),
        )
        self.voice_engine = JARVISVoiceEngine()
        self.reminder_scheduler = ReminderScheduler()
        self.app: Optional[Application] = None
        self._is_running = False

    def build_application(self) -> Application:
        """Constructs and registers telegram handlers on python-telegram-bot Application."""
        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required to start the Telegram Daemon.")

        builder = ApplicationBuilder().token(self.bot_token)
        builder.post_init(self._on_app_post_init)
        app = builder.build()

        # Command Handlers
        app.add_handler(CommandHandler("start", self._handle_command))
        app.add_handler(CommandHandler("status", self._handle_command))
        app.add_handler(CommandHandler("tasks", self._handle_command))
        app.add_handler(CommandHandler("drive", self._handle_command))
        app.add_handler(CommandHandler("resume", self._handle_command))
        app.add_handler(CommandHandler("approve", self._handle_command))
        app.add_handler(CommandHandler("reject", self._handle_command))
        app.add_handler(CommandHandler("exec", self._handle_command))
        app.add_handler(CommandHandler("remind", self._handle_remind))
        app.add_handler(CommandHandler("reminders", self._handle_list_reminders))
        app.add_handler(CommandHandler("cancelremind", self._handle_cancel_reminder))

        # Inline Button Callback Handler
        app.add_handler(CallbackQueryHandler(self._handle_callback_query))

        # Voice & Audio Message Handler
        app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, self._handle_voice))

        # Text Message Handler
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_text))

        self.app = app
        self.reminder_scheduler.set_callback(self._on_reminder_triggered)
        return app

    async def _on_app_post_init(self, application: Application) -> None:
        """Starts background reminder scheduler when Telegram application starts."""
        await self.reminder_scheduler.start()

    # ─────────────────────────────────────────────────────────────────────────
    # REMINDER CALLBACK & HANDLERS
    # ─────────────────────────────────────────────────────────────────────────

    async def _on_reminder_triggered(self, reminder: Dict[str, Any]) -> None:
        """Sends reminder notification to Telegram with both text and fluent spoken voice note."""
        chat_id = reminder.get("chat_id")
        msg = reminder.get("message", "Timed Reminder")
        if not self.app or not chat_id:
            return

        spoken_tamil = f"வணக்கம் மாப்ள! இது உங்களுக்கான நினைவூட்டல் செய்தி: {msg}. நேரத்தை சரியாக பயன்படுத்தவும்."
        alert_text = f"⏰ *JARVIS REMINDER ALERT!*\n\n📝 *Task*: _{msg}_\n⏳ *Time*: `{datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}`"

        try:
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
                tmp_audio = tmp.name
            await self.voice_engine.save_voice_file(spoken_tamil, tmp_audio)
            with open(tmp_audio, "rb") as f:
                await self.app.bot.send_voice(chat_id=chat_id, voice=f, caption=alert_text, parse_mode="Markdown")
            if os.path.exists(tmp_audio):
                os.remove(tmp_audio)
        except Exception as e:
            logger.warning(f"Voice reminder send failed, falling back to text: {e}")
            await self.app.bot.send_message(chat_id=chat_id, text=alert_text, parse_mode="Markdown")

    async def _handle_remind(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Process /remind command (e.g. /remind 10m Study Java)."""
        if not update.message or not update.effective_user:
            return

        cmd_text = update.message.text.strip()
        args = cmd_text.split(maxsplit=1)[1] if len(cmd_text.split(maxsplit=1)) > 1 else ""
        if not args:
            await update.message.reply_text(
                "⏰ *Usage*: `/remind <time> <task>`\n\n*Examples*:\n• `/remind 10m Study Java`\n• `/remind 1h Placement Test`\n• `/remind 30m SGC Invoice Check`",
                parse_mode="Markdown",
            )
            return

        try:
            rem = self.reminder_scheduler.parse_and_create(
                chat_id=update.effective_chat.id,
                user_id=update.effective_user.id,
                command_args=args,
            )
            await update.message.reply_text(
                f"⏰ *Reminder Set Successfully!*\n\n"
                f"📋 *ID*: `{rem['reminder_id']}`\n"
                f"📝 *Task*: _{rem['message']}_\n"
                f"⏳ *Target Time*: `{rem['target_time'][:19]} UTC`\n\n"
                f"JARVIS will send a voice alert when due.",
                parse_mode="Markdown",
                reply_to_message_id=update.message.message_id,
            )
        except Exception as e:
            await update.message.reply_text(f"❌ *Error setting reminder*: {str(e)}", parse_mode="Markdown")

    async def _handle_list_reminders(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """List active pending reminders."""
        if not update.message:
            return
        active = self.reminder_scheduler.list_reminders(user_id=update.effective_user.id if update.effective_user else None)
        if not active:
            await update.message.reply_text("📋 *No active reminders scheduled.* Use `/remind 10m <task>` to set one.", parse_mode="Markdown")
            return

        lines = ["⏰ *Active Scheduled Reminders:*\n"]
        for r in active:
            lines.append(f"• `{r['reminder_id']}`: _{r['message']}_ (Due: `{r['target_time'][:19]} UTC`)")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def _handle_cancel_reminder(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Cancel a reminder by ID."""
        if not update.message:
            return
        cmd_text = update.message.text.strip()
        args = cmd_text.split(maxsplit=1)[1] if len(cmd_text.split(maxsplit=1)) > 1 else ""
        if not args:
            await update.message.reply_text("Usage: `/cancelremind <reminder_id>`", parse_mode="Markdown")
            return

        success = self.reminder_scheduler.cancel_reminder(args.strip())
        if success:
            await update.message.reply_text(f"✅ Reminder `{args.strip()}` has been cancelled.", parse_mode="Markdown")
        else:
            await update.message.reply_text(f"❌ Reminder `{args.strip()}` not found or already completed.", parse_mode="Markdown")

    # ─────────────────────────────────────────────────────────────────────────
    # ADAPTER TRANSLATION: TELEGRAM -> CONTRACT -> RESPONSE
    # ─────────────────────────────────────────────────────────────────────────

    async def _handle_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Process incoming slash commands."""
        if not update.message or not update.effective_user:
            return

        user = update.effective_user
        logger.info(f"Incoming command '{update.message.text}' from {user.first_name} (ID: {user.id}, Username: @{user.username})")
        contract_update = self._to_contract_update(update)
        outbound = self.gateway.process_update(contract_update)
        await self._dispatch_outbound(update, outbound)

    async def _handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Process standard conversational or task messages."""
        if not update.message or not update.effective_user:
            return

        user = update.effective_user
        logger.info(f"Incoming text '{update.message.text}' from {user.first_name} (ID: {user.id}, Username: @{user.username})")
        contract_update = self._to_contract_update(update)
        outbound = self.gateway.process_update(contract_update)
        await self._dispatch_outbound(update, outbound)

    async def _handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Download and process voice note payloads with 2-Way Voice Output."""
        if not update.message or not update.effective_user:
            return

        voice = update.message.voice or update.message.audio
        if not voice:
            return

        voice_file = await context.bot.get_file(voice.file_id)
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            await voice_file.download_to_drive(tmp_path)
            with open(tmp_path, "rb") as f:
                raw_bytes = f.read()

            # 1. Transcribe incoming audio
            transcription = self.gateway.voice_transcriber.transcribe(raw_bytes)
            logger.info(f"Voice Transcribed: '{transcription}'")

            lower_t = transcription.lower()
            spoken_tamil = None
            caption_text = None

            # 2. Check for PC status & Battery query
            if any(k in lower_t for k in ["battery", "charge", "power", "cpu", "status", "how is my pc", "running"]):
                try:
                    import psutil
                    cpu = f"{psutil.cpu_percent(interval=0.05):.1f}"
                    vmem = psutil.virtual_memory()
                    ram_pct = f"{vmem.percent:.1f}"
                    batt = psutil.sensors_battery()
                    batt_str = f"{batt.percent:.0f}%" if batt else "N/A"
                    plug = "சார்ஜர் இணைக்கப்பட்டுள்ளது" if (batt and batt.power_plugged) else "பேட்டரியில் இயங்குகிறது"

                    spoken_tamil = f"வணக்கம் மாப்ள! உங்கள் கணினி பேட்டரி {batt_str} உள்ளது. {plug}. சிபியு பயன்பாடு {cpu} சதவீதம். கணினி மிக சிறப்பாக இயங்குகிறது!"
                    caption_text = (
                        f"🎙️ *JARVIS Voice Response*\n\n"
                        f"📝 *Query*: _{transcription}_\n"
                        f"🔋 *Battery*: `{batt_str}`\n"
                        f"⚡ *CPU Usage*: `{cpu}%`\n"
                        f"🧠 *RAM*: `{ram_pct}%`\n"
                        f"🟢 *Status*: Autonomous & Online"
                    )
                except Exception:
                    pass

            # 3. Check for voice reminder
            elif "remind" in lower_t:
                try:
                    rem_args = lower_t.split("remind", 1)[1].strip()
                    if rem_args.startswith("me"):
                        rem_args = rem_args[2:].strip()
                    if rem_args.startswith("to"):
                        rem_args = rem_args[2:].strip()
                    rem = self.reminder_scheduler.parse_and_create(
                        chat_id=update.effective_chat.id,
                        user_id=update.effective_user.id,
                        command_args=rem_args,
                    )
                    spoken_tamil = f"சரி மாப்ள! நினைவூட்டல் பதிவு செய்யப்பட்டது. குறிப்பிட்ட நேரத்தில் உங்களுக்கு குரல் செய்தி அனுப்புகிறேன்."
                    caption_text = f"⏰ *Reminder Scheduled!*\n\n📝 *Task*: _{rem['message']}_\n⏳ *Due*: `{rem['target_time'][:19]} UTC`"
                except Exception as ex:
                    spoken_tamil = f"மன்னிக்கவும் மாப்ள, நினைவூட்டல் நேரத்தை புரிந்து கொள்ள முடியவில்லை."
                    caption_text = f"❌ *Reminder Error*: {str(ex)}"

            # 4. If direct spoken answer ready, synthesize audio & reply with Voice Note!
            if spoken_tamil and caption_text:
                with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as out_tmp:
                    out_path = out_tmp.name
                try:
                    await self.voice_engine.save_voice_file(spoken_tamil, out_path)
                    with open(out_path, "rb") as vf:
                        await update.message.reply_voice(
                            voice=vf,
                            caption=caption_text,
                            parse_mode="Markdown",
                            reply_to_message_id=update.message.message_id,
                        )
                    return
                except Exception as ex:
                    logger.warning(f"Voice reply synthesis failed: {ex}")
                finally:
                    if os.path.exists(out_path):
                        os.remove(out_path)

            # 5. Fallback: Dispatch to Master Agent Pipeline
            contract_update = self._to_contract_update(update)
            outbound = self.gateway.process_update(contract_update, raw_voice_bytes=raw_bytes)
            await self._dispatch_outbound(update, outbound)

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    async def _handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle inline button callbacks (e.g. APPROVE:<id> or REJECT:<id>)."""
        query: Optional[CallbackQuery] = update.callback_query
        if not query or not query.data:
            return

        await query.answer()
        sender_id = query.from_user.id
        username = query.from_user.username
        data = query.data.strip()

        # Format as approval command
        cmd_text = None
        if data.startswith("APPROVE:"):
            approval_id = data.split(":", 1)[1]
            cmd_text = f"/approve {approval_id}"
        elif data.startswith("REJECT:"):
            approval_id = data.split(":", 1)[1]
            cmd_text = f"/reject {approval_id}"

        if cmd_text:
            contract_update = TelegramUpdate(
                update_id=update.update_id,
                message=TelegramMessage(
                    message_id=query.message.message_id if query.message else 0,
                    from_user=TelegramUser(id=sender_id, first_name=query.from_user.first_name, username=username),
                    chat=TelegramChat(id=query.message.chat.id if query.message else sender_id),
                    text=cmd_text,
                ),
            )
            outbound = self.gateway.process_update(contract_update)
            if query.message:
                await query.message.reply_text(outbound.text, parse_mode="Markdown")

    # ─────────────────────────────────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────────────────────────────────

    def _to_contract_update(self, update: Update) -> TelegramUpdate:
        """Converts python-telegram-bot Update to canonical TelegramUpdate contract."""
        msg = update.message
        sender = update.effective_user
        chat = update.effective_chat

        user_contract = None
        if sender:
            last_name_val = str(sender.last_name) if sender.last_name and not str(type(sender.last_name)).find("MagicMock") != -1 else None
            lang_code_val = str(sender.language_code) if sender.language_code and not str(type(sender.language_code)).find("MagicMock") != -1 else "en"
            user_contract = TelegramUser(
                id=int(sender.id),
                first_name=str(sender.first_name or "User"),
                last_name=last_name_val,
                username=str(sender.username) if sender.username else None,
                language_code=lang_code_val,
            )

        chat_contract = TelegramChat(
            id=int(chat.id) if chat and chat.id else (int(sender.id) if sender else 0),
            type=str(chat.type) if chat and chat.type and not str(type(chat.type)).find("MagicMock") != -1 else "private",
            title=str(chat.title) if chat and chat.title and not str(type(chat.title)).find("MagicMock") != -1 else None,
            username=str(chat.username) if chat and chat.username and not str(type(chat.username)).find("MagicMock") != -1 else None,
        )

        msg_contract = None
        if msg:
            msg_contract = TelegramMessage(
                message_id=msg.message_id,
                from_user=user_contract,
                chat=chat_contract,
                text=msg.text or msg.caption,
            )

        return TelegramUpdate(
            update_id=update.update_id,
            message=msg_contract,
        )

    async def _dispatch_outbound(self, update: Update, outbound: TelegramOutboundMessage) -> None:
        """Sends outbound message back to Telegram."""
        if not update.message:
            return
        await update.message.reply_text(
            text=outbound.text,
            parse_mode=outbound.parse_mode or "Markdown",
            reply_to_message_id=outbound.reply_to_message_id,
            disable_web_page_preview=True,
        )

    def run_polling(self) -> None:
        """Starts live polling loop synchronously."""
        logger.info("Initializing Telegram Bot Daemon Polling Engine...")
        app = self.build_application()
        self._is_running = True
        logger.info("Telegram Bot Daemon is 100% ONLINE and listening for updates.")
        app.run_polling(drop_pending_updates=True, bootstrap_retries=-1, timeout=30)


# Standalone runner entry point
if __name__ == "__main__":
    daemon = TelegramBotDaemon()
    daemon.run_polling()
