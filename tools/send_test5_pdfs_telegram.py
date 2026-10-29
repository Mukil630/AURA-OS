import os
import requests

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = "6233907249"

files_to_send = [
    {
        "path": r"C:\Users\mukil\Desktop\Economics_Test_5_Part1_Q1_to_Q30.pdf",
        "name": "Economics_Test_5_Part1_Q1_to_Q30.pdf",
        "caption": (
            "📄 <b>பொருளாதாரம் மாதிரித் தேர்வு 5 (பகுதி 1: வினாக்கள் 1 - 30)</b>\n\n"
            "• <b>மொத்த வினாக்கள்</b>: 30 (Q1 - Q30)\n"
            "• <b>உள்ளடக்கம்</b>: TNPSC பொருளியல் வினாக்கள், 4 ஆப்ஷன்கள், சரியான விடைக் குறிப்பு & புத்தக ஆதாரங்கள்\n\n"
            "✅ <i>JARVIS Prime Antigravity Delivery</i>"
        )
    },
    {
        "path": r"C:\Users\mukil\Desktop\Economics_Test_5_All_Q1_to_Q75.pdf",
        "name": "Economics_Test_5_All_Q1_to_Q75.pdf",
        "caption": (
            "📚 <b>பொருளாதாரம் மாதிரித் தேர்வு 5 (முழு மாதிரி வினாத்தாள்: வினாக்கள் 1 - 75)</b>\n\n"
            "• <b>மொத்த வினாக்கள்</b>: 75 முழு வினாக்கள் (Q1 - Q75)\n"
            "• <b>பாடத்திட்டம்</b>: சமச்சீர் 9-12 பொருளியல், PYQs, மத்திய பட்ஜெட் 2026-27 & நடப்பு நிகழ்வுகள்\n"
            "• <b>அம்சங்கள்</b>: முழுமையான விடைக் குறிப்புகள் மற்றும் விரிவான விளக்கங்கள்\n\n"
            "✅ <i>JARVIS Prime Antigravity Delivery</i>"
        )
    }
]

for item in files_to_send:
    p = item["path"]
    if not os.path.exists(p):
        print(f"Error: {p} not found")
        continue
    size_kb = os.path.getsize(p) // 1024
    print(f"Uploading {item['name']} ({size_kb} KB) to Telegram...")
    with open(p, "rb") as doc:
        f = {"document": (item["name"], doc, "application/pdf")}
        data = {
            "chat_id": CHAT_ID,
            "caption": item["caption"],
            "parse_mode": "HTML"
        }
        r = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendDocument", data=data, files=f, timeout=60)
        print("Response:", r.status_code, r.json().get("ok"))

print("Done!")
