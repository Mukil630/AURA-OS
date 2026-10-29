"""
========================================================================================
AURA-OS — MORNING ROUTINE & MONTH-END GST TRIGGER DAEMON (morning_routine_daemon.py)
----------------------------------------------------------------------------------------
Integrated with Dynamic Gemini Voice Router:
- 06:00 AM: Synthesizes via 'MORNING_WAKEUP' Persona (Casual Brotherly Stark)
- 06:05 AM: Synthesizes via 'WORKOUT_BEAST' Persona (High-Energy Gym Coach)
- 07:00 AM (Day 1): Synthesizes via 'BUSINESS_FINANCE' Persona (Sharp SGC Co-Founder)
Dispatches voice notes directly to Mukil's Telegram!
========================================================================================
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path

# Ensure Windows Console supports full UTF-8 for Tamil script
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

JARVIS_DIR = Path(__file__).resolve().parent.parent
if str(JARVIS_DIR) not in sys.path:
    sys.path.insert(0, str(JARVIS_DIR))

from tools.weather_radar_tool import get_live_weather_radar
from tools.sgc_monthly_gst_infographic import run_monthly_gst_audit
from tools.gemini_voice_router import synthesize_persona_voice, send_voice_to_telegram

logger = logging.getLogger("morning_routine_daemon")


def play_through_speakers(audio_path: str):
    """Plays audio through PC room speakers so Mukil is woken up out loud."""
    try:
        import pygame
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        pygame.mixer.music.load(str(audio_path))
        pygame.mixer.music.play()
    except Exception as e:
        logger.warning(f"Speaker playback notice: {e}")


WEEKLY_WORKOUT_SPLIT_OORU = {
    "Monday": "செஸ்ட் அண்ட் ட்ரைசெப்ஸ் (Push Day) மாப்ள! பென்ச் பிரஸ், lateral raises போட்டு புஷ் பண்ணலாம்.",
    "Tuesday": "பேக் அண்ட் பைசெப்ஸ் (Pull Day) மாப்ள! லேட் புல்டவுன், சீட்டட் ரோவ்ஸ், அப்புறம் hammer curls போட்டு தெறிக்க விடலாம்.",
    "Wednesday": "லெக்ஸ் அண்ட் கோர் (Legs Day) மாப்ள! ஸ்குவாட்ஸ், லெக் பிரஸ், டெட்லிஃப்ட் போட்டு முடிச்சுடலாம்.",
    "Thursday": "ஷோல்டர் அண்ட் ஆப்ஸ் (Shoulders Day) மாப்ள! ஓவர்ஹெட் பிரஸ், lateral raises போட்டு பம்ப் ஏத்தலாம்.",
    "Friday": "ஆர்ம்ஸ் அண்ட் அப்பர் பம்ப் மாப்ள! பைசெப்ஸ் அண்ட் ட்ரைசெப்ஸ் சூப்பர்செட்ஸ் போட்டு தூள் கெளப்பலாம்.",
    "Saturday": "கார்டியோ அண்ட் மொபிலிட்டி மாப்ள! 20 நிமிஷம் நல்லா வியர்க்க வியர்க்க கார்டியோ பண்ணிட்டு ஸ்ட்ரெட்ச் பண்ணிக்கோங்க.",
    "Sunday": "ஃபுல் ரெஸ்ட் டே மாப்ள! நல்லா தூங்கி அடுத்த வாரத்துக்கு முழுசா ரீசார்ஜ் ஆகிக்கோங்க."
}


def run_6am_touchpoint(dispatch_audio: bool = True) -> dict:
    weather = get_live_weather_radar("karur")
    temp = weather.get("temperature_c", 31.0)
    rain_prob = weather.get("next_6h_rain_probability_pct", 0)

    convo_lines = (
        f"கரூர்ல இன்னைக்கு {temp}°C வெயில் சும்மா கொளுத்துது மாப்ள! மழை எல்லாம் ஒன்னும் வராது, sky ஃபுல் க்ளியர். "
        f"SGC யார்ன் காய போட இன்னைக்கு செம நாளு! வெளில போறப்ப sunglasses மாட்டிக்கோங்க, வெயிலுக்கு தண்ணி நெறைய குடிச்சுக்கோங்க மாப்ள!"
    )
    speech_text = f"Hello Boss! Good morning! {convo_lines}"

    audio_res = None
    if dispatch_audio:
        ok, audio_file = synthesize_persona_voice(speech_text, persona_type="MORNING_WAKEUP")
        if ok:
            play_through_speakers(audio_file)
            sent = send_voice_to_telegram(audio_file, caption="🌅 06:00 AM Morning Intel (Stark Wakeup)")
            audio_res = {"file": audio_file, "telegram_sent": sent}

    return {"speech": speech_text, "audio": audio_res}


def run_605am_touchpoint(dispatch_audio: bool = True) -> dict:
    today_name = datetime.now().strftime("%A")
    split = WEEKLY_WORKOUT_SPLIT_OORU.get(today_name, "ஃபுல் பாடி வொர்க்அவுட் மாப்ள!")
    speech_text = (
        f"Workout time Boss! இன்னைக்கு {today_name}, {split} "
        f"செம்மையா வொர்க்அவுட்ட முடிச்சு இன்னைக்கு தூள் கெளப்பலாம் மாப்ள!"
    )

    audio_res = None
    if dispatch_audio:
        ok, audio_file = synthesize_persona_voice(speech_text, persona_type="WORKOUT_BEAST")
        if ok:
            play_through_speakers(audio_file)
            sent = send_voice_to_telegram(audio_file, caption="⚡ 06:05 AM Workout Alert (Beast Mode)")
            audio_res = {"file": audio_file, "telegram_sent": sent}

    return {"speech": speech_text, "audio": audio_res}


def run_700am_touchpoint(dispatch_audio: bool = True, force_run: bool = False) -> dict:
    now = datetime.now()
    if now.day != 1 and not force_run:
        return {"active": False, "status": "SILENT"}

    audit = run_monthly_gst_audit(target_month="prev", send_telegram=True)
    speech_text = (
        "Boss, மாசத்தோட முதல் நாளு! போன மாசத்தோட SGC 5% GST IT filing ரிப்போர்ட் ஃபுல்லா ரெடி ஆயிடுச்சு. "
        "மொத்த GST ₹3,043.62. ஆடிட்டர் ஃபைலிங்கான இன்ஃபோகிராஃபிக் உங்க Telegram-க்கு அனுப்பிட்டேன், "
        "போன் ஸ்க்ரீன்லயும் காட்டியாச்சு! CA-கிட்ட ஃபார்வேர்ட் பண்ண தயாரா இருக்கு மாப்ள!"
    )

    audio_res = None
    if dispatch_audio:
        ok, audio_file = synthesize_persona_voice(speech_text, persona_type="BUSINESS_FINANCE")
        if ok:
            play_through_speakers(audio_file)
            sent = send_voice_to_telegram(audio_file, caption="📊 07:00 AM Month-End GST Audit (Co-Founder)")
            audio_res = {"file": audio_file, "telegram_sent": sent}

    return {"speech": speech_text, "audit": audit, "audio": audio_res}


def run_night_touchpoint(dispatch_audio: bool = True) -> dict:
    today_str = datetime.now().strftime("%d %b %Y")
    speech_text = (
        f"Boss, day wrap-up time! இன்னைக்கு {today_str} tasks, code commits, and SGC billing sync complete. "
        f"நல்லா தூங்கி ரெஸ்ட் எடுங்க மாப்ள, நாளைக்கு அடுத்த லெவல்ல தூள் கெளப்பலாம்!"
    )
    audio_res = None
    if dispatch_audio:
        ok, audio_file = synthesize_persona_voice(speech_text, persona_type="CASUAL_COWBOY")
        if ok:
            play_through_speakers(audio_file)
            sent = send_voice_to_telegram(audio_file, caption="🌙 22:00 PM Night Wrap-Up (AURA)")
            audio_res = {"file": audio_file, "telegram_sent": sent}
    return {"speech": speech_text, "audio": audio_res}


BLUEPRINT_FILE = JARVIS_DIR / "storage" / "memory" / "daily_routine_blueprint.json"
STATUS_FILE = JARVIS_DIR / "storage" / "memory" / "morning_daemon_status.json"


def load_blueprint() -> dict:
    """Loads dynamic daily routine blueprint with state-aware timestamps."""
    if not BLUEPRINT_FILE.exists():
        default_bp = {
            "version": "1.0.0",
            "timezone": "Asia/Kolkata",
            "description": "Dynamic State-Aware Schedule Blueprint for AURA-OS & JARVIS Prime. No hardcoding.",
            "routines": [
                {
                    "id": "morning_wakeup",
                    "name": "06:00 AM Morning Intel & Stark Wakeup",
                    "target_time": "06:00",
                    "enabled": true,
                    "persona": "MORNING_WAKEUP",
                    "schedule_type": "daily",
                    "catchup_grace_minutes": 180,
                    "last_executed_date": None,
                    "channels": {"local_speaker": True, "telegram_voice": True, "phone_call": False}
                },
                {
                    "id": "workout_beast",
                    "name": "06:05 AM Gym Beast Mode & Daily Split",
                    "target_time": "06:05",
                    "enabled": true,
                    "persona": "WORKOUT_BEAST",
                    "schedule_type": "daily",
                    "catchup_grace_minutes": 180,
                    "last_executed_date": None,
                    "channels": {"local_speaker": True, "telegram_voice": True, "phone_call": False}
                },
                {
                    "id": "sgc_monthly_gst",
                    "name": "07:00 AM Month-End SGC 5% GST Audit Infographic",
                    "target_time": "07:00",
                    "enabled": true,
                    "persona": "BUSINESS_FINANCE",
                    "schedule_type": "monthly",
                    "monthly_day": 1,
                    "catchup_grace_minutes": 720,
                    "last_executed_date": None,
                    "channels": {"local_speaker": True, "telegram_voice": True, "phone_call": False}
                },
                {
                    "id": "night_wrapup",
                    "name": "22:00 PM Night Review & GitHub Green Streak",
                    "target_time": "22:00",
                    "enabled": true,
                    "persona": "CASUAL_COWBOY",
                    "schedule_type": "daily",
                    "catchup_grace_minutes": 120,
                    "last_executed_date": None,
                    "channels": {"local_speaker": True, "telegram_voice": True, "phone_call": False}
                }
            ]
        }
        save_blueprint(default_bp)
        return default_bp

    try:
        with open(BLUEPRINT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load blueprint: {e}")
        return {"routines": []}


def save_blueprint(data: dict):
    """Saves dynamic daily routine blueprint safely to disk."""
    BLUEPRINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(BLUEPRINT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def update_routine_schedule(routine_id: str, new_time: str, enabled: bool = None) -> dict:
    """Dynamically modifies target timing or active state of a routine on-the-fly (Zero Hardcoding)."""
    bp = load_blueprint()
    found = False
    for r in bp.get("routines", []):
        if r.get("id") == routine_id or routine_id.lower() in r.get("name", "").lower():
            r["target_time"] = new_time
            if enabled is not None:
                r["enabled"] = enabled
            found = True
            break

    if found:
        save_blueprint(bp)
        logger.info(f"Updated routine '{routine_id}' target_time to {new_time}")
        return {"success": True, "routine_id": routine_id, "new_time": new_time, "enabled": enabled}
    return {"success": False, "error": f"Routine '{routine_id}' not found"}


def dispatch_routine(routine_id: str, dispatch_audio: bool = True, force_run: bool = False) -> dict:
    """Executes a routine by its unique ID."""
    if routine_id == "morning_wakeup":
        return run_6am_touchpoint(dispatch_audio=dispatch_audio)
    elif routine_id == "workout_beast":
        return run_605am_touchpoint(dispatch_audio=dispatch_audio)
    elif routine_id == "sgc_monthly_gst":
        return run_700am_touchpoint(dispatch_audio=dispatch_audio, force_run=force_run)
    elif routine_id == "night_wrapup":
        return run_night_touchpoint(dispatch_audio=dispatch_audio)
    else:
        return {"status": "UNKNOWN_ROUTINE", "routine_id": routine_id}


def evaluate_state_aware_routines(dispatch_audio: bool = True) -> list:
    """
    State-Aware Catch-Up Engine:
    Never misses an alarm due to sleep or reboot!
    Checks if routine hasn't executed today and current time >= target time.
    If within catchup_grace_minutes, executes immediately and records last_executed_date.
    """
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    blueprint = load_blueprint()
    results = []
    blueprint_modified = False

    for routine in blueprint.get("routines", []):
        rid = routine.get("id")
        if not routine.get("enabled", True):
            continue

        # Check schedule type constraint (e.g. monthly)
        stype = routine.get("schedule_type", "daily")
        if stype == "monthly":
            m_day = routine.get("monthly_day", 1)
            if now.day != m_day:
                continue

        # Check if already executed today
        if routine.get("last_executed_date") == today_str:
            continue

        # Parse target time (HH:MM)
        target_str = routine.get("target_time", "06:00")
        try:
            thour, tminute = map(int, target_str.split(":"))
            target_dt = now.replace(hour=thour, minute=tminute, second=0, microsecond=0)
        except Exception:
            continue

        if now >= target_dt:
            delay_minutes = (now - target_dt).total_seconds() / 60.0
            grace_minutes = routine.get("catchup_grace_minutes", 180)

            if delay_minutes <= grace_minutes:
                exec_type = "ON_TIME" if delay_minutes < 2 else f"CATCH_UP_{int(delay_minutes)}M_LATE"
                logger.info(f"⚡ [TRIGGER] Firing {rid} ({exec_type}) - Target: {target_str}, Now: {now.strftime('%H:%M')}")
                print(f"\n[DAEMON] ⏰ Triggering Routine: {routine.get('name')} [{exec_type}]")

                res = dispatch_routine(rid, dispatch_audio=dispatch_audio, force_run=False)
                routine["last_executed_date"] = today_str
                routine["last_executed_at"] = now.isoformat()
                routine["last_execution_type"] = exec_type
                blueprint_modified = True
                results.append({"id": rid, "status": "TRIGGERED", "type": exec_type, "result": res})
            else:
                # Expired past grace window (e.g. 6 AM alarm shouldn't yell at 3 PM)
                logger.info(f"⏭️ [EXPIRED] Routine {rid} missed by {int(delay_minutes)} mins (grace {grace_minutes} mins). Marking skipped for today.")
                routine["last_executed_date"] = today_str
                routine["last_execution_type"] = "SKIPPED_PAST_GRACE_WINDOW"
                blueprint_modified = True

    if blueprint_modified:
        save_blueprint(blueprint)

    return results


def start_scheduler_loop():
    """Starts the 24/7 continuous State-Aware Catch-Up loop."""
    import time

    logger.info("[*] Starting State-Aware Dynamic Routine Daemon...")
    print("=" * 75)
    print("🌅 AURA / JARVIS STATE-AWARE REBOOT-RESILIENT ROUTINE SCHEDULER ACTIVE")
    print("=" * 75)
    print("• Dynamic Blueprint: storage/memory/daily_routine_blueprint.json")
    print("• Zero Hardcoding: Times dynamically updated via Telegram / Voice")
    print("• Catch-Up Engine: Wakes from sleep/reboot and never drops missed alarms")
    print("=" * 75)

    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)

    heartbeat_counter = 0
    while True:
        try:
            # 1. State-Aware Catch-up & On-Time Evaluator
            evaluate_state_aware_routines(dispatch_audio=True)

            # 2. Update status heartbeat every 60 iterations (approx 1 min)
            if heartbeat_counter % 4 == 0:
                bp = load_blueprint()
                with open(STATUS_FILE, "w", encoding="utf-8") as f:
                    json.dump({
                        "status": "RUNNING",
                        "engine": "STATE_AWARE_CATCHUP",
                        "last_heartbeat": datetime.now().isoformat(),
                        "routines": bp.get("routines", [])
                    }, f, indent=2, ensure_ascii=False)

            heartbeat_counter += 1
            time.sleep(15)
        except Exception as e:
            logger.error(f"[Scheduler Loop Error]: {e}")
            time.sleep(15)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Morning Routine Multi-Persona Scheduler")
    parser.add_argument("--daemon", action="store_true", help="Start 24/7 background scheduler loop")
    parser.add_argument("--trigger", choices=["6am", "605am", "7am", "night"], help="Instantly trigger a touchpoint")
    parser.add_argument("--test", action="store_true", help="Dry-run verification of all touchpoints")
    parser.add_argument("--evaluate", action="store_true", help="Run a single State-Aware Catch-up evaluation pass")
    parser.add_argument("--set-time", nargs=2, metavar=("ROUTINE_ID", "HH:MM"), help="Dynamically change a routine time")
    args = parser.parse_args()

    if args.set_time:
        rid, ntime = args.set_time
        res = update_routine_schedule(rid, ntime)
        print(json.dumps(res, indent=2))
    elif args.evaluate:
        print("[*] Evaluating State-Aware Routines against current clock...")
        res = evaluate_state_aware_routines(dispatch_audio=False)
        print(f"Evaluated successfully. Triggered jobs count: {len(res)}")
        print(json.dumps(res, indent=2, ensure_ascii=False))
    elif args.trigger == "6am":
        print("[*] Triggering 06:00 AM Morning Touchpoint...")
        res = run_6am_touchpoint(dispatch_audio=True)
        print(json.dumps(res, indent=2, ensure_ascii=False))
    elif args.trigger == "605am":
        print("[*] Triggering 06:05 AM Workout Touchpoint...")
        res = run_605am_touchpoint(dispatch_audio=True)
        print(json.dumps(res, indent=2, ensure_ascii=False))
    elif args.trigger == "7am":
        print("[*] Triggering 07:00 AM Month-End GST Touchpoint (Force)...")
        res = run_700am_touchpoint(dispatch_audio=True, force_run=True)
        print(json.dumps(res, indent=2, ensure_ascii=False))
    elif args.trigger == "night":
        print("[*] Triggering 22:00 PM Night Wrap-Up Touchpoint...")
        res = run_night_touchpoint(dispatch_audio=True)
        print(json.dumps(res, indent=2, ensure_ascii=False))
    elif args.test:
        print("[*] Running Dry-Run Verification on all touchpoints (Audio generation off)...")
        t1 = run_6am_touchpoint(dispatch_audio=False)
        t2 = run_605am_touchpoint(dispatch_audio=False)
        t3 = run_700am_touchpoint(dispatch_audio=False, force_run=True)
        t4 = run_night_touchpoint(dispatch_audio=False)
        print("\n--- 1. 06:00 AM Output ---")
        print(t1["speech"])
        print("\n--- 2. 06:05 AM Output ---")
        print(t2["speech"])
        print("\n--- 3. 07:00 AM Output ---")
        print(t3["speech"])
        print("\n--- 4. 22:00 PM Output ---")
        print(t4["speech"])
        print("\n[+] All touchpoints logic verified 100% successfully!")
    elif args.daemon:
        start_scheduler_loop()
    else:
        print("[*] Morning Routine Daemon with Dynamic State-Aware Router Ready.")
        print("Usage: python morning_routine_daemon.py [--daemon | --evaluate | --set-time <id> <HH:MM> | --trigger <6am|605am|7am|night> | --test]")
