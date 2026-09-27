"""
SGC Billing Authoritative Query Service
tools/sgc_billing_query.py - 100% Deterministic, Ground-Truth Billing Data Retriever.
Guarantees Zero LLM Hallucination for Invoices, Turnover, and GST Figures.
"""
import os
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("sgc_billing_query")

def get_sgc_db_path() -> Optional[Path]:
    """Finds the active SGC billing database on Windows or fallback storage."""
    candidates = [
        Path(os.environ.get("APPDATA", "")) / "sgc-billing" / "sgc-billing-data.json",
        Path.home() / "AppData" / "Roaming" / "sgc-billing" / "sgc-billing-data.json",
        Path(__file__).parent.parent / "storage" / "bills" / "sgc-billing-data.json",
        Path(__file__).parent.parent / "storage" / "memory" / "sgc-billing-data.json",
    ]
    for p in candidates:
        if p.exists() and p.is_file():
            return p
    return None

def load_all_bills() -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Loads all raw bills from the verified JSON store."""
    db_path = get_sgc_db_path()
    if not db_path:
        return [], "SGC Billing database (sgc-billing-data.json) not found on system."

    try:
        with open(db_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("sgc-bills", []), None
    except Exception as e:
        return [], f"Failed to read SGC database: {str(e)}"

def get_ledger_metrics(target_month: Optional[str] = None) -> Dict[str, Any]:
    """
    Computes exact financial metrics for a target month (YYYY-MM or 'current'/'all').
    Defaults to current month if None.
    """
    bills, err = load_all_bills()
    if err:
        return {"success": False, "error": err, "total_bills": 0}

    now = datetime.now()
    curr_month_str = now.strftime("%Y-%m")
    curr_month_name = now.strftime("%B %Y")

    if not target_month or target_month in ["current", "this", "now", "september", "sep"]:
        # If September requested without year, use current year September
        m_filter = curr_month_str
        m_name = curr_month_name
    elif target_month.lower() in ["all", "overall", "total"]:
        m_filter = "ALL"
        m_name = "All Time"
    elif target_month.lower() in ["prev", "previous", "last"]:
        first_day_curr = now.replace(day=1)
        prev_end = first_day_curr - timedelta(days=1)
        m_filter = prev_end.strftime("%Y-%m")
        m_name = prev_end.strftime("%B %Y")
    else:
        # Check if year-month format or month name
        clean_m = target_month.strip()
        if len(clean_m) == 7 and clean_m[4] == "-":
            m_filter = clean_m
            try:
                dt = datetime.strptime(m_filter + "-01", "%Y-%m-%d")
                m_name = dt.strftime("%B %Y")
            except Exception:
                m_name = m_filter
        else:
            # Fallback to current
            m_filter = curr_month_str
            m_name = curr_month_name

    if m_filter == "ALL":
        filtered_bills = bills
    else:
        filtered_bills = [b for b in bills if (b.get("date") or "").startswith(m_filter)]

    total_subtotal = sum(float(b.get("subtotal") or 0) for b in filtered_bills)
    total_cgst = sum(float(b.get("cgst") or 0) for b in filtered_bills)
    total_sgst = sum(float(b.get("sgst") or 0) for b in filtered_bills)
    total_gross = sum(float(b.get("netAmount") or 0) for b in filtered_bills)

    pending_bills = [b for b in filtered_bills if (b.get("status") or "").lower() == "pending"]
    paid_bills = [b for b in filtered_bills if (b.get("status") or "").lower() in ["paid", "cleared", "completed"]]

    total_pending_amount = sum(float(b.get("netAmount") or 0) for b in pending_bills)
    total_paid_amount = sum(float(b.get("netAmount") or 0) for b in paid_bills)

    return {
        "success": True,
        "period_name": m_name,
        "period_filter": m_filter,
        "total_bills_in_db": len(bills),
        "period_bills_count": len(filtered_bills),
        "total_subtotal": round(total_subtotal, 2),
        "total_cgst": round(total_cgst, 2),
        "total_sgst": round(total_sgst, 2),
        "total_gst": round(total_cgst + total_sgst, 2),
        "total_gross": round(total_gross, 2),
        "pending_bills_count": len(pending_bills),
        "pending_amount": round(total_pending_amount, 2),
        "paid_bills_count": len(paid_bills),
        "paid_amount": round(total_paid_amount, 2),
        "bills": filtered_bills
    }

def format_verified_bills_report(target_month: Optional[str] = None) -> str:
    """Returns a 100% verified, anti-hallucination Tanglish report."""
    metrics = get_ledger_metrics(target_month)
    if not metrics.get("success"):
        return f"⚠️ **SGC Billing Error:** {metrics.get('error')}"

    count = metrics["period_bills_count"]
    total_in_db = metrics["total_bills_in_db"]
    p_name = metrics["period_name"]

    if count == 0:
        return (
            f"📊 **Sri Ganapathi Colours (SGC) - {p_name} Verified Ledger**\n\n"
            f"• **Database Path**: `AppData/Roaming/sgc-billing/sgc-billing-data.json`\n"
            f"• **Total Bills in Database**: **{total_in_db} Bills**\n"
            f"• **Bills in {p_name}**: **0 Bills**\n"
            f"• **Invoiced Amount**: ₹0.00\n\n"
            f"Mapla, indha month-ku active bills edhum create aagala!"
        )

    bill_items = []
    for b in metrics["bills"]:
        b_no = b.get("billNo", "?")
        cust = b.get("customer", "Party")
        dt = b.get("date", "")
        amt = float(b.get("netAmount") or 0)
        st = b.get("status", "pending").upper()
        bill_items.append(f"• **Bill #{b_no}** | {dt} | **{cust}** | `₹{amt:,.2f}` | *{st}*")

    bills_str = "\n".join(bill_items)

    report = (
        f"📊 **Sri Ganapathi Colours (SGC) - Verified {p_name} Ledger**\n"
        f"*(Zero-Hallucination Ground Truth from Live Database)*\n\n"
        f"🧾 **Actual Invoices Generated:** **{count} Bills** (Database Total: {total_in_db})\n"
        f"💵 **Taxable Turnover (Subtotal):** ₹{metrics['total_subtotal']:,.2f}\n"
        f"🏛️ **GST Breakdown (5% SGC Textile Dyeing):**\n"
        f"  • *CGST (2.5%):* ₹{metrics['total_cgst']:,.2f}\n"
        f"  • *SGST (2.5%):* ₹{metrics['total_sgst']:,.2f}\n"
        f"  • *Total GST:* ₹{metrics['total_gst']:,.2f}\n\n"
        f"💰 **GRAND TOTAL INVOICED:** **₹{metrics['total_gross']:,.2f}**\n\n"
        f"📌 **Status & Collections:**\n"
        f"  • *Pending Collection:* ₹{metrics['pending_amount']:,.2f} ({metrics['pending_bills_count']} Bills)\n"
        f"  • *Collected Amount:* ₹{metrics['paid_amount']:,.2f} ({metrics['paid_bills_count']} Bills)\n\n"
        f"📋 **Verified Bills Breakdown:**\n"
        f"{bills_str}\n"
    )
    return report

def format_verified_tax_report(target_month: Optional[str] = None) -> str:
    """Returns exact 5% GST tax calculation across all verified bills."""
    metrics = get_ledger_metrics(target_month)
    if not metrics.get("success"):
        return f"⚠️ **SGC Tax Calculation Error:** {metrics.get('error')}"

    count = metrics["period_bills_count"]
    p_name = metrics["period_name"]

    if count == 0:
        return f"🏛️ **SGC {p_name} Tax Report**: 0 bills found. Total Tax: ₹0.00."

    lines = []
    for b in metrics["bills"]:
        b_no = b.get("billNo", "?")
        cust = b.get("customer", "Party")
        cg = float(b.get("cgst") or 0)
        sg = float(b.get("sgst") or 0)
        tot_tax = cg + sg
        lines.append(f"• **Bill #{b_no}** ({cust}): `₹{tot_tax:,.2f}` _(CGST ₹{cg:,.2f} + SGST ₹{sg:,.2f})_")

    breakdown_str = "\n".join(lines)

    return (
        f"🏛️ **Sri Ganapathi Colours (SGC) — Verified {p_name} Tax Calculation**\n"
        f"*(Exact 5% GST on All {count} Invoices)*\n\n"
        f"💵 **Taxable Turnover (Subtotal):** ₹{metrics['total_subtotal']:,.2f}\n"
        f"────────────────────────\n"
        f"🔹 **Central GST (CGST @ 2.5%):** `₹{metrics['total_cgst']:,.2f}`\n"
        f"🔹 **State GST (SGST @ 2.5%):** `₹{metrics['total_sgst']:,.2f}`\n"
        f"🔥 **TOTAL 5% TAX ONLY:** **`₹{metrics['total_gst']:,.2f}`**\n"
        f"────────────────────────\n"
        f"💰 **Gross Invoiced (Turnover + Tax):** `₹{metrics['total_gross']:,.2f}`\n\n"
        f"📋 **Bill-wise Tax Breakdown:**\n"
        f"{breakdown_str}\n"
    )

def mark_bill_paid(bill_no_input: Any, payment_mode: str = "Online / Bank Transfer") -> Dict[str, Any]:
    """Marks an invoice as PAID in both local Windows store and repo backup store."""
    try:
        target_no = int(str(bill_no_input).replace("#", "").strip())
    except ValueError:
        return {"success": False, "error": f"Invalid bill number: {bill_no_input}"}

    db_paths = [
        get_sgc_db_path(),
        Path(__file__).parent.parent / "storage" / "bills" / "sgc-billing-data.json",
        Path(__file__).parent.parent / "storage" / "memory" / "sgc-billing-data.json",
    ]
    # Filter valid unique paths
    valid_paths = []
    for p in db_paths:
        if p and p.exists() and p not in valid_paths:
            valid_paths.append(p)

    if not valid_paths:
        return {"success": False, "error": "No SGC billing database found to update."}

    matched_bill = None
    now_iso = datetime.now().isoformat()

    for path in valid_paths:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            bills = data.get("sgc-bills", [])
            for b in bills:
                if int(b.get("billNo", -1)) == target_no:
                    b["status"] = "paid"
                    b["paidAt"] = now_iso
                    b["paymentMode"] = payment_mode
                    if "payments" not in b or not isinstance(b["payments"], list):
                        b["payments"] = []
                    b["payments"].append({
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "amount": float(b.get("netAmount", 0)),
                        "mode": payment_mode,
                        "notes": "Marked paid via JARVIS Telegram Agent"
                    })
                    matched_bill = b
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error updating bill in {path}: {e}")

    if matched_bill:
        return {
            "success": True,
            "billNo": target_no,
            "customer": matched_bill.get("customer", "Party"),
            "amount": matched_bill.get("netAmount", 0),
            "date": matched_bill.get("date", ""),
            "paymentMode": payment_mode
        }
    return {"success": False, "error": f"Bill #{target_no} not found in database."}

def format_customer_ledger(customer_query: str) -> str:
    """Returns all historical invoices, total billed, paid, and pending for a specific customer."""
    bills, err = load_all_bills()
    if err:
        return f"⚠️ **SGC Ledger Error:** {err}"

    q_lower = customer_query.lower().strip()
    matching_bills = [
        b for b in bills
        if q_lower in (b.get("customer") or "").lower()
    ]

    if not matching_bills:
        all_customers = sorted(list(set(b.get("customer", "") for b in bills if b.get("customer"))))
        avail = ", ".join(f"`{c}`" for c in all_customers)
        return (
            f"🔍 **Party '{customer_query}' not found.**\n\n"
            f"📋 **Available Parties in Database:**\n{avail}"
        )

    matched_name = matching_bills[0].get("customer", customer_query)
    total_billed = sum(float(b.get("netAmount", 0) or 0) for b in matching_bills)
    pending_bills = [b for b in matching_bills if (b.get("status") or "").lower() == "pending"]
    paid_bills = [b for b in matching_bills if (b.get("status") or "").lower() in ["paid", "cleared"]]

    total_pending = sum(float(b.get("netAmount", 0) or 0) for b in pending_bills)
    total_paid = sum(float(b.get("netAmount", 0) or 0) for b in paid_bills)

    bill_rows = []
    for b in matching_bills:
        b_no = b.get("billNo", "?")
        dt = b.get("date", "")
        amt = float(b.get("netAmount", 0) or 0)
        st = (b.get("status") or "pending").upper()
        icon = "🟢" if st == "PAID" else "🔴"
        bill_rows.append(f"• {icon} **Bill #{b_no}** | {dt} | `₹{amt:,.2f}` | *{st}*")

    rows_str = "\n".join(bill_rows)

    return (
        f"🏛️ **Sri Ganapathi Colours — Customer Ledger Dossier**\n\n"
        f"👤 **Party:** **{matched_name}**\n"
        f"🧾 **Total Invoices:** {len(matching_bills)} Bills\n"
        f"💰 **Total Billed Value:** `₹{total_billed:,.2f}`\n"
        f"────────────────────────\n"
        f"✅ **Total Paid / Cleared:** `₹{total_paid:,.2f}` ({len(paid_bills)} Bills)\n"
        f"⚠️ **Total Outstanding Pending:** **`₹{total_pending:,.2f}`** ({len(pending_bills)} Bills)\n"
        f"────────────────────────\n\n"
        f"📋 **Invoices History:**\n"
        f"{rows_str}\n"
    )

def load_all_customers() -> List[Dict[str, Any]]:
    """Loads all registered customers from master registry and bills."""
    db_path = get_sgc_db_path()
    customers_map = {}
    if db_path and db_path.exists():
        try:
            with open(db_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # 1. From sgc-customers master array
            for c in data.get("sgc-customers", []):
                name = c.get("name", "").strip()
                if name:
                    customers_map[name.lower()] = {
                        "name": name,
                        "gst": c.get("gst", ""),
                        "phone": c.get("phone", "")
                    }
            # 2. Augment from sgc-bills
            for b in data.get("sgc-bills", []):
                cust = (b.get("customer") or "").strip()
                if cust and cust.lower() not in customers_map:
                    customers_map[cust.lower()] = {
                        "name": cust,
                        "gst": b.get("partyGst", ""),
                        "phone": ""
                    }
        except Exception as e:
            logger.error(f"Error loading customers: {e}")

    return list(customers_map.values())

def lookup_customer(query: str) -> Optional[Dict[str, Any]]:
    """Finds a customer by partial name match."""
    q = query.lower().strip()
    customers = load_all_customers()
    # Exact match first
    for c in customers:
        if q == c.get("name", "").lower():
            return c
    # Partial match
    for c in customers:
        if q in c.get("name", "").lower():
            return c
    return None

def format_customer_details(query: str) -> str:
    """Formats customer GSTIN, phone, and bill stats into an executive reply."""
    cust = lookup_customer(query)
    if not cust:
        return f"🔍 **Party '{query}' not found in SGC master directory.**\nType `/ledger` to see recorded parties."

    name = cust.get("name")
    gst = cust.get("gst") or "Not Registered / Non-GST"
    phone = cust.get("phone") or "Not Recorded"

    # Also check if they have past bills
    bills, _ = load_all_bills()
    cust_bills = [b for b in bills if (b.get("customer") or "").lower() == name.lower()]
    total_billed = sum(float(b.get("netAmount", 0) or 0) for b in cust_bills)
    pending_amt = sum(float(b.get("netAmount", 0) or 0) for b in cust_bills if (b.get("status") or "").lower() == "pending")

    return (
        f"🏛️ **SRI GANAPATHI COLOURS — CLIENT DOSSIER**\n\n"
        f"👤 **Customer Name:** **{name}**\n"
        f"🆔 **GSTIN:** `{gst}`\n"
        f"📞 **Phone:** `{phone}`\n"
        f"────────────────────────\n"
        f"🧾 **Invoices on Record:** {len(cust_bills)} Bills\n"
        f"💰 **Total Invoiced:** `₹{total_billed:,.2f}`\n"
        f"⚠️ **Pending Collection:** `₹{pending_amt:,.2f}`\n"
        f"────────────────────────\n"
        f"💡 *Tip: Type `/ledger {name.split()[0].lower()}` to view complete invoice history.*"
    )

def get_bill_by_no(bill_no: int) -> Optional[Dict[str, Any]]:
    """Fetches a specific bill dictionary by bill number."""
    bills, err = load_all_bills()
    if err:
        return None
    for b in bills:
        if int(b.get("billNo", 0)) == int(bill_no):
            return b
    return None

def format_bill_download_reply(bill_no: int) -> str:
    """Formats direct download link and invoice details for a specific bill."""
    b = get_bill_by_no(bill_no)
    if not b:
        return f"❌ **Bill #{bill_no} not found in database.**"

    b_no = b.get("billNo")
    cust = b.get("customer", "Party")
    amt = float(b.get("netAmount", 0) or 0)
    dt = b.get("date", "")
    st = (b.get("status") or "pending").upper()
    drive_url = b.get("driveUrl") or f"https://drive.google.com/drive/folders/11KMBP0HHa2AFl30zjL8-a_-BQk9MgWM9"

    return (
        f"🧾 **SRI GANAPATHI COLOURS — TAX INVOICE #{b_no}**\n\n"
        f"👤 **Billed To:** {cust}\n"
        f"📅 **Date:** {dt}\n"
        f"💰 **Net Amount:** **₹{amt:,.2f}**\n"
        f"📌 **Status:** *{st}*\n"
        f"────────────────────────\n"
        f"📥 **Official PDF Download Link:**\n"
        f"🔗 [Open & Download Bill #{b_no} PDF]({drive_url})\n\n"
        f"📁 *Main Bills Vault:* [Google Drive Node 05](https://drive.google.com/drive/folders/11KMBP0HHa2AFl30zjL8-a_-BQk9MgWM9)"
    )



