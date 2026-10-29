import requests
import datetime
import time

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = "6233907249"

text = (
    "🚨 <b>MUKIL MAAPLA! 12:05 PM REMINDER ALERT!</b> ⏰\n\n"
    "✅ <b>Live Test Verification Successful!</b>\n"
    "Unga Telegram notification engine 100% supersonic speed-la work aagudhu! 🚀\n\n"
    "🕒 <b>Current Time</b>: 12:05 PM\n"
    "📌 <b>Target Task</b>: Evening 6:30 PM Accenture PAN Card Registration Reminder is confirmed active!"
)

url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

def send_alert():
    try:
        r = requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}, timeout=10)
        print("Test 12:05 alert delivered:", r.status_code)
    except Exception as e:
        print("Error sending test alert:", e)

if __name__ == "__main__":
    send_alert()
