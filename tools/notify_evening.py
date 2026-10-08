import requests
import os

TELEGRAM_BOT_TOKEN = "8738700204:AAGfOluaOWUUp5HgZTN0ZXiwxbZrlDEituk"
CHAT_ID = "6233907249"
RESUME_PDF_PATH = r"C:\Users\mukil\Desktop\MUKILARASU_S_RESUME.pdf"

def send_rich_evening_reminder():
    # 1. Send Rich Card with Interactive Inline Buttons
    rich_text = (
        "👑 <b>AURA-OS | EXECUTIVE PARTNER REMINDER</b> ⏰\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚡ <b>Priority Alert</b>: <code>ACCENTURE BACKEND SPRINT</code>\n"
        "📍 <b>Role Target</b>: Associate Engineer – Backend (L12)\n"
        "🏢 <b>Job ID</b>: <code>R00357520</code> (Kochi)\n"
        "💰 <b>Package</b>: ₹4.6 LPA – ₹6.5 LPA\n\n"
        "📊 <b>Application Progress:</b>\n"
        "<code>[██████████████░░] 85% Completed</code>\n\n"
        "✅ 1. Profile Created (VSB IT, 7.9 CGPA)\n"
        "✅ 2. 1-Page ATS Resume Generated & Ready\n"
        "⏳ 3. <b>PAN Card Entry & Final Submit</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 <i>Tip: Click buttons below to launch portal or view your cloud resume directly on phone!</i>"
    )

    inline_keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "🚀 Open Accenture Portal",
                    "url": "https://www.accenture.com/in-en/careers/jobsearch?jk=Associate%20Software%20Engineer&sb=1"
                },
                {
                    "text": "☁️ Drive Master Resume",
                    "url": "https://drive.google.com/file/d/1TpyzV7OGEf-YQfGLUpusAI5cDDvF1kAJ/view?usp=drive_link"
                }
            ],
            [
                {
                    "text": "💼 Candidate Portal Login",
                    "url": "https://indiacampus.accenture.com/candidate/#/login/"
                }
            ]
        ]
    }

    url_msg = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": rich_text,
        "parse_mode": "HTML",
        "reply_markup": inline_keyboard
    }

    try:
        r1 = requests.post(url_msg, json=payload, timeout=10)
        print("Rich card sent:", r1.status_code)
    except Exception as e:
        print("Error sending rich message:", e)

    # 2. Also Send the actual Resume PDF Document directly to phone!
    if os.path.exists(RESUME_PDF_PATH):
        url_doc = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
        try:
            with open(RESUME_PDF_PATH, "rb") as f:
                r2 = requests.post(
                    url_doc,
                    data={
                        "chat_id": CHAT_ID,
                        "caption": "📄 <b>Mukilarasu S — Master 1-Page ATS Resume (PDF)</b>\n<i>Ready to download & upload directly from mobile!</i>",
                        "parse_mode": "HTML"
                    },
                    files={"document": ("MUKILARASU_S_RESUME.pdf", f, "application/pdf")},
                    timeout=15
                )
            print("Resume document sent:", r2.status_code)
        except Exception as e:
            print("Error sending PDF document:", e)

if __name__ == "__main__":
    send_rich_evening_reminder()
