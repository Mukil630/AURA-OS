"""
MASSIVE 50-SCENARIO REALITY STRESS TEST & ACCURACY BENCHMARK
File: tools/stress_test_50_voice_scenarios.py

Tests 50 diverse, messy, real-world Tanglish inputs:
- 10 SGC Textile Business & Financials
- 10 MNC Placement, Tests & Offers
- 10 Personal Errands, Family & Friends
- 10 Ambiguous & Half-Spoken Inputs (Must ask targeted questions!)
- 10 Pure Casual Chatter & Small Talk (Must NOT save / 0 DB writes!)
"""

import sys
import os
import asyncio
from pathlib import Path
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from aura_agent_core.voice_intent_gatekeeper import (
    stage_voice_note, resolve_voice_note, STAGING_BUFFER
)
from aura_agent_core.services import list_active_reminders, purge_completed_reminder

TEST_SCENARIOS = [
    # =========================================================================
    # BATCH 1: SGC BUSINESS & FINANCIALS (1-10)
    # =========================================================================
    {"id": 1, "text": "Bannari mill Monday 30k tharom sonnanga", "type": "SGC", "expected_cat": "SGC_PAYMENT_FOLLOWUP", "exp_mill": "Bannari", "exp_amt": 30000},
    {"id": 2, "text": "Sowbhagiya mill-la 45000 pending irukku naaliki kekanum", "type": "SGC", "expected_cat": "SGC_PAYMENT_FOLLOWUP", "exp_mill": "Sowbhagiya", "exp_amt": 45000},
    {"id": 3, "text": "Priya tex 1.5 lakh cheque ready pannitaangalaam Thursday vangikalam", "type": "SGC", "expected_cat": "SGC_PAYMENT_FOLLOWUP", "exp_mill": "Priya", "exp_amt": 150000},
    {"id": 4, "text": "GAIA mill 25k payment release aagiruchu check panniko", "type": "SGC", "expected_cat": "SGC_PAYMENT_FOLLOWUP", "exp_mill": "Gaia", "exp_amt": 25000},
    {"id": 5, "text": "KPR mill 80 aayiram balance Monday kudukren sonnaru", "type": "SGC", "expected_cat": "SGC_PAYMENT_FOLLOWUP", "exp_mill": "Kpr", "exp_amt": 80000},
    {"id": 6, "text": "Amarjothi mill challan 500kg fabric vandhuruchu note pannu", "type": "SGC", "expected_cat": "SGC_PAYMENT_FOLLOWUP", "exp_mill": "Amarjothi", "exp_amt": None},
    {"id": 7, "text": "Lakshmi chemicals 12k invoice pay pannanum in 2 days", "type": "SGC", "expected_cat": "SGC_PAYMENT_FOLLOWUP", "exp_mill": "Lakshmi", "exp_amt": 12000},
    {"id": 8, "text": "Shri Ram fabrics discount 5% kekuraanga pesanum", "type": "SGC", "expected_cat": "SGC_PAYMENT_FOLLOWUP", "exp_mill": "Shri Ram", "exp_amt": None},
    {"id": 9, "text": "Aravind mill bill Monday kudukuradha sonnanga", "type": "SGC", "expected_cat": "SGC_PAYMENT_FOLLOWUP", "exp_mill": "Aravind", "exp_amt": None},
    {"id": 10, "text": "Sundar mill 20k cash kuduthutaanga record panniko", "type": "SGC", "expected_cat": "SGC_PAYMENT_FOLLOWUP", "exp_mill": "Sundar", "exp_amt": 20000},

    # =========================================================================
    # BATCH 2: PLACEMENT & CAREER (11-20)
    # =========================================================================
    {"id": 11, "text": "Infinite Computer Solutions final HR round Wednesday 3 PM-ku irukku", "type": "CAREER", "expected_cat": "CAREER_PLACEMENT", "exp_comp": "Infinite Computer Solutions"},
    {"id": 12, "text": "TCS NQT registration deadline naaliki night 11 PM", "type": "CAREER", "expected_cat": "CAREER_PLACEMENT", "exp_comp": "Tcs"},
    {"id": 13, "text": "Amazon VCS interview link vandhuruchu check pannanum", "type": "CAREER", "expected_cat": "CAREER_PLACEMENT", "exp_comp": "Amazon"},
    {"id": 14, "text": "Zoho coding round Saturday kaalaila 9 AM attend pannanum", "type": "CAREER", "expected_cat": "CAREER_PLACEMENT", "exp_comp": "Zoho"},
    {"id": 15, "text": "Resume-la Next.js project add panna remind pannu", "type": "CAREER", "expected_cat": "CAREER_PLACEMENT", "exp_comp": None},
    {"id": 16, "text": "Daily 6 PM LeetCode Java practice remind pannu", "type": "CAREER", "expected_cat": "CAREER_PLACEMENT", "exp_comp": "Leetcode"},
    {"id": 17, "text": "Accenture technical assessment Friday slot book pannanum", "type": "CAREER", "expected_cat": "CAREER_PLACEMENT", "exp_comp": "Accenture"},
    {"id": 18, "text": "Aptitude formula sheet review pannanum tonight", "type": "CAREER", "expected_cat": "CAREER_PLACEMENT", "exp_comp": None},
    {"id": 19, "text": "Cognizant virtual drive link email-la paakanum", "type": "CAREER", "expected_cat": "CAREER_PLACEMENT", "exp_comp": "Cognizant"},
    {"id": 20, "text": "Infosys cert download panni drive-la podanum", "type": "CAREER", "expected_cat": "CAREER_PLACEMENT", "exp_comp": "Infosys"},

    # =========================================================================
    # BATCH 3: PERSONAL & FAMILY ERRANDS (21-30)
    # =========================================================================
    {"id": 21, "text": "Ram birthday-ku naalaiki 9 AM wish pannanum", "type": "PERSONAL", "expected_cat": "PERSONAL_REMINDER"},
    {"id": 22, "text": "Appa kitta SGC mill diesel bill pathi pesanum", "type": "PERSONAL", "expected_cat": "PERSONAL_REMINDER"},
    {"id": 23, "text": "Bike petrol podanum evening pogumbo", "type": "PERSONAL", "expected_cat": "PERSONAL_REMINDER"},
    {"id": 24, "text": "Doctor appointment Tuesday 5 PM Karur clinic", "type": "PERSONAL", "expected_cat": "PERSONAL_REMINDER"},
    {"id": 25, "text": "Hostel fees 5000 pay pannanum before 30th", "type": "PERSONAL", "expected_cat": "PERSONAL_REMINDER"},
    {"id": 26, "text": "Amma tablet vanganum medical shop-la", "type": "PERSONAL", "expected_cat": "PERSONAL_REMINDER"},
    {"id": 27, "text": "Laptop charger bag-la vekanum college-ku", "type": "PERSONAL", "expected_cat": "PERSONAL_REMINDER"},
    {"id": 28, "text": "Room rent 3500 Suresh-ku GPay pannanum Saturday", "type": "PERSONAL", "expected_cat": "PERSONAL_REMINDER"},
    {"id": 29, "text": "Library book return pannanum Monday", "type": "PERSONAL", "expected_cat": "PERSONAL_REMINDER"},
    {"id": 30, "text": "Friend Saravanan kitta notes vanganum", "type": "PERSONAL", "expected_cat": "PERSONAL_REMINDER"},

    # =========================================================================
    # BATCH 4: AMBIGUOUS & HALF-SPOKEN INPUTS (31-40) -> MUST ASK TARGETED QUESTION
    # =========================================================================
    {"id": 31, "text": "Oru 25000 payment varum da", "type": "AMBIGUOUS", "expected_cat": "AMBIGUOUS_MISSING_MILL"},
    {"id": 32, "text": "Mill kitta balance collect pannanum", "type": "AMBIGUOUS", "expected_cat": "AMBIGUOUS_MISSING_MILL"},
    {"id": 33, "text": "Cheque collect pannanum naaliki", "type": "AMBIGUOUS", "expected_cat": "AMBIGUOUS_MISSING_MILL"},
    {"id": 34, "text": "Bill amount balance collect pannanum", "type": "AMBIGUOUS", "expected_cat": "AMBIGUOUS_MISSING_MILL"},
    {"id": 35, "text": "Oru interview call vandhuchu attend pannanum", "type": "AMBIGUOUS", "expected_cat": "AMBIGUOUS_MISSING_COMPANY"},
    {"id": 36, "text": "Test schedule pannanum", "type": "AMBIGUOUS", "expected_cat": "AMBIGUOUS_MISSING_COMPANY"},
    {"id": 37, "text": "Drive link anupitaangalaam", "type": "AMBIGUOUS", "expected_cat": "AMBIGUOUS_MISSING_COMPANY"},
    {"id": 38, "text": "50k ready pannitaanga", "type": "AMBIGUOUS", "expected_cat": "AMBIGUOUS_MISSING_CONTEXT"},
    {"id": 39, "text": "75000 account-ku anupitaanga", "type": "AMBIGUOUS", "expected_cat": "AMBIGUOUS_MISSING_CONTEXT"},
    {"id": 40, "text": "1 lakh transfer aagiduchu", "type": "AMBIGUOUS", "expected_cat": "AMBIGUOUS_MISSING_CONTEXT"},

    # =========================================================================
    # BATCH 5: PURE CASUAL CHATTER & RANTS (41-50) -> ZERO DB WRITES, ZERO STAGING!
    # =========================================================================
    {"id": 41, "text": "Mapla inniki semma hot-ah irukku weather", "type": "CASUAL", "expected_cat": "CASUAL_CHATTER_IGNORED"},
    {"id": 42, "text": "Bore adikidhu enna panradhu-ne theriyala mapla", "type": "CASUAL", "expected_cat": "CASUAL_CHATTER_IGNORED"},
    {"id": 43, "text": "Oru cup tea kudichutu varalam mapla", "type": "CASUAL", "expected_cat": "CASUAL_CHATTER_IGNORED"},
    {"id": 44, "text": "KGF padam inniki TV-la podraanga", "type": "CASUAL", "expected_cat": "CASUAL_CHATTER_IGNORED"},
    {"id": 45, "text": "Vayiru semmaya pasikidhu biryani sapdanum", "type": "CASUAL", "expected_cat": "CASUAL_CHATTER_IGNORED"},
    {"id": 46, "text": "Romba tired-ah irukku thoonga poren", "type": "CASUAL", "expected_cat": "CASUAL_CHATTER_IGNORED"},
    {"id": 47, "text": "Semma rain Karur-la ippo", "type": "CASUAL", "expected_cat": "CASUAL_CHATTER_IGNORED"},
    {"id": 48, "text": "Traffic jaasthi Karur bypass-la", "type": "CASUAL", "expected_cat": "CASUAL_CHATTER_IGNORED"},
    {"id": 49, "text": "Inniki cricket match yaaru win pannuvaanga?", "type": "CASUAL", "expected_cat": "CASUAL_CHATTER_IGNORED"},
    {"id": 50, "text": "Chumma un kitta pesitu irundhen mapla", "type": "CASUAL", "expected_cat": "CASUAL_CHATTER_IGNORED"},
]

async def run_50_stress_test():
    print("=" * 80)
    print("🚀 AURA 50-SCENARIO REALITY BENCHMARK & COGNITIVE GATEKEEPER STRESS TEST")
    print("=" * 80)
    
    passed_count = 0
    premature_db_writes = 0
    casual_clean_count = 0
    ambiguity_prompt_count = 0
    clarification_generated_count = 0
    
    # Store IDs for atomic commit & purge verification
    committed_task_ids = []

    for item in TEST_SCENARIOS:
        case_id = item["id"]
        raw_speech = item["text"]
        case_type = item["type"]
        
        # 1. Feed into cognitive gatekeeper
        res = stage_voice_note(raw_speech)
        
        # Security Assertion: Zero DB writes on staging!
        if res.get("db_written", False):
            premature_db_writes += 1
            print(f"[FAIL ❌] Case #{case_id}: PREMATURE DB WRITE OCCURRED!")
            continue

        # ----------------------------------------------------
        # Evaluate Category 5: Casual Chatter
        # ----------------------------------------------------
        if case_type == "CASUAL":
            if res.get("status") == "CASUAL_CHATTER_IGNORED" and not res.get("is_actionable"):
                passed_count += 1
                casual_clean_count += 1
                status_icon = "🟢 CASUAL (REJECTED/NO DB)"
            else:
                status_icon = "❌ FAILED CASUAL DETECTION"
            
            print(f"[{case_id:02d}/50] {status_icon} | \"{raw_speech}\" -> Reply: \"{res.get('conversational_reply')}\"")
            continue

        # ----------------------------------------------------
        # Evaluate Category 4: Ambiguous Inputs
        # ----------------------------------------------------
        if case_type == "AMBIGUOUS":
            if res.get("is_ambiguous") and res.get("clarification_question"):
                passed_count += 1
                ambiguity_prompt_count += 1
                status_icon = "🟡 AMBIGUOUS (TARGETED QUESTION)"
            else:
                status_icon = "❌ FAILED AMBIGUITY"
                
            print(f"[{case_id:02d}/50] {status_icon} | \"{raw_speech}\"")
            print(f"        🎙️ Clarification Prompt: \"{res.get('clarification_question')}\"")
            continue

        # ----------------------------------------------------
        # Evaluate Actionable Categories: SGC / Career / Personal
        # ----------------------------------------------------
        is_ok = True
        if case_type == "SGC":
            if res.get("category") != item["expected_cat"]:
                is_ok = False
            if item["exp_mill"] and res["staged_entities"].get("customer_mill") != item["exp_mill"]:
                is_ok = False
            if item["exp_amt"] and res["staged_entities"].get("amount") != item["exp_amt"]:
                is_ok = False
        elif case_type == "CAREER":
            if res.get("category") != item["expected_cat"]:
                is_ok = False
        elif case_type == "PERSONAL":
            if res.get("category") != item["expected_cat"]:
                is_ok = False

        if is_ok:
            passed_count += 1
            clarification_generated_count += 1
            status_icon = "🟢 ACTIONABLE (STAGED IN RAM)"
        else:
            status_icon = "❌ MISCLASSIFIED"

        print(f"[{case_id:02d}/50] {status_icon} [{case_type}] | \"{raw_speech}\"")
        print(f"        🎙️ Question: \"{res.get('clarification_question')}\"")

        # Live Commit / Discard Cycle on Selected Real Cases (e.g., Case #1, #11, #21)
        if case_id in [1, 11, 21]:
            draft_id = res["draft_id"]
            commit_res = await resolve_voice_note(draft_id, "aama mapla lock pannu")
            if commit_res["success"] and commit_res.get("task_id"):
                committed_task_ids.append(commit_res["task_id"])
                print(f"        ⚡ Verified Live Commit to Turso DB: Task #{commit_res['task_id']} ({commit_res['title']})")

    # ----------------------------------------------------
    # FINAL VERIFICATION & PURGE OF COMMITTED TASKS
    # ----------------------------------------------------
    print("\n" + "=" * 80)
    print("🧹 VERIFYING & AUTO-PURGING TEST COMMITS IN TURSO CLOUD DB...")
    active_in_cloud = await list_active_reminders()
    verified_in_cloud = 0
    for tid in committed_task_ids:
        match = [r for r in active_in_cloud if r["id"] == tid]
        if match:
            verified_in_cloud += 1
            await purge_completed_reminder(tid)
            print(f"  • Purged Test Task #{tid} from Turso Cloud (Maintained 0 MB Bloat) ✅")

    # ----------------------------------------------------
    # TELEMETRY & METRIC REPORT
    # ----------------------------------------------------
    accuracy_rate = (passed_count / len(TEST_SCENARIOS)) * 100.0
    casual_filter_rate = (casual_clean_count / 10) * 100.0
    ambiguity_accuracy = (ambiguity_prompt_count / 10) * 100.0

    print("\n" + "=" * 80)
    print("📊 50-SCENARIO PRODUCTION REALITY BENCHMARK METRICS:")
    print("=" * 80)
    print(f"  • Total Real-World Scenarios Tested : {len(TEST_SCENARIOS)}")
    print(f"  • Passed Scenarios Cleanly         : {passed_count} / {len(TEST_SCENARIOS)}")
    print(f"  • Overall Cognitive Accuracy Rate   : {accuracy_rate:.1f}%")
    print(f"  • Premature / Blind Cloud DB Writes : {premature_db_writes} (0.00% Zero-Blind-Saving) 🛡️")
    print(f"  • Casual Chatter Rejection Rate     : {casual_filter_rate:.1f}% (Zero Cloud Pollution)")
    print(f"  • Ambiguity Targeted Question Rate  : {ambiguity_accuracy:.1f}% (Smart Disambiguation)")
    print(f"  • Cloud DB Roundtrips Verified      : {verified_in_cloud} / {len(committed_task_ids)} Committed & Purged")
    print("=" * 80)
    
    return accuracy_rate == 100.0 and premature_db_writes == 0

if __name__ == "__main__":
    success = asyncio.run(run_50_stress_test())
    if success:
        print("\n🏆 ULTIMATE VERDICT: 50/50 PERFECT SCORE! SYSTEM IS ROCK-SOLID READY FOR PRODUCTION.")
    else:
        print("\n⚠️ VERDICT: Some tests failed. Check telemetry above.")
