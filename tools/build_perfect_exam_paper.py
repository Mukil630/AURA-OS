# -*- coding: utf-8 -*-
"""
Generate 100% Pure Professional Tamil Economics Test Question Paper:
- A & B options on top (side-by-side)
- C & D options below that (side-by-side)
- NO Tanglish / NO unnecessary English brackets
- NO textbook reference tags
- NO answers or explanations
- Completely offline (NO Google Drive storage)
- Sends directly to Mukil's Telegram bot
"""

import os
import sys
import re
import requests
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
import win32com.client
import pymupdf

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

KEEP_ACRONYMS = {
    'GDP', 'MSME', 'GNP', 'NNP', 'G20', 'PMKSY', 'MGNREGA', 'NITI', 
    'CBDT', 'MRTP', 'APMC', 'RBI', 'LAF', 'D-SIBs', 'CRR', 'SEBI', 
    'SIDBI', 'IRDAI', 'NABARD', 'FCI', 'IDBI', 'EXIM', 'IRDP', 
    'NRY', 'NSAP', 'JGSY', 'SGSY', 'SFDA', 'JRY', 'IAY', 'MoSPI', 'GST'
}

def clean_tamil_text(text):
    """Strips unnecessary English words while preserving valid acronyms and Tamil content."""
    if not text:
        return ""
    def repl(m):
        content = m.group(1).strip()
        if content in KEEP_ACRONYMS:
            return f" ({content})"
        # If it contains Tamil or numbers only (e.g. '(1)', '(A)'), preserve
        if any('\u0b80' <= c <= '\u0bff' for c in content) or content.isdigit():
            return f" ({content})"
        return ""
    cleaned = re.sub(r'\s*\(([A-Za-z0-9\s\-\/\'\,\.]+)\)', repl, text)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned

def set_table_no_borders(table):
    tblPr = table._tbl.tblPr
    tblBorders = OxmlElement('w:tblBorders')
    for b in ['top', 'left', 'bottom', 'right', 'insideH', 'insideV']:
        node = OxmlElement(f'w:{b}')
        node.set(qn('w:val'), 'none')
        tblBorders.append(node)
    tblPr.append(tblBorders)

def set_cell_margins(cell, top=20, bottom=20, left=40, right=40):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        node = OxmlElement(f'w:{m}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)

def extract_questions():
    with open(r"C:\Users\mukil\Desktop\build_test5_doc.py", "r", encoding="utf-8") as f:
        code = f.read()
    
    start_idx = code.find("questions = [")
    end_idx = code.find("    # Filter questions", start_idx)
    if end_idx == -1:
        end_idx = code.find("    # --- Add Questions to Document ---", start_idx)
    
    q_code = code[start_idx:end_idx].strip()
    local_env = {}
    exec(q_code, {}, local_env)
    return local_env["questions"]

def generate_paper(docx_path, pdf_path):
    raw_questions = extract_questions()
    print(f"Loaded {len(raw_questions)} questions.")

    doc = docx.Document()

    # A4 margins (0.7 in)
    for section in doc.sections:
        section.top_margin = Inches(0.7)
        section.bottom_margin = Inches(0.7)
        section.left_margin = Inches(0.7)
        section.right_margin = Inches(0.7)
        section.page_width = Inches(8.27)
        section.page_height = Inches(11.69)

    style = doc.styles['Normal']
    font = style.font
    font.name = 'Nirmala UI'
    font.size = Pt(10.5)
    font.color.rgb = RGBColor(0x11, 0x18, 0x27)

    # Title
    title_p = doc.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_p.paragraph_format.space_before = Pt(0)
    title_p.paragraph_format.space_after = Pt(2)
    t_run = title_p.add_run("பொருளாதாரம் மாதிரித் தேர்வு – 5")
    t_run.font.name = 'Nirmala UI'
    t_run.font.size = Pt(16)
    t_run.font.bold = True
    t_run.font.color.rgb = RGBColor(0x1A, 0x36, 0x5D)

    sub_p = doc.add_paragraph()
    sub_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub_p.paragraph_format.space_after = Pt(6)
    s_run = sub_p.add_run("நேரம்: 1 மணி 30 நிமிடம்          |          மொத்த வினாக்கள்: 75          |          மதிப்பெண்கள்: 75")
    s_run.font.name = 'Nirmala UI'
    s_run.font.size = Pt(10)
    s_run.font.bold = True
    s_run.font.color.rgb = RGBColor(0x4A, 0x55, 0x68)

    div_p = doc.add_paragraph()
    div_p.paragraph_format.space_after = Pt(10)
    div_run = div_p.add_run("―" * 60)
    div_run.font.color.rgb = RGBColor(0xCB, 0xD5, 0xE0)

    col_width = Inches(3.4)

    for item in raw_questions:
        q_text_clean = clean_tamil_text(item['q'])

        qp = doc.add_paragraph()
        qp.paragraph_format.space_before = Pt(6)
        qp.paragraph_format.space_after = Pt(3)
        qp.paragraph_format.line_spacing = 1.15

        q_num = qp.add_run(f"{item['num']}. ")
        q_num.font.name = 'Nirmala UI'
        q_num.font.size = Pt(10.5)
        q_num.font.bold = True

        q_txt = qp.add_run(q_text_clean)
        q_txt.font.name = 'Nirmala UI'
        q_txt.font.size = Pt(10.5)
        q_txt.font.bold = True

        # Clean 4 options
        opts = [clean_tamil_text(o) for o in item.get('options', [])]
        opt_a = opts[0] if len(opts) > 0 else ""
        opt_b = opts[1] if len(opts) > 1 else ""
        opt_c = opts[2] if len(opts) > 2 else ""
        opt_d = opts[3] if len(opts) > 3 else ""

        # Layout:
        # Row 1 (Mela):   A) ...   |   B) ...
        # Row 2 (Keela):  C) ...   |   D) ...
        table = doc.add_table(rows=2, cols=2)
        set_table_no_borders(table)

        row1 = table.rows[0]
        c_a, c_b = row1.cells[0], row1.cells[1]
        c_a.width = col_width
        c_b.width = col_width
        set_cell_margins(c_a, top=15, bottom=15, left=30, right=30)
        set_cell_margins(c_b, top=15, bottom=15, left=30, right=30)

        p_a = c_a.paragraphs[0]
        p_a.paragraph_format.space_before = Pt(0)
        p_a.paragraph_format.space_after = Pt(2)
        r_a = p_a.add_run(opt_a)
        r_a.font.name = 'Nirmala UI'
        r_a.font.size = Pt(10)

        p_b = c_b.paragraphs[0]
        p_b.paragraph_format.space_before = Pt(0)
        p_b.paragraph_format.space_after = Pt(2)
        r_b = p_b.add_run(opt_b)
        r_b.font.name = 'Nirmala UI'
        r_b.font.size = Pt(10)

        row2 = table.rows[1]
        c_c, c_d = row2.cells[0], row2.cells[1]
        c_c.width = col_width
        c_d.width = col_width
        set_cell_margins(c_c, top=15, bottom=15, left=30, right=30)
        set_cell_margins(c_d, top=15, bottom=15, left=30, right=30)

        p_c = c_c.paragraphs[0]
        p_c.paragraph_format.space_before = Pt(0)
        p_c.paragraph_format.space_after = Pt(4)
        r_c = p_c.add_run(opt_c)
        r_c.font.name = 'Nirmala UI'
        r_c.font.size = Pt(10)

        p_d = c_d.paragraphs[0]
        p_d.paragraph_format.space_before = Pt(0)
        p_d.paragraph_format.space_after = Pt(4)
        r_d = p_d.add_run(opt_d)
        r_d.font.name = 'Nirmala UI'
        r_d.font.size = Pt(10)

    doc.save(docx_path)
    print(f"[OK] Saved DOCX: {docx_path}")

    # Convert to PDF
    print("Converting to PDF via Word COM...")
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
        doc_obj.SaveAs(os.path.abspath(pdf_path), FileFormat=17)
        doc_obj.Close(False)
        print(f"[OK] Saved PDF: {pdf_path} ({os.path.getsize(pdf_path):,} bytes)")
    finally:
        word.Quit()

def dispatch_to_telegram(pdf_path):
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    CHAT_ID = "6233907249"

    caption = (
        "📝 <b>பொருளாதாரம் மாதிரித் தேர்வு – 5 (மாதிரி வினாத்தாள்)</b>\n\n"
        "• <b>விருப்பங்கள் வடிவமைப்பு</b>:\n"
        "  A) ...                    B) ...  (மேலே)\n"
        "  C) ...                    D) ...  (கீழே)\n\n"
        "• <b>மொத்த வினாக்கள்</b>: 75\n"
        "• <b>நேரம்</b>: 1 மணி 30 நிமிடம் | <b>மதிப்பெண்கள்</b>: 75\n"
        "• <b>சிறப்பம்சம்</b>: தூய தமிழ் வடிவம், விடைக்குறிப்புகள் எதுவுமின்றி மாதிரித் தேர்வு எழுதும் நோக்கத்திற்காகத் தயார் செய்யப்பட்டது.\n\n"
        "வாழ்த்துகள் முகில்!"
    )

    print("Dispatching to Telegram...")
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

    generate_paper(docx_file, pdf_file)
    dispatch_to_telegram(pdf_file)

    # Render page 1 preview to verify
    doc_m = pymupdf.open(pdf_file)
    doc_m[0].get_pixmap(dpi=150).save(os.path.join(desktop, "Economics_Test_5_Clean_Preview.png"))
    print("Preview image saved at Desktop/Economics_Test_5_Clean_Preview.png")
    print("All tasks finished successfully. ZERO files on Google Drive.")
