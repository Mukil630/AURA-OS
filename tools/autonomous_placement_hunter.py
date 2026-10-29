import os
import sys
import json
import time
from pathlib import Path
import requests
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_DIR = BASE_DIR / "storage"
TAILORED_DIR = STORAGE_DIR / "tailored_resumes"
MEMORY_DIR = STORAGE_DIR / "memory"
DESKTOP_DIR = Path(os.environ.get("USERPROFILE", "C:/Users/mukil")) / "Desktop"

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = "6233907249"

TAILORED_DIR.mkdir(parents=True, exist_ok=True)
MEMORY_DIR.mkdir(parents=True, exist_ok=True)

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>MUKILARASU S - {role_title} Resume</title>
<style>
  @page {{
    size: letter;
    margin: 0.38in 0.52in 0.38in 0.52in;
  }}
  * {{
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    color: #111827;
    background: #ffffff;
    line-height: 1.28;
    font-size: 9.3pt;
    -webkit-font-smoothing: antialiased;
  }}
  .header {{
    text-align: center;
    margin-bottom: 5px;
  }}
  .header h1 {{
    font-size: 18pt;
    font-weight: 700;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    color: #111827;
    margin-bottom: 2px;
  }}
  .header .subtitle {{
    font-size: 9.8pt;
    font-weight: 700;
    color: #111827;
    margin-bottom: 2px;
  }}
  .header .contact-links {{
    font-size: 8.6pt;
    color: #374151;
    display: flex;
    justify-content: center;
    flex-wrap: wrap;
    gap: 8px;
  }}
  .header .contact-links a {{
    color: #1d4ed8;
    text-decoration: none;
  }}
  .section-title {{
    font-size: 9.8pt;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: #111827;
    border-bottom: 1.2px solid #111827;
    padding-bottom: 1px;
    margin-top: 5px;
    margin-bottom: 3px;
  }}
  .summary-text {{
    font-size: 8.8pt;
    color: #374151;
    line-height: 1.30;
    text-align: justify;
  }}
  .entry {{
    margin-bottom: 3px;
  }}
  .entry-header {{
    display: flex;
    justify-content: space-between;
    align-items: baseline;
  }}
  .entry-title {{
    font-weight: 700;
    color: #111827;
    font-size: 9.2pt;
  }}
  .entry-subtitle {{
    font-style: italic;
    color: #4b5563;
    font-size: 8.7pt;
  }}
  .entry-date {{
    font-size: 8.6pt;
    font-weight: 600;
    color: #374151;
    text-align: right;
  }}
  ul.bullets {{
    list-style-type: disc;
    margin-left: 13pt;
    margin-top: 1px;
  }}
  ul.bullets li {{
    font-size: 8.7pt;
    color: #374151;
    margin-bottom: 1px;
    line-height: 1.24;
  }}
  .skills-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 8.7pt;
  }}
  .skills-table td {{
    padding: 1px 0;
    vertical-align: top;
  }}
  .skill-cat {{
    font-weight: 700;
    color: #111827;
    width: 22%;
    white-space: nowrap;
  }}
  .skill-val {{
    color: #374151;
    width: 78%;
  }}
  .cert-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.5px 12px;
    font-size: 8.6pt;
    color: #374151;
  }}
  .additional-text {{
    font-size: 8.6pt;
    color: #374151;
    margin-top: 2px;
  }}
</style>
</head>
<body>

  <!-- HEADER -->
  <div class="header">
    <h1>MUKILARASU S</h1>
    <div class="subtitle">{header_subtitle}</div>
    <div class="contact-links">
      <a href="mailto:mukilarasu55@gmail.com">mukilarasu55@gmail.com</a>
      <span>•</span>
      <span>+91-9080030538</span>
      <span>•</span>
      <span>Karur, Tamil Nadu</span>
      <span>•</span>
      <a href="https://www.linkedin.com/in/mukilarasu-s-333771302/">LinkedIn</a>
      <span>•</span>
      <a href="https://github.com/Mukil630">GitHub</a>
      <span>•</span>
      <a href="https://leetcode.com/u/Mukil55/">LeetCode</a>
    </div>
  </div>

  <!-- SUMMARY -->
  <div class="section-title">SUMMARY</div>
  <div class="summary-text">
    {summary_text}
  </div>

  <!-- TECHNICAL SKILLS -->
  <div class="section-title">TECHNICAL SKILLS</div>
  <table class="skills-table">
    {skills_rows}
  </table>

  <!-- PROJECTS -->
  <div class="section-title">PROJECTS</div>
  {projects_html}

  <!-- INTERNSHIPS & EXPERIENCE -->
  <div class="section-title">INTERNSHIPS & EXPERIENCE</div>
  <div class="entry">
    <div class="entry-header">
      <span class="entry-title">Hero MotoCorp Ltd. – Research & Development Intern</span>
      <span class="entry-date">1 Month</span>
    </div>
    <ul class="bullets">
      <li>Gained industrial exposure to automotive engineering testing protocols, product development workflows, and automated reporting systems.</li>
    </ul>
  </div>
  <div class="entry">
    <div class="entry-header">
      <span class="entry-title">IBM – AI & Automation Weekend Internship</span>
      <span class="entry-date">2026</span>
    </div>
    <ul class="bullets">
      <li>Completed comprehensive training covering enterprise AI fundamentals, workflow automation patterns, and intelligent cloud system architectures.</li>
    </ul>
  </div>

  <!-- EDUCATION -->
  <div class="section-title">EDUCATION</div>
  <div class="entry">
    <div class="entry-header">
      <span class="entry-title">VSB Engineering College, Karur</span>
      <span class="entry-date">2023 – 2027</span>
    </div>
    <div class="entry-header">
      <span>B.Tech – Information Technology</span>
      <span class="entry-date"><strong>CGPA: 7.9 / 10</strong></span>
    </div>
  </div>
  <div class="entry">
    <div class="entry-header">
      <span class="entry-title">Bharani Park Matric Hr. Sec. School, Karur</span>
      <span class="entry-date">Class XII: <strong>69.33%</strong> (2021 – 2023)</span>
    </div>
  </div>

  <!-- CERTIFICATIONS -->
  <div class="section-title">CERTIFICATIONS & ACHIEVEMENTS</div>
  <div class="cert-grid">
    <div>• <strong>Infosys Certified Java Programmer</strong> – Infosys (2024)</div>
    <div>• <strong>AI Agents for Beginners</strong> – Simplilearn SkillUp (2026)</div>
    <div>• <strong>AI & ML Made Easy</strong> – Udemy (2025)</div>
    <div>• <strong>Demystifying Networking</strong> – NPTEL Elite (2025)</div>
    <div>• <strong>AI & Automation Course Completion</strong> – 2025</div>
  </div>

  <!-- ADDITIONAL -->
  <div class="section-title">ADDITIONAL</div>
  <div class="additional-text">
    <strong>Areas of Interest:</strong> {areas_of_interest}
  </div>

</body>
</html>
"""

def generate_tailored_pdf(company_name: str, role_title: str, domain: str = "aiml") -> Path:
    safe_name = "".join(c for c in company_name if c.isalnum() or c in ("_", "-")).upper()
    pdf_filename = f"MUKILARASU_S_{safe_name}_RESUME.pdf"
    output_pdf_desktop = DESKTOP_DIR / pdf_filename
    storage_pdf = TAILORED_DIR / pdf_filename
    temp_html = TAILORED_DIR / f"temp_{safe_name}.html"

    header_subtitle = "AI & Automation Engineer | Backend AI/ML | LLM Applications"
    summary_text = (
        f"Final-year B.Tech Information Technology student with hands-on experience building AI applications, "
        f"backend APIs, and LLM-driven automation workflows. Proficient in Python, REST APIs, RAG, LangChain, "
        f"LangGraph, and SQL databases. Developed production-ready solutions including WhatsApp AI SaaS, "
        f"multimodal invoice extraction, and autonomous agentic workflows. Seeking {role_title} at {company_name} "
        f"to contribute to high-performance, scalable engineering architectures."
    )

    skills_rows = """
    <tr>
      <td class="skill-cat">Programming</td>
      <td class="skill-val">Python, Java</td>
    </tr>
    <tr>
      <td class="skill-cat">AI / ML</td>
      <td class="skill-val">Machine Learning, Deep Learning, Generative AI, LLM Applications, AI Agents</td>
    </tr>
    <tr>
      <td class="skill-cat">AI Frameworks</td>
      <td class="skill-val">LangChain, LangGraph</td>
    </tr>
    <tr>
      <td class="skill-cat">Backend / APIs</td>
      <td class="skill-val">REST APIs, Flask, API Integration</td>
    </tr>
    <tr>
      <td class="skill-cat">Databases</td>
      <td class="skill-val">SQL, PostgreSQL</td>
    </tr>
    <tr>
      <td class="skill-cat">Automation</td>
      <td class="skill-val">Automation Workflows, AI-powered Automation, Playwright</td>
    </tr>
    <tr>
      <td class="skill-cat">Tools / Platforms</td>
      <td class="skill-val">Git, GitHub, Postman, Railway</td>
    </tr>
    """

    projects_html = """
    <div class="entry">
      <div class="entry-header">
        <span class="entry-title">Botify – AI-Powered WhatsApp Bot SaaS</span>
        <span class="entry-subtitle">Freelance</span>
      </div>
      <ul class="bullets">
        <li>Architected a production-ready multi-tenant SaaS platform integrating Groq LLM and WhatsApp API for automated client support, dynamic scheduling, and subscription workflows.</li>
        <li>Built backend conversation handlers, webhooks, and an administrative telemetry dashboard to monitor token usage and bot performance.</li>
      </ul>
    </div>

    <div class="entry">
      <div class="entry-header">
        <span class="entry-title">AI Billing Automation Bot</span>
        <span class="entry-subtitle">Freelance</span>
      </div>
      <ul class="bullets">
        <li>Developed an end-to-end multimodal pipeline extracting handwritten invoice data from physical documents using the Groq API.</li>
        <li>Automated dynamic customer matching, ledger reconciliation, Cloudinary storage, and instant digital invoice dispatch via Telegram.</li>
      </ul>
    </div>

    <div class="entry">
      <div class="entry-header">
        <span class="entry-title">Agentic AI Workflow Automation Platform</span>
        <span class="entry-subtitle">Core AI</span>
      </div>
      <ul class="bullets">
        <li>Engineered an autonomous multi-agent framework utilizing LLM reasoning, LangGraph, and Playwright for complex task planning and browser automation.</li>
        <li>Implemented stateful context routing, dynamic tool execution, and error self-healing routines to eliminate manual web operations.</li>
      </ul>
    </div>

    <div class="entry">
      <div class="entry-header">
        <span class="entry-title">SGC Billing – Desktop Invoicing Application</span>
        <span class="entry-subtitle">Freelance</span>
      </div>
      <ul class="bullets">
        <li>Built an offline-first desktop enterprise application using Electron and React with high-speed calculation engines and zero error margin.</li>
        <li>Implemented automated PDF invoice generation via Puppeteer and secure background cloud synchronization to Google Drive via OAuth 2.0.</li>
      </ul>
    </div>
    """

    areas_of_interest = "Backend AI/ML, Generative AI, Multi-Agent Systems, Workflow Automation, LLM Applications, API Engineering"

    rendered_html = HTML_TEMPLATE.format(
        role_title=role_title,
        header_subtitle=header_subtitle,
        summary_text=summary_text,
        skills_rows=skills_rows,
        projects_html=projects_html,
        areas_of_interest=areas_of_interest
    )

    temp_html.write_text(rendered_html, encoding="utf-8")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1200, "height": 1600})
        page.goto(temp_html.as_uri(), wait_until="networkidle")

        page.pdf(
            path=str(output_pdf_desktop),
            format="Letter",
            print_background=True,
            margin={"top": "0.36in", "bottom": "0.36in", "left": "0.50in", "right": "0.50in"}
        )
        import shutil
        shutil.copyfile(output_pdf_desktop, storage_pdf)
        browser.close()

    if temp_html.exists():
        try:
            temp_html.unlink()
        except Exception:
            pass

    return output_pdf_desktop

def create_tailored_pitch(company_name: str, role_title: str, hiring_person: str = "Hiring Team") -> str:
    pitch = (
        f"Hi {hiring_person},\n\n"
        f"I came across the {role_title} opening at {company_name} and wanted to reach out directly.\n\n"
        f"I'm a final-year B.Tech IT student specializing in Python, Backend APIs, LangChain, and Agentic AI workflows. "
        f"I have built production applications including a multi-tenant WhatsApp AI SaaS and multimodal document extraction pipelines using LLMs.\n\n"
        f"I have tailored my resume specifically for {company_name} and would love to discuss how I can contribute to your engineering goals.\n\n"
        f"📄 Resume: https://drive.google.com/file/d/1TpyzV7OGEf-YQfGLUpusAI5cDDvF1kAJ/view?usp=drive_link\n"
        f"💻 GitHub: https://github.com/Mukil630\n\n"
        f"Thank you for your time!\n"
        f"Mukilarasu S"
    )
    return pitch

def notify_telegram(company_name: str, role_title: str, job_url: str, pdf_path: Path, pitch_msg: str):
    caption = (
        f"🎯 <b>NEW TAILORED APPLICATION READY!</b>\n\n"
        f"🏢 <b>Company:</b> {company_name}\n"
        f"💼 <b>Role:</b> {role_title}\n"
        f"🔗 <b>Job URL:</b> {job_url}\n\n"
        f"📄 <i>Tailored 1-page ATS Resume attached below.</i>\n"
        f"✨ <i>Pitch message sent below for easy copy-paste to LinkedIn!</i>"
    )

    # 1. Send Document
    with open(pdf_path, "rb") as doc:
        files = {"document": (pdf_path.name, doc, "application/pdf")}
        data = {
            "chat_id": TELEGRAM_CHAT_ID,
            "caption": caption,
            "parse_mode": "HTML"
        }
        r1 = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument",
            data=data,
            files=files,
            timeout=30
        )

    # 2. Send Pitch Message
    pitch_payload = (
        f"💬 <b>TAILORED LINKEDIN MESSAGE (Ready to send):</b>\n\n"
        f"<code>{pitch_msg}</code>"
    )
    data_msg = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": pitch_payload,
        "parse_mode": "HTML"
    }
    r2 = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        data=data_msg,
        timeout=30
    )
    return r1.ok and r2.ok

def log_application(company_name: str, role_title: str, job_url: str, pdf_path: str):
    log_file = MEMORY_DIR / "job_applications_log.json"
    data = []
    if log_file.exists():
        try:
            data = json.loads(log_file.read_text(encoding="utf-8"))
        except Exception:
            data = []

    data.append({
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "company": company_name,
        "role": role_title,
        "job_url": job_url,
        "resume_pdf": str(pdf_path),
        "status": "READY_FOR_OUTREACH"
    })

    log_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

def process_opportunity(company_name: str, role_title: str, job_url: str, hiring_person: str = "Hiring Team"):
    print(f"[*] Processing opportunity for {company_name} - {role_title}...")
    pdf_path = generate_tailored_pdf(company_name, role_title)
    print(f"[+] Tailored PDF generated: {pdf_path}")
    pitch = create_tailored_pitch(company_name, role_title, hiring_person)
    print(f"[+] Pitch created.")
    success = notify_telegram(company_name, role_title, job_url, pdf_path, pitch)
    print(f"[+] Telegram dispatch success: {success}")
    log_application(company_name, role_title, job_url, str(pdf_path))
    print(f"[+] Logged to persistent memory.")
    return success

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--company", default="RBG.AI", help="Company Name")
    parser.add_argument("--role", default="Intern - Back-end AI/ML", help="Role Title")
    parser.add_argument("--url", default="https://forms.gle/1Uw9JqQuf8bshfQf8", help="Job URL / Form")
    parser.add_argument("--person", default="Kishore Kumar M", help="Hiring Person / Recruiter")
    args = parser.parse_args()

    process_opportunity(args.company, args.role, args.url, args.person)
