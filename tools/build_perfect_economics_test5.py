# -*- coding: utf-8 -*-
"""
Build 100% Flawless, Professional Exam Question Paper Word Document (.docx)
- All 75 Questions from Mukil's parsed input
- Universal Microsoft Nirmala UI font at exact 10 pt (renders flawlessly on PC Desktop MS Word & Mobile Word)
- Bulletproof 2x2 side-by-side options (A & B on top, C & D below)
- Fixed table geometry with zero-borders, cantSplit, keep_with_next
- Clean header without any extraneous metadata boxes or answer references
- Automated PDF conversion via Word COM
"""

import os
import sys
import re
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
import win32com.client
import pymupdf

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

desktop = r"C:\Users\mukil\Desktop"
output_docx = os.path.join(desktop, "Economics_Test_5_Perfect.docx")
output_pdf = os.path.join(desktop, "Economics_Test_5_Perfect.pdf")

def load_all_75_questions():
    with open(os.path.join(desktop, "mukil_pasted_raw.txt"), "r", encoding="utf-8") as f:
        raw = f.read()

    raw = re.sub(r'</?USER_REQUEST>', '', raw).strip()
    if "ethu enna mampala" in raw:
        raw = raw.split("ethu enna mampala")[0].strip()

    q_blocks = re.split(r'\n(?=\d+\.\s)', raw)
    first_q_idx = 0
    for idx, b in enumerate(q_blocks):
        if re.match(r'^\d+\.\s', b.strip()):
            first_q_idx = idx
            break

    questions_raw = q_blocks[first_q_idx:]
    parsed_list = []

    for qb in questions_raw:
        lines = [l.strip() for l in qb.strip().splitlines() if l.strip()]
        if not lines:
            continue
        
        m = re.match(r'^(\d+)\.\s*(.*)', lines[0])
        if not m:
            continue
        
        q_num = int(m.group(1))
        q_text = m.group(2)
        
        opt_lines = []
        q_extra = []
        for l in lines[1:]:
            if re.search(r'^[A-D]\)', l):
                opt_lines.append(l)
            else:
                if not opt_lines:
                    q_extra.append(l)
                else:
                    opt_lines.append(l)
                    
        full_q = q_text
        if q_extra:
            full_q += "\n" + "\n".join(q_extra)
            
        full_opt_str = " \t ".join(opt_lines)
        opt_matches = list(re.finditer(r'([A-D])\)\s*', full_opt_str))
        opts = {}
        for i in range(len(opt_matches)):
            letter = opt_matches[i].group(1)
            start = opt_matches[i].end()
            end = opt_matches[i+1].start() if i+1 < len(opt_matches) else len(full_opt_str)
            opts[letter] = full_opt_str[start:end].strip()
            
        parsed_list.append({
            'num': q_num,
            'q': full_q,
            'A': opts.get('A', ''),
            'B': opts.get('B', ''),
            'C': opts.get('C', ''),
            'D': opts.get('D', '')
        })

    return parsed_list

def apply_font_style(run, font_name="Nirmala UI", size_pt=10, bold=False, color=(26, 32, 44)):
    run.font.name = font_name
    run.font.size = Pt(size_pt)
    run.font.bold = bold
    run.font.color.rgb = RGBColor(*color)
    
    rPr = run._r.get_or_add_rPr()
    rFonts = rPr.find(qn('w:rFonts'))
    if rFonts is None:
        rFonts = OxmlElement('w:rFonts')
        rPr.append(rFonts)
    rFonts.set(qn('w:ascii'), font_name)
    rFonts.set(qn('w:hAnsi'), font_name)
    rFonts.set(qn('w:cs'), font_name)

def set_cell_properties(cell, width_in, top_dxa=20, bottom_dxa=20, left_dxa=25, right_dxa=25):
    tcPr = cell._tc.get_or_add_tcPr()
    tcW = OxmlElement('w:tcW')
    tcW.set(qn('w:w'), str(int(width_in * 1440)))
    tcW.set(qn('w:type'), 'dxa')
    tcPr.append(tcW)
    
    tcMar = OxmlElement('w:tcMar')
    for side, val in [('top', top_dxa), ('bottom', bottom_dxa), ('left', left_dxa), ('right', right_dxa)]:
        node = OxmlElement(f'w:{side}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)

def build_docx():
    questions = load_all_75_questions()
    print(f"Loaded {len(questions)} questions.")

    doc = docx.Document()

    # Page Setup: A4 with 0.65 in margins
    for sec in doc.sections:
        sec.top_margin = Inches(0.65)
        sec.bottom_margin = Inches(0.65)
        sec.left_margin = Inches(0.65)
        sec.right_margin = Inches(0.65)
        sec.page_width = Inches(8.27)
        sec.page_height = Inches(11.69)

    # --- Header ---
    title_p = doc.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_p.paragraph_format.space_before = Pt(0)
    title_p.paragraph_format.space_after = Pt(2)
    t_run = title_p.add_run("பொருளாதாரம் மாதிரித் தேர்வு – 5")
    apply_font_style(t_run, font_name="Nirmala UI", size_pt=14, bold=True, color=(26, 54, 93))

    sub_p = doc.add_paragraph()
    sub_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub_p.paragraph_format.space_after = Pt(4)
    s_run = sub_p.add_run("நேரம்: 1 மணி 30 நிமிடம்          |          மொத்த வினாக்கள்: 75          |          மதிப்பெண்கள்: 75")
    apply_font_style(s_run, font_name="Nirmala UI", size_pt=9.5, bold=True, color=(74, 85, 104))

    div_p = doc.add_paragraph()
    div_p.paragraph_format.space_after = Pt(8)
    div_run = div_p.add_run("―" * 65)
    apply_font_style(div_run, font_name="Nirmala UI", size_pt=9, bold=False, color=(203, 213, 224))

    col_w_in = 3.48 # 3.48 * 2 = 6.96 in (fits 8.27 - 1.30 = 6.97 in)

    for item in questions:
        # Question Paragraph
        qp = doc.add_paragraph()
        qp.paragraph_format.space_before = Pt(5)
        qp.paragraph_format.space_after = Pt(2)
        qp.paragraph_format.line_spacing = 1.15
        qp.paragraph_format.keep_with_next = True # Keep with table

        q_num_run = qp.add_run(f"{item['num']}. ")
        apply_font_style(q_num_run, font_name="Nirmala UI", size_pt=10, bold=True)

        q_text_run = qp.add_run(item['q'])
        apply_font_style(q_text_run, font_name="Nirmala UI", size_pt=10, bold=True)

        # 2x2 Table
        tbl = doc.add_table(rows=2, cols=2)
        tbl.alignment = docx.enum.table.WD_TABLE_ALIGNMENT.CENTER
        tbl.autofit = False

        tblPr = tbl._tbl.tblPr
        tblLayout = OxmlElement('w:tblLayout')
        tblLayout.set(qn('w:type'), 'fixed')
        tblPr.append(tblLayout)

        tblBorders = OxmlElement('w:tblBorders')
        for b in ['top', 'left', 'bottom', 'right', 'insideH', 'insideV']:
            node = OxmlElement(f'w:{b}')
            node.set(qn('w:val'), 'none')
            tblBorders.append(node)
        tblPr.append(tblBorders)

        # Row 1: A and B
        row1 = tbl.rows[0]
        rPr1 = row1._tr.get_or_add_trPr()
        rPr1.append(OxmlElement('w:cantSplit'))

        c_a, c_b = row1.cells[0], row1.cells[1]
        set_cell_properties(c_a, col_w_in)
        set_cell_properties(c_b, col_w_in)

        p_a = c_a.paragraphs[0]
        p_a.paragraph_format.space_before = Pt(0)
        p_a.paragraph_format.space_after = Pt(1)
        p_a.paragraph_format.line_spacing = 1.1
        r_a_lbl = p_a.add_run("A) ")
        apply_font_style(r_a_lbl, font_name="Nirmala UI", size_pt=10, bold=True)
        r_a_txt = p_a.add_run(item['A'])
        apply_font_style(r_a_txt, font_name="Nirmala UI", size_pt=10, bold=False)

        p_b = c_b.paragraphs[0]
        p_b.paragraph_format.space_before = Pt(0)
        p_b.paragraph_format.space_after = Pt(1)
        p_b.paragraph_format.line_spacing = 1.1
        r_b_lbl = p_b.add_run("B) ")
        apply_font_style(r_b_lbl, font_name="Nirmala UI", size_pt=10, bold=True)
        r_b_txt = p_b.add_run(item['B'])
        apply_font_style(r_b_txt, font_name="Nirmala UI", size_pt=10, bold=False)

        # Row 2: C and D
        row2 = tbl.rows[1]
        rPr2 = row2._tr.get_or_add_trPr()
        rPr2.append(OxmlElement('w:cantSplit'))

        c_c, c_d = row2.cells[0], row2.cells[1]
        set_cell_properties(c_c, col_w_in)
        set_cell_properties(c_d, col_w_in)

        p_c = c_c.paragraphs[0]
        p_c.paragraph_format.space_before = Pt(0)
        p_c.paragraph_format.space_after = Pt(2)
        p_c.paragraph_format.line_spacing = 1.1
        r_c_lbl = p_c.add_run("C) ")
        apply_font_style(r_c_lbl, font_name="Nirmala UI", size_pt=10, bold=True)
        r_c_txt = p_c.add_run(item['C'])
        apply_font_style(r_c_txt, font_name="Nirmala UI", size_pt=10, bold=False)

        p_d = c_d.paragraphs[0]
        p_d.paragraph_format.space_before = Pt(0)
        p_d.paragraph_format.space_after = Pt(2)
        p_d.paragraph_format.line_spacing = 1.1
        r_d_lbl = p_d.add_run("D) ")
        apply_font_style(r_d_lbl, font_name="Nirmala UI", size_pt=10, bold=True)
        r_d_txt = p_d.add_run(item['D'])
        apply_font_style(r_d_txt, font_name="Nirmala UI", size_pt=10, bold=False)

    doc.save(output_docx)
    print(f"Saved {output_docx}")

def convert_to_pdf():
    word = win32com.client.DispatchEx('Word.Application')
    word.Visible = False
    doc = word.Documents.Open(output_docx)
    if os.path.exists(output_pdf):
        os.remove(output_pdf)
    doc.SaveAs(output_pdf, FileFormat=17)
    doc.Close()
    word.Quit()
    print(f"Saved {output_pdf}")

if __name__ == '__main__':
    build_docx()
    convert_to_pdf()
