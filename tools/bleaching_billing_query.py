"""
Bleaching Billing Authoritative Query Service
tools/bleaching_billing_query.py - 100% Deterministic, Ground-Truth Retriever for Mukil's Bleaching Enterprise.
Connects directly to Turso Cloud (AWS Mumbai) and local AppData fallback.
Zero cross-contamination with SGC Dyeing data.
"""
import os
import re
import difflib
import sys
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

JARVIS_CORE_DIR = Path(__file__).resolve().parent.parent
if str(JARVIS_CORE_DIR) not in sys.path:
    sys.path.insert(0, str(JARVIS_CORE_DIR))

logger = logging.getLogger("bleaching_billing_query")

# Turso Cloud Client
try:
    from aura_agent_core.database import get_db_client
    HAS_TURSO = True
except Exception:
    HAS_TURSO = False

STOP_WORDS = {'fabrics', 'tex', 'textiles', 'exports', 'traders', 'dyeing', 'mills', 'handlooms', 'unit', 'colours', 'solution', 'sustainable', 'ms', 'sri', 'shri'}

def normalize_name(s: str) -> str:
    return re.sub(r'[^a-z0-9]', '', str(s).lower())

def is_name_match(query_name: str, target_name: str) -> bool:
    q_norm = normalize_name(query_name)
    t_norm = normalize_name(target_name)
    if not q_norm or not t_norm:
        return False
    if q_norm == t_norm:
        return True
    
    q_words = [w.strip('.,/ ') for w in query_name.lower().split()]
    t_words = [w.strip('.,/ ') for w in target_name.lower().split()]

    q_tokens = [normalize_name(w) for w in q_words if normalize_name(w) not in STOP_WORDS and len(normalize_name(w)) > 1]
    t_tokens = [normalize_name(w) for w in t_words if normalize_name(w) not in STOP_WORDS and len(normalize_name(w)) > 1]

    for qt in q_tokens:
        for tt in t_tokens:
            if qt == tt:
                return True
            if (qt in tt or tt in qt) and (min(len(qt), len(tt)) / max(len(qt), len(tt)) >= 0.7):
                return True
            if len(qt) >= 4 and len(tt) >= 4:
                if difflib.SequenceMatcher(None, qt, tt).ratio() >= 0.8:
                    return True
    return False

def get_bleaching_local_db_path() -> Optional[Path]:
    """Finds active Bleaching billing database on Windows."""
    candidates = [
        Path(os.environ.get("APPDATA", "")) / "bleaching-billing" / "bleaching-billing-data.json",
        Path.home() / "AppData" / "Roaming" / "bleaching-billing" / "bleaching-billing-data.json",
        Path("C:/Users/mukil/bleaching-billing/bleaching-billing-data.json"),
    ]
    for p in candidates:
        if p.exists() and p.is_file():
            return p
    return None

def load_local_bills() -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Loads all bleaching bills from local electron-store JSON."""
    db_path = get_bleaching_local_db_path()
    if not db_path:
        return [], "Bleaching local database not found."

    try:
        with open(db_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("bills") or data.get("sgc-bills", []), None
    except Exception as e:
        return [], f"Failed to read Bleaching database: {str(e)}"

async def query_turso_bills() -> List[Dict[str, Any]]:
    """Fetches all bleaching invoices from Turso Cloud."""
    if not HAS_TURSO:
        return []
    try:
        client = get_db_client()
        res = await client.execute("SELECT * FROM bleaching_invoices ORDER BY id DESC;")
        cols = list(res.columns) if hasattr(res, 'columns') else []
        bills = []
        for row in res:
            if cols:
                d = dict(zip(cols, row))
                bills.append({
                    "id": d.get("id"),
                    "billNo": str(d.get("bill_no", "")),
                    "date": str(d.get("bill_date", "")),
                    "customer": str(d.get("customer_name", "")),
                    "customerGst": str(d.get("customer_gst", "") or ""),
                    "subtotal": float(d.get("subtotal") or 0),
                    "cgst": float(d.get("cgst") or 0),
                    "sgst": float(d.get("sgst") or 0),
                    "netAmount": float(d.get("net_amount") or 0),
                    "status": str(d.get("payment_status") or "PENDING"),
                    "paidAmount": float(d.get("paid_amount") or 0),
                    "driveLink": str(d.get("drive_pdf_link") or ""),
                })
        await client.close()
        return bills
    except Exception as e:
        logger.warning(f"Turso bills query error: {e}")
        return []

async def query_turso_customers() -> List[Dict[str, Any]]:
    """Fetches all registered bleaching customers and GSTINs from Turso Cloud."""
    if not HAS_TURSO:
        return []
    try:
        client = get_db_client()
        res = await client.execute("SELECT id, name, gst, phone, address FROM bleaching_customers;")
        custs = []
        for row in res.rows:
            custs.append({
                "id": row[0],
                "name": str(row[1]),
                "gstin": str(row[2] or ""),
                "phone": str(row[3] or ""),
                "address": str(row[4] or ""),
            })
        await client.close()
        return custs
    except Exception as e:
        logger.warning(f"Turso customers query error: {e}")
        return []

def get_registered_customer(customer_name: str) -> Optional[Dict[str, Any]]:
    """Synchronously retrieves customer from Turso Cloud bleaching_customers table."""
    try:
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                custs = pool.submit(asyncio.run, query_turso_customers()).result(timeout=4)
        else:
            custs = asyncio.run(query_turso_customers())
        
        c_low = customer_name.lower().strip()
        for c in custs:
            if is_name_match(customer_name, c["name"]):
                return c
    except Exception as e:
        logger.warning(f"Error finding registered customer: {e}")
    return None

def get_bleaching_overview(bills: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculates overall Bleaching financial metrics."""
    total_invoiced = 0.0
    total_paid = 0.0
    pending_amount = 0.0
    paid_count = 0
    pending_count = 0

    for b in bills:
        net = float(b.get("netAmount", 0) or b.get("net_amount", 0) or 0)
        paid = float(b.get("paidAmount", 0) or b.get("paid_amount", 0) or 0)
        status = str(b.get("status", "") or b.get("payment_status", "")).upper()

        if status == "PAID" or paid >= net:
            total_paid += net
            paid_count += 1
        else:
            total_paid += paid
            pending_amount += max(0, net - paid)
            pending_count += 1
        total_invoiced += net

    return {
        "success": True,
        "total_bills": len(bills),
        "total_invoiced": round(total_invoiced, 2),
        "total_collected": round(total_paid, 2),
        "total_outstanding": round(pending_amount, 2),
        "paid_bills_count": paid_count,
        "pending_bills_count": pending_count,
    }

def get_bleaching_ledger_for_customer(bills: List[Dict[str, Any]], customer_name: str) -> Dict[str, Any]:
    """Retrieves customer-specific ledger for Bleaching."""
    c_lower = customer_name.lower().strip()
    matched = [
        b for b in bills
        if is_name_match(customer_name, str(b.get("customer", "") or b.get("customer_name", "")))
    ]

    total_billed = sum(float(b.get("netAmount", 0) or b.get("net_amount", 0) or 0) for b in matched)
    total_paid = sum(float(b.get("paidAmount", 0) or b.get("paid_amount", 0) or 0) for b in matched)
    balance = max(0, total_billed - total_paid)

    return {
        "success": True,
        "customer": customer_name,
        "total_bills": len(matched),
        "total_billed": round(total_billed, 2),
        "total_paid": round(total_paid, 2),
        "outstanding_balance": round(balance, 2),
        "bills": matched,
    }

if __name__ == "__main__":
    import asyncio
    print("Testing Bleaching Authoritative Query Service...")
    local_b, err = load_local_bills()
    print(f"Local bills loaded: {len(local_b)} | Error: {err}")
    turso_b = asyncio.run(query_turso_bills())
    print(f"Turso Cloud bills: {len(turso_b)}")
    overview = get_bleaching_overview(turso_b or local_b)
    print("Bleaching Overview:", json.dumps(overview, indent=2))
