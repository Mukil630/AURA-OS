import json
import os
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from tools.sgc_billing_query import load_all_bills

def get_overdue_report() -> dict:
    """Analyzes pending bills in SGC Billing and returns overdue analysis & follow-up messages."""
    bills, err = load_all_bills()
    if err:
        return {"error": err}
    now = datetime.now()

    pending_bills = []
    total_pending = 0.0

    for b in bills:
        if b.get("status", "").lower() == "pending":
            net = float(b.get("netAmount", 0))
            total_pending += net
            date_str = b.get("date", "")
            days_ago = 0
            try:
                b_date = datetime.strptime(date_str, "%Y-%m-%d")
                days_ago = (now - b_date).days
            except Exception:
                pass

            if days_ago > 30:
                tier = "CRITICAL_30_DAYS"
                badge = "🔴"
            elif days_ago > 14:
                tier = "WARNING_15_DAYS"
                badge = "🟡"
            else:
                tier = "RECENT"
                badge = "🟢"

            # Pre-formatted professional follow-up message in Tamil & English
            customer = b.get("customer", "Client")
            bill_no = b.get("billNo")
            draft_msg = (
                f"Vanakkam sir, Sri Ganapathi Colours la irundhu. "
                f"Namma Invoice #{bill_no} (Dated: {date_str}) total amount Rs.{net:,.0f} pending-la irukku. "
                f"Please update payment status when convenient. Bank: CSB Bank, A/C: 003204157368195001, IFSC: CSBK0000032. Nandri!"
            )

            pending_bills.append({
                "bill_no": bill_no,
                "customer": customer,
                "date": date_str,
                "days_overdue": days_ago,
                "net_amount": net,
                "tier": tier,
                "badge": badge,
                "draft_followup": draft_msg
            })

    pending_bills.sort(key=lambda x: x["days_overdue"], reverse=True)

    return {
        "total_pending_amount": total_pending,
        "total_pending_count": len(pending_bills),
        "bills": pending_bills,
        "as_of": now.strftime("%Y-%m-%d %I:%M %p")
    }

def generate_executive_radar_report() -> str:
    rep = get_overdue_report()
    if rep.get("error"):
        return f"⚠️ **SGC Overdue Radar:** {rep['error']}"

    total = rep["total_pending_amount"]
    count = rep["total_pending_count"]
    bills = rep["bills"]

    if count == 0:
        return "🎉 **All SGC bills are 100% cleared! Zero pending payments.**"

    lines = [
        f"📊 **Sri Ganapathi Colours — Overdue & Collection Radar**\n",
        f"• **Total Outstanding:** **`₹{total:,.2f}`** across **{count} Pending Bills**",
        f"• **As of:** `{rep['as_of']}`\n",
        f"📋 **Pending Bills Breakdown:**"
    ]

    for b in bills:
        lines.append(
            f"• {b['badge']} **Bill #{b['bill_no']}** | **{b['customer']}** | `₹{b['net_amount']:,.2f}` | *{b['days_overdue']} days age* ({b['date']})"
        )

    lines.append(
        f"\n☁️ **Master Vault:** [Google Drive Bills Folder](https://drive.google.com/drive/folders/11KMBP0HHa2AFl30zjL8-a_-BQk9MgWM9)"
    )
    return "\n".join(lines)

def format_overdue_telegram() -> str:
    return generate_executive_radar_report()

if __name__ == "__main__":
    print(generate_executive_radar_report())
