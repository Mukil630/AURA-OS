# -*- coding: utf-8 -*-
"""
Generate Mock Test Question Paper (75 Questions without answers/explanations):
1. DOCX: Economics_Test_5_Question_Paper_Without_Answers.docx
2. PDF: Economics_Test_5_Question_Paper_Without_Answers.pdf
3. Send to Mukil's Telegram bot
4. Upload to Google Drive Master Vault
"""

import os
import sys
import requests
import win32com.client
from build_test5_doc import create_test5_document

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

desktop = r"C:\Users\mukil\Desktop"
docx_path = os.path.join(desktop, "Economics_Test_5_Question_Paper_Without_Answers.docx")
pdf_path = os.path.join(desktop, "Economics_Test_5_Question_Paper_Without_Answers.pdf")

print("=== 1. Generating DOCX (Without Answers) ===")
create_test5_document(
    output_path=docx_path,
    start_q=1,
    end_q=75,
    title_suffix="மாதிரி வினாத்தாள் (Question Paper Only)",
    show_answers=False
)
print("[OK] DOCX created:", docx_path)

print("\n=== 2. Converting DOCX to PDF via Word COM Automation ===")
word = win32com.client.DispatchEx("Word.Application")
word.Visible = False
word.DisplayAlerts = 0

wdFormatPDF = 17
try:
    if os.path.exists(pdf_path):
        try:
            os.remove(pdf_path)
        except Exception:
            pass
    doc = word.Documents.Open(os.path.abspath(docx_path))
    doc.SaveAs(os.path.abspath(pdf_path), FileFormat=wdFormatPDF)
    doc.Close(False)
    print(f"[OK] PDF created: {pdf_path} ({os.path.getsize(pdf_path):,} bytes)")
finally:
    word.Quit()

print("\n=== 3. Sending Question Paper PDF to Mukil's Telegram ===")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = "6233907249"

caption = (
    "📝 <b>பொருளாதாரம் மாதிரித் தேர்வு 5 - வினாத்தாள் (QUESTION PAPER)</b>\n\n"
    "• <b>மொத்த வினாக்கள்</b>: 75 வினாக்கள் (Q1 முதல் Q75 வரை)\n"
    "• <b>வடிவம்</b>: தேர்வு எழுதுவதற்காக விடைகள் நீக்கப்பட்ட மாதிரி வினாத்தாள் (Only Questions & 4 Options)\n"
    "• <b>நேரம்</b>: 1 மணி 30 நிமிடங்கள் | <b>மதிப்பெண்</b>: 75\n\n"
    "🎯 <i>தேர்வு எழுதி பயிற்சி செய்ய தயார்! All the best Boss!</i>"
)

with open(pdf_path, "rb") as f:
    r = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendDocument",
        data={"chat_id": CHAT_ID, "caption": caption, "parse_mode": "HTML"},
        files={"document": (os.path.basename(pdf_path), f, "application/pdf")},
        timeout=60
    )
    print("[OK] Telegram dispatch status:", r.status_code, r.json().get("ok"))

print("\n=== 4. Uploading to Google Drive Master Vault ===")
try:
    sys.path.insert(0, r"C:\Users\mukil\jarvis-core")
    from tools.sync_to_drive import get_drive_service, upload_file_to_vault
    from config import DRIVE_FOLDER_ID
    service = get_drive_service()
    if service:
        res = upload_file_to_vault(service, pdf_path, DRIVE_FOLDER_ID)
        if res:
            print("[OK] Google Drive Link:", res.get('webViewLink'))
except Exception as e:
    print("Drive upload error:", e)

print("\n=== ALL TASKS COMPLETED SUCCESSFULLY! ===")
