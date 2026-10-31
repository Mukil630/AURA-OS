"""
BLEACHING ENTERPRISE - MODEL CONTEXT PROTOCOL (MCP) SERVER
tools/bleaching_mcp_server.py

Authoritative Financial & Industrial Operations MCP Server for Mukil's Independent Bleaching Enterprise.
Zero Cross-Contamination with SGC Dyeing Data.
Powered by Turso Cloud Edge SQLite & Local AppData.
"""

import sys
import os
import json
import warnings
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

warnings.filterwarnings("ignore")

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

JARVIS_CORE_DIR = Path(__file__).resolve().parent.parent
if str(JARVIS_CORE_DIR) not in sys.path:
    sys.path.insert(0, str(JARVIS_CORE_DIR))

from mcp.server.fastmcp import FastMCP
from tools.bleaching_billing_query import (
    load_local_bills,
    query_turso_bills,
    get_bleaching_overview,
    get_bleaching_ledger_for_customer,
    HAS_TURSO
)

mcp = FastMCP(
    "bleaching-mcp",
    instructions="Authoritative Financial & Operations Server for Mukil's Independent Bleaching Enterprise."
)

@mcp.tool()
async def bleaching_get_financial_overview() -> str:
    """
    Retrieves authoritative financial metrics for Mukil's Bleaching Enterprise.
    Returns Total Bills, Gross Invoiced, Total Collected, and Outstanding Receivables from Turso Cloud.
    """
    bills = await query_turso_bills()
    if not bills:
        bills, _ = load_local_bills()

    metrics = get_bleaching_overview(bills)
    return json.dumps({
        "enterprise": "Bleaching Unit (Salavai Unit - Mukil's Venture)",
        "source": "Turso Cloud (AWS Mumbai)" if HAS_TURSO else "Local AppData",
        "data": metrics,
        "timestamp": datetime.now().isoformat()
    }, indent=2)

@mcp.tool()
async def bleaching_list_invoices(status: Optional[str] = None, limit: int = 20) -> str:
    """
    Lists recent Bleaching invoices with status, customer name, date, subtotal, and net amount.
    Filter by status ('PENDING' or 'PAID').
    """
    bills = await query_turso_bills()
    if not bills:
        bills, _ = load_local_bills()

    if status:
        st_upper = status.upper().strip()
        bills = [b for b in bills if str(b.get("status", "") or b.get("payment_status", "")).upper() == st_upper]

    return json.dumps({
        "total_returned": len(bills[:limit]),
        "invoices": bills[:limit]
    }, indent=2)

@mcp.tool()
async def bleaching_get_customer_ledger(customer_name: str) -> str:
    """
    Retrieves complete statement and outstanding balance for a specific bleaching customer.
    Example customer: 'Eco Fusion', 'Unity Exports', 'AMSA EXPORTS'.
    """
    bills = await query_turso_bills()
    if not bills:
        bills, _ = load_local_bills()

    ledger = get_bleaching_ledger_for_customer(bills, customer_name)
    return json.dumps(ledger, indent=2)

if __name__ == "__main__":
    mcp.run()
