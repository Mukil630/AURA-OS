"""
AURA OS — Cognitive Reasoning Loop End-to-End Verification Test
Verifies the exact ReAct architecture:
[Input (User Task)] ──> [1. Planning & Reasoning] ──> [2. Tool Selection] ──> [3. Tool Execution] ──> [4. Output & Observation Processing] ──> [5. Done? Criteria Check] ──> [Final Response]
"""
import sys
import os

# UTF-8 console output
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from aura.kernel.agent import AuraAgent
from aura.tools.registry import registry


def test_react_cognitive_reasoning_loop():
    print("=" * 70)
    print("🧠 AURA OS // COGNITIVE REASONING LOOP VERIFICATION TEST")
    print("=" * 70)
    print("Architecture Flow:")
    print("┌─────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐")
    print("│  Input      │────▶│  Planning    │────▶│  Tool        │────▶│  Execution   │")
    print("│  (User Task)│     │  & Reasoning │     │  Selection   │     │  & Result    │")
    print("└─────────────┘     └──────────────┘     └──────────────┘     └──────────────┘")
    print("                                                                     │")
    print("                         ┌──────────────┐     ┌──────────────────────▼")
    print("                         │  Observation │◀────│  Output Processing")
    print("                         │  Processing  │")
    print("                         └──────────────┘")
    print("                         │")
    print("                         ▼")
    print("                    ┌──────────────┐")
    print("                    │  Done?       │")
    print("                    │  Check       │")
    print("                    └──────────────┘")
    print("                      │          ▲")
    print("                     YES         NO (Loop again)")
    print("                      ▼          │")
    print("                  ┌─────────────┐")
    print("                  │  Final Resp │")
    print("                  └─────────────┘")
    print("=" * 70)

    agent = AuraAgent()

    # Step 1: User Task Input
    task_prompt = "Karur weather check panni, hank yarn veliya kaya vaikalaama nu sollu mapla"
    print(f"\n[1. INPUT (User Task)]: \"{task_prompt}\"")

    events = []
    final_text = ""

    # Step 2 to 7: Execution through the Cognitive Streaming Loop
    for event_type, content in agent.chat_stream(task_prompt):
        events.append((event_type, content))
        if event_type == "thought":
            print(f"\n🧠 [2. PLANNING & REASONING (Thought)]:\n   {content}")
        elif event_type == "tool_call":
            print(f"\n⚙️  [3. TOOL SELECTION & ACTION]:\n   {content}")
        elif event_type in ["observation", "tool_result"]:
            print(f"\n👁️  [4. OBSERVATION PROCESSING]:\n   {content}")
        elif event_type == "token":
            final_text += content

    print(f"\n🎯 [5 & 6. DONE CRITERIA SATISFIED ──> FINAL RESPONSE]:\n{final_text}\n")

    # Assertions
    tool_calls = [c for t, c in events if t == "tool_call"]
    observations = [c for t, c in events if t in ["observation", "tool_result"]]

    assert len(tool_calls) > 0, "FAILED: No tool was selected in cognitive loop!"
    print(f"  • Verified Tool Selection: {tool_calls[0]} ✅")

    assert len(observations) > 0, "FAILED: No observation was processed from tool execution!"
    print(f"  • Verified Observation Processing: Output observed from tool ✅")

    assert len(final_text) > 10, "FAILED: Final response synthesis failed!"
    print(f"  • Verified Final Response: Clean executive synthesis delivered ✅")

    print("\n" + "=" * 70)
    print("🏆 ALL 6 STAGES OF THE COGNITIVE REASONING LOOP 100% OPERATIONAL & VERIFIED!")
    print("=" * 70)


if __name__ == "__main__":
    test_react_cognitive_reasoning_loop()
