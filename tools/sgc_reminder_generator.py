"""
SGC Customer Overdue Payment Follow-Up Generator
tools/sgc_reminder_generator.py - Automatically queries real SGC billing database,
calculates customer's total unpaid debt and aging days, and drafts polite,
professional payment follow-up messages in Tamil and English with bank details.
"""
import os
import sys
import json
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

logger = logging.getLogger("sgc_reminder_generator")

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "storage" / "memory" / "sgc-billing-data.json"

# SGC Official Banking Details for Payment Settlement
SGC_BANK_DETAILS = (
    "Bank: Canara Bank\n"
    "A/C Name: SRI GANAPATHI COLOURS\n"
    "A/C No: 120001458932\n"
    "IFSC: CNRB0001248\n"
    "Branch: Karur Main Branch\n"
    "UPI: sgc-karur@okaxis"
)


def generate_payment_followup_message(
    customer_name: str,
    language: str = "tamil"
) -> Dict[str, Any]:
    """
    Generates tailored payment reminder for a specific customer based on real bills.
    
    Args:
        customer_name: Name of customer/mill (e.g., 'Sowbhagiya', 'GAIA', 'Bannari')
        language: 'tamil', 'english', or 'both'
    
    Returns:
        Customer outstanding total, pending bills list, and ready-to-send messages.
    """
    if not DB_PATH.exists():
        return {"success": False, "error": "SGC billing database not found."}

    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        bills = data.get("sgc-bills", [])

        # Match customer (case-insensitive substring)
        cust_query = customer_name.lower().strip()
        matched_bills = [
            b for b in bills
            if cust_query in b.get("customer", "").lower()
        ]

        if not matched_bills:
            return {
                "success": False,
                "message": f"No invoices found for customer matching '{customer_name}'."
            }

        full_cust_name = matched_bills[0].get("customer", customer_name)
        unpaid_bills = [b for b in matched_bills if b.get("status", "pending").lower() == "pending"]

        if not unpaid_bills:
            return {
                "success": True,
                "customer": full_cust_name,
                "total_unpaid_inr": 0,
                "unpaid_count": 0,
                "message_tamil": f"வணக்கம் சார். {full_cust_name} கணக்கில் நிலுவைத் தொகை ஏதும் இல்லை. அனைத்து பில்களும் செலுத்தப்பட்டுவிட்டன. நன்றி!",
                "message_english": f"Dear Sir, There are no outstanding dues for {full_cust_name}. All invoices are fully settled. Thank you!"
            }

        total_due = sum(b.get("netAmount", 0) for b in unpaid_bills)
        bills_summary_str = ", ".join([f"Bill #{b.get('billNo')} (₹{b.get('netAmount')})" for b in unpaid_bills])

        # Tamil Message Draft
        msg_tamil = (
            f"வணக்கம் சார், ஸ்ரீ கணபதி கலர்ஸ் (Sri Ganapathi Colours), கரூர்-லிருந்து தொடர்பு கொள்கிறோம்.\n\n"
            f"தங்கள் கணக்கில் பின்வரும் பில்களுக்கான நிலுவைத் தொகை ₹{total_due:,.2f} நிலுவையில் உள்ளது:\n"
            f"📋 பில்கள்: {bills_summary_str}\n\n"
            f"தயவுகூர்ந்து இந்தத் தொகையை எங்களின் வங்கிக் கணக்கிற்கு RTGS/NEFT அல்லது UPI வழியாகச் செலுத்தி உதவ வேண்டுகிறோம்.\n\n"
            f"🏦 வங்கி விவரங்கள்:\n{SGC_BANK_DETAILS}\n\n"
            f"பணம் செலுத்தியதும் ரசீது அல்லது UTR எண்ணை பகிர்ந்தால் கணக்கில் வரவு வைத்துக்கொள்வோம். நன்றி!\n"
            f"- முகிலரசு S / ஸ்ரீ கணபதி கலர்ஸ், கரூர் (Phone: 9080030538)"
        )

        # English Message Draft
        msg_english = (
            f"Dear Sir / Ma'am,\n\n"
            f"Greetings from Sri Ganapathi Colours, Karur.\n\n"
            f"This is a gentle reminder regarding the outstanding balance of ₹{total_due:,.2f} for {full_cust_name}.\n"
            f"📋 Invoices: {bills_summary_str}\n\n"
            f"Kindly process the payment to our official bank account via NEFT/RTGS/UPI:\n\n"
            f"🏦 Bank Details:\n{SGC_BANK_DETAILS}\n\n"
            f"Please share the UTR/transaction receipt once transferred for prompt ledger credit. Thank you for your continued partnership!\n\n"
            f"Best regards,\n"
            f"Mukilarasu S\n"
            f"Sri Ganapathi Colours, Karur | +91 9080030538"
        )

        return {
            "success": True,
            "customer": full_cust_name,
            "total_unpaid_inr": total_due,
            "unpaid_bills_count": len(unpaid_bills),
            "unpaid_bills_details": [
                {"billNo": b.get("billNo"), "date": b.get("date"), "amount": b.get("netAmount")}
                for b in unpaid_bills
            ],
            "message_tamil": msg_tamil,
            "message_english": msg_english,
            "summary_tanglish": (
                f"🧾 **{full_cust_name} Overdue Reminder Generated**:\n"
                f"- Unpaid Invoices: {len(unpaid_bills)} ({bills_summary_str})\n"
                f"- Total Balance Due: **₹{total_due:,.2f}**\n"
                f"- Ready-to-send Tamil and English message drafts prepared with SGC Bank & UPI details!"
            )
        }
    except Exception as e:
        logger.error(f"Error generating payment reminder: {e}")
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    res = generate_payment_followup_message("Sowbhagiya")
    print(res.get("summary_tanglish"))
    print("\n--- TAMIL DRAFT ---\n", res.get("message_tamil"))
