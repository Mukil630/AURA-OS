"""Interactive Command-Line Tester for Mukil's 6-Stage Master Cognitive Engine."""
import asyncio
import os
import sys

# Configure UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.brain.master_orchestrator import MasterOrchestrator
from app.tools.tts_engine import JARVISVoiceEngine

async def cli_loop():
    orchestrator = MasterOrchestrator()
    voice_engine = JARVISVoiceEngine()

    print("\n" + "=" * 70)
    print("🌌 AURA-OS / JARVIS: INTERACTIVE MASTER COGNITIVE CONSOLE")
    print("=" * 70)
    print("💡 Try typing any of these:")
    print("  • 'Hi maapla, how are you?'  (Casual conversation)")
    print("  • 'Open youtube'             (PC-Pilot application launch)")
    print("  • 'Scrape https://example.com' (Web dynamic processing)")
    print("  • 'Delete all system files'  (Clarification safety block)")
    print("  • Type 'exit' or 'quit' to close console.")
    print("=" * 70 + "\n")

    while True:
        try:
            user_input = input("\n👤 Mukil: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit", "q"]:
                print("👋 Exiting JARVIS Console. Have a great day Boss!")
                break

            print("\n⚙️ [6-Stage Engine Processing...]")
            resp = await orchestrator.process_user_input(
                user_input=user_input,
                user_name="Mukil"
            )

            print(f"\n🤖 JARVIS [{resp.response_type}]:")
            print(f"{resp.text}")

            if resp.plan:
                print(f"\n📋 Execution Plan ({len(resp.plan.steps)} steps):")
                for s in resp.plan.steps:
                    print(f"  • Step {s.order}: {s.name} ({s.tool_name})")

            if resp.step_results:
                print(f"\n⚡ Step Verification Results:")
                for sr in resp.step_results:
                    print(f"  • {sr.step_id}: {sr.status}")

        except (KeyboardInterrupt, EOFError):
            print("\n👋 Console interrupted. Exiting.")
            break
        except Exception as e:
            print(f"\n❌ Error processing input: {e}")

if __name__ == "__main__":
    asyncio.run(cli_loop())
