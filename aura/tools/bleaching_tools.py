"""
AURA OS Bleaching Unit & Daily P&L Ledger Tools
Automates logging production and daily expenses directly into the live Google Sheet & local Excel ledger.
"""
import os
import sys
from typing import Dict, Any, Optional

# Ensure tools can be found
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tools.bleaching_ledger_tool import (
    record_production,
    record_expense,
    get_daily_summary,
    GOOGLE_SHEET_URL
)


def record_bleaching_production(
    customer: str,
    material: str,
    kgs: float,
    rate_per_kg: float,
    dc_no: str = "AUTO-DC"
) -> str:
    """
    Records a bleaching production batch, calculates total revenue, and updates the live Google Sheet.
    Example: customer='Sowbhagiya', material='30s Grey Yarn', kgs=1500, rate_per_kg=12.0
    """
    res = record_production(customer, material, kgs, rate_per_kg, dc_no)
    return (
        f"✅ Production Recorded:\n"
        f"• Batch: {res['batch_no']}\n"
        f"• Customer: {customer}\n"
        f"• Weight: {kgs} KGs @ ₹{rate_per_kg}/kg\n"
        f"• Total Revenue: ₹{res['total_revenue']:,.2f}\n"
        f"• Live Google Sheet: {GOOGLE_SHEET_URL}"
    )


def record_bleaching_expense(
    category: str,
    item: str,
    vendor: str,
    amount: float,
    payment_mode: str = "UPI"
) -> str:
    """
    Records an expense (Chemicals, Power/EB, Labour, Maintenance, Misc) and updates the live Google Sheet.
    Example: category='Chemicals', item='H2O2 Hydrogen Peroxide 50%', vendor='Lakshmi Chem', amount=4500
    """
    res = record_expense(category, item, vendor, amount, payment_mode=payment_mode)
    return (
        f"✅ Expense Logged:\n"
        f"• Category: {category}\n"
        f"• Item: {item} ({vendor})\n"
        f"• Amount: ₹{amount:,.2f} ({payment_mode})\n"
        f"• Live Google Sheet: {GOOGLE_SHEET_URL}"
    )


def get_bleaching_daily_summary(date_str: str = "") -> str:
    """
    Gets the daily Profit & Loss (P&L) summary for today (or specified date YYYY-MM-DD).
    Returns total KGs processed, gross revenue, category expenses, and net daily profit.
    """
    summary = get_daily_summary(date_str if date_str else None)
    if summary.get("message"):
        return f"📊 Bleaching Summary ({summary['date']}): {summary['message']}\nLive Sheet: {GOOGLE_SHEET_URL}"

    return (
        f"📊 Sri Ganapathi Colours - Bleaching Unit Daily P&L ({summary['date']})\n"
        f"────────────────────────\n"
        f"🏭 Total KGs Bleached: {summary['total_kgs']:,.1f} KGs\n"
        f"💵 Gross Revenue: ₹{summary['gross_revenue']:,.2f}\n"
        f"────────────────────────\n"
        f"📉 Daily Expenses Breakdown:\n"
        f"  • Chemicals (H2O2, Caustic, etc.): ₹{summary['chemicals_cost']:,.2f}\n"
        f"  • Electricity (TNEB Power): ₹{summary['power_eb']:,.2f}\n"
        f"  • Labour / Wages: ₹{summary['labour_wages']:,.2f}\n"
        f"  • Maintenance & Misc: ₹{summary['maintenance_misc']:,.2f}\n"
        f"  • Total Expenses: ₹{summary['total_expenses']:,.2f}\n"
        f"────────────────────────\n"
        f"💰 NET DAILY PROFIT: ₹{summary['net_profit']:,.2f} (Margin: {summary['profit_margin']})\n"
        f"📱 Live Google Sheet Link: {GOOGLE_SHEET_URL}"
    )


def get_bleaching_sheet_link() -> str:
    """Returns the live Google Sheet URL for Mukil's Bleaching Unit Daily P&L Ledger."""
    return f"📱 SGC Bleaching Unit Master Google Sheet:\n{GOOGLE_SHEET_URL}"
