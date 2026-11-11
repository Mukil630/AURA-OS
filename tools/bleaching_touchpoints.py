import os
import sys
import logging
from datetime import datetime
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import TELEGRAM_BOT_TOKEN

logger = logging.getLogger("bleaching_touchpoints")
CHAT_ID = "6233907249"

def run_bleaching_morning_touchpoint() -> dict:
    """Dispatches the 08:00 AM Bleaching Attendance Poll & Morning Work Form."""
    today_str = datetime.now().strftime("%d-%b-%Y")
    
    # 1. Send Interactive Attendance Poll
    url_poll = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPoll"
    payload_poll = {
        "chat_id": CHAT_ID,
        "question": f"🏭 Bleaching Attendance ({today_str}) — Tick Present:",
        "options": [
            "Person 1 (Present)",
            "Person 2 (Present)",
            "Person 3 (Present)",
            "Person 4 (Present)",
            "Person 5 (Present)",
            "⚡ All 5 Present"
        ],
        "is_anonymous": False,
        "allows_multiple_answers": True
    }
    try:
        r1 = requests.post(url_poll, json=payload_poll, timeout=10)
        logger.info(f"Morning Attendance Poll sent: {r1.status_code}")
    except Exception as e:
        logger.error(f"Error sending morning poll: {e}")

    # 2. Send Kaalai Work Details Form
    url_msg = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    text_form = (
        f"🌅 <b>BLEACHING UNIT — KAALAI WORK FORM (08:00 AM)</b>\n"
        f"📅 <b>Date</b>: {today_str}\n\n"
        f"Mapla, mele ulla Poll-la aatkalai tick pannitu, indha <b>3 details</b>-ah mattum reply pannunga:\n\n"
        f"1️⃣ <b>Customer / Company</b>: (e.g. <i>Sri Balaji Knits</i>)\n"
        f"2️⃣ <b>Inward Kattu</b>: (e.g. <i>50</i>)\n"
        f"3️⃣ <b>Rate per Kattu</b>: (e.g. <i>150</i>)\n"
        f"4️⃣ <i>(Yaarachum leave-na reason, e.g. Person 3 fever)</i>\n\n"
        f"🔒 <i>Note: Salary (₹3,000) + Other expenses (₹2,000) = ₹5,000 total out-flow locked!</i>\n\n"
        f"👉 <b>Single line reply example</b>:\n"
        f"<code>Sri Balaji Knits, 50 kattu, 150 rate, Person 3 fever</code>\n\n"
        f"Neenga reply potta udaney Excel-la Kaalai slot fill aagidum! 🚀"
    )
    payload_msg = {
        "chat_id": CHAT_ID,
        "text": text_form,
        "parse_mode": "HTML"
    }
    try:
        r2 = requests.post(url_msg, json=payload_msg, timeout=10)
        logger.info(f"Morning Form sent: {r2.status_code}")
        return {"status": "SUCCESS", "poll_ok": r1.ok if 'r1' in locals() else False, "form_ok": r2.ok}
    except Exception as e:
        logger.error(f"Error sending morning form: {e}")
        return {"status": "ERROR", "error": str(e)}

def run_bleaching_night_touchpoint() -> dict:
    """Dispatches the 08:00 PM (20:00) Bleaching Night Closing Form."""
    today_str = datetime.now().strftime("%d-%b-%Y")
    url_msg = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    text_closing = (
        f"🌙 <b>BLEACHING UNIT — NIGHT CLOSING FORM (08:00 PM)</b>\n"
        f"📅 <b>Date</b>: {today_str}\n\n"
        f"Mapla, shift mudinjidha? Innaiki night evalavu Kattu mudinjadhu nu sollu:\n\n"
        f"👉 <b>Just reply with Completed Kattu count</b>:\n"
        f"<i>(Example: <code>48 kattu</code> illana <code>50</code>)</i>\n\n"
        f"🔒 <i>Fixed Outflow: Cooli (₹3,000) + Expenses (₹2,000) = ₹5,000 Auto-deducted!</i>\n\n"
        f"Neenga mudinja count sonna udaney Net Profit & Target status pottu Excel row complete pannidren! 🔥"
    )
    payload_msg = {
        "chat_id": CHAT_ID,
        "text": text_closing,
        "parse_mode": "HTML"
    }
    try:
        r = requests.post(url_msg, json=payload_msg, timeout=10)
        logger.info(f"Night Closing Form sent: {r.status_code}")
        return {"status": "SUCCESS", "ok": r.ok}
    except Exception as e:
        logger.error(f"Error sending night closing form: {e}")
        return {"status": "ERROR", "error": str(e)}
