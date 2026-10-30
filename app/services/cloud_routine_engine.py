"""
========================================================================================
AURA-OS — 24/7 CLOUD ROUTINE & MORNING INTEL ENGINE (cloud_routine_engine.py)
----------------------------------------------------------------------------------------
Runs natively on Render Cloud (Linux) & Local PC with 100% Zero-PC Dependency:
- 06:00 AM IST: Synthesizes via 'MORNING_WAKEUP' Persona (Casual Brotherly Stark)
- 06:05 AM IST: Synthesizes via 'WORKOUT_BEAST' Persona (High-Energy Gym Coach)
- 07:00 AM IST (1st of Month): Synthesizes via 'BUSINESS_FINANCE' Persona (SGC GST Audit)
- 22:00 PM IST: Synthesizes via 'CASUAL_COWBOY' Persona (Night Retrospective)
- Dispatches Gemini Native Audio Voice Notes + Rich Markdown to Mukil's Telegram!
- Includes Restart-Resilient Catch-Up Engine & Webhook Trigger Support.
========================================================================================
"""

import os
import sys
import json
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List

# Ensure UTF-8 output
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import config
from tools.weather_radar_tool import get_live_weather_radar, generate_human_sensory_weather_speech
from tools.gemini_voice_router import synthesize_persona_voice, send_voice_to_telegram

logger = logging.getLogger("cloud_routine_engine")

IST_TZ = timezone(timedelta(hours=5, minutes=30))
BLUEPRINT_FILE = BASE_DIR / "storage" / "memory" / "daily_routine_blueprint.json"
STATUS_FILE = BASE_DIR / "storage" / "memory" / "cloud_routine_status.json"

WEEKLY_WORKOUT_SPLIT_OORU = {
    "Monday": "செஸ்ட் அண்ட் ட்ரைசெப்ஸ் (Push Day) மாப்ள! பென்ச் பிரஸ், lateral raises போட்டு புஷ் பண்ணலாம்.",
    "Tuesday": "பேக் அண்ட் பைசெப்ஸ் (Pull Day) மாப்ள! லேட் புல்டவுன், சீட்டட் ரோவ்ஸ், அப்புறம் hammer curls போட்டு தெறிக்க விடலாம்.",
    "Wednesday": "லெக்ஸ் அண்ட் கோர் (Legs Day) மாப்ள! ஸ்குவாட்ஸ், லெக் பிரஸ், டெட்லிஃப்ட் போட்டு முடிச்சுடலாம்.",
    "Thursday": "ஷோல்டர் அண்ட் ஆப்ஸ் (Shoulders Day) மாப்ள! ஓவர்ஹெட் பிரஸ், lateral raises போட்டு பம்ப் ஏத்தலாம்.",
    "Friday": "ஆர்ம்ஸ் அண்ட் அப்பர் பம்ப் மாப்ள! பைசெப்ஸ் அண்ட் ட்ரைசெப்ஸ் சூப்பர்செட்ஸ் போட்டு தூள் கெளப்பலாம்.",
    "Saturday": "கார்டியோ அண்ட் மொபிலிட்டி மாப்ள! 20 நிமிஷம் நல்லா வியர்க்க வியர்க்க கார்டியோ பண்ணிட்டு ஸ்ட்ரெட்ச் பண்ணிக்கோங்க.",
    "Sunday": "ஃபுல் ரெஸ்ட் டே மாப்ள! நல்லா தூங்கி அடுத்த வாரத்துக்கு முழுசா ரீசார்ஜ் ஆகிக்கோங்க."
}


def send_telegram_markdown_alert(text: str) -> bool:
    """Dispatches high-priority text alert directly to Mukil's Telegram."""
    import requests
    token = getattr(config, "TELEGRAM_BOT_TOKEN", None) or os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = getattr(config, "AUTHORIZED_TELEGRAM_USERS", [6233907249])[0]
    if not token or not chat_id:
        return False
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        resp = requests.post(url, json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }, timeout=10)
        return resp.json().get("ok", False)
    except Exception as e:
        logger.error(f"Failed to send telegram markdown alert: {e}")
        return False


class CloudRoutineEngine:
    def __init__(self):
        self._running = False
        self._loop_task: Optional[asyncio.Task] = None
        self._ensure_blueprint()

    def _ensure_blueprint(self) -> dict:
        if not BLUEPRINT_FILE.exists():
            default_bp = {
                "version": "2.0.0",
                "timezone": "Asia/Kolkata",
                "description": "24/7 Cloud Dynamic Schedule Blueprint for AURA-OS & JARVIS Prime",
                "routines": [
                    {
                        "id": "morning_wakeup",
                        "name": "06:00 AM Morning Intel & Stark Wakeup",
                        "target_time": "06:00",
                        "enabled": True,
                        "persona": "MORNING_WAKEUP",
                        "schedule_type": "daily",
                        "catchup_grace_minutes": 180,
                        "last_executed_date": None,
                        "description": "Karur live weather radar, 33C sun intensity, Hank Yarn sun-drying report & Brotherly wake-up call."
                    },
                    {
                        "id": "workout_beast",
                        "name": "06:05 AM Gym Beast Mode & Daily Split",
                        "target_time": "06:05",
                        "enabled": True,
                        "persona": "WORKOUT_BEAST",
                        "schedule_type": "daily",
                        "catchup_grace_minutes": 180,
                        "last_executed_date": None,
                        "description": "Day-specific gym split (Push/Pull/Legs/Shoulders/Arms/Cardio/Rest) with high-energy coaching audio."
                    },
                    {
                        "id": "sgc_monthly_gst",
                        "name": "07:00 AM Month-End SGC 5% GST Audit Infographic",
                        "target_time": "07:00",
                        "enabled": True,
                        "persona": "BUSINESS_FINANCE",
                        "schedule_type": "monthly",
                        "monthly_day": 1,
                        "catchup_grace_minutes": 720,
                        "last_executed_date": None,
                        "description": "Runs on the 1st of every month. SGC 5% GST IT filing audit & Telegram summary."
                    },
                    {
                        "id": "night_wrapup",
                        "name": "22:00 PM Night Review & GitHub Green Streak",
                        "target_time": "22:00",
                        "enabled": True,
                        "persona": "CASUAL_COWBOY",
                        "schedule_type": "daily",
                        "catchup_grace_minutes": 120,
                        "last_executed_date": None,
                        "description": "Nightly wrap-up, GitHub commit streak audit, and Drive mesh sync verification."
                    }
                ]
            }
            self.save_blueprint(default_bp)
            return default_bp
        return self.load_blueprint()

    def load_blueprint(self) -> dict:
        try:
            with open(BLUEPRINT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load blueprint: {e}")
            return {"routines": []}

    def save_blueprint(self, data: dict):
        try:
            BLUEPRINT_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(BLUEPRINT_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save blueprint: {e}")

    def update_schedule(self, routine_id: str, new_time: str, enabled: Optional[bool] = None) -> dict:
        bp = self.load_blueprint()
        found = False
        for r in bp.get("routines", []):
            if r.get("id") == routine_id or routine_id.lower() in r.get("name", "").lower():
                r["target_time"] = new_time
                if enabled is not None:
                    r["enabled"] = enabled
                found = True
                break
        if found:
            self.save_blueprint(bp)
            logger.info(f"Updated routine '{routine_id}' target_time to {new_time}")
            return {"success": True, "routine_id": routine_id, "new_time": new_time, "enabled": enabled}
        return {"success": False, "error": f"Routine '{routine_id}' not found"}

    def run_morning_wakeup(self, dispatch_audio: bool = True) -> dict:
        """06:00 AM Karur Weather + Stark Tone Wakeup."""
        weather = get_live_weather_radar("karur")
        convo_lines = generate_human_sensory_weather_speech(weather)
        speech_text = f"Good morning Boss Mukil! {convo_lines}"

        audio_res = None
        if dispatch_audio:
            ok, audio_file = synthesize_persona_voice(speech_text, persona_type="MORNING_WAKEUP")
            if ok:
                caption = f"🌅 *06:00 AM Morning Intel (Stark Wakeup)*\n\n{speech_text}"
                sent = send_voice_to_telegram(audio_file, caption=caption)
                audio_res = {"file": audio_file, "telegram_sent": sent}
            else:
                send_telegram_markdown_alert(f"🌅 *06:00 AM Morning Intel*\n\n{speech_text}")

        return {"speech": speech_text, "audio": audio_res}

    def run_workout_beast(self, dispatch_audio: bool = True) -> dict:
        """06:05 AM Workout Beast Mode."""
        now_ist = datetime.now(IST_TZ)
        today_name = now_ist.strftime("%A")
        split = WEEKLY_WORKOUT_SPLIT_OORU.get(today_name, "ஃபுல் பாடி வொர்க்அவுட் மாப்ள!")
        speech_text = (
            f"Workout time Boss! இன்னைக்கு {today_name}, {split} "
            f"செம்மையா வொர்க்அவுட்ட முடிச்சு இன்னைக்கு தூள் கெளப்பலாம் மாப்ள!"
        )

        audio_res = None
        if dispatch_audio:
            ok, audio_file = synthesize_persona_voice(speech_text, persona_type="WORKOUT_BEAST")
            if ok:
                caption = f"⚡ *06:05 AM Workout Alert (Beast Mode)*\n\n{speech_text}"
                sent = send_voice_to_telegram(audio_file, caption=caption)
                audio_res = {"file": audio_file, "telegram_sent": sent}
            else:
                send_telegram_markdown_alert(f"⚡ *06:05 AM Workout Alert*\n\n{speech_text}")

        return {"speech": speech_text, "audio": audio_res}

    def run_sgc_monthly_gst(self, dispatch_audio: bool = True, force_run: bool = False) -> dict:
        """07:00 AM 1st of Month SGC GST Audit."""
        now_ist = datetime.now(IST_TZ)
        if now_ist.day != 1 and not force_run:
            return {"active": False, "status": "SILENT (Not 1st of month)"}

        from tools.sgc_monthly_gst_infographic import run_monthly_gst_audit
        audit = run_monthly_gst_audit(target_month="prev", send_telegram=True)
        speech_text = (
            "Boss, மாசத்தோட முதல் நாளு! போன மாசத்தோட SGC 5% GST IT filing ரிப்போர்ட் ஃபுல்லா ரெடி ஆயிடுச்சு. "
            "ஆடிட்டர் ஃபைலிங்கான இன்ஃபோகிராஃபிக் உங்க Telegram-க்கு அனுப்பிட்டேன், CA-கிட்ட ஃபார்வேர்ட் பண்ண தயாரா இருக்கு மாப்ள!"
        )

        audio_res = None
        if dispatch_audio:
            ok, audio_file = synthesize_persona_voice(speech_text, persona_type="BUSINESS_FINANCE")
            if ok:
                caption = f"📊 *07:00 AM Month-End GST Audit*\n\n{speech_text}"
                sent = send_voice_to_telegram(audio_file, caption=caption)
                audio_res = {"file": audio_file, "telegram_sent": sent}
            else:
                send_telegram_markdown_alert(f"📊 *07:00 AM Month-End GST Audit*\n\n{speech_text}")

        return {"speech": speech_text, "audit": audit, "audio": audio_res}

    def run_night_wrapup(self, dispatch_audio: bool = True) -> dict:
        """22:00 PM Night Retrospective."""
        now_ist = datetime.now(IST_TZ)
        today_str = now_ist.strftime("%d %b %Y")
        speech_text = (
            f"Boss, day wrap-up time! இன்னைக்கு {today_str} tasks, code commits, and SGC billing sync complete. "
            f"நல்லா தூங்கி ரெஸ்ட் எடுங்க மாப்ள, நாளைக்கு அடுத்த லெவல்ல தூள் கெளப்பலாம்!"
        )

        audio_res = None
        if dispatch_audio:
            ok, audio_file = synthesize_persona_voice(speech_text, persona_type="CASUAL_COWBOY")
            if ok:
                caption = f"🌙 *22:00 PM Night Wrap-Up (AURA)*\n\n{speech_text}"
                sent = send_voice_to_telegram(audio_file, caption=caption)
                audio_res = {"file": audio_file, "telegram_sent": sent}
            else:
                send_telegram_markdown_alert(f"🌙 *22:00 PM Night Wrap-Up*\n\n{speech_text}")

        return {"speech": speech_text, "audio": audio_res}

    def execute_routine(self, routine_id: str, dispatch_audio: bool = True, force_run: bool = False) -> dict:
        """Executes any routine by its ID."""
        logger.info(f"⚡ [EXECUTE] Firing Routine '{routine_id}' (force={force_run})")
        if routine_id in ["morning_wakeup", "6am"]:
            res = self.run_morning_wakeup(dispatch_audio=dispatch_audio)
        elif routine_id in ["workout_beast", "605am"]:
            res = self.run_workout_beast(dispatch_audio=dispatch_audio)
        elif routine_id in ["sgc_monthly_gst", "7am"]:
            res = self.run_sgc_monthly_gst(dispatch_audio=dispatch_audio, force_run=force_run)
        elif routine_id in ["night_wrapup", "night", "22pm"]:
            res = self.run_night_wrapup(dispatch_audio=dispatch_audio)
        else:
            return {"success": False, "error": f"Unknown routine '{routine_id}'"}

        # Record last executed in blueprint
        bp = self.load_blueprint()
        now_ist = datetime.now(IST_TZ)
        today_str = now_ist.strftime("%Y-%m-%d")
        for r in bp.get("routines", []):
            if r.get("id") == routine_id:
                r["last_executed_date"] = today_str
                r["last_executed_at"] = now_ist.isoformat()
                r["last_execution_type"] = "TRIGGERED"
                break
        self.save_blueprint(bp)

        return {"success": True, "routine_id": routine_id, "result": res}

    def evaluate_state_aware_routines(self, dispatch_audio: bool = True) -> list:
        """
        Cloud Catch-Up Evaluator:
        Checks if any routine hasn't executed today and current IST time >= target time.
        If within catchup_grace_minutes, executes immediately and records last_executed_date.
        """
        now_ist = datetime.now(IST_TZ)
        today_str = now_ist.strftime("%Y-%m-%d")
        blueprint = self.load_blueprint()
        results = []
        blueprint_modified = False

        for routine in blueprint.get("routines", []):
            rid = routine.get("id")
            if not routine.get("enabled", True):
                continue

            stype = routine.get("schedule_type", "daily")
            if stype == "monthly":
                m_day = routine.get("monthly_day", 1)
                if now_ist.day != m_day:
                    continue

            if routine.get("last_executed_date") == today_str:
                continue

            target_str = routine.get("target_time", "06:00")
            try:
                thour, tminute = map(int, target_str.split(":"))
                target_dt = now_ist.replace(hour=thour, minute=tminute, second=0, microsecond=0)
            except Exception:
                continue

            if now_ist >= target_dt:
                delay_minutes = (now_ist - target_dt).total_seconds() / 60.0
                grace_minutes = routine.get("catchup_grace_minutes", 180)

                if delay_minutes <= grace_minutes:
                    exec_type = "ON_TIME" if delay_minutes < 2 else f"CATCH_UP_{int(delay_minutes)}M_LATE"
                    logger.info(f"⏰ [TRIGGER] Firing {rid} [{exec_type}] - Target: {target_str}, Now IST: {now_ist.strftime('%H:%M')}")

                    res = self.execute_routine(rid, dispatch_audio=dispatch_audio, force_run=False)
                    routine["last_executed_date"] = today_str
                    routine["last_executed_at"] = now_ist.isoformat()
                    routine["last_execution_type"] = exec_type
                    blueprint_modified = True
                    results.append({"id": rid, "status": "TRIGGERED", "type": exec_type, "result": res})
                else:
                    logger.info(f"⏭️ Routine {rid} missed by {int(delay_minutes)} mins (grace {grace_minutes} mins). Marking skipped.")
                    routine["last_executed_date"] = today_str
                    routine["last_execution_type"] = "SKIPPED_PAST_GRACE_WINDOW"
                    blueprint_modified = True

        if blueprint_modified:
            self.save_blueprint(blueprint)

        return results

    async def _continuous_loop(self):
        """Asynchronous continuous loop running on Render Cloud."""
        logger.info("🟢 CloudRoutineEngine 24/7 background loop active (Asia/Kolkata).")
        heartbeat = 0
        while self._running:
            try:
                # Run catchup & on-time check
                self.evaluate_state_aware_routines(dispatch_audio=True)

                # Write status heartbeat every ~1 minute
                if heartbeat % 4 == 0:
                    bp = self.load_blueprint()
                    now_ist = datetime.now(IST_TZ)
                    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
                    with open(STATUS_FILE, "w", encoding="utf-8") as f:
                        json.dump({
                            "status": "RUNNING_24_7_CLOUD",
                            "engine": "AURA_CLOUD_ROUTINE_ENGINE",
                            "current_ist": now_ist.strftime("%Y-%m-%d %I:%M:%S %p IST"),
                            "routines": bp.get("routines", [])
                        }, f, indent=2, ensure_ascii=False)

                heartbeat += 1
            except Exception as e:
                logger.error(f"[CloudRoutineEngine Loop Error]: {e}")

            await asyncio.sleep(15)

    def start(self):
        if self._running:
            return
        self._running = True
        self._loop_task = asyncio.create_task(self._continuous_loop())

    def stop(self):
        self._running = False
        if self._loop_task:
            self._loop_task.cancel()
        logger.info("🛑 CloudRoutineEngine loop stopped.")


# Global Singleton Instance for Cloud
cloud_routine_engine = CloudRoutineEngine()
