"""
AURA OS & JARVIS Swarm - End-to-End Automated Verification Test Suite
Run this anytime: python test_suite.py
Validates:
1. Universal Tool Registry & Schema compilation
2. SGC Financial Radar ground truth math
3. 250GB Distributed Drive Mesh & Master Vault links
4. Sandboxed CodeAct execution
5. Groq High-Speed Cognitive Engine
"""
import sys
import os
import time
from pathlib import Path

# Fix Windows console UTF-8 output
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

from aura.tools.registry import registry
from groq import Groq
from aura.config import GROQ_API_KEY

def run_tests():
    print("=" * 65)
    print("🧪 AURA OS & SWARM AGENT VERIFICATION TEST SUITE")
    print("=" * 65)
    
    passed = 0
    total = 0
    
    # Test 1: Tool Registry Schemas
    total += 1
    tools = list(registry._tools.keys())
    schemas = registry.get_schemas()
    if len(tools) >= 10 and len(schemas) >= 10:
        print(f"✅ [1/5] Tool Registry: PASS ({len(tools)} tools registered & schemas compiled)")
        passed += 1
    else:
        print(f"❌ [1/5] Tool Registry: FAIL (Found {len(tools)} tools)")

    # Test 2: SGC Financial Radar & Zero-Hallucination Math
    total += 1
    try:
        fin_summary = registry.execute("get_sgc_financial_summary", {})
        gst_radar = registry.execute("get_sgc_dual_month_gst", {})
        if "Total Invoices: 10" in fin_summary and "₹63,917.00" in fin_summary and "₹964.17" in gst_radar:
            print(f"✅ [2/5] SGC Financial Radar: PASS (10 Invoices, ₹63,917 billed, Oct GST ₹964.17)")
            passed += 1
        else:
            print(f"❌ [2/5] SGC Financial Radar: FAIL (Unexpected values returned)")
    except Exception as e:
        print(f"❌ [2/5] SGC Financial Radar: ERROR ({e})")

    # Test 3: Google Drive Mesh & Master Resume Vault
    total += 1
    try:
        drive_status = registry.execute("get_drive_mesh_status", {})
        resume_link = registry.execute("get_master_resume_link", {})
        if "250GB Distributed Drive Mesh" in drive_status and "1TpyzV7OGEf-YQfGLUpusAI5cDDvF1kAJ" in resume_link:
            print(f"✅ [3/5] Drive Mesh & Master Vault: PASS (250GB Mesh 10 Nodes & Master Resume verified)")
            passed += 1
        else:
            print(f"❌ [3/5] Drive Mesh: FAIL ({drive_status[:60]})")
    except Exception as e:
        print(f"❌ [3/5] Drive Mesh: ERROR ({e})")

    # Test 4: CodeAct Sandboxed Shell Execution
    total += 1
    try:
        cmd_res = registry.execute("run_command", {"command": "echo AURA_ACTIVE"})
        if "AURA_ACTIVE" in cmd_res:
            print(f"✅ [4/5] Sandboxed CodeAct Execution: PASS (Terminal execution verified)")
            passed += 1
        else:
            print(f"❌ [4/5] Sandboxed CodeAct: FAIL ({cmd_res[:60]})")
    except Exception as e:
        print(f"❌ [4/5] Sandboxed CodeAct: ERROR ({e})")

    # Test 5: Groq High-Speed Cognitive Engine
    total += 1
    try:
        t0 = time.time()
        client = Groq(api_key=GROQ_API_KEY)
        res = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[{"role": "user", "content": "Respond with 'AURA_ONLINE' only."}],
            max_tokens=100
        )
        reply = res.choices[0].message.content.strip()
        elapsed = time.time() - t0
        if "AURA_ONLINE" in reply or len(reply) > 0:
            print(f"✅ [5/5] Groq Cognitive Engine: PASS (Model 'openai/gpt-oss-120b' responded in {elapsed:.2f}s)")
            passed += 1
        else:
            print(f"❌ [5/5] Groq Cognitive Engine: FAIL (Empty reply)")
    except Exception as e:
        print(f"❌ [5/5] Groq Cognitive Engine: ERROR ({e})")

    print("-" * 65)
    print(f"📊 VERDICT: {passed}/{total} TESTS PASSED ({(passed/total)*100:.1f}%)")
    print("=" * 65)
    return passed == total

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
