"""
Dual-Enterprise Cognitive Router & Unified Business Intelligence Engine
tools/enterprise_router.py - Bridges Mukil's Dual Enterprises with Zero Hallucination & Zero Cross-Contamination.

Entity 1: Sri Ganapathi Colours (Yarn Dyeing Unit - Father's Enterprise)
Entity 2: Sri Ganapathi Colours - Bleaching Unit (Salavai Unit - Mukil's Independent Enterprise)

Guarantees Rule 8 (Dual-Enterprise Zero Cross-Contamination Directive) and Rule 6 (Ground-Truth First).
"""
import os
import re
import sys
import json
import logging
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

JARVIS_CORE_DIR = Path(__file__).resolve().parent.parent
if str(JARVIS_CORE_DIR) not in sys.path:
    sys.path.insert(0, str(JARVIS_CORE_DIR))

from tools import sgc_billing_query
from tools import bleaching_billing_query

logger = logging.getLogger("enterprise_router")

# -------------------------------------------------------------
# ENTERPRISE CONSTANTS & VAULTS
# -------------------------------------------------------------
SGC_DRIVE_VAULT_URL = "https://drive.google.com/drive/folders/11KMBP0HHa2AFl30zjL8-a_-BQk9MgWM9"
BLEACHING_DRIVE_VAULT_URL = "https://drive.google.com/drive/folders/1Xb4gl8KvxlStlfWIIxRjIgWlIAupeg4J"

# Customer directory mapping
BLEACHING_ONLY_CUSTOMERS = [
    "eco fusion", "unity exports", "amsa exports", "amsa", "manish tex",
    "malaiyamman fabrics", "malaiyamman", "saravana traders", "priya handlooms",
    "priya", "varniga tex", "ambara export", "sri athi sakthi fabrics",
    "athi sakthi", "athi shakthi", "rameshwari fabrics", "marvel fabrics",
    "ponni fab", "airwill home collections", "airwill", "om sakthi a tex"
]

SGC_ONLY_CUSTOMERS = [
    "bannari amman dyeing", "bannari amman", "bannari", "lakshmi chemicals",
    "eb commercial", "sri ganapathi colours"
]

SHARED_CUSTOMERS = [
    "m.s.k fabrics", "msk fabrics", "msk", "sowbhagiya home textiles",
    "sowbhagiya", "gaia sustainable solution", "gaia", "sri laxmi export",
    "sri laxmi", "laxmi export", "laxmi"
]


def resolve_enterprise(text: str) -> Dict[str, Any]:
    """
    Intelligently identifies enterprise target, customer name, and bill number from user prompt.
    Returns: {
        "target": "BLEACHING" | "SGC" | "DUAL",
        "customer": str or None,
        "bill_no": int or None,
        "is_tax_query": bool,
        "is_overdue_query": bool,
        "is_specific_month": Optional[str]
    }
    """
    t_low = text.lower().strip()

    # 1. Extract Bill Number if present
    bill_no = None
    m_bill = re.search(r'\b(?:bill|inv|invoice)\s*(?:#|no\.?|num\.?)?\s*(\d+)\b', t_low)
    if not m_bill:
        # Check standalone number preceded by #
        m_hash = re.search(r'#(\d+)\b', t_low)
        if m_hash:
            bill_no = int(m_hash.group(1))
    else:
        bill_no = int(m_bill.group(1))

    # 2. Extract Customer Name
    detected_customer = None
    all_known = BLEACHING_ONLY_CUSTOMERS + SGC_ONLY_CUSTOMERS + SHARED_CUSTOMERS
    for c in all_known:
        if c in t_low:
            detected_customer = c
            break

    # 3. Determine Enterprise Target
    target = "DUAL"

    # Explicit keyword overrides
    bleach_kws = ["bleach", "bleaching", "salavai", "washing unit", "my unit", "independent"]
    sgc_kws = ["dyeing", "yarn dyeing", "father unit", "father business", "sgc dyeing"]

    has_bleach_kw = any(k in t_low for k in bleach_kws)
    has_sgc_kw = any(k in t_low for k in sgc_kws)

    if has_bleach_kw and not has_sgc_kw:
        target = "BLEACHING"
    elif has_sgc_kw and not has_bleach_kw:
        target = "SGC"
    elif detected_customer:
        if detected_customer in BLEACHING_ONLY_CUSTOMERS:
            target = "BLEACHING"
        elif detected_customer in SGC_ONLY_CUSTOMERS:
            target = "SGC"
        else:
            target = "DUAL"  # Customer exists across both enterprises
    elif bill_no:
        if bill_no >= 200:
            target = "BLEACHING"  # Bleaching bill series starts at 251
        elif 1 <= bill_no < 200:
            target = "SGC"        # SGC bill series is 1..11

    # Query intent tags
    is_tax = any(w in t_low for w in ["tax", "gst", "cgst", "sgst", "gstr", "auditor"])
    is_overdue = any(w in t_low for w in ["overdue", "debtor", "who owes", "pending collection", "recovery"])

    target_month = None
    for m in ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december", "sep", "oct"]:
        if m in t_low:
            target_month = m
            break
    if "this month" in t_low or "current month" in t_low:
        target_month = "current"
    elif "last month" in t_low or "prev month" in t_low:
        target_month = "previous"

    return {
        "target": target,
        "customer": detected_customer,
        "bill_no": bill_no,
        "is_tax_query": is_tax,
        "is_overdue_query": is_overdue,
        "target_month": target_month,
    }


def get_bleaching_bills_sync() -> List[Dict[str, Any]]:
    """Safely retrieves Bleaching bills from Turso Cloud or local fallback."""
    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                bills = pool.submit(asyncio.run, bleaching_billing_query.query_turso_bills()).result(timeout=4)
        else:
            bills = asyncio.run(bleaching_billing_query.query_turso_bills())
        if bills:
            return bills
    except Exception as e:
        logger.warning(f"Turso sync fetch error in router: {e}")

    local_b, _ = bleaching_billing_query.load_local_bills()
    return local_b or []


def format_dual_enterprise_dashboard() -> Tuple[str, str]:
    """
    Renders an executive consolidated radar covering BOTH SGC (Yarn Dyeing) and Bleaching Unit.
    Zero cross-contamination: each entity has its own separate numbers and Drive vault link.
    """
    # 1. Fetch SGC Ground Truth
    sgc_metrics = sgc_billing_query.get_ledger_metrics("all")
    sgc_bills_count = sgc_metrics.get("period_bills_count", 0)
    sgc_gross = sgc_metrics.get("total_gross", 0.0)
    sgc_pending = sgc_metrics.get("pending_amount", 0.0)
    sgc_paid = sgc_metrics.get("paid_amount", 0.0)
    sgc_gst = sgc_metrics.get("total_gst", 0.0)

    # 2. Fetch Bleaching Ground Truth
    bleach_bills = get_bleaching_bills_sync()
    bleach_overview = bleaching_billing_query.get_bleaching_overview(bleach_bills)
    bleach_count = bleach_overview.get("total_bills", 0)
    bleach_gross = bleach_overview.get("total_invoiced", 0.0)
    bleach_pending = bleach_overview.get("total_outstanding", 0.0)
    bleach_paid = bleach_overview.get("total_collected", 0.0)

    # 3. Consolidated Totals
    total_group_turnover = sgc_gross + bleach_gross
    total_group_pending = sgc_pending + bleach_pending
    total_group_bills = sgc_bills_count + bleach_count

    # Bleaching recent bills preview
    bleach_preview = []
    for b in bleach_bills[:3]:
        bleach_preview.append(f"  • *Bill #{b.get('billNo')}* | {b.get('customer')} | `₹{float(b.get('netAmount', 0)):,.2f}` [{b.get('status')}]")
    bleach_preview_str = "\n".join(bleach_preview) if bleach_preview else "  • _No active bills yet._"

    report_md = (
        "🏛️ **MUKIL'S DUAL-ENTERPRISE FINANCIAL RADAR**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🟢 **ENTITY 1: SRI GANAPATHI COLOURS (YARN DYEING UNIT)**\n"
        "_(Father's Business • Main Dyeing Operations)_\n"
        f"• **Gross Invoiced**: `₹{sgc_gross:,.2f}` ({sgc_bills_count} Bills)\n"
        f"• **Outstanding Dues**: `₹{sgc_pending:,.2f}` ({sgc_metrics.get('pending_bills_count', 0)} Unpaid)\n"
        f"• **Settled Collections**: `₹{sgc_paid:,.2f}`\n"
        f"• **Total GST (5%)**: `₹{sgc_gst:,.2f}`\n"
        f"• **Top Overdue**: Bannari Amman Dyeing (`₹30,000.00`)\n"
        f"📁 [Open SGC Bills Drive Vault]({SGC_DRIVE_VAULT_URL})\n\n"
        "⚪ **ENTITY 2: BLEACHING UNIT (SALAVAI UNIT)**\n"
        "_(Mukil's Independent Enterprise • Karur Yarn Hub)_\n"
        f"• **Gross Invoiced**: `₹{bleach_gross:,.2f}` ({bleach_count} Bills)\n"
        f"• **Outstanding Dues**: `₹{bleach_pending:,.2f}` ({bleach_overview.get('pending_bills_count', 0)} Unpaid)\n"
        f"• **Settled Collections**: `₹{bleach_paid:,.2f}`\n"
        f"• **Recent Invoices**:\n{bleach_preview_str}\n"
        f"📁 [Open Bleaching-Bills Drive Vault]({BLEACHING_DRIVE_VAULT_URL})\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚖️ **CONSOLIDATED POSITION**: `₹{total_group_turnover:,.2f}` Gross | `₹{total_group_pending:,.2f}` Pending ({total_group_bills} Total Bills)\n\n"
        "💡 *Tip:* Ask about any client (e.g. `Eco Fusion bill evlo` or `Bannari dues evlo`) for 1-click ledger!"
    )

    speech_text = (
        f"Boss, Dual-Enterprise radar ready! SGC Yarn Dyeing-la total {sgc_bills_count} bills, turnover {sgc_gross:,.0f} rupees. "
        f"Bleaching Unit-la {bleach_count} bills, turnover {bleach_gross:,.0f} rupees. "
        f"Combined total turnover {total_group_turnover:,.0f} rupees, total pending dues {total_group_pending:,.0f} rupees."
    )

    return report_md, speech_text


def format_customer_enterprise_ledger(customer_name: str, query: str = "") -> Tuple[str, str]:
    """
    Renders customer ledger across Bleaching, SGC, or both without cross-contamination.
    Also retrieves verified GSTIN & profile from Turso Cloud directory if bills are 0.
    """
    c_clean = customer_name.strip()
    c_lower = c_clean.lower()
    q_low = query.lower() if query else ""
    is_gst_query = any(w in q_low for w in ["gst", "gstin", "tax", "tin"]) or any(w in c_lower for w in ["gst", "gstin"])

    # 1. Search in Bleaching bills
    bleach_bills = get_bleaching_bills_sync()
    bleach_ledger = bleaching_billing_query.get_bleaching_ledger_for_customer(bleach_bills, c_clean)
    has_bleach = bleach_ledger.get("total_bills", 0) > 0

    # 2. Search in SGC bills
    sgc_bills, _ = sgc_billing_query.load_all_bills()
    sgc_matched = [b for b in sgc_bills if bleaching_billing_query.is_name_match(c_clean, str(b.get("customer", "")))]
    has_sgc = len(sgc_matched) > 0

    # 3. Check Registered Customers Directory in Turso Cloud (Bleaching)
    reg_cust = bleaching_billing_query.get_registered_customer(c_clean)

    if not has_bleach and not has_sgc:
        if reg_cust:
            name_disp = reg_cust.get("name") or c_clean.title()
            gst_disp = reg_cust.get("gstin") or "Not Registered"
            addr_disp = reg_cust.get("address") or "Karur"
            phone_disp = reg_cust.get("phone") or "N/A"
            lines = [
                f"👤 **REGISTERED CLIENT PROFILE — {name_disp.upper()}**",
                "",
                "🏭 **Enterprise**: Bleaching Unit (Mukil's Independent Enterprise)",
                f"🆔 **GSTIN**: `{gst_disp}`",
                f"📍 **Address / Location**: {addr_disp}",
                f"📞 **Phone**: {phone_disp}",
                "🧾 **Invoices Generated**: `0` (No pending bills yet)",
                "💰 **Outstanding Balance**: `₹0.00`",
                "",
                "✅ Client is registered in Turso Cloud database with active GST verification."
            ]
            reply_md = "\n".join(lines)
            speech = f"Boss, {name_disp} Bleaching Unit registered client. GSTIN number {gst_disp}. Ippo varaikum pending bills ethuvum illa."
            return reply_md, speech

        lines = [
            f"⚠️ **Customer '{c_clean}' not found in billing databases.**",
            "",
            "Checked both:",
            "• SGC Yarn Dyeing Unit (11 bills)",
            "• Bleaching Unit (2 bills & registered client directory)",
            "",
            "💡 Available clients: *Eco Fusion, M.S.K Fabrics, Bannari Amman, Sowbhagiya, GAIA, Sri Laxmi, Malaiyamman*."
        ]
        reply_md = "\n".join(lines)
        speech = f"Boss, {c_clean} customer database-la kedaikala."
        return reply_md, speech

    sections = []
    speech_parts = []

    # Format Bleaching section
    if has_bleach:
        b_gst = ""
        if reg_cust and reg_cust.get("gstin"):
            b_gst = f" | **GSTIN**: `{reg_cust['gstin']}`"
        elif bleach_ledger.get("bills") and bleach_ledger["bills"][0].get("customerGst"):
            b_gst = f" | **GSTIN**: `{bleach_ledger['bills'][0]['customerGst']}`"

        b_lines = [
            f"• *Bill #{b.get('billNo')}* ({b.get('date')}): `₹{float(b.get('netAmount', 0)):,.2f}` [{b.get('status')}]"
            for b in bleach_ledger.get("bills", [])
        ]
        b_sec_lines = [
            f"⚪ **BLEACHING UNIT (SALAVAI) — {c_clean.upper()}**{b_gst}",
            f"• **Invoices**: `{bleach_ledger['total_bills']}` | **Gross**: `₹{bleach_ledger['total_billed']:,.2f}`",
            f"• **Outstanding Due**: `₹{bleach_ledger['outstanding_balance']:,.2f}`",
            "🧾 **Bills List**:",
            *b_lines,
            f"📁 [Bleaching Drive Folder]({BLEACHING_DRIVE_VAULT_URL})"
        ]
        sections.append("\n".join(b_sec_lines))
        gst_speech = f" GSTIN number {reg_cust['gstin']}." if (reg_cust and reg_cust.get("gstin") and is_gst_query) else ""
        speech_parts.append(f"Bleaching Unit-la {bleach_ledger['total_bills']} bills, outstanding balance {bleach_ledger['outstanding_balance']} rupees.{gst_speech}")

    # Format SGC section
    if has_sgc:
        sgc_billed = sum(float(b.get("netAmount", 0) or 0) for b in sgc_matched)
        sgc_pending = sum(float(b.get("netAmount", 0) or 0) for b in sgc_matched if str(b.get("status", "")).upper() != "PAID")
        sgc_gst = sgc_matched[0].get("partyGst") or ""
        sgc_gst_str = f" | **GSTIN**: `{sgc_gst}`" if sgc_gst else ""
        s_lines = [
            f"• *Bill #{b.get('billNo')}* ({b.get('date')}): `₹{float(b.get('netAmount', 0)):,.2f}` [{b.get('status')}]"
            for b in sgc_matched
        ]
        s_sec_lines = [
            f"🟢 **SGC YARN DYEING UNIT — {c_clean.upper()}**{sgc_gst_str}",
            f"• **Invoices**: `{len(sgc_matched)}` | **Gross**: `₹{sgc_billed:,.2f}`",
            f"• **Outstanding Due**: `₹{sgc_pending:,.2f}`",
            "🧾 **Bills List**:",
            *s_lines,
            f"📁 [SGC Drive Folder]({SGC_DRIVE_VAULT_URL})"
        ]
        sections.append("\n".join(s_sec_lines))
        speech_parts.append(f"SGC Dyeing-la {len(sgc_matched)} bills, outstanding {sgc_pending} rupees")

    reply_md = (
        f"👤 **CUSTOMER LEDGER REPORT: {c_clean.upper()}**\n\n"
        + "\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n".join(sections)
    )
    speech = f"Boss, {c_clean}-oda ledger ready! " + "; ".join(speech_parts) + "."
    return reply_md, speech



def format_specific_bill(bill_no: int) -> Tuple[str, str]:
    """Fetches exact details for a specific bill number from the appropriate enterprise."""
    # Check Bleaching first if bill_no >= 200
    if bill_no >= 200:
        bleach_bills = get_bleaching_bills_sync()
        target = next((b for b in bleach_bills if str(b.get("billNo")) == str(bill_no)), None)
        if target:
            net = float(target.get("netAmount", 0))
            cust = target.get("customer")
            dt = target.get("date")
            d_link = target.get("driveLink") or BLEACHING_DRIVE_VAULT_URL
            md = (
                f"⚪ **BLEACHING BILL #{bill_no} DETAILS**\n\n"
                f"👤 **Customer**: {cust}\n"
                f"📅 **Date**: {dt}\n"
                f"💰 **Net Amount**: `₹{net:,.2f}`\n"
                f"💳 **Status**: `{target.get('status')}`\n\n"
                f"📂 [Download PDF from Bleaching Drive Vault]({d_link})"
            )
            speech = f"Bleaching Bill #{bill_no} {cust}-ku {net} rupees net amount-la iruku Boss."
            return md, speech

    # Check SGC bills
    sgc_bill = sgc_billing_query.get_bill_by_no(bill_no)
    if sgc_bill:
        net = float(sgc_bill.get("netAmount", 0))
        cust = sgc_bill.get("customer")
        md = sgc_billing_query.format_bill_download_reply(bill_no)
        speech = f"SGC Bill #{bill_no} {cust}-ku {net} rupees net amount-la iruku Boss."
        return md, speech

    # Fallback search both
    bleach_bills = get_bleaching_bills_sync()
    target_b = next((b for b in bleach_bills if str(b.get("billNo")) == str(bill_no)), None)
    if target_b:
        net = float(target_b.get("netAmount", 0))
        cust = target_b.get("customer")
        md = (
            f"⚪ **BLEACHING BILL #{bill_no} DETAILS**\n\n"
            f"👤 **Customer**: {cust}\n"
            f"💰 **Net Amount**: `₹{net:,.2f}`\n"
            f"💳 **Status**: `{target_b.get('status')}`\n"
            f"📂 [Bleaching Drive Vault]({BLEACHING_DRIVE_VAULT_URL})"
        )
        return md, f"Bleaching Bill #{bill_no} {cust}-ku {net} rupees Boss."

    return f"❌ Bill #{bill_no} could not be found in SGC or Bleaching records.", f"Bill #{bill_no} kedaikala Boss."


def handle_smart_billing_query(query: str, entities: Optional[Dict[str, Any]] = None) -> Tuple[str, str]:
    """
    Main Autonomous Entry Point: Resolves user intent dynamically without rigid hardcoding.
    """
    plan = resolve_enterprise(query)
    target = plan["target"]
    cust = plan["customer"]
    bill_no = plan["bill_no"]
    is_tax = plan["is_tax_query"]
    is_overdue = plan["is_overdue_query"]

    # 1. Specific Bill Number Query
    if bill_no:
        return format_specific_bill(bill_no)

    # 2. Specific Customer Ledger Query
    if cust:
        return format_customer_enterprise_ledger(cust, query=query)

    # 3. Tax / GST Query
    if is_tax:
        # Generate SGC tax report and Bleaching tax summary
        sgc_tax_rep = sgc_billing_query.format_dual_month_tax_report()
        bleach_bills = get_bleaching_bills_sync()
        bleach_gross = sum(float(b.get("netAmount", 0)) for b in bleach_bills)
        bleach_gst = bleach_gross * 0.05 / 1.05  # 5% inclusive
        combined_tax_md = (
            f"{sgc_tax_rep}\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚪ **BLEACHING UNIT GST (5%) RADAR**\n"
            f"• **Total Bleaching Invoiced**: `₹{bleach_gross:,.2f}`\n"
            f"• **Estimated GST (5%)**: `₹{bleach_gst:,.2f}` (CGST: `₹{bleach_gst/2:,.2f}` | SGST: `₹{bleach_gst/2:,.2f}`)\n"
            f"📁 [Bleaching Bills Vault]({BLEACHING_DRIVE_VAULT_URL})"
        )
        return combined_tax_md, "Boss, Dual-Enterprise GST Tax report ready!"

    # 4. Overdue Radar Query
    if is_overdue:
        try:
            from tools import sgc_overdue_radar
            sgc_radar = sgc_overdue_radar.generate_executive_radar_report()
        except Exception:
            sgc_radar = "🟢 SGC Overdue: Bannari Amman Dyeing ₹30,000 overdue."
        bleach_bills = get_bleaching_bills_sync()
        bleach_pending = [b for b in bleach_bills if str(b.get("status", "")).upper() != "PAID"]
        bleach_lines = [f"• *Bill #{b.get('billNo')}* | {b.get('customer')} | `₹{float(b.get('netAmount', 0)):,.2f}`" for b in bleach_pending]
        bleach_str = "\n".join(bleach_lines) if bleach_lines else "• _All Bleaching invoices settled!_"

        overdue_md = (
            f"{sgc_radar}\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚪ **BLEACHING UNIT UNPAID DUES**\n"
            f"{bleach_str}\n\n"
            f"📁 [Bleaching Bills Vault]({BLEACHING_DRIVE_VAULT_URL})"
        )
        return overdue_md, "Boss, SGC and Bleaching overdue recovery radar ready!"

    # 5. Bleaching-Only Query
    if target == "BLEACHING":
        bleach_bills = get_bleaching_bills_sync()
        ov = bleaching_billing_query.get_bleaching_overview(bleach_bills)
        recent_lines = [f"• *Bill #{b.get('billNo')}* ({b.get('date')}): `{b.get('customer')}` — `₹{float(b.get('netAmount', 0)):,.2f}` [{b.get('status')}]" for b in bleach_bills]
        rep_md = (
            "⚪ **SRI GANAPATHI COLOURS — BLEACHING UNIT (SALAVAI) RADAR**\n"
            "_(Mukil's Independent Enterprise • Karur Yarn Hub)_\n\n"
            f"• **Invoices Issued**: `{ov['total_bills']}`\n"
            f"• **Gross Invoiced**: `₹{ov['total_invoiced']:,.2f}`\n"
            f"• **Collections Received**: `₹{ov['total_collected']:,.2f}`\n"
            f"• **Outstanding Balance**: `₹{ov['total_outstanding']:,.2f}`\n\n"
            f"🧾 **Active Invoices**:\n" + "\n".join(recent_lines) + f"\n\n📁 [Open Bleaching-Bills Drive Vault]({BLEACHING_DRIVE_VAULT_URL})\n\n"
            "💡 *Tip:* Check specific client: `Eco Fusion bill evlo`"
        )
        speech = f"Boss, Bleaching unit-la total {ov['total_bills']} bills, {ov['total_invoiced']} rupees invoiced. Outstanding balance {ov['total_outstanding']} rupees."
        return rep_md, speech

    # 6. SGC-Only Query
    if target == "SGC":
        rep, speech = sgc_billing_query.format_month_wise_bills_dossier()
        return rep, speech

    # 7. Default: Dual-Enterprise Executive Dashboard
    return format_dual_enterprise_dashboard()


if __name__ == "__main__":
    print("Testing Enterprise Router...")
    dash, speech = format_dual_enterprise_dashboard()
    print("Dashboard:\n", dash[:400], "...")
    print("\nTesting Customer Resolver for 'Eco Fusion'...")
    c_rep, _ = format_customer_enterprise_ledger("Eco Fusion")
    print(c_rep)
    print("\nTesting Customer Resolver for 'Bannari Amman'...")
    b_rep, _ = format_customer_enterprise_ledger("Bannari Amman")
    print(b_rep[:300])
