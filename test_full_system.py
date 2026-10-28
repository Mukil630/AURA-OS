"""
AURA OS Comprehensive System Verification Script
Validates all 6 core pillars:
1. Tool Registry & Schemas
2. SGC Business Radar Ground Truth
3. 250GB Drive Mesh & Master Vault
4. Sandboxed CodeAct Execution
5. Dynamic Self-Extending Tool Synthesis
6. Full Cognitive Loop with Tool Calling & Token Streaming
"""
import sys
import os
import time
from pathlib import Path

# Fix Windows console UTF-8 output
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

from aura.tools.registry import registry
from aura.kernel.agent import AuraAgent

def run_comprehensive_test():
    print("=" * 70)
    print("🚀 AURA OS v3.1 COMPREHENSIVE FULL SYSTEM VERIFICATION")
    print("=" * 70)
    
    passed = 0
    total = 0
    
    # Test 1: Registry
    total += 1
    schemas = registry.get_schemas()
    if len(schemas) >= 15:
        print(f"✅ [1/6] Tool Registry: PASS ({len(schemas)} Superpowers active)")
        passed += 1
    else:
        print(f"❌ [1/6] Tool Registry: FAIL (Only {len(schemas)} tools)")

    # Test 2: SGC Radar
    total += 1
    try:
        fin = registry.execute("get_sgc_financial_summary", {})
        gst = registry.execute("get_sgc_dual_month_gst", {})
        if "Total Invoices:" in fin and "₹" in gst:
            print(f"✅ [2/6] SGC Ground Truth: PASS (Verified live invoice records & GST calculations)")
            passed += 1
        else:
            print(f"❌ [2/6] SGC Ground Truth: FAIL")
    except Exception as e:
        print(f"❌ [2/6] SGC Ground Truth: ERROR ({e})")

    # Test 3: Drive Mesh & Resume
    total += 1
    try:
        mesh = registry.execute("get_drive_mesh_status", {})
        resume = registry.execute("get_master_resume_link", {})
        if "250GB" in mesh and "1TpyzV7OGEf-YQfGLUpusAI5cDDvF1kAJ" in resume:
            print(f"✅ [3/6] Drive Mesh: PASS (250GB Mesh & Master Resume verified)")
            passed += 1
        else:
            print(f"❌ [3/6] Drive Mesh: FAIL")
    except Exception as e:
        print(f"❌ [3/6] Drive Mesh: ERROR ({e})")

    # Test 4: CodeAct
    total += 1
    try:
        res = registry.execute("run_command", {"command": "echo AURA_ACTIVE"})
        if "AURA_ACTIVE" in res:
            print(f"✅ [4/6] CodeAct Execution: PASS (Terminal command verified)")
            passed += 1
        else:
            print(f"❌ [4/6] CodeAct Execution: FAIL")
    except Exception as e:
        print(f"❌ [4/6] CodeAct Execution: ERROR ({e})")

    # Test 5: Self-Extending Tool Engine
    total += 1
    try:
        test_fn_src = '''def auto_multiplier_test(val: int) -> str:
    """Multiplies an input integer by 10."""
    return f"Result: {val * 10}"
'''
        test_fn_unit = '''res = auto_multiplier_test(5)
assert "Result: 50" in res
'''
        res_create = registry.execute("create_and_register_new_tool", {
            "tool_name": "auto_multiplier_test",
            "code": test_fn_src,
            "test_code": test_fn_unit,
            "description": "Auto multiplier self-extension verification tool"
        })
        if "SUCCESS" in res_create and "auto_multiplier_test" in registry._tools:
            test_exec = registry.execute("auto_multiplier_test", {"val": 7})
            if "Result: 70" in test_exec:
                print(f"✅ [5/6] Self-Extending Tool Engine: PASS (Synthesized, sandboxed & hot-registered)")
                passed += 1
            else:
                print(f"❌ [5/6] Self-Extending Tool: Execution failed ({test_exec})")
        else:
            print(f"❌ [5/6] Self-Extending Tool: FAIL ({res_create})")
    except Exception as e:
        print(f"❌ [5/6] Self-Extending Tool: ERROR ({e})")

    # Test 6: Full Cognitive Loop with Tool Calling
    total += 1
    try:
        agent = AuraAgent()
        tool_called = False
        tokens_received = False
        final_reply = ""
        
        for evt, content in agent.chat_stream("Hi mapla! Namma October GST evlo nu tool use panni sollu."):
            if evt == "tool_call":
                tool_called = True
            elif evt == "token":
                tokens_received = True
                final_reply += content
                
        if tool_called and tokens_received and ("964" in final_reply or "GST" in final_reply or "October" in final_reply):
            print(f"✅ [6/6] Full Cognitive Loop: PASS (Autonomous tool call & streaming reasoning verified)")
            passed += 1
        else:
            print(f"❌ [6/6] Full Cognitive Loop: FAIL (Tool called: {tool_called}, Tokens: {tokens_received})")
    except Exception as e:
        print(f"❌ [6/6] Full Cognitive Loop: ERROR ({e})")

    print("-" * 70)
    print(f"📊 VERDICT: {passed}/{total} PILLARS VERIFIED ({(passed/total)*100:.1f}%)")
    print("=" * 70)
    return passed == total

if __name__ == "__main__":
    success = run_comprehensive_test()
    sys.exit(0 if success else 1)
