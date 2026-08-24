import os
import sys
import json
from datetime import datetime, timedelta

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from brain.adaptive_scheduler import AdaptiveScheduler, SCHEDULE_DB_PATH

def test_adaptive_scheduler_autonomous():
    print("="*70)
    print("AURA AUTONOMOUS TEST: ADAPTIVE SCHEDULER & AUTO-REVERT ENGINE")
    print("="*70)
    
    # 1. Reset state to clean baseline
    if os.path.exists(SCHEDULE_DB_PATH):
        os.remove(SCHEDULE_DB_PATH)
        
    sched = AdaptiveScheduler()
    
    # TEST 1: Baseline routine verification
    print("\n[TEST 1] Testing Baseline Routine...")
    base = sched.get_today_active_schedule()
    assert base["mode"] == "BASELINE_ROUTINE", "Expected BASELINE_ROUTINE mode"
    assert "Java Collections & DSA Drill" in base["schedule"]["evening_19_00"]["task"]
    print("  [PASS] Baseline routine loaded correctly!")
    
    # TEST 2: Create 7-Day Sprint Override (Capgemini Drive)
    print("\n[TEST 2] Testing 7-Day Placement Sprint Creation...")
    sprint = sched.create_sprint_override("Capgemini Placement Drive Sprint", duration_days=7, focus_topics=["Capgemini Pseudo Code", "Game-Based Aptitude", "Technical Interview"])
    assert sprint["status"] == "ACTIVE"
    assert sprint["duration_days"] == 7
    print(f"  [PASS] Active Sprint Override Created: '{sprint['sprint_name']}' until {sprint['expiry_date']}")
    
    # TEST 3: Verify Active Schedule has switched to Sprint Mode
    print("\n[TEST 3] Verifying Effective Schedule Switch to Sprint Mode...")
    active_now = sched.get_today_active_schedule()
    assert active_now["mode"] == "SPRINT_OVERRIDE"
    assert "Capgemini" in active_now["schedule"]["evening_19_00"]["task"]
    print(f"  [PASS] Active mode is SPRINT_OVERRIDE: {active_now['schedule']['evening_19_00']['task']}")
    
    # TEST 4: Simulate Sprint Expiration (Fast-forward to Day 8) and Test Auto-Reversion
    print("\n[TEST 4] Simulating Sprint Expiration & Testing Auto-Reversion State Machine...")
    state = sched.load_schedule_state()
    # Force expiry date to yesterday to simulate passing of 7 days
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    state["active_override"]["expiry_date"] = yesterday
    sched.save_schedule_state(state)
    
    # Trigger auto-revert check
    revert_result = sched.check_and_auto_revert()
    assert revert_result["status"] == "AUTO_REVERTED", f"Expected AUTO_REVERTED, got {revert_result['status']}"
    print(f"  [PASS] Auto-Reversion State Machine Triggered: {revert_result['message']}")
    
    # TEST 5: Verify Schedule is 100% restored to Baseline
    print("\n[TEST 5] Verifying Post-Reversion Schedule is Back to Baseline...")
    restored = sched.get_today_active_schedule()
    assert restored["mode"] == "BASELINE_ROUTINE"
    assert "Java Collections & DSA Drill" in restored["schedule"]["evening_19_00"]["task"]
    print("  [PASS] Baseline routine 100% Restored automatically!")
    
    print("\n" + "="*70)
    print("ALL 5 SCHEDULER & AUTO-REVERSION TESTS PASSED WITH 100% SUCCESS!")
    print("="*70)

if __name__ == "__main__":
    test_adaptive_scheduler_autonomous()
