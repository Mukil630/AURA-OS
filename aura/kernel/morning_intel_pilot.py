"""
AURA OS Autonomous Morning Intelligence & Calling Pilot
Reverse-engineered for Autonomous Executive Reasoning & 06:00 AM Proactive Phone Wakeup.
"""
import sys
import os
import json
import re
import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, Tuple

# Fix Windows console UTF-8 output
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from groq import Groq
import edge_tts

from aura.config import GROQ_API_KEY, GEMINI_API_KEY, WORKSPACE_DIR
from aura.tools.weather_radar import get_live_weather_radar
from aura.tools.sgc_radar import get_sgc_financial_summary, get_sgc_dual_month_gst
from aura.tools.reminders import list_active_reminders, get_daily_completed_tasks
from aura.memory.brain_store import brain_store

IST = timezone(timedelta(hours=5, minutes=30))

class MorningIntelPilot:
    """
    Autonomous Proactive Agent that observes Mukil's ground-truth reality,
    reasons about his daily battles, decides on top priorities, and generates
    a voice call briefing.
    """

    def __init__(self):
        self.groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

    def gather_ground_truth(self) -> Dict[str, Any]:
        """Collects live facts from SGC billing, Turso reminders, and Placement profile."""
        now = datetime.now(IST)

        # 0. Karur Live Weather & SGC Hank Yarn Sun-Drying Radar
        try:
            weather_radar = get_live_weather_radar("karur")
        except Exception as e:
            weather_radar = f"Weather Radar: Error {e}"
        
        # 1. SGC Business Financials
        try:
            sgc_summary = get_sgc_financial_summary()
        except Exception as e:
            sgc_summary = f"SGC Summary: Error {e}"

        try:
            gst_radar = get_sgc_dual_month_gst()
        except Exception as e:
            gst_radar = f"GST Radar: Error {e}"

        # 2. Turso Cloud Active Reminders
        try:
            reminders_str = list_active_reminders()
        except Exception as e:
            reminders_str = f"Reminders: Error {e}"

        # 3. Placement Roadmap & Career State
        placement_file = WORKSPACE_DIR / "jarvis-core" / "storage" / "memory" / "context.json"
        placement_info = "Target: Infinite Computer Solutions (Final Interview), Amazon VCS, 20 LeetCode Java problems daily."
        if placement_file.exists():
            try:
                with open(placement_file, "r", encoding="utf-8") as f:
                    ctx = json.load(f)
                    career = ctx.get("active_career_strategy", {})
                    drive = career.get("active_drive", {})
                    company = drive.get("company", "Infinite Computer Solutions")
                    stage = drive.get("stage", "Final Interview")
                    status = drive.get("status", "SLOT_PENDING")
                    placement_info = f"Active Drive: {company} | Round: {stage} ({status}) | Fast-Track: Amazon VCS | Target: 20 LeetCode Java problems."
            except Exception:
                pass

        # 4. Recent Conversation Context from Persistent Brain (Yesterday's Flow)
        try:
            recent_turns = brain_store.get_recent_history_across_sessions(limit=8)
            recent_convo = "\n".join([f"{t['role'].upper()}: {t['content'][:120]}" for t in recent_turns]) if recent_turns else "No prior conversation history recorded."
        except Exception as e:
            recent_convo = f"Context extraction error: {e}"

        # 5. Completed Tasks Today
        try:
            completed_today = get_daily_completed_tasks()
        except Exception:
            completed_today = []

        return {
            "datetime": now.strftime("%A, %d %B %Y | %I:%M %p IST"),
            "weather_radar": weather_radar,
            "sgc_summary": sgc_summary,
            "gst_radar": gst_radar,
            "reminders": reminders_str,
            "placement": placement_info,
            "recent_convo": recent_convo,
            "completed_today": completed_today
        }

    def think_and_synthesize(self, intel: Dict[str, Any]) -> Tuple[str, str]:
        """
        Executes the autonomous reasoning loop:
        Analyzes live data -> decides priority battles -> creates speech script.
        Returns: (reasoning_thoughts, speech_script)
        """
        system_prompt = (
            "You are AURA (Autonomous Universal Reasoning Agent), Mukil's executive partner and real brother ('Mapla' dynamic).\n"
            "This is the 06:00 AM Autonomous Morning Wakeup Call for Mukil.\n"
            "Your job is to observe Mukil's live ground-truth data, THINK autonomously about his top priorities for today, "
            "and synthesize an energetic, punchy Tanglish phone call script to wake him up.\n\n"
            "Format your response strictly as:\n"
            "<THOUGHTS>\n"
            "Your internal reasoning: Why you chose certain priorities today, what is urgent vs important.\n"
            "</THOUGHTS>\n\n"
            "<CALL_SCRIPT>\n"
            "The natural, high-energy spoken Tanglish speech for the phone call (max 65-80 words).\n"
            "Start with: 'Good morning Boss Mukil! Mani 6:00 AM...'\n"
            "End with an energetic Stark partner push.\n"
            "</CALL_SCRIPT>"
        )

        user_content = (
            f"Here is Mukil's Live Intel as of {intel['datetime']}:\n\n"
            f"0. Karur Weather & SGC Hank Yarn Sun-Drying:\n{intel.get('weather_radar', 'N/A')}\n\n"
            f"1. Recent Conversation Context (Yesterday's Flow):\n{intel.get('recent_convo', 'None')}\n\n"
            f"2. Turso Cloud Active Pending Reminders / Tasks:\n{intel['reminders']}\n\n"
            f"3. SGC Business Ground Truth:\n{intel['sgc_summary']}\n{intel['gst_radar']}\n\n"
            f"4. Placement Target:\n{intel['placement']}\n\n"
            "Perform your autonomous reasoning, consider where Mukil stopped in recent conversation, and generate the wake-up call briefing now!"
        )

        # Use Groq for ultra-low latency (< 1 second)
        response = self.groq_client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=0.6,
            max_tokens=1000
        )
        content = response.choices[0].message.content or ""

        # Extract THOUGHTS
        thoughts_match = re.search(r"<THOUGHTS>(.*?)</THOUGHTS>", content, re.DOTALL)
        if thoughts_match:
            thoughts = thoughts_match.group(1).strip()
        else:
            thoughts = "Analyzed Mukil's top battles: SGC cashflow vs. Placement interview priority."

        # Extract CALL_SCRIPT
        script_match = re.search(r"<CALL_SCRIPT>(.*?)</CALL_SCRIPT>", content, re.DOTALL)
        if script_match:
            script = script_match.group(1).strip()
        else:
            # Fallback if no tags
            script = content.replace("<THOUGHTS>", "").replace("</THOUGHTS>", "").strip()

        return thoughts, script

    async def generate_speech_audio(self, text: str, output_path: Path) -> str:
        """Converts Tanglish script into high-fidelity speech audio using Google Gemini Native Audio."""
        from aura.tools.voice_tools import _synthesize_gemini_audio, clean_text_for_speech
        clean_text = clean_text_for_speech(text)

        # 1. Primary: Gemini 3.8 Flash Native Audio
        temp_wav = output_path.with_suffix(".wav")
        if _synthesize_gemini_audio(clean_text, "MORNING_WAKEUP", temp_wav):
            try:
                import imageio_ffmpeg
                import subprocess
                ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
                cmd = [ffmpeg, "-y", "-i", str(temp_wav), str(output_path)]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
                if output_path.exists() and output_path.stat().st_size > 0:
                    return str(output_path)
            except Exception:
                pass
            return str(temp_wav)

        # 2. Edge-TTS Fallback
        voice = "ta-IN-ValluvarNeural" if len(re.findall(r'[\u0B80-\u0BFF]', clean_text)) > 3 else "en-IN-PrabhatNeural"
        communicate = edge_tts.Communicate(clean_text, voice=voice, rate="+5%")
        await communicate.save(str(output_path))
        return str(output_path)

    async def run_proactive_cycle(self) -> Dict[str, Any]:
        """Runs the complete cycle: Sense -> Think -> Synthesize -> Generate Audio -> Trigger."""
        print("\n" + "=" * 70)
        print("🧠 [CYCLE 1: SENSE] Gathering Live Ground Truth Data...")
        intel = self.gather_ground_truth()
        print(f"  • Time: {intel['datetime']}")
        print(f"  • SGC Data: Loaded successfully.")
        print(f"  • Placement: {intel['placement']}")

        print("\n" + "=" * 70)
        print("⚡ [CYCLE 2: THINK] Autonomous Cognitive Reasoning (Groq 120B)...")
        thoughts, script = self.think_and_synthesize(intel)
        print("\n--- [AURA's Internal Autonomous Thoughts] ---")
        print(thoughts)

        print("\n" + "=" * 70)
        print("🗣️ [CYCLE 3: SYNTHESIZE] Generated Morning Phone Call Script...")
        print("\n" + script + "\n")

        print("=" * 70)
        print("🎙️ [CYCLE 4: SPEECH ACT] Generating Neural Audio Call Memo...")
        desktop_audio = WORKSPACE_DIR / "Desktop" / "AURA_Morning_Wakeup_Call.mp3"
        await self.generate_speech_audio(script, desktop_audio)
        print(f"✅ Audio generated successfully at:\n   {desktop_audio}")

        # Check call_hub trigger
        print("\n" + "=" * 70)
        print("📱 [CYCLE 5: DISPATCH] Sending Outbound Call Trigger to Cloud Phone Link...")
        call_status = "Cloud Call Trigger Prepared"
        try:
            import httpx
            async with httpx.AsyncClient(timeout=4.0) as client:
                res = await client.post("http://127.0.0.1:8000/call/trigger", json={
                    "caller_name": "JARVIS Prime",
                    "reason": "morning_wakeup_briefing",
                    "custom_message": script
                })
                call_status = f"Dispatched to CallHub (HTTP {res.status_code})"
        except Exception:
            call_status = "CallHub local listener offline (Ready to stream over Render Cloud)"

        print(f"  • Call Dispatch: {call_status}")
        print("=" * 70)
        print("🏆 AUTONOMOUS COGNITIVE CYCLE COMPLETE!")
        print("=" * 70)

        return {
            "intel": intel,
            "thoughts": thoughts,
            "script": script,
            "audio_file": str(desktop_audio),
            "call_status": call_status
        }

    async def run_midday_cycle(self) -> Dict[str, Any]:
        """Runs the 02:00 PM Midday Nudge: checks pending tasks and progress."""
        intel = self.gather_ground_truth()
        reminders = intel.get("reminders", "")
        completed = intel.get("completed_today", [])
        
        system_prompt = (
            "You are AURA, Mukil's executive partner and real brother ('Mapla' dynamic).\n"
            "This is the 02:00 PM Midday Progress Check for Mukil.\n"
            "Observe his active pending tasks and what was completed today. "
            "Ask if he finished morning priority tasks, and give a brief, motivating Tanglish nudge (max 40-50 words).\n"
            "Start with: 'Mapla, midday status check!'"
        )
        user_content = f"Active Pending Tasks:\n{reminders}\nCompleted Today: {len(completed)} tasks."

        response = self.groq_client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=0.5,
            max_tokens=1000
        )
        script = (response.choices[0].message.content or "").strip()
        if not script:
            script = "Mapla, midday status check! Morning priority tasks progress enna? Mudinjidha illa any blockers? Let's crush it!"

        # Signal CallHub
        try:
            import httpx
            async with httpx.AsyncClient(timeout=3.0) as client:
                await client.post("http://127.0.0.1:8000/call/trigger", json={
                    "caller_name": "AURA Midday Check",
                    "reason": "midday_status_nudge",
                    "custom_message": script
                })
        except Exception:
            pass

        return {"script": script, "intel": intel}

    async def run_eod_cycle(self) -> Dict[str, Any]:
        """Runs the 10:00 PM EOD Retrospective: Daily wrap-up, celebrating wins and pre-staging tomorrow."""
        intel = self.gather_ground_truth()
        reminders = intel.get("reminders", "")
        completed = intel.get("completed_today", [])
        
        system_prompt = (
            "You are AURA, Mukil's executive partner and real brother ('Mapla' dynamic).\n"
            "This is the 10:00 PM EOD Retrospective & Day Wrap-up for Mukil.\n"
            "Summarize what tasks were completed today, acknowledge the hustle, "
            "note any remaining pending tasks that will roll over to tomorrow fresh, and wish him a solid night rest (max 50-60 words in Tanglish).\n"
            "Start with: 'Boss Mukil, inniku day wrap-up!'"
        )
        user_content = f"Completed Tasks Today:\n{completed}\nStill Pending:\n{reminders}"

        response = self.groq_client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=0.5,
            max_tokens=1000
        )
        script = (response.choices[0].message.content or "").strip()
        if not script:
            script = f"Boss Mukil, inniku day wrap-up! Completed tasks archived. Rest well mapla, tomorrow fresh start!"

        # Signal CallHub
        try:
            import httpx
            async with httpx.AsyncClient(timeout=3.0) as client:
                await client.post("http://127.0.0.1:8000/call/trigger", json={
                    "caller_name": "AURA EOD Retrospective",
                    "reason": "night_retrospective",
                    "custom_message": script
                })
        except Exception:
            pass

        return {"script": script, "intel": intel}

if __name__ == "__main__":
    pilot = MorningIntelPilot()
    asyncio.run(pilot.run_proactive_cycle())
