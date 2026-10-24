import os
from pathlib import Path
from playwright.sync_api import sync_playwright

HTML_CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Mukilarasu S - Resume</title>
<style>
  @page {
    size: A4;
    margin: 10mm 14mm 10mm 14mm;
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
    line-height: 1.35;
    font-size: 10.2pt;
    -webkit-font-smoothing: antialiased;
  }
  .header {
    text-align: center;
    border-bottom: 1.5px solid #1f2937;
    padding-bottom: 8px;
    margin-bottom: 10px;
  }
  .header h1 {
    font-size: 20pt;
    font-weight: 700;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    color: #111827;
    margin-bottom: 3px;
  }
  .header .title {
    font-size: 11pt;
    font-weight: 600;
    color: #374151;
    margin-bottom: 4px;
  }
  .header .contact-links {
    font-size: 9pt;
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
    font-size: 10.5pt;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: #111827;
    border-bottom: 1px solid #9ca3af;
    padding-bottom: 2px;
    margin-top: 9px;
    margin-bottom: 5px;
  }
  .entry {
    margin-bottom: 6px;
  }
  .entry-header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
  }
  .entry-title {
    font-weight: 700;
    color: #111827;
    font-size: 10pt;
  }
  .entry-subtitle {
    font-style: italic;
    color: #4b5563;
    font-size: 9.5pt;
  }
  .entry-date {
    font-size: 9pt;
    font-weight: 600;
    color: #374151;
    text-align: right;
  }
  .entry-badge {
    font-size: 8.5pt;
    background: #f3f4f6;
    border: 1px solid #e5e7eb;
    padding: 1px 6px;
    border-radius: 4px;
    font-weight: 600;
    color: #374151;
  }
  ul.bullets {
    list-style-type: disc;
    margin-left: 17px;
    margin-top: 2px;
  }
  ul.bullets li {
    font-size: 9.3pt;
    color: #374151;
    margin-bottom: 2px;
    line-height: 1.32;
  }
  .skills-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 9.3pt;
  }
  .skills-table td {
    padding: 2px 0;
    vertical-align: top;
  }
  .skill-cat {
    font-weight: 700;
    color: #111827;
    width: 25%;
    white-space: nowrap;
  }
  .skill-val {
    color: #374151;
    width: 75%;
  }
  .cert-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 3px 12px;
    font-size: 9pt;
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
    <div class="title">Software Engineer | Full-Stack & AI Developer</div>
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
      <div class="entry-subtitle">Higher Secondary Certificate (Class XII)</div>
      <div class="entry-date">Percentage: 69.33%</div>
    </div>
  </div>

  <!-- TECHNICAL SKILLS -->
  <div class="section-title">Technical Skills</div>
  <table class="skills-table">
    <tr>
      <td class="skill-cat">Programming Languages:</td>
      <td class="skill-val">Core Java (OOPs, Collections, Exception Handling), Python, SQL, JavaScript</td>
    </tr>
    <tr>
      <td class="skill-cat">Web & Desktop Development:</td>
      <td class="skill-val">React.js, Node.js, Electron.js, Flask, HTML5, CSS3, REST APIs</td>
    </tr>
    <tr>
      <td class="skill-cat">Databases & Cloud APIs:</td>
      <td class="skill-val">MySQL, PostgreSQL, SQLite, Google Drive API (OAuth 2.0), Cloudinary</td>
    </tr>
    <tr>
      <td class="skill-cat">Developer Tools & Platforms:</td>
      <td class="skill-val">Git, GitHub, VS Code, Postman, Playwright, Linux / Windows</td>
    </tr>
  </table>

  <!-- PROJECTS -->
  <div class="section-title">Projects</div>
  
  <div class="entry">
    <div class="entry-header">
      <div>
        <span class="entry-title">SGC Billing – Enterprise Desktop Invoicing Application</span>
        <span class="entry-badge">Freelance Production App</span>
      </div>
      <div class="entry-date">Electron, React, Node.js, Drive OAuth</div>
    </div>
    <ul class="bullets">
      <li>Built an offline-first desktop application for a local business to generate, manage, and calculate customer invoices.</li>
      <li>Implemented automated high-speed PDF invoice generation and background cloud synchronization to Google Drive via OAuth 2.0.</li>
      <li>Engineered robust calculation engines with zero-loss crash recovery, eliminating manual invoicing errors.</li>
    </ul>
  </div>

  <div class="entry">
    <div class="entry-header">
      <div>
        <span class="entry-title">Botify – AI-Powered Multi-Tenant WhatsApp Platform</span>
        <span class="entry-badge">Freelance SaaS</span>
      </div>
      <div class="entry-date">Python, Flask, PostgreSQL, Groq API</div>
    </div>
    <ul class="bullets">
      <li>Architected a web-based SaaS platform enabling small businesses to deploy automated WhatsApp bots for client inquiries.</li>
      <li>Integrated Groq API for intelligent text responses, appointment scheduling, and automated customer conversation flows.</li>
      <li>Developed an administrative analytics dashboard to monitor incoming client requests and bot interaction telemetry.</li>
    </ul>
  </div>

  <div class="entry">
    <div class="entry-header">
      <div>
        <span class="entry-title">AI Billing Automation Bot</span>
        <span class="entry-badge">Automation Tool</span>
      </div>
      <div class="entry-date">Python, Telegram API, Groq LLM</div>
    </div>
    <ul class="bullets">
      <li>Developed an automated pipeline extracting structured line items from physical handwritten invoice images using Groq LLM.</li>
      <li>Automated customer ledger verification, dynamic tax calculations, and instant digital invoice dispatch via Telegram bot.</li>
    </ul>
  </div>

  <div class="entry" style="margin-bottom: 2px;">
    <div class="entry-header">
      <div>
        <span class="entry-title">Agentic AI Autonomous Workflow Platform</span>
        <span class="entry-badge">Core AI Project</span>
      </div>
      <div class="entry-date">Python, Playwright, LLM Tooling</div>
    </div>
    <ul class="bullets">
      <li>Created automated web-browsing scripts using Playwright to handle multi-step form submissions and data extraction.</li>
    </ul>
  </div>

  <!-- INTERNSHIPS -->
  <div class="section-title">Internships</div>
  <div class="entry">
    <div class="entry-header">
      <div>
        <span class="entry-title">Hero MotoCorp Ltd.</span>, <span class="entry-subtitle">Chennai, Tamil Nadu</span>
      </div>
      <div class="entry-date">1 Month</div>
    </div>
    <div class="entry-header">
      <div class="entry-subtitle">Research & Development (R&D) Engineering Intern</div>
      <div class="entry-date">Automotive Engineering</div>
    </div>
    <ul class="bullets">
      <li>Observed engineering testing protocols, industrial workflows, and automated reporting methods inside the R&D facility.</li>
    </ul>
  </div>

  <div class="entry" style="margin-bottom: 2px;">
    <div class="entry-header">
      <div>
        <span class="entry-title">IBM</span>, <span class="entry-subtitle">Virtual Internship</span>
      </div>
      <div class="entry-date">2026</div>
    </div>
    <div class="entry-header">
      <div class="entry-subtitle">AI & Automation Virtual Intern</div>
      <div class="entry-date">Enterprise AI</div>
    </div>
    <ul class="bullets">
      <li>Completed training modules on artificial intelligence fundamentals, workflow automation, and enterprise cloud architectures.</li>
    </ul>
  </div>

  <!-- CERTIFICATIONS -->
  <div class="section-title">Certifications & Achievements</div>
  <div class="cert-grid">
    <div class="cert-item">• <strong>Infosys Certified Java Programmer</strong> – Infosys (2024)</div>
    <div class="cert-item">• <strong>Demystifying Networking</strong> – NPTEL Elite (2025)</div>
    <div class="cert-item">• <strong>AI & ML Made Easy</strong> – Udemy (2025)</div>
    <div class="cert-item">• <strong>AI Agents for Beginners</strong> – Simplilearn SkillUp (2026)</div>
  </div>

</body>
</html>
"""

def generate_pdf():
    desktop = Path(os.environ["USERPROFILE"]) / "Desktop"
    output_pdf_desktop = desktop / "MUKILARASU_S_RESUME.pdf"
    output_png_preview = desktop / "MUKILARASU_S_RESUME_PREVIEW.png"
    storage_pdf = Path(r"C:\Users\mukil\jarvis-core\storage\tailored_resumes\MUKILARASU_S_SOFTWARE_ENGINEER_RESUME.pdf")
    storage_pdf.parent.mkdir(parents=True, exist_ok=True)

    html_file = Path(r"C:\Users\mukil\jarvis-core\storage\tailored_resumes\resume_temp.html")
    html_file.write_text(HTML_CONTENT, encoding="utf-8")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1200, "height": 1600})
        page.goto(html_file.as_uri(), wait_until="networkidle")

        # Generate exact 1-page A4 PDF
        page.pdf(
            path=str(output_pdf_desktop),
            format="A4",
            print_background=True,
            margin={"top": "10mm", "bottom": "10mm", "left": "14mm", "right": "14mm"}
        )
        print(f"[OK] Generated PDF on Desktop: {output_pdf_desktop}")

        # Also copy to storage
        import shutil
        shutil.copyfile(output_pdf_desktop, storage_pdf)
        print(f"[OK] Copied to storage: {storage_pdf}")

        # Also capture high-resolution preview screenshot
        page.screenshot(path=str(output_png_preview), full_page=True)
        print(f"[OK] Generated PNG Preview on Desktop: {output_png_preview}")

        browser.close()

if __name__ == "__main__":
    generate_pdf()
