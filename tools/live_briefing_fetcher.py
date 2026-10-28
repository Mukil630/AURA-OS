"""
========================================================================================
JARVIS LIVE TOOL-BASED BRIEFING RETRIEVER (live_briefing_fetcher.py)
----------------------------------------------------------------------------------------
Zero-Hallucination Live Data Fetcher:
1. Queries Open-Meteo REST API for Karur live climate.
2. Reads physical sgc-billing-data.json for actual unpaid invoices.
3. Reads living_task_ledger.json for active user rules.
========================================================================================
"""

import sys
import os
import json
from datetime import datetime

JARVIS_DIR = r"C:\Users\mukil\jarvis-core"
if JARVIS_DIR not in sys.path:
    sys.path.insert(0, JARVIS_DIR)

from tools.weather_radar_tool import get_live_weather_radar
from brain.living_task_ledger import LivingTaskLedger

def get_realtime_data(city: str = "karur") -> dict:
    # 1. Weather
    weather = get_live_weather_radar(city)
    
    # 2. SGC Physical Bills
    sgc_path = r"C:\Users\mukil\AppData\Roaming\sgc-billing\sgc-billing-data.json"
    bills_data = []
    total_pending = 0.0
    latest_bill = {}
    
    if os.path.exists(sgc_path):
        with open(sgc_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
            bills_data = raw.get("sgc-bills", [])
            pending = [b for b in bills_data if str(b.get("status", "")).lower() != "paid"]
            total_pending = sum(float(b.get("netAmount") or b.get("total") or 0.0) for b in pending)
            if pending:
                latest_bill = pending[-1]

    # 3. Task Ledger Anomalies
    ledger = LivingTaskLedger()
    anomalies = ledger.evaluate_daily_anomalies()

    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %I:%M %p"),
        "city": weather.get("location", city.capitalize()),
        "temperature_c": weather.get("temperature_c"),
        "rain_prob_pct": weather.get("next_6h_rain_probability_pct"),
        "hank_drying_safe": weather.get("safe_for_outdoor_drying"),
        "sgc_total_bills": len(bills_data),
        "sgc_total_pending_inr": total_pending,
        "latest_pending_bill_no": latest_bill.get("billNo") or latest_bill.get("bill_no"),
        "latest_pending_customer": latest_bill.get("customer") or latest_bill.get("partyName"),
        "latest_pending_amount": float(latest_bill.get("netAmount") or latest_bill.get("total") or 0.0),
        "active_anomalies": anomalies
    }

if __name__ == "__main__":
    res = get_realtime_data("karur")
    print(json.dumps(res, indent=2))
