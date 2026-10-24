# -*- coding: utf-8 -*-
"""
Generate separated and full PDFs for Economics Test 5:
1. Part 1: First 30 Questions (Q1 to Q30) -> Economics_Test_5_Part1_Q1_to_Q30.pdf
2. All Questions: (Q1 to Q75) -> Economics_Test_5_All_Q1_to_Q75.pdf
3. Part 2: Remaining Questions (Q31 to Q75) -> Economics_Test_5_Part2_Q31_to_Q75.pdf
Converts docx to high-resolution vector PDF using native Word COM automation.
"""

import os
import sys
import time
import win32com.client
from build_test5_doc import create_test5_document

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

desktop = r"C:\Users\mukil\Desktop"

tasks = [
    {
        "name": "Part 1 (Q1 - Q30)",
        "start_q": 1,
        "end_q": 30,
        "suffix": "பகுதி 1: வினாக்கள் 1 - 30",
        "docx": os.path.join(desktop, "Economics_Test_5_Part1_Q1_to_Q30.docx"),
        "pdf": os.path.join(desktop, "Economics_Test_5_Part1_Q1_to_Q30.pdf")
    },
    {
        "name": "All Questions (Q1 - Q75)",
        "start_q": 1,
        "end_q": 75,
        "suffix": "முழு மாதிரி வினாத்தாள்: வினாக்கள் 1 - 75",
        "docx": os.path.join(desktop, "Economics_Test_5_All_Q1_to_Q75.docx"),
        "pdf": os.path.join(desktop, "Economics_Test_5_All_Q1_to_Q75.pdf")
    },
    {
        "name": "Part 2 (Q31 - Q75)",
        "start_q": 31,
        "end_q": 75,
        "suffix": "பகுதி 2: வினாக்கள் 31 - 75",
        "docx": os.path.join(desktop, "Economics_Test_5_Part2_Q31_to_Q75.docx"),
        "pdf": os.path.join(desktop, "Economics_Test_5_Part2_Q31_to_Q75.pdf")
    }
]

def main():
    print("=== STEP 1: Creating DOCX files ===")
    for t in tasks:
        print(f"Creating DOCX for {t['name']}...")
        create_test5_document(t['docx'], start_q=t['start_q'], end_q=t['end_q'], title_suffix=t['suffix'])

    print("\n=== STEP 2: Converting DOCX to PDF via Word COM Automation ===")
    word = win32com.client.DispatchEx("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0

    wdFormatPDF = 17

    try:
        for t in tasks:
            docx_path = os.path.abspath(t['docx'])
            pdf_path = os.path.abspath(t['pdf'])
            print(f"Converting: {t['docx']} -> {t['pdf']}")
            
            # Remove old PDF if exists
            if os.path.exists(pdf_path):
                try:
                    os.remove(pdf_path)
                except Exception:
                    pass

            doc = word.Documents.Open(docx_path)
            doc.SaveAs(pdf_path, FileFormat=wdFormatPDF)
            doc.Close(False)
            print(f"[OK] Created PDF: {pdf_path} ({os.path.getsize(pdf_path):,} bytes)")

    finally:
        word.Quit()
        print("\nWord application closed successfully.")

    print("\n=== ALL PDFS CREATED SUCCESSFULLY! ===")
    for t in tasks:
        if os.path.exists(t['pdf']):
            size_kb = os.path.getsize(t['pdf']) / 1024
            print(f"- {os.path.basename(t['pdf'])}: {size_kb:.1f} KB")

if __name__ == "__main__":
    main()
