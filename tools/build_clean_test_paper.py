# -*- coding: utf-8 -*-
"""
Generate clean, minimal Question Paper exactly as in the original PDF:
- NO metadata tables
- NO book references or tags ([12th ECO...], etc.)
- NO answers, NO explanations
- Just pure numbered questions and 4 options (A, B, C, D)
- NO Google Drive upload (Drive storage completely disabled as per user instruction)
- Output clean DOCX and PDF on Desktop, and dispatch directly to Mukil's Telegram
"""

import os
import sys
import requests
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
import win32com.client

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Import questions list from build_test5_doc
sys.path.insert(0, r"C:\Users\mukil\Desktop")
from build_test5_doc import create_test5_document

# Let's inspect the questions from build_test5_doc. We can write a dedicated clean generator
# that reads the questions list directly from the python file.
import inspect

def extract_questions():
    # Load questions directly
    with open(r"C:\Users\mukil\Desktop\build_test5_doc.py", "r", encoding="utf-8") as f:
        code = f.read()
    
    # Extract the questions list definition
    start_idx = code.find("questions = [")
    end_idx = code.find("    # Filter questions", start_idx)
    if end_idx == -1:
        end_idx = code.find("    # --- Add Questions to Document ---", start_idx)
    
    q_code = code[start_idx:end_idx].strip()
    local_env = {}
    exec(q_code, {}, local_env)
    return local_env["questions"]

def create_clean_question_paper(docx_path, pdf_path):
    questions = extract_questions()
    print(f"Loaded {len(questions)} questions.")

    doc = docx.Document()

    # Set Margins (0.75 in)
    for section in doc.sections:
        section.top_margin = Inches(0.75)
        section.bottom_margin = Inches(0.75)
        section.left_margin = Inches(0.75)
        section.right_margin = Inches(0.75)
        section.page_width = Inches(8.27)  # A4
        section.page_height = Inches(11.69)

    # Style
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Nirmala UI'
    font.size = Pt(10.5)
    font.color.rgb = RGBColor(0x00, 0x00, 0x00)

    # Header Title
    title_p = doc.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_p.paragraph_format.space_before = Pt(0)
    title_p.paragraph_format.space_after = Pt(2)
    t_run = title_p.add_run("பொருளாதாரம் (ECONOMICS) - மாதிரித் தேர்வு 5")
    t_run.font.name = 'Nirmala UI'
    t_run.font.size = Pt(16)
    t_run.font.bold = True
    t_run.font.color.rgb = RGBColor(0x1A, 0x36, 0x5D)

    # Simple Subtitle (Time & Marks)
    sub_p = doc.add_paragraph()
    sub_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub_p.paragraph_format.space_after = Pt(8)
    s_run = sub_p.add_run("நேரம்: 1 மணி 30 நிமிடம்    |    மொத்த வினாக்கள்: 75    |    மதிப்பெண்கள்: 75")
    s_run.font.name = 'Nirmala UI'
    s_run.font.size = Pt(10)
    s_run.font.bold = True
    s_run.font.color.rgb = RGBColor(0x4A, 0x55, 0x68)

    # Divider line
    div_p = doc.add_paragraph()
    div_p.paragraph_format.space_after = Pt(10)
    div_run = div_p.add_run("―" * 58)
    div_run.font.color.rgb = RGBColor(0xA0, 0xAE, 0xC0)

    # Render each question cleanly
    for item in questions:
        qp = doc.add_paragraph()
        qp.paragraph_format.space_before = Pt(6)
        qp.paragraph_format.space_after = Pt(3)
        qp.paragraph_format.line_spacing = 1.15

        # Pure Question Number + Text (NO reference tags)
        q_num = qp.add_run(f"{item['num']}. ")
        q_num.font.name = 'Nirmala UI'
        q_num.font.size = Pt(10.5)
        q_num.font.bold = True

        q_txt = qp.add_run(item['q'])
        q_txt.font.name = 'Nirmala UI'
        q_txt.font.size = Pt(10.5)
        q_txt.font.bold = True

        # Options
        for opt in item['options']:
            op = doc.add_paragraph()
            op.paragraph_format.left_indent = Inches(0.25)
            op.paragraph_format.space_before = Pt(1)
            op.paragraph_format.space_after = Pt(1)
            op_run = op.add_run(opt)
            op_run.font.name = 'Nirmala UI'
            op_run.font.size = Pt(10)

        # Space after last option
        op.paragraph_format.space_after = Pt(6)

    # Save docx
    doc.save(docx_path)
    print(f"[OK] Saved DOCX: {docx_path}")

    # Convert to PDF via Word COM
    print("Converting to PDF...")
    word = win32com.client.DispatchEx("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0
    try:
        if os.path.exists(pdf_path):
            try:
                os.remove(pdf_path)
            except Exception:
                pass
        doc_obj = word.Documents.Open(os.path.abspath(docx_path))
        doc_obj.SaveAs(os.path.abspath(pdf_path), FileFormat=17) # 17 = wdFormatPDF
        doc_obj.Close(False)
        print(f"[OK] Saved PDF: {pdf_path} ({os.path.getsize(pdf_path):,} bytes)")
    finally:
        word.Quit()

def send_to_telegram(pdf_path):
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    CHAT_ID = "6233907249"

    caption = (
        "📝 <b>பொருளாதாரம் - மாதிரித் தேர்வு 5 (வினாத்தாள்)</b>\n\n"
        "• <b>மொத்த வினாக்கள்</b>: 75\n"
        "• <b>அமைப்பு</b>: Original PDF-ல் இருந்தது போன்ற சுத்தமான வடிவம் (No extra details, no answers, no book tags).\n\n"
        "🎯 <i>டெஸ்ட் எழுத ரெடியா இருக்கு மாப்ள!</i>"
    )

    print("Dispatching clean question paper to Telegram...")
    with open(pdf_path, "rb") as f:
        r = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendDocument",
            data={"chat_id": CHAT_ID, "caption": caption, "parse_mode": "HTML"},
            files={"document": ("Economics_Test_5_Question_Paper.pdf", f, "application/pdf")},
            timeout=60
        )
        print("[OK] Telegram status:", r.status_code, r.json().get("ok"))

if __name__ == "__main__":
    desktop = r"C:\Users\mukil\Desktop"
    docx_file = os.path.join(desktop, "Economics_Test_5_Question_Paper.docx")
    pdf_file = os.path.join(desktop, "Economics_Test_5_Question_Paper.pdf")

    create_clean_question_paper(docx_file, pdf_file)
    send_to_telegram(pdf_file)
    print("\nAll done! NO Drive upload performed.")
