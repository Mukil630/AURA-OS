import requests
import datetime

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = "6233907249"

text = (
    "🚨 <b>MUKIL MAAPLA! 12:20 PM LIVE REMINDER ALERT!</b> ⏰\n\n"
    "🎯 <b>Test Status</b>: 100% PRECISE ON-TIME DELIVERY!\n"
    "🕒 <b>Trigger Time</b>: 12:20 PM IST\n\n"
    "📌 <b>Target Task Today</b>: Evening 6:30 PM Accenture Backend Engineer Application Submit Pannu\n"
    "📄 <b>Resume on Desktop</b>: <code>C:\\Users\\mukil\\Desktop\\MUKILARASU_S_RESUME.pdf</code>\n\n"
    "<i>JARVIS Dual-Brain Reminder Engine is locked and ready for your command, Maapla! 🚀</i>"
)

url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

def send_alert():
    try:
        r = requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}, timeout=10)
        print(f"12:20 PM alert delivered: {r.status_code}")
    except Exception as e:
        print(f"Error sending 12:20 PM alert: {e}")

if __name__ == "__main__":
    send_alert()
