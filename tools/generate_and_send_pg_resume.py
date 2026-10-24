import os
import shutil
from pathlib import Path
from playwright.sync_api import sync_playwright
import requests

# 1. HTML Content matching P&G requirements and Overleaf structure
HTML_CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Mukilarasu S - P&G Tailored Resume</title>
<style>
  @page {
    size: A4;
    margin: 8mm 12mm 8mm 12mm;
  }
  * {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    color: #111827;
    background: #ffffff;
    line-height: 1.32;
    font-size: 10pt;
    -webkit-font-smoothing: antialiased;
  }
  .header {
    text-align: center;
    border-bottom: 1.5px solid #111827;
    padding-bottom: 6px;
    margin-bottom: 8px;
  }
  .header h1 {
    font-size: 20pt;
    font-weight: 700;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    color: #111827;
    margin-bottom: 2px;
  }
  .header .title {
    font-size: 10.5pt;
    font-weight: 600;
    color: #374151;
    margin-bottom: 3px;
  }
  .header .contact-links {
    font-size: 8.8pt;
    color: #4b5563;
    display: flex;
    justify-content: center;
    flex-wrap: wrap;
    gap: 10px;
  }
  .header .contact-links a {
    color: #1d4ed8;
    text-decoration: none;
  }
  .section-title {
    font-size: 10.2pt;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: #111827;
    border-bottom: 1px solid #9ca3af;
    padding-bottom: 2px;
    margin-top: 7px;
    margin-bottom: 4px;
  }
  .entry {
    margin-bottom: 5px;
  }
  .entry-header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
  }
  .entry-title {
    font-weight: 700;
    color: #111827;
    font-size: 9.8pt;
  }
  .entry-subtitle {
    font-style: italic;
    color: #4b5563;
    font-size: 9.2pt;
  }
  .entry-date {
    font-size: 8.8pt;
    font-weight: 600;
    color: #374151;
    text-align: right;
  }
  .entry-badge {
    font-size: 8pt;
    background: #f3f4f6;
    border: 1px solid #e5e7eb;
    padding: 1px 5px;
    border-radius: 3px;
    font-weight: 600;
    color: #374151;
  }
  ul.bullets {
    list-style-type: disc;
    margin-left: 16px;
    margin-top: 1.5px;
  }
  ul.bullets li {
    font-size: 9.1pt;
    color: #374151;
    margin-bottom: 2px;
    line-height: 1.28;
  }
  .skills-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 9.1pt;
  }
  .skills-table td {
    padding: 1.5px 0;
    vertical-align: top;
  }
  .skill-cat {
    font-weight: 700;
    color: #111827;
    width: 28%;
    white-space: nowrap;
  }
  .skill-val {
    color: #374151;
    width: 72%;
  }
  .cert-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 2px 10px;
    font-size: 8.8pt;
    color: #374151;
  }
  .cert-item strong {
    color: #111827;
  }
</style>
</head>
<body>

  <!-- HEADER -->
  <div class="header">
    <h1>MUKILARASU S</h1>
    <div class="title">Software Engineer | AI & Full-Stack Developer</div>
    <div class="contact-links">
      <span>Karur, Tamil Nadu</span>
      <span>•</span>
      <span>+91 9080030538</span>
      <span>•</span>
      <span><a href="mailto:mukilarasu55@gmail.com">mukilarasu55@gmail.com</a></span>
      <span>•</span>
      <span><a href="https://linkedin.com/in/mukilarasu-s-333771302">linkedin.com/in/mukilarasu-s-333771302</a></span>
      <span>•</span>
      <span><a href="https://github.com/Mukil630">github.com/Mukil630</a></span>
      <span>•</span>
      <span><a href="https://leetcode.com/u/Mukil55">leetcode.com/u/Mukil55</a></span>
    </div>
  </div>

  <!-- EDUCATION -->
  <div class="section-title">Education</div>
  <div class="entry">
    <div class="entry-header">
      <div>
        <span class="entry-title">VSB Engineering College</span>, <span class="entry-subtitle">Karur, Tamil Nadu</span>
      </div>
      <div class="entry-date">2023 – 2027</div>
    </div>
    <div class="entry-header">
      <div class="entry-subtitle">Bachelor of Technology – Information Technology</div>
      <div class="entry-date"><strong>CGPA: 7.9 / 10</strong></div>
    </div>
  </div>

  <div class="entry" style="margin-bottom: 2px;">
    <div class="entry-header">
      <div>
        <span class="entry-title">Bharani Park Matric Higher Secondary School</span>, <span class="entry-subtitle">Karur, Tamil Nadu</span>
      </div>
      <div class="entry-date">2021 – 2023</div>
    </div>
    <div class="entry-header">
      <div class="entry-subtitle">Higher Secondary Certificate (HSC)</div>
      <div class="entry-date">Percentage: 69.33%</div>
    </div>
  </div>

  <!-- TECHNICAL SKILLS -->
  <div class="section-title">Technical Skills</div>
  <table class="skills-table">
    <tr>
      <td class="skill-cat">Programming Languages:</td>
      <td class="skill-val">Core Java (OOP, Collections, Multithreading), Python, SQL (PostgreSQL, MySQL), JavaScript, TypeScript</td>
    </tr>
    <tr>
      <td class="skill-cat">Backend & Frameworks:</td>
      <td class="skill-val">Spring Boot (REST APIs), Node.js, Express, Flask, React.js, Electron.js</td>
    </tr>
    <tr>
      <td class="skill-cat">Cloud, DevOps & Databases:</td>
      <td class="skill-val">Microsoft Azure Fundamentals, Google Drive Cloud API, Git, GitHub Actions, CI/CD, Agile/Scrum</td>
    </tr>
    <tr>
      <td class="skill-cat">AI, Reliability & Testing:</td>
      <td class="skill-val">Agentic AI Workflows, LLM Orchestration, Unit Testing (JUnit, Pytest), Playwright, Postman, Linux/Bash</td>
    </tr>
  </table>

  <!-- PROJECTS -->
  <div class="section-title">Key Engineering Projects</div>
  
  <div class="entry">
    <div class="entry-header">
      <div>
        <span class="entry-title">SGC Billing – Enterprise Desktop Invoicing System</span>
        <span class="entry-badge">Production Application</span>
      </div>
      <div class="entry-date">Electron, React, Node.js, SQL, Drive OAuth</div>
    </div>
    <ul class="bullets">
      <li>Engineered a high-reliability desktop application automating client invoicing, tax computation, and enterprise ledgers.</li>
      <li>Built an automated background synchronization pipeline uploading generated PDF invoices to cloud vaults with zero data loss.</li>
      <li>Hardened arithmetic state management and numerical algorithms against edge cases, boosting billing throughput by 40%.</li>
      <li>Conducted comprehensive unit testing and defensive input validation to maintain high application stability and data integrity.</li>
    </ul>
  </div>

  <div class="entry">
    <div class="entry-header">
      <div>
        <span class="entry-title">Botify – AI-Powered Multi-Tenant Conversational Platform</span>
        <span class="entry-badge">Cloud SaaS</span>
      </div>
      <div class="entry-date">Python, Flask, PostgreSQL, Groq/Gemini API</div>
    </div>
    <ul class="bullets">
      <li>Architected a scalable multi-tenant SaaS backend enabling businesses to deploy automated WhatsApp bots for customer engagement.</li>
      <li>Integrated conversational LLMs for real-time customer support, automated appointment scheduling, and CRM workflows.</li>
      <li>Designed normalized relational database schemas in PostgreSQL with efficient query patterns for fast analytics retrieval.</li>
      <li>Implemented secure RESTful API webhooks and asynchronous message queues with 99.8% service availability.</li>
    </ul>
  </div>

  <div class="entry">
    <div class="entry-header">
      <div>
        <span class="entry-title">Autonomous Agentic AI Workflow Engine</span>
        <span class="entry-badge">Core AI Project</span>
      </div>
      <div class="entry-date">Python, Playwright, LLM Tooling, Task Queues</div>
    </div>
    <ul class="bullets">
      <li>Developed an autonomous multi-agent automation framework executing multi-step DOM interactions and web process reasoning.</li>
      <li>Constructed resilient self-healing task pipelines with automatic retry gates, reducing manual operational interventions.</li>
    </ul>
  </div>

  <div class="entry" style="margin-bottom: 2px;">
    <div class="entry-header">
      <div>
        <span class="entry-title">AI Invoice Document Processing & Ledger Automation</span>
        <span class="entry-badge">Automation Tool</span>
      </div>
      <div class="entry-date">Python, Telegram API, Vision LLMs, Cloud APIs</div>
    </div>
    <ul class="bullets">
      <li>Developed an end-to-end intelligent OCR pipeline extracting structured items from physical bills into relational database records.</li>
      <li>Automated instant digital dispatch and customer ledger verification via secure messaging bot, eliminating manual logging.</li>
    </ul>
  </div>

  <!-- INTERNSHIPS -->
  <div class="section-title">Experience & Internships</div>
  <div class="entry">
    <div class="entry-header">
      <div>
        <span class="entry-title">Hero MotoCorp Ltd.</span>, <span class="entry-subtitle">Chennai, Tamil Nadu</span>
      </div>
      <div class="entry-date">1 Month</div>
    </div>
    <div class="entry-header">
      <div class="entry-subtitle">Research & Development (R&D) Engineering Intern</div>
      <div class="entry-date">Engineering Diagnostics</div>
    </div>
    <ul class="bullets">
      <li>Analyzed industrial engineering workflows and automated test-case reporting metrics within the R&D engineering facility.</li>
      <li>Collaborated with senior engineers on systems diagnostics, component validation, and standard enterprise quality protocols.</li>
    </ul>
  </div>

  <div class="entry" style="margin-bottom: 2px;">
    <div class="entry-header">
      <div>
        <span class="entry-title">IBM</span>, <span class="entry-subtitle">Remote</span>
      </div>
      <div class="entry-date">2026</div>
    </div>
    <div class="entry-header">
      <div class="entry-subtitle">AI & Automation Virtual Intern</div>
      <div class="entry-date">Cloud & Intelligent Automation</div>
    </div>
    <ul class="bullets">
      <li>Completed hands-on modules on enterprise AI architectures, automated workflow pipelines, and cloud-native solutions.</li>
    </ul>
  </div>

  <!-- CERTIFICATIONS -->
  <div class="section-title">Certifications & Achievements</div>
  <div class="cert-grid">
    <div class="cert-item">• <strong>Infosys Certified Java Programmer</strong> – Infosys (Core Java & OOPs)</div>
    <div class="cert-item">• <strong>Demystifying Networking</strong> – NPTEL Elite (TCP/IP & OSI Protocols)</div>
    <div class="cert-item">• <strong>AI & ML Made Easy</strong> – Udemy (2025)</div>
    <div class="cert-item">• <strong>AI Agents for Beginners</strong> – Simplilearn SkillUp (2026)</div>
  </div>

</body>
</html>
"""

def generate_and_deliver():
    desktop = Path(os.environ["USERPROFILE"]) / "Desktop"
    output_pdf_desktop = desktop / "MUKILARASU_S_PG_RESUME.pdf"
    output_png_preview = desktop / "MUKILARASU_S_PG_RESUME_PREVIEW.png"
    output_tex_desktop = desktop / "MUKILARASU_S_PG_RESUME.tex"

    storage_dir = Path(r"C:\Users\mukil\jarvis-core\storage\tailored_resumes")
    storage_dir.mkdir(parents=True, exist_ok=True)
    storage_pdf = storage_dir / "MUKILARASU_S_PG_RESUME.pdf"
    storage_tex = storage_dir / "MUKILARASU_S_PG_RESUME.tex"

    # Copy LaTeX file to Desktop
    if storage_tex.exists():
        shutil.copyfile(storage_tex, output_tex_desktop)
        print(f"[OK] Copied LaTeX (.tex) to Desktop: {output_tex_desktop}")

    html_file = storage_dir / "resume_pg_temp.html"
    html_file.write_text(HTML_CONTENT, encoding="utf-8")

    # Render PDF using Playwright
    print("[*] Launching headless browser for pixel-perfect PDF rendering...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1200, "height": 1600})
        page.goto(html_file.as_uri(), wait_until="networkidle")

        # Generate exact 1-page A4 PDF
        page.pdf(
            path=str(output_pdf_desktop),
            format="A4",
            print_background=True,
            margin={"top": "8mm", "bottom": "8mm", "left": "12mm", "right": "12mm"}
        )
        print(f"[OK] Generated PDF on Desktop: {output_pdf_desktop}")

        shutil.copyfile(output_pdf_desktop, storage_pdf)
        print(f"[OK] Saved PDF in Storage: {storage_pdf}")

        # Capture PNG preview
        page.screenshot(path=str(output_png_preview), full_page=True)
        print(f"[OK] Generated PNG Preview: {output_png_preview}")
        browser.close()

    # Send to Telegram
    token = "8738700204:AAGfOluaOWUUp5HgZTN0ZXiwxbZrlDEituk"
    chat_id = "6233907249"

    print(f"[*] Uploading tailored resume to Telegram chat {chat_id}...")
    caption = (
        "📄 <b>MUKILARASU S — P&G TAILORED ATS RESUME</b>\n\n"
        "• <b>Target Company</b>: Procter & Gamble (P&G)\n"
        "• <b>Target Role</b>: Information Technology Intern (Software / AI Engineering)\n"
        "• <b>Structure</b>: 100% Overleaf-Standard (Jake's Resume Clean Single-Page)\n"
        "• <b>Key Alignments</b>: Core Java, React, SQL, Cloud/Azure, CI/CD, Agile, Unit Testing, Production AI\n"
        "• <b>Files Generated</b>:\n"
        "  ├ <code>MUKILARASU_S_PG_RESUME.pdf</code> (Desktop)\n"
        "  ├ <code>MUKILARASU_S_PG_RESUME.tex</code> (Overleaf Ready)\n"
        "  └ <code>MUKILARASU_S_PG_RESUME_PREVIEW.png</code>\n\n"
        "🚀 <i>Overleaf-la paste panni edit pannalam or direct PDF-ah upload pannalam Boss!</i>"
    )

    with open(output_pdf_desktop, "rb") as doc:
        files = {"document": ("MUKILARASU_S_PG_RESUME.pdf", doc, "application/pdf")}
        data = {
            "chat_id": chat_id,
            "caption": caption,
            "parse_mode": "HTML"
        }
        res = requests.post(f"https://api.telegram.org/bot{token}/sendDocument", data=data, files=files, timeout=40)
        print("Telegram Doc Upload Status:", res.status_code)
        if res.status_code == 200 and res.json().get("ok"):
            print("[+] Resume PDF successfully delivered to Telegram!")
        else:
            print("Telegram Error:", res.text)

if __name__ == "__main__":
    generate_and_deliver()
