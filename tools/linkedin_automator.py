import os
import sys
import time
import logging
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from memory.memory_manager import MemoryManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("linkedin_automator")

POST_CONTENT = """🚀 Announcing AURA — My Autonomous Unified Response Assistant (A 24/7 Multi-Device AI Operating System) 🌌

Over the past few weeks, I’ve been analyzing the limitations of traditional AI assistants and static chatbots. Most existing tools suffer from two major flaws:
1. They rely on rigid, hardcoded scripts.
2. They die the moment your laptop is closed.

To solve this, I am engineering AURA (Autonomous Unified Response Assistant) — a 24/7 persistent, cloud-native Agentic AI Operating System designed to seamlessly bridge Phone, Cloud, and PC hardware.

🧠 Core Architectural Innovations:
1️⃣ 24/7 Cloud-Native Brain: Operates continuously in a cloud container, running background job scrapers, Gmail radars, and scheduled tasks even when my laptop is turned off.
2️⃣ Universal Dynamic CodeAct Engine: Instead of hardcoded tool definitions, AURA dynamically plans, writes Python/PowerShell scripts on the fly, auto-debugs errors, and executes arbitrary tasks autonomously.
3️⃣ Adaptive Sprints with Auto-Reversion: Context-aware scheduling that dynamically reorganizes daily routines into high-intensity sprints (e.g., 7-day placement drives) and automatically restores baseline habits upon deadline completion.
4️⃣ Multi-Device Telemetry & Voice Integration: Low-latency voice triggers from Android ("Hey Google" / Shortcuts) control physical PC hardware through authenticated tunnels and Stark security protocols.
5️⃣ Enterprise Memory & Cloud Vault: Dual-tier persistence combining Supabase/PostgreSQL state tracking with a 5TB Google Drive Master Vault.

I am officially taking this journey public and will be sharing daily engineering updates, architecture breakthroughs, and technical learnings right here on LinkedIn!

🔗 Open-Source Repository: https://github.com/Mukil630/AURA-OS

Stack: Python | FastAPI | LangGraph | Groq Llama-3.3 70B | Playwright | Cloudflare Tunnels | PostgreSQL | Git Automation

#AIEngineering #AgenticAI #LangGraph #AutonomousAgents #FullStack #Python #SoftwareArchitecture #BuildInPublic #Innovation #DevCommunity"""

class LinkedInAutomator:
    """
    Autonomous LinkedIn Post Publisher using Playwright Browser Automation.
    """
    def __init__(self, session_dir=None):
        self.session_dir = session_dir or os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage", "browser_session")
        os.makedirs(self.session_dir, exist_ok=True)
        self.mem = MemoryManager()

    def publish_post(self, text: str = POST_CONTENT, auto_submit: bool = False):
        logger.info("⚡ Launching Autonomous LinkedIn Publisher...")
        
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                self.session_dir,
                headless=False,
                channel="chrome",
                args=["--disable-blink-features=AutomationControlled", "--start-maximized"],
                no_viewport=True
            )
            page = context.pages[0] if context.pages else context.new_page()
            
            logger.info("Navigating to LinkedIn feed...")
            page.goto("https://www.linkedin.com/feed/", timeout=60000)
            time.sleep(4)
            
            if "login" in page.url:
                logger.info("Please sign into LinkedIn in the opened browser window...")
                print("\n[AURA LINKEDIN] Sign in to LinkedIn once. Waiting for feed...")
                page.wait_for_url("https://www.linkedin.com/feed/**", timeout=120000)
            
            try:
                # 1. Click "Start a post" button
                start_btn = page.locator("button:has-text('Start a post'), button.share-box-feed-entry__trigger").first
                if start_btn.is_visible(timeout=8000):
                    start_btn.click()
                    logger.info("Clicked 'Start a post' button!")
                    time.sleep(2)
                
                # 2. Find post editor and inject text
                editor = page.locator("div.editor-content div.ql-editor, div[contenteditable='true']").first
                if editor.is_visible(timeout=5000):
                    editor.fill(text)
                    logger.info("✅ Post text typed into LinkedIn editor!")
                    time.sleep(2)
                
                # 3. If auto_submit is True, click the 'Post' button
                if auto_submit:
                    post_btn = page.locator("button.share-actions__primary-action, button:has-text('Post')").first
                    if post_btn.is_enabled(timeout=4000):
                        post_btn.click()
                        logger.info("🚀 Clicked 'Post' button! Post is now live on LinkedIn!")
                        time.sleep(4)
                else:
                    print("\n[AURA LINKEDIN] Post is pre-filled on your screen! Click 'Post' button to publish.")
                    time.sleep(5)
            except Exception as e:
                logger.error(f"Error during LinkedIn automation: {e}")
                
            time.sleep(3)
            context.close()

if __name__ == "__main__":
    automator = LinkedInAutomator()
    automator.publish_post(POST_CONTENT, auto_submit=False)
