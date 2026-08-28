"""Autonomous Placement & Job Application Agent for JARVIS / AURA-OS.
Autonomously discovers active tech openings, generates tailored application packages with Mukil's Master Resume,
creates cold outreach pitches, and tracks application pipelines.
"""
import json
import logging
import os
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4
from groq import Groq

logger = logging.getLogger("JobApplyAgent")

MUKIL_MASTER_RESUME_URL = "https://drive.google.com/file/d/1TpyzV7OGEf-YQfGLUpusAI5cDDvF1kAJ/view?usp=drive_link"
MUKIL_PORTFOLIO_GITHUB = "https://github.com/Mukil630"
APPLICATIONS_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "job_applications.json")

MUKIL_CANDIDATE_PROFILE = """
Candidate Name: Mukil
Role: AI Engineer / Full-Stack Developer & Agentic Systems Architect
Primary Skills: Python, FastAPI, TypeScript/JavaScript, React, Node.js, Generative AI (LLMs, Function Calling, LangChain, LlamaIndex),
Autonomous Multi-Agent Architecture, REST APIs, Microservices, PostgreSQL, MongoDB, Docker, Git/GitHub, Linux/Windows Automation.
Master Resume Link: https://drive.google.com/file/d/1TpyzV7OGEf-YQfGLUpusAI5cDDvF1kAJ/view?usp=drive_link
GitHub: https://github.com/Mukil630
Tone: High-agency, proactive, sharp, results-driven problem solver with production experience in autonomous AI pipelines.
"""


class JobApplyAgent:
    """
    Autonomous Job Application & Pipeline Tracker Agent.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self._client: Optional[Groq] = None
        if self.api_key:
            try:
                self._client = Groq(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Could not initialize Groq in JobApplyAgent: {e}")
        self._ensure_storage()

    def _ensure_storage(self) -> None:
        """Ensures data directory and applications log file exist."""
        os.makedirs(os.path.dirname(APPLICATIONS_FILE), exist_ok=True)
        if not os.path.exists(APPLICATIONS_FILE):
            with open(APPLICATIONS_FILE, "w", encoding="utf-8") as f:
                json.dump([], f, indent=2)

    def _load_applications(self) -> List[Dict[str, Any]]:
        """Loads application records from JSON."""
        try:
            with open(APPLICATIONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _save_applications(self, apps: List[Dict[str, Any]]) -> None:
        """Saves application records to JSON."""
        with open(APPLICATIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(apps, f, indent=2, ensure_ascii=False)

    def search_jobs(self, role: str = "AI Engineer", location: str = "Remote / India") -> List[Dict[str, str]]:
        """
        Discovers job opportunities across LinkedIn, Google Jobs, and Wellfound.
        Generates direct verified search links and application access URLs.
        """
        encoded_role = urllib.parse.quote_plus(f"{role} {location}".strip())
        role_only = urllib.parse.quote_plus(role.strip())

        return [
            {
                "platform": "LinkedIn Jobs",
                "role": role,
                "location": location,
                "search_url": f"https://www.linkedin.com/jobs/search/?keywords={encoded_role}&f_TPR=r86400",
                "description": "Active openings posted within last 24 hours on LinkedIn.",
            },
            {
                "platform": "Google Jobs Aggregator",
                "role": role,
                "location": location,
                "search_url": f"https://www.google.com/search?q={encoded_role}+jobs+apply",
                "description": "Multi-board aggregated listings with 1-click apply links.",
            },
            {
                "platform": "Wellfound (AngelList)",
                "role": role,
                "location": location,
                "search_url": f"https://wellfound.com/jobs?query={role_only}",
                "description": "High-growth AI startups and direct founder application portals.",
            },
            {
                "platform": "Naukri Tech Portal",
                "role": role,
                "location": location,
                "search_url": f"https://www.naukri.com/{role.lower().replace(' ', '-')}-jobs-in-{location.lower().replace(' ', '-')}",
                "description": "Direct recruiter postings for Indian tech hubs.",
            },
        ]

    def generate_application_package(
        self,
        company_name: str,
        job_title: str,
        job_description: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Uses Groq LLM to generate a customized cover letter, cold outreach email,
        and ATS-friendly screening answers tailored specifically to Mukil's Master Resume.
        """
        jd_context = job_description or f"Opening for {job_title} at {company_name}. Looking for strong skills in Python, AI Engineering, FastAPI, and Autonomous Systems."

        prompt = f"""
You are an expert Executive Tech Career Partner for Mukil.
Based on Mukil's profile below and the target job description, generate a tailored application package.

{MUKIL_CANDIDATE_PROFILE}

TARGET COMPANY: {company_name}
TARGET ROLE: {job_title}
JOB DESCRIPTION:
{jd_context}

Output a JSON object with the following fields:
1. "cover_letter": A compelling, concise 3-paragraph cover letter highlighting autonomous AI agent engineering and full-stack capabilities.
2. "cold_pitch_email": A high-impact 100-word cold outreach message to the Hiring Manager / Founder with Mukil's resume link.
3. "key_selling_points": 3 bullet points why Mukil is the ideal candidate for this role.
4. "screening_answer_why_hire": A crisp 2-sentence response to "Why are you the right fit for this role?".

Ensure Mukil's Master Resume link ({MUKIL_MASTER_RESUME_URL}) is naturally referenced.
Format output as pure valid JSON.
"""
        default_package = {
            "cover_letter": f"Dear Hiring Team at {company_name},\n\nI am writing to express my strong interest in the {job_title} position. With deep production experience in Autonomous Agent Architecture, Python/FastAPI microservices, and Generative AI pipelines, I build end-to-end systems that drive measurable engineering velocity.\n\nYou can review my full portfolio and Master Resume here: {MUKIL_MASTER_RESUME_URL}.\n\nBest regards,\nMukil",
            "cold_pitch_email": f"Hi Team,\n\nI noticed {company_name} is hiring a {job_title}. I specialize in building Autonomous AI Systems and scalable full-stack applications (Python/FastAPI/React). My Master Resume is here: {MUKIL_MASTER_RESUME_URL}. Would love to discuss how I can contribute to your engineering goals.\n\nBest,\nMukil",
            "key_selling_points": [
                "Production experience building autonomous multi-agent operating systems (AURA-OS)",
                "Full-stack proficiency in Python, FastAPI, TypeScript, React, and LLM tool calling",
                "Self-directed builder with track record of high-speed deployment and clean architecture"
            ],
            "screening_answer_why_hire": f"I combine deep full-stack engineering with modern Agentic AI workflows to deliver resilient, production-ready solutions faster than traditional cycles."
        }

        if not self._client:
            return default_package

        try:
            response = self._client.chat.completions.create(
                model="qwen/qwen3.8-27b",
                messages=[
                    {"role": "system", "content": "You are a specialized career agent for Mukil. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
            )
            raw = response.choices[0].message.content
            if raw:
                parsed = json.loads(raw)
                return {**default_package, **parsed}
        except Exception as e:
            logger.warning(f"Groq application package generation failed: {e}")

        return default_package

    def log_application(
        self,
        company: str,
        role: str,
        apply_url: Optional[str] = None,
        notes: Optional[str] = None,
        status: str = "APPLIED",
    ) -> Dict[str, Any]:
        """
        Logs a job application in the persistent pipeline tracker.
        """
        apps = self._load_applications()
        app_id = f"job_{uuid4().hex[:8]}"
        now_str = datetime.now(timezone.utc).isoformat()

        record = {
            "application_id": app_id,
            "company": company.strip(),
            "role": role.strip(),
            "apply_url": apply_url or f"https://www.google.com/search?q={urllib.parse.quote_plus(company + ' ' + role + ' jobs')}",
            "resume_link": MUKIL_MASTER_RESUME_URL,
            "applied_at": now_str,
            "status": status,
            "notes": notes or "Autonomous application tracked by JARVIS",
        }

        apps.insert(0, record)
        self._save_applications(apps)
        return record

    def list_applications(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Returns recent job application records.
        """
        apps = self._load_applications()
        return apps[:limit]

    def get_pipeline_summary(self) -> str:
        """
        Formats application tracker into an executive Telegram report for Mukil.
        """
        apps = self._load_applications()
        if not apps:
            return (
                "📋 *Job Application Pipeline Tracker*\n\n"
                "No applications logged yet, Boss. Use `/jobs apply <company> <role>` "
                "or say _'Find AI Engineer jobs'_ to launch auto-application!"
            )

        lines = [
            f"💼 *JARVIS JOB APPLICATION PIPELINE* ({len(apps)} Total Applications)\n",
            f"📄 *Master Resume Linked*: [View Resume PDF]({MUKIL_MASTER_RESUME_URL})\n"
        ]

        for idx, app in enumerate(apps[:8], 1):
            status_icon = "🟢" if app["status"] == "APPLIED" else ("🟡" if app["status"] == "INTERVIEWING" else "🔵")
            lines.append(
                f"{idx}. {status_icon} *{app['company']}* - `{app['role']}`\n"
                f"   • Status: *{app['status']}* | Applied: `{app['applied_at'][:10]}`\n"
                f"   • Link: [Apply / Post Link]({app['apply_url']})"
            )

        return "\n".join(lines)
