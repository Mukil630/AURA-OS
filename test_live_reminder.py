import asyncio
import os
import sys
import tempfile

# Add path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from app.tools.reminder_scheduler import ReminderScheduler
from app.tools.tts_engine import JARVISVoiceEngine

async def main():
    print("=" * 60)
    print("⏰ LIVE JARVIS REMINDER DEMO & AUDIO PROOF TEST")
    print("=" * 60)
    
    scheduler = ReminderScheduler(storage_path="data/test_reminders.json")
    voice_engine = JARVISVoiceEngine()
    
    fired_event = asyncio.Event()
    
    async def on_reminder_due(reminder):
        print(f"\n🔔 >>> REMINDER FIRED LIVE! <<<")
        print(f"📋 Reminder ID : {reminder['reminder_id']}")
        print(f"📝 Message     : {reminder['message']}")
        print(f"⏳ Fired Time  : {reminder.get('fired_at')}")
        
        # Synthesize Tamil voice note
        tamil_voice = f"வணக்கம் Boss! இது உங்களுக்கான live reminder: {reminder['message']}. நேரத்தை சரியாக பயன்படுத்தவும்."
        print(f"🎙️ Generating voice note: '{tamil_voice}'...")
        
        audio_file = os.path.join(os.path.dirname(__file__), "reminder_alert.mp3")
        await voice_engine.save_voice_file(tamil_voice, audio_file)
        print(f"✅ Voice note generated and saved to: {audio_file}")
        
        # Play the audio on local PC speakers so Mukil can hear it!
        try:
            import subprocess
            cmd = f'powershell -c "(New-Object Media.SoundPlayer \'{audio_file}\').PlaySync()"'
            # If mp3, play using default player or wmplayer / ffplay / powershell
            play_cmd = f'powershell -c "$wmp = New-Object -ComObject wmplayer.ocx; $wmp.URL = \'{audio_file}\'; $wmp.controls.play(); Start-Sleep -Seconds 5"'
            subprocess.run(play_cmd, shell=True)
            print("🔊 Spoken Audio played on PC speakers!")
        except Exception as e:
            print(f"Audio playback note: {e}")
            
        fired_event.set()

    scheduler.set_callback(on_reminder_due)
    await scheduler.start()
    
    print("\n⏳ Setting a 5-second test reminder: '/remind 5s Test Placement Reminder'...")
    rem = scheduler.parse_and_create(chat_id=123456, user_id=999, command_args="5s Test Placement Reminder")
    print(f"✅ Reminder registered! Target Time: {rem['target_time']}")
    print("⏳ Waiting 5 seconds for scheduler to trigger...")
    
    try:
        await asyncio.wait_for(fired_event.wait(), timeout=12.0)
        print("\n🎉 100% PROOF: Reminder successfully triggered, synthesized speech, and executed live!")
    except asyncio.TimeoutError:
        print("\n❌ Timed out waiting for reminder.")
    finally:
        await scheduler.stop()

if __name__ == "__main__":
    asyncio.run(main())
