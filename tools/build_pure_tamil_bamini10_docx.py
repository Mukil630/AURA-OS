# -*- coding: utf-8 -*-
"""
Build 100% Pure Tamil Word Document (.docx) with Bamini 10pt font:
- EXACT SAME TAMIL LANGUAGE as the handwritten scan
- ZERO extra English translations in brackets (e.g. no '(Frictional Unemployment)', no '(Minimum Needs Programme)')
- True Unicode Tamil (no scrambled ASCII letters)
- Every single run tagged with Font: 'Bamini', Size: 10 pt
- 2x2 options layout: A & B on top, C & D below
- Direct Telegram dispatch to Mukil
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

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

desktop = r"C:\Users\mukil\Desktop"

KEEP_ACRONYMS = {
    'GDP', 'MSME', 'GNP', 'NNP', 'G20', 'PMKSY', 'MGNREGA', 'NITI', 
    'CBDT', 'MRTP', 'APMC', 'RBI', 'LAF', 'D-SIBs', 'CRR', 'SEBI', 
    'SIDBI', 'IRDAI', 'NABARD', 'FCI', 'IDBI', 'EXIM', 'IRDP', 
    'NRY', 'NSAP', 'JGSY', 'SGSY', 'SFDA', 'JRY', 'IAY', 'MoSPI', 'GST'
}

def clean_pure_tamil(text):
    """Removes added English translations in brackets, keeping only pure Tamil and real acronyms."""
    if not text:
        return ""
    def repl(m):
        content = m.group(1).strip()
        if content in KEEP_ACRONYMS:
            return f" ({content})"
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

def set_cell_margins(cell, top=10, bottom=10, left=20, right=20):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        node = OxmlElement(f'w:{m}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)

def apply_bamini_10(run, bold=False, size_pt=10, color_rgb=(17, 24, 39)):
    font_name = "Bamini"
    run.font.name = font_name
    run.font.size = Pt(size_pt)
    run.font.bold = bold
    run.font.color.rgb = RGBColor(*color_rgb)
    
    rPr = run._r.get_or_add_rPr()
    rFonts = rPr.find(qn('w:rFonts'))
    if rFonts is None:
        rFonts = OxmlElement('w:rFonts')
        rPr.append(rFonts)
    rFonts.set(qn('w:ascii'), font_name)
    rFonts.set(qn('w:hAnsi'), font_name)
    rFonts.set(qn('w:cs'), font_name)
    rFonts.set(qn('w:eastAsia'), font_name)

def extract_questions():
    with open(os.path.join(desktop, "build_test5_doc.py"), "r", encoding="utf-8") as f:
        code = f.read()
    start_idx = code.find("questions = [")
    end_idx = code.find("    # Filter questions", start_idx)
    if end_idx == -1:
        end_idx = code.find("    # --- Add Questions to Document ---", start_idx)
    q_code = code[start_idx:end_idx].strip()
    local_env = {}
    exec(q_code, {}, local_env)
    return local_env["questions"]

def generate_doc(output_path):
    raw_questions = extract_questions()
    print(f"Loaded {len(raw_questions)} questions.")

    doc = docx.Document()

    # Margins: 0.7 in
    for section in doc.sections:
        section.top_margin = Inches(0.7)
        section.bottom_margin = Inches(0.7)
        section.left_margin = Inches(0.7)
        section.right_margin = Inches(0.7)
        section.page_width = Inches(8.27)
        section.page_height = Inches(11.69)

    # Header
    title_p = doc.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_p.paragraph_format.space_before = Pt(0)
    title_p.paragraph_format.space_after = Pt(2)
    t_run = title_p.add_run("பொருளாதாரம் மாதிரித் தேர்வு – 5")
    apply_bamini_10(t_run, bold=True, size_pt=14, color_rgb=(26, 54, 93))

    sub_p = doc.add_paragraph()
    sub_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub_p.paragraph_format.space_after = Pt(6)
    s_run = sub_p.add_run("நேரம்: 1 மணி 30 நிமிடம்          |          மொத்த வினாக்கள்: 75          |          மதிப்பெண்கள்: 75")
    apply_bamini_10(s_run, bold=True, size_pt=9.5, color_rgb=(74, 85, 104))

    div_p = doc.add_paragraph()
    div_p.paragraph_format.space_after = Pt(8)
    div_run = div_p.add_run("―" * 60)
    apply_bamini_10(div_run, bold=False, size_pt=9, color_rgb=(203, 213, 224))

    col_width = Inches(3.4)

    for item in raw_questions:
        q_text = clean_pure_tamil(item['q'])

        qp = doc.add_paragraph()
        qp.paragraph_format.space_before = Pt(5)
        qp.paragraph_format.space_after = Pt(2)
        qp.paragraph_format.line_spacing = 1.15

        q_num = qp.add_run(f"{item['num']}. ")
        apply_bamini_10(q_num, bold=True, size_pt=10)

        q_txt = qp.add_run(q_text)
        apply_bamini_10(q_txt, bold=True, size_pt=10)

        # Options in pure Tamil
        opts = [clean_pure_tamil(o) for o in item.get('options', [])]
        opt_a = opts[0] if len(opts) > 0 else ""
        opt_b = opts[1] if len(opts) > 1 else ""
        opt_c = opts[2] if len(opts) > 2 else ""
        opt_d = opts[3] if len(opts) > 3 else ""

        table = doc.add_table(rows=2, cols=2)
        set_table_no_borders(table)

        row1 = table.rows[0]
        c_a, c_b = row1.cells[0], row1.cells[1]
        c_a.width = col_width
        c_b.width = col_width
        set_cell_margins(c_a, top=10, bottom=10, left=20, right=20)
        set_cell_margins(c_b, top=10, bottom=10, left=20, right=20)

        p_a = c_a.paragraphs[0]
        p_a.paragraph_format.space_before = Pt(0)
        p_a.paragraph_format.space_after = Pt(1)
        r_a = p_a.add_run(opt_a)
        apply_bamini_10(r_a, bold=False, size_pt=10)

        p_b = c_b.paragraphs[0]
        p_b.paragraph_format.space_before = Pt(0)
        p_b.paragraph_format.space_after = Pt(1)
        r_b = p_b.add_run(opt_b)
        apply_bamini_10(r_b, bold=False, size_pt=10)

        row2 = table.rows[1]
        c_c, c_d = row2.cells[0], row2.cells[1]
        c_c.width = col_width
        c_d.width = col_width
        set_cell_margins(c_c, top=10, bottom=10, left=20, right=20)
        set_cell_margins(c_d, top=10, bottom=10, left=20, right=20)

        p_c = c_c.paragraphs[0]
        p_c.paragraph_format.space_before = Pt(0)
        p_c.paragraph_format.space_after = Pt(3)
        r_c = p_c.add_run(opt_c)
        apply_bamini_10(r_c, bold=False, size_pt=10)

        p_d = c_d.paragraphs[0]
        p_d.paragraph_format.space_before = Pt(0)
        p_d.paragraph_format.space_after = Pt(3)
        r_d = p_d.add_run(opt_d)
        apply_bamini_10(r_d, bold=False, size_pt=10)

    doc.save(output_path)
    print(f"[OK] Successfully saved pure Tamil Bamini 10 Word Document: {output_path}")

def send_to_telegram(file_path):
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    CHAT_ID = "6233907249"

    caption = (
        "📝 <b>பொருளாதாரம் மாதிரித் தேர்வு 5 - Word Document (Bamini 10)</b>\n\n"
        "• <b>மொழி</b>: 100% அசல் தூய தமிழ் (Same Tamil Language & Questions, ஆங்கிலக் குறிப்புகள் எதுவும் இல்லை)\n"
        "• <b>Font</b>: Bamini (10 pt)\n"
        "• <b>வடிவமைப்பு</b>: A & B மேலே, C & D கீழே (2×2 Side-by-Side)\n\n"
        "✅ <i>Word-ல் திறக்கக்கூடிய முழுமையான வினாத்தாள் மாப்ள!</i>"
    )

    print("Sending Word document to Telegram...")
    with open(file_path, "rb") as f:
        r = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendDocument",
            data={"chat_id": CHAT_ID, "caption": caption, "parse_mode": "HTML"},
            files={"document": ("Economics_Test_5_Tamil_Bamini_10.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            timeout=60
        )
        print("Telegram status:", r.status_code, r.json().get("ok"))

if __name__ == "__main__":
    out_docx = os.path.join(desktop, "Economics_Test_5_Tamil_Bamini_10.docx")
    generate_doc(out_docx)
    send_to_telegram(out_docx)
    print("Done!")
