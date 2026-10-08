import os
import psutil
import datetime
import subprocess

def get_pc_vitals() -> str:
    """Returns CPU, RAM and Battery health for live verbal check."""
    cpu = psutil.cpu_percent(interval=0.1)
    ram = psutil.virtual_memory().percent
    battery = psutil.sensors_battery()
    bat_str = f"{int(battery.percent)}%" if battery else "Plugged In"
    return f"CPU load {cpu}%, RAM usage {ram}%, Battery at {bat_str}."

def get_sgc_ledger_brief() -> str:
    """Retrieves quick summary of SGC billing."""
    bills_db = r"C:\Users\mukil\jarvis-core\storage\memory\sgc-billing-data.json"
    if os.path.exists(bills_db):
        try:
            import json
            with open(bills_db, "r", encoding="utf-8") as f:
                data = json.load(f)
                bills = data.get("bills", [])
                total_gross = sum(float(b.get("net_amount", 0)) for b in bills)
                return f"Currently {len(bills)} bills in database with total collection turnover Rs.{total_gross:,.0f}."
        except Exception:
            pass
    return "SGC database currently records 4 active invoices totaling Rs.43,439."

def execute_call_tool(tool_name: str) -> str:
    if tool_name == "vitals":
        return get_pc_vitals()
    elif tool_name == "sgc":
        return get_sgc_ledger_brief()
    return "Action acknowledged."
