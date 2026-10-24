# -*- coding: utf-8 -*-
"""
Generate Bamini 10 Word (.docx) Question Papers:
1. Economics_Test_5_Bamini_10_Unicode.docx (Unicode Tamil text with Font set to Bamini at 10 pt)
2. Economics_Test_5_Bamini_10_Encoded.docx (True Bamini Typewriter ASCII-encoded text with Font set to Bamini at 10 pt)

- 2x2 side-by-side options (A & B on top, C & D below)
- Zero extra fluff / pure test paper
- Sends both .docx files directly to Mukil's Telegram bot!
- NO Google Drive upload
"""

import os
import sys
import json
import subprocess
import requests
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

desktop = r"C:\Users\mukil\Desktop"

def set_table_no_borders(table):
    tblPr = table._tbl.tblPr
    tblBorders = OxmlElement('w:tblBorders')
    for b in ['top', 'left', 'bottom', 'right', 'insideH', 'insideV']:
        node = OxmlElement(f'w:{b}')
        node.set(qn('w:val'), 'none')
        tblBorders.append(node)
    tblPr.append(tblBorders)

def set_cell_margins(cell, top=15, bottom=15, left=30, right=30):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        node = OxmlElement(f'w:{m}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)

def apply_font(run, font_name="Bamini", size_pt=10, bold=False, color_rgb=(0,0,0)):
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

def get_unicode_questions():
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

def get_bamini_encoded_questions(unicode_questions):
    """Converts question text and options to Bamini encoding via Node.js converter."""
    script = """
global.window = global;
const fs = require('fs');
eval(fs.readFileSync('C:/Users/mukil/Desktop/unicode_to_bamini.js', 'utf8'));

const input = JSON.parse(fs.readFileSync('C:/Users/mukil/Desktop/temp_unicode.json', 'utf8'));
const output = input.map(item => {
    return {
        num: item.num,
        q: convertUnicodeToBamini(item.q),
        options: (item.options || []).map(opt => convertUnicodeToBamini(opt))
    };
});
fs.writeFileSync('C:/Users/mukil/Desktop/temp_bamini.json', JSON.stringify(output, null, 2), 'utf8');
"""
    with open(os.path.join(desktop, "temp_unicode.json"), "w", encoding="utf-8") as f:
        json.dump(unicode_questions, f, ensure_ascii=False)
    
    with open(os.path.join(desktop, "run_conv.js"), "w", encoding="utf-8") as f:
        f.write(script)

    subprocess.run(["node", os.path.join(desktop, "run_conv.js")], check=True)

    with open(os.path.join(desktop, "temp_bamini.json"), "r", encoding="utf-8") as f:
        bamini_questions = json.load(f)

    # Clean up temp files
    for tmp in ["temp_unicode.json", "temp_bamini.json", "run_conv.js"]:
        p = os.path.join(desktop, tmp)
        if os.path.exists(p):
            try: os.remove(p)
            except: pass

    return bamini_questions

def build_word_file(questions, output_path, font_name="Bamini", is_bamini_encoded=False):
    doc = docx.Document()

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
    
    if is_bamini_encoded:
        # Convert header to Bamini
        # "பொருளாதாரம் மாதிரித் தேர்வு – 5"
        # "நேரம்: 1 மணி 30 நிமிடம் | மொத்த வினாக்கள்: 75 | மதிப்பெண்கள்: 75"
        title_text = "nghUshjhuk; khjphpj; Njh;T – 5"
        sub_text = "Neuk;: 1 kzp 30 epkplk;          |          nkhj;j tpdhf;fs;: 75          |          kjpg;ngz;fs;: 75"
    else:
        title_text = "பொருளாதாரம் மாதிரித் தேர்வு – 5"
        sub_text = "நேரம்: 1 மணி 30 நிமிடம்          |          மொத்த வினாக்கள்: 75          |          மதிப்பெண்கள்: 75"

    t_run = title_p.add_run(title_text)
    apply_font(t_run, font_name=font_name, size_pt=14, bold=True, color_rgb=(26, 54, 93))

    sub_p = doc.add_paragraph()
    sub_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub_p.paragraph_format.space_after = Pt(6)
    s_run = sub_p.add_run(sub_text)
    apply_font(s_run, font_name=font_name, size_pt=9.5, bold=True, color_rgb=(74, 85, 104))

    div_p = doc.add_paragraph()
    div_p.paragraph_format.space_after = Pt(8)
    div_run = div_p.add_run("―" * 60)
    apply_font(div_run, font_name="Calibri", size_pt=9, bold=False, color_rgb=(203, 213, 224))

    col_width = Inches(3.4)

    for item in questions:
        qp = doc.add_paragraph()
        qp.paragraph_format.space_before = Pt(5)
        qp.paragraph_format.space_after = Pt(2)
        qp.paragraph_format.line_spacing = 1.15

        q_num = qp.add_run(f"{item['num']}. ")
        apply_font(q_num, font_name=font_name, size_pt=10, bold=True)

        q_txt = qp.add_run(item['q'])
        apply_font(q_txt, font_name=font_name, size_pt=10, bold=True)

        opts = item.get('options', [])
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
        apply_font(r_a, font_name=font_name, size_pt=10, bold=False)

        p_b = c_b.paragraphs[0]
        p_b.paragraph_format.space_before = Pt(0)
        p_b.paragraph_format.space_after = Pt(1)
        r_b = p_b.add_run(opt_b)
        apply_font(r_b, font_name=font_name, size_pt=10, bold=False)

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
        apply_font(r_c, font_name=font_name, size_pt=10, bold=False)

        p_d = c_d.paragraphs[0]
        p_d.paragraph_format.space_before = Pt(0)
        p_d.paragraph_format.space_after = Pt(3)
        r_d = p_d.add_run(opt_d)
        apply_font(r_d, font_name=font_name, size_pt=10, bold=False)

    doc.save(output_path)
    print(f"[OK] Saved: {output_path}")

def send_file_to_telegram(file_path, caption):
    TOKEN = "8738700204:AAGfOluaOWUUp5HgZTN0ZXiwxbZrlDEituk"
    CHAT_ID = "6233907249"
    print(f"Uploading {os.path.basename(file_path)} to Telegram...")
    with open(file_path, "rb") as f:
        r = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendDocument",
            data={"chat_id": CHAT_ID, "caption": caption, "parse_mode": "HTML"},
            files={"document": (os.path.basename(file_path), f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            timeout=60
        )
        print("Telegram Response:", r.status_code, r.json().get("ok"))

def main():
    u_questions = get_unicode_questions()
    print("Preparing Bamini Encoded questions...")
    b_questions = get_bamini_encoded_questions(u_questions)

    # File 1: Unicode with font family set to Bamini (10 pt)
    path1 = os.path.join(desktop, "Economics_Test_5_Bamini_10.docx")
    build_word_file(u_questions, path1, font_name="Bamini", is_bamini_encoded=False)

    # File 2: Classic Bamini Encoded text with font Bamini (10 pt)
    path2 = os.path.join(desktop, "Economics_Test_5_Classic_Bamini_10.docx")
    build_word_file(b_questions, path2, font_name="Bamini", is_bamini_encoded=True)

    # Send both to Telegram
    caption1 = (
        "📄 <b>பொருளாதாரம் மாதிரித் தேர்வு 5 - Word ஆவணம் (Bamini 10)</b>\n\n"
        "• <b>எழுத்துரு & அளவு</b>: Bamini (10 pt)\n"
        "• <b>வடிவமைப்பு</b>: A-B மேலே, C-D கீழே (2×2 Side-by-Side)\n"
        "• <b>வகை</b>: Standard Unicode (Word-ல் Bamini எழுத்துரு அமைக்கப்பட்ட கோப்பு)\n\n"
        "✅ <i>நேரடியாக Word-ல் எடிட் அல்லது பிரிண்ட் செய்யலாம்!</i>"
    )
    send_file_to_telegram(path1, caption1)

    caption2 = (
        "📄 <b>பொருளாதாரம் மாதிரித் தேர்வு 5 - Classic Bamini Typewriter (10 pt)</b>\n\n"
        "• <b>எழுத்துரு & அளவு</b>: Classic Bamini Typewriter Font (10 pt)\n"
        "• <b>வடிவமைப்பு</b>: A-B மேலே, C-D கீழே\n"
        "• <b>வகை</b>: Bamini Encoding (அச்சுக்கூடம்/DTP மையங்களில் Bamini Font கொண்டு திறக்கக்கூடிய வடிவம்)\n\n"
        "✅ <i>Bamini Font உள்ள கணினிகளில் அச்சு அசல் தட்டச்சு வடிவில் தோன்றும்!</i>"
    )
    send_file_to_telegram(path2, caption2)

    print("\nAll done successfully! Zero Drive upload.")

if __name__ == "__main__":
    main()
