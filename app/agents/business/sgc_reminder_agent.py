"""SGC Automated Customer Payment Reminder & Overdue Tracking Agent.
Handles overdue age calculation, bilingual (Tamil & English) reminder generation,
Drive invoice linking, WhatsApp URL crafting, and automated dispatch.
"""
import json
import logging
import os
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger("SGCReminderAgent")

SGC_ACTIVE_DRIVE_FOLDER_URL = "https://drive.google.com/drive/folders/11KMBP0HHa2AFl30zjL8-a_-BQk9MgWM9?usp=drive_link"
SGC_BILLING_DATA_PATH = os.path.join(os.environ.get("APPDATA", ""), "sgc-billing", "sgc-billing-data.json")
REMINDER_LOGS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "sgc_reminders_log.json")


class SGCReminderAgent:
    """
    Automated Financial Overdue Radar & WhatsApp Payment Reminder Engine for Sri Ganapathi Colours.
    """

    def __init__(self, data_path: Optional[str] = None):
        self.data_path = data_path or SGC_BILLING_DATA_PATH
        self._ensure_storage()

    def _ensure_storage(self) -> None:
        os.makedirs(os.path.dirname(REMINDER_LOGS_PATH), exist_ok=True)
        if not os.path.exists(REMINDER_LOGS_PATH):
            with open(REMINDER_LOGS_PATH, "w", encoding="utf-8") as f:
                json.dump([], f, indent=2)

    def load_billing_data(self) -> Dict[str, Any]:
        """Loads billing records from desktop appdata or fallback."""
        if os.path.exists(self.data_path):
            try:
                with open(self.data_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading SGC billing data: {e}")
        return {"sgc-bills": [], "drive-folder-id": "11KMBP0HHa2AFl30zjL8-a_-BQk9MgWM9"}

    def get_overdue_analysis(self) -> List[Dict[str, Any]]:
        """
        Analyzes all pending invoices, calculates days overdue since billing date,
        and groups total balance by customer.
        """
        data = self.load_billing_data()
        bills = data.get("sgc-bills", [])
        now_dt = datetime.now()

        customer_map: Dict[str, Dict[str, Any]] = {}

        for b in bills:
            if str(b.get("status", "")).lower() != "pending":
                continue

            cust = b.get("customer", "Unknown")
            b_no = b.get("billNo")
            date_str = b.get("date", "")
            amt = float(b.get("netAmount", 0))
            gst = b.get("partyGst", "")
            drive_url = b.get("driveUrl") or SGC_ACTIVE_DRIVE_FOLDER_URL

            # Calculate days elapsed
            days_elapsed = 0
            if date_str:
                try:
                    b_dt = datetime.strptime(date_str, "%Y-%m-%d")
                    days_elapsed = (now_dt - b_dt).days
                except Exception:
                    pass

            if cust not in customer_map:
                customer_map[cust] = {
                    "customer_name": cust,
                    "party_gst": gst,
                    "total_pending_balance": 0.0,
                    "bills": [],
                    "oldest_bill_days": 0,
                }

            customer_map[cust]["total_pending_balance"] += amt
            customer_map[cust]["oldest_bill_days"] = max(customer_map[cust]["oldest_bill_days"], days_elapsed)
            customer_map[cust]["bills"].append({
                "bill_no": b_no,
                "date": date_str,
                "amount": amt,
                "days_overdue": days_elapsed,
                "drive_url": drive_url,
            })

        # Convert to sorted list by highest overdue amount
        overdue_list = list(customer_map.values())
        overdue_list.sort(key=lambda x: x["total_pending_balance"], reverse=True)
        return overdue_list

    def generate_reminder_message(
        self,
        customer_name: str,
        language: str = "tamil",
        contact_phone: str = "9080030538",
    ) -> Dict[str, Any]:
        """
        Generates a respectful, highly professional payment reminder pitch in Tamil or English
        including exact invoice breakdown, total balance, and Google Drive PDF vault link.
        """
        overdue_customers = {c["customer_name"]: c for c in self.get_overdue_analysis()}
        cust_data = overdue_customers.get(customer_name)

        if not cust_data:
            # Fallback single generic reminder
            return {
                "customer_name": customer_name,
                "text": f"வணக்கம் {customer_name}, ஸ்ரீ கணபதி கலர்ஸ் (SGC) இலிருந்து. நிலுவையில் உள்ள பில் தொகையை சரிபார்த்து அனுப்புமாறு கேட்டுக்கொள்கிறோம்.",
                "whatsapp_url": "",
                "total_balance": 0.0,
            }

        total_bal = cust_data["total_pending_balance"]
        bills_summary_ta = []
        bills_summary_en = []

        for b in cust_data["bills"]:
            bills_summary_ta.append(f"• பில் #{b['bill_no']} (தேதி: {b['date']}) - ₹{b['amount']:,.2f}")
            bills_summary_en.append(f"• Bill #{b['bill_no']} (Date: {b['date']}) - Rs {b['amount']:,.2f}")

        bills_text_ta = "\n".join(bills_summary_ta)
        bills_text_en = "\n".join(bills_summary_en)

        # Tamil Template
        msg_tamil = (
            f"வணக்கம் {customer_name},\n\n"
            f"ஸ்ரீ கணபதி கலர்ஸ் (Sri Ganapathi Colours) நிறுவனத்திலிருந்து அன்புடன் நினைவூட்டுகிறோம்.\n\n"
            f"தங்களுடைய கணக்கில் பின்வரும் பில் தொகை(கள்) நிலுவையில் உள்ளன:\n"
            f"{bills_text_ta}\n\n"
            f"📌 *மொத்த நிலுவைத் தொகை: ₹{total_bal:,.2f}*\n\n"
            f"📄 *பில் PDF விவரங்கள் (Google Drive Vault):*\n"
            f"{SGC_ACTIVE_DRIVE_FOLDER_URL}\n\n"
            f"தயவுசெய்து கணக்கை சரிபார்த்து தொகையை அனுப்பிவைக்குமாறு அன்புடன் கேட்டுக்கொள்கிறோம்.\n\n"
            f"நன்றி,\n"
            f"ஸ்ரீ கணபதி கலர்ஸ் | தொடர்புக்கு: {contact_phone}"
        )

        # English Template
        msg_english = (
            f"Dear {customer_name},\n\n"
            f"Warm greetings from Sri Ganapathi Colours (SGC).\n\n"
            f"This is a gentle reminder regarding the pending invoice balance in your account:\n"
            f"{bills_text_en}\n\n"
            f"📌 *Total Pending Balance: Rs {total_bal:,.2f}*\n\n"
            f"📄 *View Invoices on Google Drive Vault:*\n"
            f"{SGC_ACTIVE_DRIVE_FOLDER_URL}\n\n"
            f"Kindly review and arrange for the settlement at your earliest convenience.\n\n"
            f"Thank you,\n"
            f"Sri Ganapathi Colours | Contact: {contact_phone}"
        )

        chosen_text = msg_tamil if language.lower() in ("tamil", "ta") else msg_english
        encoded_text = urllib.parse.quote_plus(chosen_text)
        wa_url = f"https://wa.me/?text={encoded_text}"

        return {
            "customer_name": customer_name,
            "total_balance": total_bal,
            "bills_count": len(cust_data["bills"]),
            "tamil_message": msg_tamil,
            "english_message": msg_english,
            "chosen_message": chosen_text,
            "whatsapp_share_url": wa_url,
            "drive_vault_url": SGC_ACTIVE_DRIVE_FOLDER_URL,
        }

    def generate_all_reminders_summary(self) -> str:
        """
        Generates an executive overview of all customer payment reminders ready for dispatch.
        """
        overdue_list = self.get_overdue_analysis()
        if not overdue_list:
            return "🎉 *Super Boss! Ella customer bills-um 100% Settled / Paid. Pending balance zero!*"

        total_pending = sum(c["total_pending_balance"] for c in overdue_list)
        lines = [
            "🧾 *SGC AUTOMATED CUSTOMER PAYMENT REMINDERS RADAR*\n",
            f"☁️ *Live Drive Vault*: [Open Bills Folder]({SGC_ACTIVE_DRIVE_FOLDER_URL})\n",
            f"💰 *Total Pending Overdue Collection*: `₹{total_pending:,.2f}` across {len(overdue_list)} Customers\n",
            "📋 *Customers Awaiting Payment Follow-Up*:"
        ]

        for idx, c in enumerate(overdue_list, 1):
            rem = self.generate_reminder_message(c["customer_name"], language="tamil")
            lines.append(
                f"{idx}. 🔴 *{c['customer_name']}*\n"
                f"   • Overdue Balance: *₹{c['total_pending_balance']:,.2f}* ({len(c['bills'])} Bills, Oldest: `{c['oldest_bill_days']} days ago`)\n"
                f"   • GST: `{c.get('party_gst') or 'N/A'}`\n"
                f"   • 💬 [1-Click WhatsApp Reminder Pitch]({rem['whatsapp_share_url']})"
            )

        lines.append(
            "\n🔒 *Stark Security Protocol*: To trigger live WhatsApp send on PC, confirm with: _'AURA Protocol Stark 55'_ or _'Send reminder to <Customer>'_."
        )
        return "\n".join(lines)

    def log_reminder_sent(
        self,
        customer_name: str,
        amount: float,
        channel: str = "WhatsApp",
        status: str = "DISPATCHED",
    ) -> Dict[str, Any]:
        """Logs a dispatched payment reminder into audit tracker."""
        records = []
        if os.path.exists(REMINDER_LOGS_PATH):
            try:
                with open(REMINDER_LOGS_PATH, "r", encoding="utf-8") as f:
                    records = json.load(f)
            except Exception:
                records = []

        rec = {
            "reminder_id": f"rem_{uuid4().hex[:8]}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "customer_name": customer_name,
            "amount": amount,
            "channel": channel,
            "status": status,
            "drive_vault": SGC_ACTIVE_DRIVE_FOLDER_URL,
        }
        records.insert(0, rec)
        with open(REMINDER_LOGS_PATH, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False)
        return rec
