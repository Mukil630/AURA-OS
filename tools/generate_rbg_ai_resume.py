import os
from pathlib import Path
from playwright.sync_api import sync_playwright

HTML_CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Mukilarasu S - AI Engineer Resume (RBG.AI)</title>
<style>
  @page {
    size: A4;
    margin: 8mm 13mm 8mm 13mm;
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
    font-size: 9.9pt;
    -webkit-font-smoothing: antialiased;
  }
  .header {
    text-align: center;
    border-bottom: 1.5px solid #1f2937;
    padding-bottom: 6px;
    margin-bottom: 8px;
  }
  .header h1 {
    font-size: 19pt;
    font-weight: 700;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    color: #111827;
    margin-bottom: 2px;
  }
  .header .title {
    font-size: 10.5pt;
    font-weight: 600;
    color: #1e40af;
    margin-bottom: 4px;
    letter-spacing: 0.3px;
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
    font-size: 10pt;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: #111827;
    border-bottom: 1px solid #9ca3af;
    padding-bottom: 2px;
    margin-top: 8px;
    margin-bottom: 5px;
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
    background: #eef2ff;
    border: 1px solid #c7d2fe;
    padding: 1px 6px;
    border-radius: 4px;
    font-weight: 600;
    color: #3730a3;
  }
  ul.bullets {
    list-style-type: disc;
    margin-left: 16px;
    margin-top: 2px;
  }
  ul.bullets li {
    font-size: 9pt;
    color: #374151;
    margin-bottom: 1.5px;
    line-height: 1.28;
  }
  .skills-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 9pt;
  }
  .skills-table td {
    padding: 2px 0;
    vertical-align: top;
  }
  .skill-cat {
    font-weight: 700;
    color: #111827;
    width: 27%;
    white-space: nowrap;
  }
  .skill-val {
    color: #374151;
    width: 73%;
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
    <div class="title">AI Engineer | Applied Machine Learning & Agentic Systems</div>
    <div class="contact-links">
      <span>Karur / Coimbatore, TN</span>
      <span>•</span>
      <span>+91 9080030538</span>
      <span>•</span>
      <span><a href="mailto:mukilarasu55@gmail.com">mukilarasu55@gmail.com</a></span>
      <span>•</span>
      <span><a href="https://linkedin.com/in/mukilarasu-s-333771302">linkedin.com/in/mukilarasu-s</a></span>
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

  <!-- TECHNICAL SKILLS -->
  <div class="section-title">Technical Skills</div>
  <table class="skills-table">
    <tr>
      <td class="skill-cat">Artificial Intelligence & ML:</td>
      <td class="skill-val">LLM Prompt Engineering, RAG Architectures, Multimodal Document AI, Computer Vision (OCR), Agentic Workflows</td>
    </tr>
    <tr>
      <td class="skill-cat">Programming Languages:</td>
      <td class="skill-val">Python, Core Java (OOPs, Collections, DSA), SQL, JavaScript</td>
    </tr>
    <tr>
      <td class="skill-cat">Frameworks & Cloud APIs:</td>
      <td class="skill-val">Groq Cloud API, Flask, FastAPI, Node.js, React.js, Electron.js, REST APIs, Google Drive OAuth 2.0</td>
    </tr>
    <tr>
      <td class="skill-cat">Databases & Tools:</td>
      <td class="skill-val">PostgreSQL, MySQL, SQLite, Playwright (Browser Automation), Git, GitHub, Postman, Linux CLI</td>
    </tr>
  </table>

  <!-- PROJECTS -->
  <div class="section-title">AI & Software Engineering Projects</div>
  
  <div class="entry">
    <div class="entry-header">
      <div>
        <span class="entry-title">Agentic AI Autonomous Workflow Platform</span>
        <span class="entry-badge">Applied AI & Automation</span>
      </div>
      <div class="entry-date">Python, LLM Tooling, Playwright, Context Engine</div>
    </div>
    <ul class="bullets">
      <li>Designed and implemented autonomous multi-agent workflows capable of dynamic task decomposition and automated web interaction.</li>
      <li>Engineered resilient browser execution pipelines using Playwright with error self-healing, automated form routing, and session recovery.</li>
      <li>Integrated stateful JSON memory caches to maintain persistent context across complex multi-step automation cycles.</li>
    </ul>
  </div>

  <div class="entry">
    <div class="entry-header">
      <div>
        <span class="entry-title">Multimodal AI Document & Invoice Intelligence Engine</span>
        <span class="entry-badge">Vision & NLP Pipeline</span>
      </div>
      <div class="entry-date">Python, Groq LLM, OCR, Telegram Gateway, SQLite</div>
    </div>
    <ul class="bullets">
      <li>Engineered an end-to-end multimodal pipeline to extract structured line items from physical handwritten & tabular invoice images.</li>
      <li>Implemented dynamic prompt formatting and schema enforcement, achieving high accuracy in parsing unstructured numerical and textual data.</li>
      <li>Automated customer ledger reconciliations, dynamic tax calculations, and real-time structured data dispatch via messaging bridges.</li>
    </ul>
  </div>

  <div class="entry">
    <div class="entry-header">
      <div>
        <span class="entry-title">Botify – Multi-Tenant AI Conversational Agent SaaS</span>
        <span class="entry-badge">Production LLM App</span>
      </div>
      <div class="entry-date">Python, Flask, PostgreSQL, Groq API, Multi-Tenancy</div>
    </div>
    <ul class="bullets">
      <li>Architected an asynchronous multi-tenant conversational AI backend enabling automated query handling and appointment scheduling.</li>
      <li>Integrated high-throughput Groq LLM API with optimized context windows, reducing inference latency while maintaining conversation state.</li>
      <li>Constructed an administrative telemetry dashboard to monitor real-time token utilization, query traffic, and agent accuracy.</li>
    </ul>
  </div>

  <div class="entry">
    <div class="entry-header">
      <div>
        <span class="entry-title">SGC Billing – Enterprise Desktop Application with Cloud Sync</span>
        <span class="entry-badge">Production Software</span>
      </div>
      <div class="entry-date">Electron.js, React, Node.js, Google Drive OAuth</div>
    </div>
    <ul class="bullets">
      <li>Built an offline-first desktop solution for industrial billing with zero calculation error margins and high-speed PDF rendering.</li>
      <li>Engineered an automated background backup mechanism syncing invoices directly to Google Drive vault via authenticated OAuth 2.0.</li>
    </ul>
  </div>

  <!-- INTERNSHIPS -->
  <div class="section-title">Internships</div>
  <div class="entry">
    <div class="entry-header">
      <div>
        <span class="entry-title">IBM</span>, <span class="entry-subtitle">Virtual Internship</span>
      </div>
      <div class="entry-date">2026</div>
    </div>
    <div class="entry-header">
      <div class="entry-subtitle">AI & Automation Virtual Intern</div>
      <div class="entry-date">Enterprise AI Systems</div>
    </div>
    <ul class="bullets">
      <li>Explored enterprise artificial intelligence architectures, cognitive workflow automation, and cloud-scale model deployment patterns.</li>
    </ul>
  </div>

  <div class="entry">
    <div class="entry-header">
      <div>
        <span class="entry-title">Hero MotoCorp Ltd.</span>, <span class="entry-subtitle">Chennai, Tamil Nadu</span>
      </div>
      <div class="entry-date">1 Month</div>
    </div>
    <div class="entry-header">
      <div class="entry-subtitle">Research & Development (R&D) Engineering Intern</div>
      <div class="entry-date">Engineering Operations</div>
    </div>
    <ul class="bullets">
      <li>Analyzed industrial workflows, component testing methodologies, and operational data monitoring inside the central R&D facility.</li>
    </ul>
  </div>

  <!-- CERTIFICATIONS -->
  <div class="section-title">Certifications & Achievements</div>
  <div class="cert-grid">
    <div class="cert-item">• <strong>Infosys Certified Java Programmer</strong> – Infosys (2024)</div>
    <div class="cert-item">• <strong>AI Agents for Beginners</strong> – Simplilearn SkillUp (2026)</div>
    <div class="cert-item">• <strong>AI & ML Made Easy: Basic to Advanced</strong> – Udemy (2025)</div>
    <div class="cert-item">• <strong>Demystifying Networking</strong> – NPTEL Elite (2025)</div>
  </div>

</body>
</html>
"""

def generate_pdf():
    desktop = Path(os.environ["USERPROFILE"]) / "Desktop"
    output_pdf_desktop = desktop / "MUKILARASU_S_RBGAI_RESUME.pdf"
    storage_pdf = Path(r"C:\Users\mukil\jarvis-core\storage\tailored_resumes\MUKILARASU_S_RBGAI_RESUME.pdf")
    storage_pdf.parent.mkdir(parents=True, exist_ok=True)

    html_file = Path(r"C:\Users\mukil\jarvis-core\storage\tailored_resumes\resume_rbg_ai_temp.html")
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
            margin={"top": "8mm", "bottom": "8mm", "left": "13mm", "right": "13mm"}
        )
        print(f"[OK] Generated RBG.AI Tailored PDF on Desktop: {output_pdf_desktop}")

        # Also copy to storage
        import shutil
        shutil.copyfile(output_pdf_desktop, storage_pdf)
        print(f"[OK] Copied to storage: {storage_pdf}")

        browser.close()

if __name__ == "__main__":
    generate_pdf()
