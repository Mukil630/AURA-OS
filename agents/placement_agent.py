import os
import sys
import json
import time
import urllib.parse
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from memory.memory_manager import MemoryManager

class PlacementAgent:
    def __init__(self, resume_path=None):
        self.mem = MemoryManager()
        self.session_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage", "indeed_session")
        os.makedirs(self.session_dir, exist_ok=True)
        
        self.resume_path = resume_path or "C:/Users/mukil/MUKILARASU_S_PERFECT_RESUME.pdf"
        self.profile = self.load_profile()
        self.applied_log_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage", "applied_jobs.json")

    def load_profile(self):
        profile_path = "C:/Users/mukil/job_automator/profile.json"
        if os.path.exists(profile_path):
            try:
                with open(profile_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "name": "MUKILARASU S",
            "first_name": "MUKILARASU",
            "last_name": "S",
            "email": "mukilarasu55@gmail.com",
            "phone": "9080030538",
            "location": "Karur, Tamil Nadu",
            "college": "VSB Engineering College",
            "degree": "Bachelor's Degree",
            "skills": ["Python", "AI", "Full-Stack Development", "FastAPI", "React", "JavaScript", "SQL"],
            "experience_years": "2"
        }

    def log_application(self, job_title, company, link, status="APPLIED"):
        logs = []
        if os.path.exists(self.applied_log_path):
            try:
                with open(self.applied_log_path, "r", encoding="utf-8") as f:
                    logs = json.load(f)
            except Exception:
                logs = []
        logs.append({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "job_title": job_title,
            "company": company,
            "link": link,
            "status": status
        })
        with open(self.applied_log_path, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=2)

    def apply_on_indeed(self, keywords="Software Engineer", location="Remote", max_applications=3, headless=False):
        print(f"\n⚡ Starting Indeed Autonomous Job Applier for: '{keywords}' in '{location}'...")
        encoded_kw = urllib.parse.quote(keywords)
        encoded_loc = urllib.parse.quote(location)
        search_url = f"https://in.indeed.com/jobs?q={encoded_kw}&l={encoded_loc}"
        
        applied_count = 0
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                self.session_dir,
                headless=headless,
                channel="chrome",
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                args=["--disable-blink-features=AutomationControlled", "--start-maximized"],
                no_viewport=True
            )
            page = context.pages[0] if context.pages else context.new_page()
            
            print(f"Navigating to Indeed search: {search_url}")
            page.goto(search_url, timeout=60000)
            time.sleep(4)
            
            # Dismiss any sign-in prompt modal if present
            try:
                close_btn = page.locator("button[aria-label='close'], button.icl-CloseButton, button[aria-label='Dismiss']").first
                if close_btn.is_visible(timeout=3000):
                    close_btn.click()
            except Exception:
                pass
            
            # Find job cards
            job_cards = page.locator("div.job_seen_beacon, td.resultContent, div.cardOutline").all()
            print(f"Found {len(job_cards)} job listings on page.")
            
            for idx, card in enumerate(job_cards):
                if applied_count >= max_applications:
                    break
                try:
                    # Click job card
                    title_elem = card.locator("h2.jobTitle, a[data-jk]").first
                    if not title_elem.is_visible():
                        continue
                    
                    job_title = title_elem.inner_text().strip()
                    print(f"\n[{idx+1}] Inspecting Job: {job_title}")
                    title_elem.click()
                    time.sleep(3)
                    
                    # Look for Apply Button
                    apply_btn = page.locator("button#indeedApplyButton, button:has-text('Apply now'), button:has-text('Easily apply')").first
                    if not apply_btn.is_visible(timeout=3000):
                        print(f"  -> Job '{job_title}' redirects to external company site or requires manual application. Skipping for safety.")
                        continue
                    
                    print(f"  -> Found Direct Apply Button! Clicking apply...")
                    apply_btn.click()
                    time.sleep(3)
                    
                    # Handle application iframe or modal if opens
                    # Check for inputs
                    phone_input = page.locator("input[type='tel'], input[id*='phone']").first
                    if phone_input.is_visible(timeout=2000):
                        phone_input.fill(self.profile.get("phone", "9080030538"))
                    
                    # Log application
                    self.log_application(job_title, "Indeed Employer", page.url, "INSPECTED_AND_OPENED")
                    applied_count += 1
                    print(f"  ✅ Application initiated for '{job_title}'!")
                    
                except Exception as card_err:
                    print(f"  Card error: {card_err}")
            
            print(f"\n🎯 Job automation run complete! Inspected & processed {applied_count} applications.")
            time.sleep(5)
            context.close()
            return f"Successfully processed {applied_count} job openings on Indeed for '{keywords}' in '{location}'!"

if __name__ == '__main__':
    agent = PlacementAgent()
    agent.apply_on_indeed(keywords="Python Developer", location="Remote", max_applications=2, headless=False)
