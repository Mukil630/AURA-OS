"""
AURA OS — Multi-Step Cognitive Chaining Test
Tests multi-tool execution chaining:
Input -> Plan -> Tool 1 (Latest Bill) -> Observe 1 -> Plan -> Tool 2 (Weather) -> Observe 2 -> Done Check -> Consolidated Response
"""
import sys
import os

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from aura.kernel.agent import AuraAgent


def test_multistep_flow():
    print("=" * 70)
    print("🧠 AURA OS // MULTI-STEP COGNITIVE CHAINING FLOW TEST")
    print("=" * 70)

    agent = AuraAgent()
    prompt = "Mapla, SGC latest bill number and customer sollu, aprom Karur weather epdi irukku nu check panni sollu."
    print(f"\n[Task Prompt]: {prompt}\n")

    events = []
    final_text = ""

    for event_type, content in agent.chat_stream(prompt):
        events.append((event_type, content))
        if event_type == "tool_call":
            print(f"⚙️  [Action / Tool]: {content}")
        elif event_type in ["observation", "tool_result"]:
            print(f"👁️  [Observation]: {content[:90]}...")
        elif event_type == "token":
            final_text += content

    print(f"\n[Final Response]:\n{final_text}\n")

    tools_called = [c for t, c in events if t == "tool_call"]
    assert any("latest_bill" in t.lower() or "sgc" in t.lower() for t in tools_called), "FAILED: SGC tool not called!"
    assert any("weather" in t.lower() for t in tools_called), "FAILED: Weather tool not called!"
    assert len(final_text) > 20, "FAILED: Final text empty!"

    print("=" * 70)
    print("🏆 MULTI-STEP CHAINING FLOW 100% VERIFIED & PASSED!")
    print("=" * 70)


if __name__ == "__main__":
    test_multistep_flow()
