"""
AURA-OS 24/7 Cloud Daily Routine Scheduler (cloud_routine_scheduler.py)
----------------------------------------------------------------------
Runs 100% inside Render Cloud Container / FastAPI Lifespan.
Zero dependency on local PC/laptop being awake.
Dispatches voice memos directly to Mukil's Telegram via Edge-TTS and Telegram Bot API.
Timezone: Asia/Kolkata (IST).
"""

import os
import sys
import json
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
import httpx

logger = logging.getLogger("cloud_routine_scheduler")
IST = timezone(timedelta(hours=5, minutes=30))

WEEKLY_WORKOUT_SPLIT = {
    "Monday": "Chest and Triceps (Push Day) mapla! Bench press, lateral raises pottu push pannalam.",
    "Tuesday": "Back and Biceps (Pull Day) mapla! Lat pulldown, seated rows, hammer curls pottu therikka vidalam.",
    "Wednesday": "Legs and Core (Legs Day) mapla! Squats, leg press, deadlift pottu mudichudalam.",
    "Thursday": "Shoulders and Abs (Shoulders Day) mapla! Overhead press, lateral raises pottu pump yethalam.",
    "Friday": "Arms and Upper Pump mapla! Biceps and triceps supersets pottu dhool kelappalam.",
    "Saturday": "Cardio and Mobility mapla! 20 minutes nalla sweat aaga cardio pannittu stretch pannikko.",
    "Sunday": "Full Rest Day mapla! Nalla thoongi next week-ku full-ah recharge aagikko."
}

ROUTINE_STATE_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "cloud_routine_state.json"


def load_state() -> dict:
    if ROUTINE_STATE_FILE.exists():
        try:
            with open(ROUTINE_STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_runs": {}}


def save_state(state: dict):
    try:
        ROUTINE_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(ROUTINE_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        logger.warning(f"Could not persist routine state: {e}")


async def synthesize_edge_tts(text: str, voice: str = "ta-IN-ValluvarNeural") -> bytes:
    """Synthesizes high-fidelity neural audio in-memory using edge-tts."""
    try:
        import edge_tts
        communicate = edge_tts.Communicate(text, voice)
        audio_data = bytearray()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data.extend(chunk["data"])
        return bytes(audio_data)
    except Exception as e:
        logger.error(f"Edge-TTS synthesis error: {e}")
        # Fallback to English voice if Tamil voice fails
        try:
            import edge_tts
            communicate = edge_tts.Communicate(text, "en-IN-PrabhatNeural")
            audio_data = bytearray()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data.extend(chunk["data"])
            return bytes(audio_data)
        except Exception as e2:
            logger.error(f"Edge-TTS fallback failed: {e2}")
            return b""


async def send_voice_to_telegram(audio_bytes: bytes, caption: str) -> bool:
    """Sends voice memo directly to Mukil's Telegram via Telegram Bot API."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_AUTHORIZED_USER_ID") or os.getenv("TELEGRAM_CHAT_ID") or "6233907249"

    if not bot_token:
        logger.warning("TELEGRAM_BOT_TOKEN not configured in environment")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendVoice"
    files = {"voice": ("routine_voice.mp3", audio_bytes, "audio/mpeg")}
    data = {"chat_id": chat_id, "caption": caption}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, data=data, files=files)
            if resp.status_code == 200:
                logger.info(f"✅ Cloud Voice Memo successfully dispatched to Telegram: {caption}")
                return True
            else:
                logger.error(f"Failed to send Telegram voice: {resp.text}")
                return False
    except Exception as e:
        logger.error(f"Telegram dispatch exception: {e}")
        return False


async def get_karur_weather_summary() -> str:
    """Fetches fast live weather for Karur using Open-Meteo or fallback."""
    try:
        # Karur lat/lon: 10.9601, 78.0766
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.open-meteo.com/v1/forecast?latitude=10.9601&longitude=78.0766&current_weather=true"
            )
            if resp.status_code == 200:
                data = resp.json().get("current_weather", {})
                temp = data.get("temperature", 31.0)
                wind = data.get("windspeed", 10.0)
                return f"Karur-la ippo {temp}°C irukku mapla, wind speed {wind} km/h. SGC hank yarn kayapoda semma climate!"
    except Exception as e:
        logger.debug(f"Open-Meteo fetch notice: {e}")
    return "Karur-la nalla clear sky and bright sun irukku mapla! SGC yarn kayapoda super climate!"


class CloudRoutineScheduler:
    """24/7 Reboot-Resilient Cloud Scheduler for Daily Touchpoints."""

    def __init__(self):
        self.is_running = False
        self.task: asyncio.Task = None

    async def _execute_6am_wakeup(self):
        weather = await get_karur_weather_summary()
        speech = f"Good morning Boss! {weather} Kaalaila fresh-ah start pannunga, innaiku day-ah full power-oda mass panrom mapla!"
        audio = await synthesize_edge_tts(speech, voice="ta-IN-ValluvarNeural")
        if audio:
            await send_voice_to_telegram(audio, caption="🌅 06:00 AM Morning Intel (Cloud AURA Stark)")

    async def _execute_605am_workout(self):
        today_name = datetime.now(IST).strftime("%A")
        split = WEEKLY_WORKOUT_SPLIT.get(today_name, "Full body workout mapla!")
        speech = f"Workout time Boss! Innaiku {today_name}, {split} Gym mudichu semma energy-oda innaiku kalakkalam mapla!"
        audio = await synthesize_edge_tts(speech, voice="ta-IN-ValluvarNeural")
        if audio:
            await send_voice_to_telegram(audio, caption="⚡ 06:05 AM Gym Beast Mode (Cloud AURA)")

    async def _execute_2200_night(self):
        today_str = datetime.now(IST).strftime("%d %b %Y")
        speech = f"Boss, day wrap-up time! Innaiku {today_str} tasks and commits complete. Nalla thoongi rest edunga mapla, naalaiku semmaya mass panrom!"
        audio = await synthesize_edge_tts(speech, voice="ta-IN-ValluvarNeural")
        if audio:
            await send_voice_to_telegram(audio, caption="🌙 22:00 PM Night Wrap-Up (Cloud AURA)")

    async def _loop(self):
        logger.info("⚡ 24/7 Cloud Daily Routine Scheduler running inside Render (IST locked)...")
        # Give server 15 seconds to finish boot
        await asyncio.sleep(15)

        while self.is_running:
            try:
                now = datetime.now(IST)
                today_str = now.strftime("%Y-%m-%d")
                current_hm = now.strftime("%H:%M")
                state = load_state()
                last_runs = state.setdefault("last_runs", {})

                # 1. 06:00 AM Morning Wakeup (Window: 06:00 to 07:30 IST)
                if ("06:00" <= current_hm <= "07:30") and last_runs.get("06:00_wakeup") != today_str:
                    logger.info("⏰ [CLOUD] Triggering 06:00 AM Morning Wakeup...")
                    await self._execute_6am_wakeup()
                    last_runs["06:00_wakeup"] = today_str
                    save_state(state)

                # 2. 06:05 AM Workout Beast Mode (Window: 06:05 to 07:30 IST)
                if ("06:05" <= current_hm <= "07:30") and last_runs.get("06:05_workout") != today_str:
                    logger.info("⏰ [CLOUD] Triggering 06:05 AM Workout Beast Mode...")
                    await self._execute_605am_workout()
                    last_runs["06:05_workout"] = today_str
                    save_state(state)

                # 3. 22:00 PM Night Wrap-Up (Window: 22:00 to 23:30 IST)
                if ("22:00" <= current_hm <= "23:30") and last_runs.get("22:00_night") != today_str:
                    logger.info("⏰ [CLOUD] Triggering 22:00 PM Night Wrap-Up...")
                    await self._execute_2200_night()
                    last_runs["22:00_night"] = today_str
                    save_state(state)

            except Exception as e:
                logger.error(f"Cloud Routine Scheduler error: {e}")

            # Poll every 30 seconds
            await asyncio.sleep(30)

    def start(self):
        if not self.is_running:
            self.is_running = True
            self.task = asyncio.create_task(self._loop())

    def stop(self):
        self.is_running = False
        if self.task:
            self.task.cancel()


cloud_routine_scheduler = CloudRoutineScheduler()
